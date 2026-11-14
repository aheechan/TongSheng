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


class AudioInput:
    """One persistent microphone stream used for both metering and recording.

    Opening/closing PortAudio streams for every utterance is what makes some
    WASAPI drivers unhappy (and it also made the level meter go dead while
    recording). Here the stream stays open; a "take" is just a flag that makes
    the callback keep the frames.
    """

    def __init__(self, sample_rate: int = 16000, device: str | int | None = None,
                 max_seconds: float = 60.0, block_ms: int = 40) -> None:
        self.sample_rate = int(sample_rate)
        self.device = parse_device(device)
        self.max_seconds = float(max_seconds)
        self.block_ms = int(block_ms)
        self._stream: Any = None
        self._lock = threading.Lock()
        self._take: list[np.ndarray] = []
        self._recording = False
        self._device_rate = 48000
        self._level_db = -90.0
        self._frames = 0
        self._overflow = 0

    # -- state ----------------------------------------------------------
    @property
    def running(self) -> bool:
        return self._stream is not None

    @property
    def recording(self) -> bool:
        return self._recording

    @property
    def level_db(self) -> float:
        return self._level_db

    @property
    def seconds(self) -> float:
        return self._frames / float(self._device_rate or 1)

    # -- device ---------------------------------------------------------
    def open(self) -> bool:
        if self._stream is not None:
            return True
        try:
            import sounddevice as sd

            device = self.device
            info = sd.query_devices(device, "input") if device is not None else \
                sd.query_devices(kind="input")
            self._device_rate = int(info.get("default_samplerate") or 48000)
            blocksize = max(256, int(self._device_rate * self.block_ms / 1000))

            def callback(indata, frames, _time, status):  # noqa: ANN001
                if status:
                    self._overflow += 1
                data = indata[:, 0].copy() if indata.ndim > 1 else indata.copy()
                rms = float(np.sqrt(np.mean(np.square(data)))) if data.size else 0.0
                self._level_db = max(-90.0, 20.0 * float(np.log10(rms + 1e-12)))
                with self._lock:
                    if not self._recording:
                        return
                    if self._frames > self.max_seconds * self._device_rate:
                        return
                    self._take.append(data)
                    self._frames += len(data)

            self._stream = sd.InputStream(
                samplerate=self._device_rate, channels=1, dtype="float32",
                device=device, blocksize=blocksize, callback=callback)
            self._stream.start()
            log.info("microphone stream open (%d Hz, block %d ms)",
                     self._device_rate, self.block_ms)
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("cannot open microphone: %s", exc)
            self._stream = None
            return False

    def close(self) -> None:
        stream = self._stream
        self._stream = None
        self._recording = False
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass

    # -- takes ----------------------------------------------------------
    def start_take(self) -> bool:
        if not self.open():
            return False
        with self._lock:
            self._take = []
            self._frames = 0
            self._recording = True
        return True

    def stop_take(self) -> np.ndarray:
        with self._lock:
            self._recording = False
            chunks = self._take
            self._take = []
            self._frames = 0
        if not chunks:
            return np.zeros(0, dtype=np.float32)
        audio = wav.to_mono(np.concatenate(chunks))
        if self._device_rate != self.sample_rate:
            audio = wav.resample(audio, self._device_rate, self.sample_rate)
        return audio

    def abort_take(self) -> None:
        with self._lock:
            self._recording = False
            self._take = []
            self._frames = 0


class Recorder:
    """Records one utterance at the device rate, then returns 16 kHz mono.

    Kept for the training dialog, which records long takes while the main
    input stream is paused.
    """

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
        self._level_db = -90.0

    @property
    def level_db(self) -> float:
        """Live input level of the take currently being recorded."""
        return self._level_db

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
            data = np.asarray(indata, dtype=np.float32)
            if data.size:
                rms = float(np.sqrt(np.mean(data ** 2)))
                self._level_db = max(-90.0, 20.0 * float(np.log10(rms + 1e-12)))
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


class MicMonitor:
    """Always-on input level meter (no buffering, just RMS).

    It is paused while the recorder owns the device, so the two never fight
    over the same microphone.
    """

    def __init__(self, device: str | int | None = None) -> None:
        self.device = parse_device(device)
        self._stream: Any = None
        self._level_db = -90.0
        self._peak_db = -90.0
        self._lock = threading.Lock()
        self._device_rate = 44100

    @property
    def level_db(self) -> float:
        with self._lock:
            return self._level_db

    @property
    def peak_db(self) -> float:
        with self._lock:
            return self._peak_db

    @property
    def running(self) -> bool:
        return self._stream is not None

    def start(self) -> bool:
        if self._stream is not None:
            return True
        try:
            import sounddevice as sd

            device = self.device
            info = sd.query_devices(device, "input") if device is not None else \
                sd.query_devices(kind="input")
            self._device_rate = int(info.get("default_samplerate") or 44100)

            def callback(indata, _frames, _time, _status):  # noqa: ANN001
                data = np.asarray(indata, dtype=np.float32)
                if data.size == 0:
                    return
                rms = float(np.sqrt(np.mean(data ** 2)))
                db = 20.0 * float(np.log10(rms + 1e-12))
                with self._lock:
                    self._level_db = db if db > -90 else -90
                    self._peak_db = max(self._peak_db * 0.995, self._level_db)

            self._stream = sd.InputStream(
                samplerate=self._device_rate, channels=1, dtype="float32",
                device=device,
                # 100 ms blocks: a handful of callbacks per second keeps the GIL
                # free for the keyboard hook and the UI (blocksize=0 can fire
                # hundreds of times per second and starve every other thread).
                blocksize=max(256, int(self._device_rate * 0.1)),
                callback=callback)
            self._stream.start()
            return True
        except Exception as exc:  # noqa: BLE001
            log.debug("mic monitor unavailable: %s", exc)
            self._stream = None
            return False

    def stop(self) -> None:
        stream = self._stream
        self._stream = None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        with self._lock:
            self._level_db = -90.0
            self._peak_db = -90.0


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


__all__ = ["Recorder", "MicMonitor", "InputDevice", "list_input_devices",
           "parse_device", "record_for"]
