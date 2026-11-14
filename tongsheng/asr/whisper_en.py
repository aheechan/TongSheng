"""English ASR through faster-whisper (offline, local weights)."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import numpy as np

from ..logs import get_logger
from .base import ASREngine, ASRResult, EngineUnavailable

log = get_logger("asr.whisper")


class WhisperEngine(ASREngine):
    name = "faster-whisper"
    language = "en"

    def __init__(self, size: str = "small", device: str = "cuda",
                 model_dir: str | Path | None = None, language: str = "en") -> None:
        self.size = size or "small"
        self.device = device or "cuda"
        self.model_dir = str(model_dir) if model_dir else ""
        self.language = language
        self._model = None
        self._lock = threading.Lock()

    def _target(self) -> str:
        if self.model_dir:
            base = Path(self.model_dir)
            candidates = [base / f"faster-whisper-{self.size}", base]
            for candidate in candidates:
                if (candidate / "model.bin").exists():
                    return str(candidate)
        return self.size

    def load(self) -> None:
        if self._model is not None:
            return
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise EngineUnavailable(
                "faster-whisper is not installed (`pip install faster-whisper`).") from exc
        target = self._target()
        attempts = [(self.device, "float16"), (self.device, "int8_float16"), ("cpu", "int8")]
        last: Exception | None = None
        for device, compute in attempts:
            if not str(device).startswith("cuda"):
                device = "cpu"
            try:
                log.info("loading faster-whisper %s on %s/%s", target, device, compute)
                self._model = WhisperModel(target, device=device, compute_type=compute,
                                           download_root=self.model_dir or None)
                self.device = device
                return
            except Exception as exc:  # noqa: BLE001
                last = exc
                self._model = None
        raise EngineUnavailable(f"cannot load faster-whisper: {last}")

    def transcribe(self, samples: np.ndarray, sample_rate: int = 16000) -> ASRResult:
        start = time.perf_counter()
        data = np.asarray(samples, dtype=np.float32).reshape(-1)
        if data.size == 0:
            return ASRResult(text="", language=self.language, engine=self.name)
        with self._lock:
            try:
                self.load()
                assert self._model is not None
                segments, info = self._model.transcribe(
                    data.astype("float32"),
                    language=self.language,
                    beam_size=5,
                    vad_filter=True,
                    condition_on_previous_text=False,
                    no_speech_threshold=0.5,
                    log_prob_threshold=-1.0,
                )
                text = "".join(seg.text for seg in segments)
                detected = getattr(info, "language", None) or self.language
            except Exception as exc:  # noqa: BLE001
                return ASRResult(language=self.language, engine=self.name,
                                 latency_ms=(time.perf_counter() - start) * 1000,
                                 error=f"{type(exc).__name__}: {exc}")
        return ASRResult(text=polish_english(text), language=str(detected),
                         engine=self.name,
                         latency_ms=(time.perf_counter() - start) * 1000)

    def close(self) -> None:
        self._model = None
        try:
            import torch

            torch.cuda.empty_cache()
        except Exception:
            pass


def polish_english(text: str) -> str:
    """Keep word spacing, fix punctuation spacing and sentence case."""
    import re

    value = (text or "").strip()
    if not value:
        return ""
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\s+([,.!?;:])", r"\1", value)
    value = re.sub(r"([,.!?;:])(?=[A-Za-z])", r"\1 ", value)
    if value and value[0].isalpha():
        value = value[0].upper() + value[1:]
    if value and value[-1] not in ".!?。！？…":
        value += "."
    return value


__all__ = ["WhisperEngine", "polish_english"]
