"""Gapless streaming playback for synthesized speech.

TTS produces chunks faster or slower than real time; the player keeps a small
buffer so consecutive sentences do not click or gap.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any

import numpy as np

from ..logs import get_logger
from . import wav

log = get_logger("audio.player")


def list_output_devices() -> list[tuple[int, str]]:
    try:
        import sounddevice as sd

        out: list[tuple[int, str]] = []
        for index, info in enumerate(sd.query_devices()):
            if int(info.get("max_output_channels", 0)) > 0:
                out.append((index, str(info.get("name", f"#{index}"))))
        return out
    except Exception:
        return []


class StreamingPlayer:
    """A tiny software mixer: push PCM at any rate, hear it back to back."""

    def __init__(self, device: str | int | None = None, blocksize_ms: int = 40) -> None:
        self.device = device
        self.blocksize_ms = blocksize_ms
        self._stream: Any = None
        self._queue: deque[np.ndarray] = deque()
        self._lock = threading.Lock()
        self._device_rate = 48000
        self._feeding = 0
        self._playing = False
        self._stop_flag = threading.Event()
        self._closed = False

    # -- lifecycle -----------------------------------------------------
    def _ensure_stream(self) -> bool:
        if self._stream is not None:
            return True
        try:
            import sounddevice as sd
        except Exception as exc:  # noqa: BLE001
            log.warning("sounddevice unavailable: %s", exc)
            return False
        try:
            import sounddevice as sd

            device = self.device
            info = sd.query_devices(device, "output") if device is not None else \
                sd.query_devices(kind="output")
            self._device_rate = int(info.get("default_samplerate") or 48000)
            blocksize = max(64, int(self._device_rate * self.blocksize_ms / 1000))
            # No WASAPI auto_convert: some devices reject it outright
            # (PaErrorCode -9984). We resample ourselves, so plain shared mode
            # works everywhere.
            self._stream = sd.OutputStream(
                samplerate=self._device_rate,
                channels=1,
                dtype="float32",
                device=device,
                blocksize=blocksize,
                callback=self._callback,
            )
            self._stream.start()
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("cannot open output stream: %s", exc)
            self._stream = None
            # last resort: let PortAudio pick everything for us
            try:
                import sounddevice as sd

                self._device_rate = 44100 if self._device_rate not in (44100, 48000) else self._device_rate
                self._stream = sd.OutputStream(
                    samplerate=self._device_rate, channels=1, dtype="float32",
                    callback=self._callback)
                self._stream.start()
                log.info("output stream opened with fallback settings")
                return True
            except Exception as exc2:  # noqa: BLE001
                log.warning("fallback output stream failed: %s", exc2)
                self._stream = None
                return False

    def _callback(self, outdata, frames, _time, _status):  # noqa: ANN001
        outdata.fill(0)
        written = 0
        with self._lock:
            while written < frames and self._queue:
                chunk = self._queue[0]
                take = min(len(chunk), frames - written)
                outdata[written:written + take, 0] = chunk[:take]
                written += take
                if take < len(chunk):
                    self._queue[0] = chunk[take:]
                else:
                    self._queue.popleft()
            self._playing = bool(self._queue)

    # -- feeding -------------------------------------------------------
    def push(self, samples: np.ndarray, samplerate: int) -> None:
        if self._closed:
            return
        data = wav.to_mono(samples)
        if data.size == 0:
            return
        with self._lock:
            self._feeding += 1
        try:
            if not self._ensure_stream():
                return
            if int(samplerate) != self._device_rate:
                data = wav.resample(data, int(samplerate), self._device_rate)
            with self._lock:
                self._queue.append(data)
                self._playing = True
        finally:
            with self._lock:
                self._feeding = max(0, self._feeding - 1)

    def play(self, samples: np.ndarray, samplerate: int) -> None:
        self.push(samples, samplerate)
        self.wait()

    # -- state ---------------------------------------------------------
    @property
    def busy(self) -> bool:
        with self._lock:
            return bool(self._queue) or self._playing

    def wait(self, timeout: float | None = None) -> bool:
        """Block until the queue drains. Returns False on timeout."""
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            with self._lock:
                pending = bool(self._queue)
            if not pending:
                return True
            if deadline is not None and time.monotonic() > deadline:
                return False
            if self._stop_flag.is_set():
                return False
            time.sleep(0.02)

    def stop(self) -> None:
        with self._lock:
            self._queue.clear()
            self._playing = False

    def close(self) -> None:
        self._closed = True
        self.stop()
        stream = self._stream
        self._stream = None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass

    def __enter__(self) -> "StreamingPlayer":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def play_file(path: str, device: str | int | None = None) -> None:
    samples, sr = wav.read_wav(path)
    player = StreamingPlayer(device=device)
    try:
        player.play(samples, sr)
    finally:
        player.close()


__all__ = ["StreamingPlayer", "play_file", "list_output_devices"]
