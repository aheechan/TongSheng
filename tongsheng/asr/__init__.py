"""ASR engine registry.

The language switch in the tray is what selects the engine: Chinese uses
FunASR Paraformer, English uses faster-whisper. A ``fake`` engine keeps unit
tests and headless machines usable.
"""

from __future__ import annotations

import time

import numpy as np

from ..config import AppConfig
from ..logs import get_logger
from .base import ASREngine, ASRResult, EngineUnavailable
from .funasr_zh import FunASREngine
from .whisper_en import WhisperEngine

log = get_logger("asr")

_ALIASES = {
    "funasr": "funasr", "paraformer": "funasr", "paraformer-zh": "funasr", "zh": "funasr",
    "whisper": "whisper", "faster-whisper": "whisper", "faster_whisper": "whisper",
    "en": "whisper",
    "fake": "fake", "none": "fake",
}


class FallbackEngine(ASREngine):
    """Try the preferred engine, then a GPU alternative - never silently CPU.

    Blackwell cards sometimes reject FunASR's CUDA build. Instead of dropping to
    CPU (slow and against the product promise) we switch to faster-whisper on
    the same GPU, which is already shipped for English.
    """

    def __init__(self, primary: ASREngine, secondary: ASREngine) -> None:
        self.primary = primary
        self.secondary = secondary
        self.active: ASREngine | None = None
        self.language = primary.language
        self.name = primary.name

    def load(self) -> None:
        if self.active is not None:
            return
        try:
            self.primary.load()
            self.active = self.primary
            self.name = self.primary.name
            log.info("ASR engine ready: %s", self.primary.name)
            return
        except Exception as exc:  # noqa: BLE001
            log.error("ASR %s unavailable on GPU: %s", self.primary.name, exc)
            log.debug("ASR primary failure", exc_info=True)
        self.secondary.load()
        self.active = self.secondary
        self.name = self.secondary.name
        log.warning("ASR switched to %s (GPU fallback)", self.secondary.name)

    def transcribe(self, samples: np.ndarray, sample_rate: int = 16000) -> ASRResult:
        self.load()
        assert self.active is not None
        result = self.active.transcribe(samples, sample_rate)
        result.engine = self.active.name
        return result

    def close(self) -> None:
        for engine in (self.primary, self.secondary):
            try:
                engine.close()  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001
                pass
        self.active = None


class FakeASR(ASREngine):
    """Deterministic engine for tests: returns a canned sentence."""

    name = "fake"

    def __init__(self, language: str = "zh", text: str | None = None,
                 delay_ms: float = 0.0) -> None:
        self.language = language
        self.text = text
        self.delay_ms = float(delay_ms)

    def load(self) -> None:
        return None

    def transcribe(self, samples: np.ndarray, sample_rate: int = 16000) -> ASRResult:
        if self.delay_ms:
            time.sleep(self.delay_ms / 1000.0)
        default = "今天天气很好，我们去公园散步吧。" if self.language == "zh" else \
            "The weather is nice today, let us take a walk in the park."
        return ASRResult(text=self.text or default, language=self.language,
                         engine=self.name, latency_ms=self.delay_ms)


def create_engine(kind: str, config: AppConfig, language: str,
                  models=None) -> ASREngine:
    key = _ALIASES.get(str(kind or "").strip().lower(), str(kind or "").strip().lower())
    if key == "fake":
        return FakeASR(language=language)
    if key == "funasr":
        primary = FunASREngine(
            model=config.asr.funasr_model if language == "zh" else "paraformer-zh",
            device=config.asr.device,
            model_cache=(models.funasr_dir if models is not None else None),
            allow_cpu_fallback=bool(getattr(config.asr, "allow_cpu_fallback", False)),
        )
        if getattr(config.asr, "gpu_fallback", "whisper") == "whisper":
            secondary = WhisperEngine(
                size=config.asr.whisper_size,
                device=config.asr.device,
                model_dir=(models.whisper_dir if models is not None else None),
                language=language,
            )
            return FallbackEngine(primary, secondary)
        return primary
    if key == "whisper":
        return WhisperEngine(
            size=config.asr.whisper_size,
            device=config.asr.device,
            model_dir=(models.whisper_dir if models is not None else None),
            language=language,
        )
    raise ValueError(f"unknown ASR engine: {kind!r}")


def engine_kind_for_language(config: AppConfig, language: str) -> str:
    return config.asr.zh_engine if language == "zh" else config.asr.en_engine


def available_engines() -> dict[str, bool]:
    import importlib.util

    return {
        "funasr": importlib.util.find_spec("funasr") is not None,
        "whisper": importlib.util.find_spec("faster_whisper") is not None,
        "fake": True,
    }


__all__ = ["ASREngine", "ASRResult", "EngineUnavailable", "FakeASR", "FallbackEngine",
           "FunASREngine", "WhisperEngine", "create_engine",
           "engine_kind_for_language", "available_engines"]
