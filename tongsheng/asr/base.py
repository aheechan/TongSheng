"""ASR engine contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np

from ..logs import get_logger

log = get_logger("asr")


class EngineUnavailable(RuntimeError):
    """Raised when an optional backend cannot be imported or loaded."""


@dataclass
class ASRResult:
    text: str = ""
    language: str = "zh"
    latency_ms: float = 0.0
    engine: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.text.strip()) and not self.error


class ASREngine(ABC):
    name: str = "base"
    language: str = "zh"

    @abstractmethod
    def load(self) -> None: ...

    @abstractmethod
    def transcribe(self, samples: np.ndarray, sample_rate: int = 16000) -> ASRResult: ...

    def warmup(self) -> float:
        """Run one silent sentence.

        Raises ``EngineUnavailable`` when the engine cannot actually produce a
        result - a model that loaded but cannot infer must never be reported as
        ready (that is what hid the pythonw/stdio bug for hours).
        """
        import time

        start = time.perf_counter()
        result = self.transcribe(np.zeros(16000, dtype=np.float32), 16000)
        error = getattr(result, "error", "")
        if error:
            log.error("%s warmup could not use the model: %s", self.name, error)
            raise EngineUnavailable(f"{self.name}: {error}")
        return (time.perf_counter() - start) * 1000.0

    def close(self) -> None:  # pragma: no cover - optional
        return None


__all__ = ["ASREngine", "ASRResult", "EngineUnavailable"]
