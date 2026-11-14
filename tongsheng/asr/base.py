"""ASR engine contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


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
        import time

        start = time.perf_counter()
        try:
            self.transcribe(np.zeros(16000, dtype=np.float32), 16000)
        except Exception:
            pass
        return (time.perf_counter() - start) * 1000.0

    def close(self) -> None:  # pragma: no cover - optional
        return None


__all__ = ["ASREngine", "ASRResult", "EngineUnavailable"]
