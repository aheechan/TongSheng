"""Chinese ASR through FunASR / Paraformer (offline, local weights)."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import numpy as np

from ..logs import get_logger
from .base import ASREngine, ASRResult, EngineUnavailable

log = get_logger("asr.funasr")


class FunASREngine(ASREngine):
    name = "funasr-paraformer"
    language = "zh"

    def __init__(self, model: str = "paraformer-zh", device: str = "cuda",
                 model_cache: str | Path | None = None,
                 punc_model: str | None = None) -> None:
        self.model_id = model or "paraformer-zh"
        self.device = device or "cuda"
        self.model_cache = str(model_cache) if model_cache else ""
        self.punc_model = punc_model
        self._model = None
        self._lock = threading.Lock()

    def _prepare_env(self) -> None:
        if self.model_cache:
            base = Path(self.model_cache)
            # ModelScope expects MODELSCOPE_CACHE/models/<org>--<name>; our cache
            # root is .../models/asr/modelscope, so hand it over unchanged -
            # pointing at the parent made ModelScope copy the 950 MB model again
            os.environ.setdefault("MODELSCOPE_CACHE", str(base))
        os.environ.setdefault("FUNASR_DISABLE_UPDATE", "1")

    def load(self) -> None:
        if self._model is not None:
            return
        self._prepare_env()
        try:
            from funasr import AutoModel
        except ImportError as exc:
            raise EngineUnavailable(
                "FunASR is not installed (`pip install funasr`).") from exc
        device = self.device
        try:
            import torch

            if str(device).startswith("cuda") and not torch.cuda.is_available():
                device = "cpu"
        except Exception:
            pass
        kwargs: dict[str, object] = {
            "model": self.model_id,
            "device": device,
            "disable_update": True,
        }
        if self.punc_model:
            kwargs["punc_model"] = self.punc_model
        log.info("loading FunASR model %s on %s", self.model_id, device)
        try:
            self._model = AutoModel(**kwargs)
        except Exception as exc:  # noqa: BLE001
            if device != "cpu":
                log.warning("FunASR failed on %s (%s); retrying on CPU", device, exc)
                log.debug("FunASR CUDA failure detail", exc_info=True)
                kwargs["device"] = "cpu"
                self._model = AutoModel(**kwargs)
            else:
                raise EngineUnavailable(f"cannot load FunASR model: {exc}") from exc
        self.device = str(device)

    def transcribe(self, samples: np.ndarray, sample_rate: int = 16000) -> ASRResult:
        start = time.perf_counter()
        data = np.asarray(samples, dtype=np.float32).reshape(-1)
        if data.size == 0:
            return ASRResult(text="", language="zh", engine=self.name)
        with self._lock:
            try:
                self.load()
                assert self._model is not None
                out = self._model.generate(input=data, batch_size_s=300)
            except Exception as exc:  # noqa: BLE001
                return ASRResult(language="zh", engine=self.name,
                                 latency_ms=(time.perf_counter() - start) * 1000,
                                 error=f"{type(exc).__name__}: {exc}")
        text = ""
        if isinstance(out, list) and out:
            text = str(out[0].get("text") or "")
        text = _clean_zh(text)
        return ASRResult(text=text, language="zh", engine=self.name,
                         latency_ms=(time.perf_counter() - start) * 1000)

    def close(self) -> None:
        self._model = None
        try:
            import torch

            torch.cuda.empty_cache()
        except Exception:
            pass


def _clean_zh(text: str) -> str:
    if not text:
        return ""
    cleaned = text.replace(" ", "").strip()
    cleaned = cleaned.replace("，", "，").replace(",", "，")
    return cleaned


__all__ = ["FunASREngine"]
