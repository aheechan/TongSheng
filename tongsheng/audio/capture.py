"""Microphone capture (push-to-talk) built on ``sounddevice``."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

import numpy as np

from ..logs import get_logger
from . import wav

log = get_logger("audio.capture")


@dataclass
class InputDevice:
    index: int
    name: str
    channels: int
    default: bool = False


def list_input_devices() -> list[InputDevice]:
    try:
        import sounddevice as sd
    except Exception as exc:  # noqa: BLE001
        log.warning("sounddevice unavailable: %s", exc)
        return []
    devices: list[InputDevice] = []
    try:
        default_index = None
        try:
            default_index = int(sd.default.device[0])
        except Exception:
            pass
        for index, info in enumerate(sd.query_devices()):
            if int(info.get("max_input_channels", 0)) < 1:
                continue
            devices.append(InputDevice(index=index, name=str(info.get("name", f"#{index}")),
                                       channels=int(info.get("max_input_channels", 1)),
                                       default=index == default_index))
    except Exception as exc:  # noqa: BLE001
        log.warning("cannot enumerate input devices: %s", exc)
    return devices


def parse_device(value: str | int | None) -> int | None:
    """Accept a device index, a name substring or None (system default)."""
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    lowered = text.lower()
    for device in list_input_devices():
        if lowered in device.name.lower():
            return device.index
    return None


class Recorder:
    """Records one utterance at the device rate, then returns 16 kHz mono."""

    def __init__(self, sample_rate: int = 16000, channels: int = 1,
                 device: str | int | None = None, max_seconds: float = 40.0) -> None:
        self.sample_rate = int(sample_rate)
        self.channels = int(channels)
        self.device = parse_device(device)
        self.max_seconds = float(max_seconds)
        self._stream: Any = None
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._recording = False
        self._device_rate = self.sample_rate
        self._overflow = 0
        self._frames = 0

    @property
    def recording(self) -> bool:
        return self._recording

    def start(self) -> None:
        import sounddevice as sd

        with self._lock:
            self._chunks = []
            self._overflow = 0
            self._frames = 0
        device = self.device
        try:
            info = sd.query_devices(device, "input") if device is not None else \
                sd.query_devices(kind="input")
            self._device_rate = int(info.get("default_samplerate") or self.sample_rate)
        except Exception:
            self._device_rate = self.sample_rate

        def callback(indata, frames, _time, status):  # noqa: ANN001
            if status:
                self._overflow += 1
            with self._lock:
                if not self._recording:
                    return
                self._chunks.append(np.array(indata, dtype=np.float32, copy=True))
                self._frames += int(frames)

        self._stream = sd.InputStream(
            samplerate=self._device_rate,
            channels=self.channels,
            device=device,
            dtype="float32",
            callback=callback,
            blocksize=0,
        )
        self._recording = True
        self._stream.start()

    def stop(self) -> np.ndarray:
        self._recording = False
        stream = self._stream
        self._stream = None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception as exc:  # noqa: BLE001
                log.warning("closing input stream failed: %s", exc)
        with self._lock:
            chunks = list(self._chunks)
            self._chunks = []
        if not chunks:
            return np.zeros(0, dtype=np.float32)
        data = np.concatenate(chunks, axis=0)
        audio = wav.to_mono(data)
        limit = int(self.max_seconds * self._device_rate)
        if limit and audio.size > limit:
            audio = audio[-limit:]
        if self._device_rate != self.sample_rate:
            audio = wav.resample(audio, self._device_rate, self.sample_rate)
        if self._overflow:
            log.debug("input overflow events: %s", self._overflow)
        return audio

    def abort(self) -> None:
        self._recording = False
        stream = self._stream
        self._stream = None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        with self._lock:
            self._chunks = []


def record_for(seconds: float, sample_rate: int = 16000,
               device: str | int | None = None) -> np.ndarray:
    """Small helper for the diagnostics panel."""
    recorder = Recorder(sample_rate=sample_rate, device=device,
                        max_seconds=max(1.0, seconds))
    recorder.start()
    try:
        import time

        time.sleep(seconds)
    finally:
        return recorder.stop()


__all__ = ["Recorder", "InputDevice", "list_input_devices", "parse_device", "record_for"]
