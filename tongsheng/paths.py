"""Filesystem layout and model discovery.

TongSheng is meant to be packaged later, but during the test phase it shares
the model weights that already live in the sibling repositories:

* project A ``PrivateVoice``  — GPT-SoVITS checkpoints, voices, ASR caches
* project B ``ALT-VoiceType`` — local GGUF translation/correction models

Every path can be pinned explicitly in ``config.yaml``; ``auto`` (the default)
runs :func:`discover` which looks at the siblings and the packaged layout.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PRIVATE_VOICE_ENV = "TONGSHENG_PRIVATE_VOICE"
ALT_VOICE_ENV = "TONGSHENG_ALT_VOICE"


def _existing(path: str | Path | None) -> Path | None:
    if not path:
        return None
    candidate = Path(str(path)).expanduser()
    try:
        if candidate.exists():
            return candidate.resolve()
    except OSError:
        return None
    return None


def _first(paths: list[Path | None]) -> Path | None:
    for path in paths:
        found = _existing(path)
        if found is not None:
            return found
    return None


def default_private_voice_root() -> Path | None:
    env = os.environ.get(PRIVATE_VOICE_ENV)
    return _first([
        Path(env) if env else None,
        ROOT.parent / "PrivateVoice",
        ROOT / "vendor" / "PrivateVoice",
    ])


def default_alt_voice_root() -> Path | None:
    env = os.environ.get(ALT_VOICE_ENV)
    return _first([
        Path(env) if env else None,
        ROOT.parent / "ALT-VoiceType",
        ROOT / "vendor" / "ALT-VoiceType",
    ])


@dataclass
class ModelPaths:
    """Resolved locations of every weight TongSheng needs at runtime."""

    gpt_sovits: Path | None = None       # upstream GPT-SoVITS repository root
    pretrained: Path | None = None       # .../GPT_SoVITS/pretrained_models
    characters: Path | None = None       # voice profiles (TongSheng/voices by default)
    asr_cache: Path | None = None        # FunASR / faster-whisper caches
    whisper_dir: Path | None = None      # .../whisper/faster-whisper-small
    funasr_dir: Path | None = None       # .../modelscope (MODELSCOPE_CACHE)
    gguf_dir: Path | None = None         # project B GGUF directory
    logs: Path | None = None
    results: Path | None = None

    def as_dict(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for key, value in self.__dict__.items():
            if value is not None:
                out[key] = str(value)
        return out

    def missing_core(self) -> list[str]:
        missing: list[str] = []
        if self.gpt_sovits is None:
            missing.append("gpt_sovits")
        if self.pretrained is None:
            missing.append("pretrained")
        return missing


def discover(private_voice: str | Path | None = None,
             alt_voice: str | Path | None = None) -> ModelPaths:
    """Best-effort discovery of shared model locations."""
    pv = _existing(private_voice) if private_voice and str(private_voice).lower() != "auto" \
        else default_private_voice_root()
    av = _existing(alt_voice) if alt_voice and str(alt_voice).lower() != "auto" \
        else default_alt_voice_root()

    gpt_sovits = pretrained = asr_cache = whisper_dir = funasr_dir = None
    if pv is not None:
        gpt_sovits = _first([pv / "GPT-SoVITS"])
        if gpt_sovits is not None:
            pretrained = _first([gpt_sovits / "GPT_SoVITS" / "pretrained_models"])
        # Packaged builds keep the ASR caches inside the dist folder.
        asr_cache = _first([
            pv / "dist" / "PrivateVoice_Ahee52" / "models_cache",
            pv / "models_cache",
            pv / "models",
        ])
    if asr_cache is not None:
        whisper_dir = _first([asr_cache / "whisper" / "faster-whisper-small",
                              asr_cache / "whisper"])
        funasr_dir = _first([asr_cache / "modelscope"])

    gguf_dir = _first([av / "models"]) if av is not None else None

    return ModelPaths(
        gpt_sovits=gpt_sovits,
        pretrained=pretrained,
        characters=_voice_repository(),
        asr_cache=asr_cache,
        whisper_dir=whisper_dir,
        funasr_dir=funasr_dir,
        gguf_dir=gguf_dir,
        logs=ROOT / "logs",
        results=ROOT / "results",
    )


def _voice_repository() -> Path:
    """``voice-repository/`` is the home of every cloned voice.

    Older builds used ``voices/``; if that is the only folder present we keep
    using it until the user migrates.
    """
    new = ROOT / "voice-repository"
    if new.is_dir():
        return new
    legacy = ROOT / "voices"
    if legacy.is_dir():
        return legacy
    return new


def resolve_llama_binary(configured: str = "llama-server") -> str:
    """Resolve ``llama-server`` from config, PATH, a bundled runtime or winget."""
    if configured:
        candidate = Path(configured)
        if candidate.is_file():
            return str(candidate)
        found = shutil.which(configured)
        if found:
            return found
    if getattr(sys, "frozen", False):
        bundled = Path(sys.executable).resolve().parent / "llama" / "llama-server.exe"
        if bundled.is_file():
            return str(bundled)
    local = os.environ.get("LOCALAPPDATA")
    if os.name == "nt" and local:
        packages = Path(local) / "Microsoft" / "WinGet" / "Packages"
        if packages.is_dir():
            for path in packages.glob("ggml.llamacpp_*/llama-server.exe"):
                if path.is_file():
                    return str(path)
    return ""


def find_gguf(name_hint: str, gguf_dir: str | Path | None) -> str:
    """Map a friendly model name to a local .gguf file.

    ``qwen3-1.7b-instruct`` should find ``Qwen3-1.7B-Q8_0.gguf`` and
    ``Index-Translate-9B`` should find ``Index-Translate-9B.Q4_K_M.gguf``.
    """
    if not gguf_dir:
        return ""
    base = Path(gguf_dir)
    if not base.is_dir():
        return ""
    hint = (name_hint or "").lower()
    if not hint:
        return ""
    candidates = sorted(base.glob("*.gguf"))
    tokens = [t for t in re.split(r"[^a-z0-9]+", hint) if t]
    best = ""
    best_score = 0.0
    for path in candidates:
        name = path.name.lower()
        flat = re.sub(r"[^a-z0-9]+", "-", name)
        if hint in flat or flat.startswith(hint):
            return str(path)
        hits = sum(1 for token in tokens if token in flat)
        score = hits / max(1, len(tokens))
        if score > best_score:
            best, best_score = str(path), score
    return best if best_score >= 0.6 else ""


def ensure_dir(path: Path | str | None) -> Path | None:
    if not path:
        return None
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target
