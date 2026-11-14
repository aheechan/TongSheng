"""WAV / PCM helpers shared by capture, ASR and playback."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np


def to_mono(samples: np.ndarray) -> np.ndarray:
    data = np.asarray(samples)
    if data.ndim == 2:
        data = data.mean(axis=1)
    return np.ascontiguousarray(data.reshape(-1), dtype=np.float32)


def read_wav(path: str | Path) -> tuple[np.ndarray, int]:
    import soundfile as sf

    data, sr = sf.read(str(path), dtype="float32", always_2d=True)
    return to_mono(data), int(sr)


def write_wav(path: str | Path, samples: np.ndarray, sr: int,
              subtype: str = "PCM_16") -> Path:
    import soundfile as sf

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(target), to_mono(samples), int(sr), subtype=subtype)
    return target


def resample(samples: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    data = to_mono(samples)
    if sr_in == sr_out or data.size == 0:
        return data
    from math import gcd

    from scipy.signal import resample_poly

    divisor = gcd(int(sr_in), int(sr_out))
    up = int(sr_out) // divisor
    down = int(sr_in) // divisor
    if up < 1 or down < 1:
        return data
    return np.ascontiguousarray(resample_poly(data, up, down).astype(np.float32))


def resample_to(samples: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    return resample(samples, sr_in, sr_out)


def trim_silence(samples: np.ndarray, sr: int, floor_db: float = -45.0,
                 pad_ms: int = 100) -> np.ndarray:
    """Cut leading/trailing silence using a 20 ms frame energy envelope."""
    data = to_mono(samples)
    if data.size == 0:
        return data
    frame = max(1, int(sr * 0.02))
    n = max(1, (data.size - frame) // frame + 1)
    usable = n * frame
    frames = data[:usable].reshape(n, frame)
    rms = 20.0 * np.log10(np.sqrt(np.mean(frames ** 2, axis=1)) + 1e-12)
    voiced = np.where(rms > floor_db)[0]
    if voiced.size == 0:
        return data
    pad = int(sr * pad_ms / 1000.0)
    start = max(0, int(voiced[0]) * frame - pad)
    end = min(data.size, (int(voiced[-1]) + 1) * frame + pad)
    return data[start:end]


def peak_normalize(samples: np.ndarray, target: float = 0.92) -> np.ndarray:
    data = to_mono(samples)
    peak = float(np.max(np.abs(data))) if data.size else 0.0
    if peak <= 1e-6:
        return data
    return (data * (target / peak)).astype(np.float32)


def rms_db(samples: np.ndarray) -> float:
    data = to_mono(samples)
    if data.size == 0:
        return -120.0
    return float(20.0 * math.log10(float(np.sqrt(np.mean(data ** 2))) + 1e-12))


def duration(samples: np.ndarray, sr: int) -> float:
    return len(samples) / float(sr or 1)


def pcm16_to_float(raw: bytes | bytearray) -> np.ndarray:
    data = np.frombuffer(bytes(raw), dtype=np.int16)
    return (data.astype(np.float32) / 32768.0).copy()


def float_to_pcm16(samples: np.ndarray) -> bytes:
    data = np.clip(to_mono(samples), -1.0, 1.0)
    return (data * 32767.0).astype(np.int16).tobytes()


__all__ = ["to_mono", "read_wav", "write_wav", "resample", "resample_to",
           "trim_silence", "peak_normalize", "rms_db", "duration",
           "pcm16_to_float", "float_to_pcm16"]
