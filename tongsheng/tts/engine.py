"""GPT-SoVITS synthesis engine with two quality tiers.

Both tiers use the *same cloned voice*; they differ in how the audio is
produced (and therefore in bandwidth and latency):

* LIVE — streamed fragments, few sampling steps, output resampled to 32 kHz
* REC  — whole-sentence synthesis, more steps, native 48 kHz (v4 vocoder)

The wrapper targets the upstream ``GPT_SoVITS.TTS_infer_pack.TTS`` API used by
PrivateVoice (project A); the older ``aquatts`` backend is not required.
"""

from __future__ import annotations

import os
import random
import sys
import threading
import time
from pathlib import Path
from typing import Any, Iterator

import numpy as np

from ..logs import get_logger

log = get_logger("tts.engine")

# Text languages understood by the v2/v3/v4 front-ends.
TEXT_LANGS = {"zh", "en", "ja", "ko", "yue"}

VERSION_SR = {"v2": 32000, "v2Pro": 32000, "v2ProPlus": 32000, "v3": 24000, "v4": 48000}

_VERSION_CACHE: dict[str, str] = {}


def detect_checkpoint_version(repo: str | Path | None, checkpoint: str | Path) -> str:
    """Read the SoVITS version from the checkpoint header (cached).

    Falls back to a filename guess when GPT-SoVITS is not importable yet.
    The upstream package computes some paths from the *current directory* at
    import time, so we chdir into the repo first (and stay there).
    """
    path = str(checkpoint)
    if path in _VERSION_CACHE:
        return _VERSION_CACHE[path]
    version = ""
    if repo is not None and Path(path).exists():
        root = Path(repo)
        try:
            os.chdir(root)
        except OSError:
            pass
        for entry in (str(root), str(root / "GPT_SoVITS")):
            if entry not in sys.path:
                sys.path.insert(0, entry)
        try:
            from GPT_SoVITS.process_ckpt import get_sovits_version_from_path_fast

            _version, model_version, _lora = get_sovits_version_from_path_fast(path)
            version = str(model_version or "")
        except Exception as exc:  # noqa: BLE001
            log.debug("version detection failed: %s", exc)
    if not version:
        name = Path(path).name.lower()
        if "_l48" in name or "s2gv4" in name or "v4" in name:
            version = "v4"
        elif "s2gv3" in name or "v3" in name:
            version = "v3"
        else:
            version = "v2"
    _VERSION_CACHE[path] = version
    return version


class TTSError(RuntimeError):
    pass


class SovitsEngine:
    """One loaded GPT-SoVITS model pair (GPT + SoVITS) for a voice."""

    def __init__(self, repo: str | Path, device: str = "cuda",
                 is_half: bool = True, pretrained: str | Path | None = None) -> None:
        self.repo = Path(repo)
        self.device = device
        self.is_half = bool(is_half)
        self.pretrained = Path(pretrained) if pretrained else \
            self.repo / "GPT_SoVITS" / "pretrained_models"
        self._tts: Any = None
        self._lock = threading.Lock()
        self._ckpt: tuple[str, str] | None = None
        self.version = ""
        self.sample_rate = 32000
        self.load_seconds = 0.0
        self._prev_cwd: str | None = None
        self._torch: Any = None

    # -- loading --------------------------------------------------------
    def _prepare_env(self) -> None:
        os.environ.setdefault("PYTHONUTF8", "1")
        os.environ.setdefault("BIGVGAN_USE_CUDA_KERNEL", "0")
        nltk = self.repo.parent / "nltk_data"
        if nltk.exists():
            os.environ.setdefault("NLTK_DATA", str(nltk))
        for entry in (str(self.repo), str(self.repo / "GPT_SoVITS")):
            if entry not in sys.path:
                sys.path.insert(0, entry)
        (self.pretrained / "fast_langdetect").mkdir(parents=True, exist_ok=True)

    def _patch_torchaudio(self) -> None:
        """torchaudio 2.11 delegates to torchcodec; use soundfile instead."""
        import soundfile as sf
        import torch
        import torchaudio

        if getattr(torchaudio, "_tongsheng_patched", False):
            return

        def _load(path, **kwargs):  # noqa: ANN001, ANN003
            data, sr = sf.read(str(path), dtype="float32", always_2d=True)
            return torch.from_numpy(data.T.copy()), int(sr)

        torchaudio.load = _load  # type: ignore[assignment]
        torchaudio._tongsheng_patched = True  # type: ignore[attr-defined]

    def _detect_version(self, sovits_ckpt: str) -> str:
        try:
            from GPT_SoVITS.process_ckpt import get_sovits_version_from_path_fast

            _version, model_version, _lora = get_sovits_version_from_path_fast(sovits_ckpt)
            return str(model_version or "")
        except Exception:
            name = Path(sovits_ckpt).name.lower()
            for key in ("v4", "v3", "v2"):
                if key in name:
                    return key
            return ""

    def load(self, gpt_ckpt: str, sovits_ckpt: str) -> None:
        with self._lock:
            if self._tts is not None and self._ckpt == (gpt_ckpt, sovits_ckpt):
                return
            if self._tts is not None:
                self._release()
            self._prepare_env()
            self._patch_torchaudio()
            import torch

            self._torch = torch
            self._prev_cwd = os.getcwd()
            os.chdir(self.repo)  # upstream resolves vocoder/pretrained paths from cwd
            try:
                from GPT_SoVITS.TTS_infer_pack.TTS import TTS, TTS_Config
            except ImportError as exc:
                os.chdir(self._prev_cwd)
                raise TTSError(
                    f"cannot import GPT-SoVITS from {self.repo}: {exc}") from exc

            version = self._detect_version(sovits_ckpt) or "v4"
            device = self.device
            if str(device).startswith("cuda") and not torch.cuda.is_available():
                log.warning("CUDA requested but unavailable; using CPU")
                device = "cpu"
            config = {"custom": {
                "device": device,
                "is_half": bool(self.is_half) and device != "cpu",
                "version": version,
                "t2s_weights_path": str(gpt_ckpt),
                "vits_weights_path": str(sovits_ckpt),
                "bert_base_path": str(self.pretrained / "chinese-roberta-wwm-ext-large"),
                "cnhuhbert_base_path": str(self.pretrained / "chinese-hubert-base"),
            }}
            start = time.perf_counter()
            try:
                tts = TTS(TTS_Config(config))
                tts.init_t2s_weights(str(gpt_ckpt))
                tts.init_vits_weights(str(sovits_ckpt))
            except Exception as exc:  # noqa: BLE001
                if self._prev_cwd:
                    os.chdir(self._prev_cwd)
                raise TTSError(f"cannot load voice weights: {exc}") from exc
            self._tts = tts
            self._ckpt = (gpt_ckpt, sovits_ckpt)
            self.version = version
            self.sample_rate = int(VERSION_SR.get(version, 32000))
            self.load_seconds = time.perf_counter() - start
            log.info("loaded %s voice in %.1fs (%s, %d Hz)", version,
                     self.load_seconds, Path(sovits_ckpt).name, self.sample_rate)

    @property
    def loaded(self) -> bool:
        return self._tts is not None

    def unload(self) -> None:
        with self._lock:
            self._release()

    def _release(self) -> None:
        self._tts = None
        self._ckpt = None
        if self._prev_cwd:
            try:
                os.chdir(self._prev_cwd)
            except OSError:
                pass
            self._prev_cwd = None
        try:
            import gc

            gc.collect()
            if self._torch is not None and self._torch.cuda.is_available():
                self._torch.cuda.empty_cache()
        except Exception:
            pass

    # -- synthesis ------------------------------------------------------
    def synthesize(
        self,
        text: str,
        ref_wav: str,
        ref_text: str,
        text_lang: str = "zh",
        prompt_lang: str = "zh",
        *,
        streaming: bool = True,
        fragment_interval: float = 0.32,
        speed: float = 1.0,
        temperature: float = 0.6,
        top_k: int = 5,
        top_p: float = 1.0,
        repetition_penalty: float = 1.9,
        sample_steps: int = 4,
        split_method: str = "cut5",
        batch_size: int = 1,
        seed: int | None = None,
    ) -> Iterator[tuple[np.ndarray, int]]:
        if self._tts is None:
            raise TTSError("TTS engine is not loaded")
        if not (text or "").strip():
            return
        lang = text_lang if text_lang in TEXT_LANGS else "zh"
        inputs: dict[str, Any] = {
            "text": text,
            "text_lang": lang,
            "ref_audio_path": str(ref_wav),
            "prompt_text": ref_text or "",
            "prompt_lang": prompt_lang if prompt_lang in TEXT_LANGS else "zh",
            "top_k": int(top_k),
            "top_p": float(top_p),
            "temperature": float(temperature),
            "text_split_method": split_method,
            "batch_size": max(1, int(batch_size)),
            "speed_factor": float(speed),
            "streaming_mode": bool(streaming),
            "return_fragment": bool(streaming),
            "fragment_interval": float(fragment_interval or 0.3),
            "seed": int(seed if seed is not None else random.randint(1, 99999)),
            "parallel_infer": True,
            "repetition_penalty": float(repetition_penalty),
            "sample_steps": int(sample_steps),
            "super_sampling": False,
        }
        start = time.perf_counter()
        first = True
        for item in self._tts.run(inputs):
            if item is None:
                continue
            if isinstance(item, tuple) and len(item) == 2:
                sr, audio = item
            else:
                sr, audio = self.sample_rate, item
            if audio is None:
                continue
            arr = np.asarray(audio, dtype=np.float32).reshape(-1)
            if arr.size == 0:
                continue
            peak = float(np.max(np.abs(arr)))
            if peak > 2.0:            # int16-scaled float from upstream
                arr = arr / 32768.0
            if first:
                log.debug("ttff %.0f ms", (time.perf_counter() - start) * 1000)
                first = False
            yield arr, int(sr or self.sample_rate)

    def synthesize_all(self, text: str, *args: Any, **kwargs: Any) -> tuple[np.ndarray, int]:
        parts: list[np.ndarray] = []
        sr = 48000
        for chunk, rate in self.synthesize(text, *args, **kwargs):
            parts.append(chunk)
            sr = rate
        if not parts:
            return np.zeros(0, dtype=np.float32), sr
        return np.concatenate(parts), sr


__all__ = ["SovitsEngine", "TTSError", "VERSION_SR", "TEXT_LANGS"]
