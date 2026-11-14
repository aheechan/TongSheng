"""Supervision of local ``llama-server`` processes for correction/translation.

Adapted from ALT-VoiceType (Apache-2.0). TongSheng only stops the servers it
started itself, and reuses anything already listening on the configured port.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from ..config import AppConfig
from ..logs import get_logger
from ..paths import resolve_llama_binary

log = get_logger("llm.servers")


class ServerError(RuntimeError):
    pass


_NO_PROXY_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def port_in_use(host: str, port: int, timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _looks_like_llama(pid: int) -> bool:
    """Only kill PIDs that really are llama-server processes."""
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, int(pid))  # QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            buffer = ctypes.create_unicode_buffer(1024)
            size = wt.DWORD(1024)
            if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                return False
            return "llama-server" in buffer.value.lower()
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return False


@dataclass
class ServerSpec:
    name: str
    binary: str
    model_path: str
    host: str
    port: int
    alias: str
    context_size: int = 4096
    gpu_layers: int = 99
    extra_args: list[str] = field(default_factory=list)
    log_dir: str | None = None

    def command(self) -> list[str]:
        return [
            self.binary, "-m", self.model_path,
            "--host", self.host, "--port", str(self.port),
            "--alias", self.alias, "-c", str(self.context_size),
            "-ngl", str(self.gpu_layers), *self.extra_args,
        ]

    def health_url(self) -> str:
        host = "127.0.0.1" if self.host in ("0.0.0.0", "::") else self.host
        return f"http://{host}:{self.port}/v1/models"

    def log_path(self) -> Path:
        base = Path(self.log_dir) if self.log_dir else Path.cwd() / "logs"
        base.mkdir(parents=True, exist_ok=True)
        return base / f"{self.name}.log"


class LlamaServer:
    def __init__(self, spec: ServerSpec) -> None:
        self.spec = spec
        self._process: subprocess.Popen | None = None
        self._log_handle = None

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def is_ready(self, timeout_s: float = 1.0, expected_alias: str | None = None) -> bool:
        try:
            with _NO_PROXY_OPENER.open(self.spec.health_url(), timeout=timeout_s) as response:
                if response.status != 200:
                    return False
                body = response.read().decode("utf-8", errors="replace")
            data = json.loads(body)
            if not isinstance(data, dict):
                return False
            # llama.cpp answers either {"data": [...]} (OpenAI style) or
            # {"models": [...]} depending on build; accept both.
            items = data.get("data")
            if not isinstance(items, list):
                items = data.get("models")
            if not isinstance(items, list):
                return False
            if expected_alias:
                ids = set()
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    for key in ("id", "name", "model"):
                        value = item.get(key)
                        if value:
                            ids.add(str(value))
                if expected_alias not in ids:
                    return False
            return True
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            return False

    def start(self) -> bool:
        if self.is_ready(expected_alias=self.spec.alias):
            return False
        if self.is_ready():
            raise ServerError(
                f"{self.spec.name}: port {self.spec.port} already serves a different "
                f"model (expected {self.spec.alias!r}); see {self.spec.log_path()}")
        if self.running:
            return False
        if not Path(self.spec.model_path).exists():
            raise ServerError(f"{self.spec.name}: model missing: {self.spec.model_path}")
        if port_in_use(self.spec.host, self.spec.port):
            # someone else owns the port: wait briefly, never spawn a second
            # server into it (that used to pile up zombies and eat all VRAM)
            for _ in range(20):
                if self.is_ready(expected_alias=self.spec.alias):
                    return False
                time.sleep(0.5)
            raise ServerError(
                f"{self.spec.name}: port {self.spec.port} is busy but not healthy; "
                f"another program may be using it")
        binary = resolve_llama_binary(self.spec.binary)
        if not binary:
            raise ServerError(
                f"{self.spec.name}: cannot find '{self.spec.binary}'. Install llama.cpp "
                "(`winget install ggml.llamacpp`) or set llm.servers.binary.")
        log_path = self.spec.log_path()
        self._log_handle = log_path.open("a", encoding="utf-8", errors="replace")
        self._log_handle.write(f"\n--- start {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        self._log_handle.flush()
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        command = self.spec.command()
        command[0] = binary
        try:
            self._process = subprocess.Popen(
                command, stdout=self._log_handle, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, creationflags=flags)
        except OSError as exc:
            raise ServerError(f"{self.spec.name}: failed to launch: {exc}") from exc
        return True

    def wait_ready(self, timeout_s: float = 90.0) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self.is_ready(expected_alias=self.spec.alias):
                return
            if self._process is not None and self._process.poll() is not None:
                raise ServerError(
                    f"{self.spec.name}: exited with {self._process.returncode}; "
                    f"see {self.spec.log_path()}")
            time.sleep(0.5)
        raise ServerError(f"{self.spec.name}: not ready after {timeout_s:.0f}s; "
                          f"see {self.spec.log_path()}")

    def probe(self, timeout_s: float = 25.0) -> None:
        payload = json.dumps({
            "model": self.spec.alias,
            "messages": [{"role": "user", "content": "Reply with OK."}],
            "temperature": 0.0, "max_tokens": 8, "stream": False,
        }).encode("utf-8")
        request = urllib.request.Request(
            self.spec.health_url().replace("/models", "/chat/completions"),
            data=payload, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with _NO_PROXY_OPENER.open(request, timeout=timeout_s) as response:
                body = response.read().decode("utf-8", errors="replace")
                if response.status != 200:
                    raise ServerError(f"{self.spec.name}: probe returned {response.status}")
            data = json.loads(body)
            if not isinstance(data.get("choices"), list) or not data["choices"]:
                raise ServerError(f"{self.spec.name}: probe response has no choices")
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise ServerError(f"{self.spec.name}: inference probe failed: {exc}") from exc

    def stop(self) -> None:
        process = self._process
        self._process = None
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        if self._log_handle is not None:
            self._log_handle.close()
            self._log_handle = None


class ServerManager:
    def __init__(self, servers: list[LlamaServer] | None = None) -> None:
        self.servers = servers or []
        self.failed: set[str] = set()
        self.startup_timeout_s = 180.0
        self.probe_timeout_s = 30.0
        self.log_dir: str | None = None

    # -- orphan bookkeeping ---------------------------------------------
    def _pidfile(self):
        from pathlib import Path

        base = Path(self.log_dir) if self.log_dir else Path("logs")
        base.mkdir(parents=True, exist_ok=True)
        return base / "llama-servers.json"

    def _cleanup_orphans(self) -> None:
        """Kill llama-server processes left behind by a previous run."""
        path = self._pidfile()
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            data = {}
        for pid in data.get("pids", []):
            try:
                if not _looks_like_llama(int(pid)):
                    continue
                os.kill(int(pid), signal.SIGTERM)
                log.info("killed orphan llama-server pid=%s", pid)
            except Exception:  # noqa: BLE001
                continue
        try:
            path.unlink()
        except OSError:
            pass

    def _remember(self) -> None:
        pids = [server._process.pid for server in self.servers
                if server._process is not None and server.running]
        try:
            self._pidfile().write_text(json.dumps({"pids": pids}), encoding="utf-8")
        except OSError:
            pass

    def _forget(self) -> None:
        try:
            self._pidfile().unlink()
        except OSError:
            pass

    @classmethod
    def from_config(cls, config: AppConfig, models=None) -> "ServerManager":
        if not config.llm.servers.enabled:
            return cls([])
        from ..paths import find_gguf

        specs: list[ServerSpec] = []
        gguf_dir = getattr(models, "gguf_dir", None)
        for name, endpoint, default_port in (
            ("corrector", config.llm.corrector, 8091),
            ("translator", config.llm.translator, 8092),
        ):
            if not (endpoint.enabled and endpoint.autostart):
                continue
            parsed = urlparse(endpoint.base_url)
            if parsed.hostname not in ("127.0.0.1", "localhost", "::1", None):
                continue
            model_path = endpoint.model_path
            if not model_path or model_path == "auto":
                model_path = find_gguf(endpoint.model, gguf_dir)
            if not model_path:
                log.warning("%s: no local gguf for %r, skipping autostart",
                            name, endpoint.model)
                continue
            extra = ["--reasoning", "off"]
            specs.append(ServerSpec(
                name=name,
                binary=config.llm.servers.binary,
                model_path=model_path,
                host=config.llm.servers.host,
                port=parsed.port or default_port,
                alias=endpoint.model,
                context_size=config.llm.servers.context_size,
                gpu_layers=config.llm.servers.gpu_layers,
                extra_args=extra,
                log_dir=str(models.logs) if models is not None and models.logs else None,
            ))
        manager = cls([LlamaServer(spec) for spec in specs])
        manager.startup_timeout_s = max(30.0, float(config.llm.servers.startup_timeout_s))
        if models is not None and getattr(models, "logs", None):
            manager.log_dir = str(models.logs)
        return manager

    def start_all(self, on_status=None) -> list[str]:
        status = on_status or (lambda _msg: None)
        errors: list[str] = []
        self.failed.clear()
        self._cleanup_orphans()
        for server in self.servers:
            try:
                if server.is_ready(expected_alias=server.spec.alias):
                    status(f"{server.spec.name}: already running")
                else:
                    status(f"starting {server.spec.name}…")
                    server.start()
                    server.wait_ready(timeout_s=self.startup_timeout_s)
                server.probe(timeout_s=self.probe_timeout_s)
                status(f"{server.spec.name}: ready")
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))
                self.failed.add(server.spec.name)
                log.warning("server %s failed: %s", server.spec.name, exc)
        self._remember()
        return errors

    def stop_all(self) -> None:
        for server in self.servers:
            try:
                server.stop()
            except Exception:
                pass
        self._forget()

    def status(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for server in self.servers:
            out[server.spec.name] = "ready" if server.is_ready(
                expected_alias=server.spec.alias) else "down"
        return out


__all__ = ["ServerSpec", "LlamaServer", "ServerManager", "ServerError"]
