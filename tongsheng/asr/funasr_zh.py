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
                 punc_model: str | None = None,
                 allow_cpu_fallback: bool = False) -> None:
        self.model_id = model or "paraformer-zh"
        self.device = device or "cuda"
        self.model_cache = str(model_cache) if model_cache else ""
        self.punc_model = punc_model
        self.allow_cpu_fallback = allow_cpu_fallback
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

        allow_cpu = bool(getattr(self, "allow_cpu_fallback", False))
        wants_cuda = str(self.device).startswith("cuda")
        if wants_cuda:
            try:
                import torch

                if not torch.cuda.is_available():
                    if not allow_cpu:
                        raise EngineUnavailable(
                            "CUDA is not available to torch; FunASR needs a working "
                            "NVIDIA driver (asr.allow_cpu_fallback=true to use CPU)")
                    wants_cuda = False
            except EngineUnavailable:
                raise
            except Exception:  # noqa: BLE001
                if not allow_cpu:
                    raise
                wants_cuda = False

        base_kwargs: dict[str, object] = {
            "model": self.model_id,
            "disable_update": True,
        }
        if self.punc_model:
            base_kwargs["punc_model"] = self.punc_model

        # Same code path as project A (AutoModel(device=...)) plus a small
        # compatibility ladder for newer cards: an explicit device index and a
        # lazily loaded CUDA module table usually clear startup failures on
        # sm_120 / Blackwell without touching the packaged runtime.
        attempts: list[tuple[str, dict[str, object]]] = []
        if wants_cuda:
            attempts.append(("cuda", {"device": "cuda"}))
            attempts.append(("cuda:0", {"device": "cuda:0"}))
            attempts.append(("cuda (lazy)", {"device": "cuda", "_lazy": True}))
        if allow_cpu or not wants_cuda:
            attempts.append(("cpu", {"device": "cpu"}))

        last: Exception | None = None
        for label, extra in attempts:
            lazy = bool(extra.pop("_lazy", False))
            if lazy:
                os.environ["CUDA_MODULE_LOADING"] = "LAZY"
                try:
                    import torch

                    torch.cuda.init()
                    torch.cuda.set_device(0)
                except Exception:  # noqa: BLE001
                    pass
            kwargs = dict(base_kwargs)
            kwargs.update(extra)
            log.info("loading FunASR model %s on %s", self.model_id, label)
            try:
                self._model = AutoModel(**kwargs)
                self.device = str(kwargs["device"])
                log.info("FunASR ready on %s", self.device)
                return
            except Exception as exc:  # noqa: BLE001
                last = exc
                log.warning("FunASR load failed on %s: %s", label, exc)
                log.error("FunASR %s failure detail", label, exc_info=True)

        detail = f"{type(last).__name__}: {last}" if last else "no device available"
        raise EngineUnavailable(
            "FunASR could not start on GPU: " + detail +
            "\nCheck the NVIDIA driver (CUDA 12.8 / 570.x or newer) for this card, "
            "or set asr.en_engine=whisper, or allow CPU with asr.allow_cpu_fallback=true")

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
