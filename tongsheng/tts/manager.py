"""TTS runtime: pick a voice, a quality tier, and stream audio out."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

from ..audio import StreamingPlayer, wav as wavmod
from ..config import AppConfig, emotion_preset
from ..logs import get_logger
from ..paths import ModelPaths
from ..text import detect_language, split_sentences
from .engine import SovitsEngine, TTSError, detect_checkpoint_version
from .voices import VoiceProfile, VoiceStore

log = get_logger("tts")


@dataclass
class SpeechResult:
    text: str
    mode: str
    sample_rate: int = 0
    seconds: float = 0.0
    path: Path | None = None
    error: str = ""


class TTSRuntime:
    def __init__(self, config: AppConfig, models: ModelPaths,
                 on_status: Callable[[str], None] | None = None) -> None:
        self.config = config
        self.models = models
        self.store = VoiceStore(models.characters or Path("voices"))
        self.on_status = on_status or (lambda _msg: None)
        self._engines: dict[str, SovitsEngine] = {}
        self._profile: VoiceProfile | None = None
        # re-entrant: speak() holds it while generating, and the warm-up thread
        # must not unload the engine underneath a running synthesis (native AV).
        self._lock = threading.RLock()
        self._stop = threading.Event()

    # -- voices ---------------------------------------------------------
    def voices(self) -> list[VoiceProfile]:
        return self.store.list()

    def voice_id(self) -> str:
        return self.config.tts.voice or ""

    def current_voice(self) -> VoiceProfile | None:
        if self._profile is not None:
            return self._profile
        profile = self.store.get(self.voice_id()) if self.voice_id() else None
        if profile is None:
            profile = self.store.first()
        return profile

    def set_voice(self, voice_id: str) -> VoiceProfile | None:
        profile = self.store.get(voice_id)
        if profile is None:
            return None
        self.config.tts.voice = profile.id
        self._profile = profile
        self.unload()
        return profile

    # -- engine ---------------------------------------------------------
    def _engine(self, mode: str, profile: VoiceProfile) -> SovitsEngine:
        tier = self.config.tier(mode)
        if self.models.gpt_sovits is None:
            raise TTSError("未找到 GPT-SoVITS 目录，请在设置中指定 paths.gpt_sovits")
        gpt, sovits = self._checkpoints(mode, profile)
        key = f"{gpt}:{sovits}"
        with self._lock:
            engine = self._engines.get(key)
            if engine is not None and engine.loaded:
                return engine
            if not self.config.tts.keep_both_tiers_loaded:
                for other_key, other in list(self._engines.items()):
                    if other_key != key:
                        other.unload()
                self._engines.clear()
            engine = SovitsEngine(self.models.gpt_sovits, device=self.config.tts.device,
                                  pretrained=self.models.pretrained)
            self.on_status(f"loading voice ({mode})")
            engine.load(gpt, sovits)
            self._engines[key] = engine
            return engine

    def _checkpoints(self, mode: str, profile: VoiceProfile) -> tuple[str, str]:
        """Tier checkpoint with a graceful fall back to the upstream base model."""
        tier = self.config.tier(mode)
        pretrained = self.models.pretrained
        if pretrained is None:
            raise TTSError("未找到预训练模型目录")
        sovits = profile.checkpoint(mode)
        if sovits and Path(sovits).exists():
            detected = detect_checkpoint_version(self.models.gpt_sovits, sovits)
            if detected != tier.version:
                log.info("voice %s checkpoint is %s but tier %s needs %s; zero-shot base",
                         profile.name, detected, mode, tier.version)
                sovits = ""
        else:
            sovits = ""
        if not sovits:
            base = self._base_sovits(tier.version)
            if base is None:
                raise TTSError(f"缺少 {tier.version} 底模，无法合成")
            sovits = str(base)
        gpt = profile.gpt_path if profile.trained else ""
        if not gpt or not Path(gpt).exists():
            gpt = str(self._default_gpt())
        return gpt, sovits

    def _base_sovits(self, version: str) -> Path | None:
        pretrained = self.models.pretrained
        if pretrained is None:
            return None
        candidates = [
            pretrained / "gsv-v4-pretrained" / "s2Gv4.pth",
            pretrained / "s2Gv4.pth",
        ] if version == "v4" else [pretrained / "s2Gv3.pth"]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _default_gpt(self) -> Path:
        if self.models.pretrained is None:
            raise TTSError("未找到预训练模型目录")
        candidate = self.models.pretrained / "s1v3.ckpt"
        if not candidate.exists():
            raise TTSError(f"缺少 GPT 权重：{candidate}")
        return candidate

    def warmup(self, mode: str | None = None) -> None:
        profile = self.current_voice()
        if profile is None:
            return
        try:
            self._engine(mode or self.config.mode, profile)
        except Exception as exc:  # noqa: BLE001
            log.warning("warmup failed: %s", exc)

    def unload(self) -> None:
        with self._lock:
            for engine in self._engines.values():
                engine.unload()
            self._engines.clear()

    def stop(self) -> None:
        self._stop.set()

    # -- synthesis ------------------------------------------------------
    def speak(self, text: str, mode: str, player: StreamingPlayer,
              out_subdir: str = "rec",
              text_lang: str | None = None,
              on_sentence: Callable[[str], None] | None = None) -> SpeechResult:
        self._stop.clear()
        profile = self.current_voice()
        result = SpeechResult(text=text, mode=mode)
        if profile is None:
            result.error = "no voice"
            return result
        value = (text or "").strip()
        if not value:
            result.error = "empty text"
            return result
        tier = self.config.tier(mode)
        try:
            engine = self._engine(mode, profile)
        except Exception as exc:  # noqa: BLE001
            result.error = str(exc)
            return result

        lang = text_lang or detect_language(value)
        ref = profile.reference_path
        if not ref.exists():
            result.error = f"参考音频不存在：{ref}"
            return result
        ref_text = profile.reference_text or ""
        # never trust a stale profile field: the prompt transcript's own language
        # is what the front-end needs (a zh prompt on English audio ruins prosody)
        prompt_lang = detect_language(ref_text) if ref_text else (
            profile.reference_lang if profile.reference_lang in ("zh", "en") else "zh")

        emo_temp, emo_topk, emo_speed = emotion_preset(self.config.tts.emotion)
        base_speed = float(self.config.tts.speed or 1.0)
        common = dict(
            ref_wav=str(ref),
            ref_text=ref_text,
            text_lang=lang,
            prompt_lang=prompt_lang,
            speed=round(base_speed * emo_speed, 3),
            temperature=emo_temp,
            top_k=emo_topk,
            top_p=self.config.tts.top_p,
            repetition_penalty=self.config.tts.repetition_penalty,
            sample_steps=tier.sample_steps,
            split_method=tier.split_method,
            batch_size=tier.batch_size,
        )
        live_gain = float(self.config.tts.live_volume or 1.0) if mode == "live" else 1.0
        start = time.perf_counter()
        total_samples = 0
        produced_sr = tier.sample_rate
        try:
            # Hold the runtime lock for the whole generation: a background
            # warm-up must never unload the engine mid-synthesis.
            self._lock.acquire()
            if mode == "rec":
                audio, sr = engine.synthesize_all(value, streaming=False, **common)
                if audio.size == 0:
                    result.error = "synthesis returned no audio"
                    return result
                audio = wavmod.resample(audio, sr, tier.sample_rate)
                produced_sr = tier.sample_rate
                result.path = self._save_recording(audio, produced_sr, out_subdir)
                player.push(audio, produced_sr)
                total_samples = audio.size
            else:
                cfg_tts = self.config.tts
                sentences = split_sentences(
                    value, cfg_tts.max_chars_per_sentence, lang,
                    min_chars=cfg_tts.min_chars_per_sentence)
                # REC renders the whole text in one call and sounds best; LIVE
                # keeps that context by rendering 1-2 sentences per call, then
                # plays them back to back while the next chunk is generated.
                sentences = _merge_for_live(
                    sentences, int(cfg_tts.live_first_chunk_chars),
                    int(cfg_tts.live_chunk_chars))
                streaming = bool(cfg_tts.live_fragments)
                gap_ms = max(0, int(cfg_tts.sentence_gap_ms))
                gap = np.zeros(int(tier.sample_rate * gap_ms / 1000.0), dtype=np.float32)
                for index, sentence in enumerate(sentences):
                    if self._stop.is_set():
                        break
                    if on_sentence:
                        on_sentence(sentence)
                    if not streaming:
                        # Project A strategy: render the whole chunk first,
                        # fade the edges, breathe between chunks, then play.
                        chunk_t0 = time.perf_counter()
                        audio, sr = self._render_sentence(
                            engine, sentence, common, lang, tier, cfg_tts)
                        render_s = time.perf_counter() - chunk_t0
                        if audio.size == 0:
                            continue
                        if sr != tier.sample_rate:
                            audio = wavmod.resample(audio, sr, tier.sample_rate)
                        audio = _apply_fades(audio, tier.sample_rate,
                                             cfg_tts.fade_in_ms, cfg_tts.fade_out_ms)
                        if live_gain != 1.0:
                            audio = np.clip(audio * live_gain, -1.0, 1.0).astype(np.float32)
                        if index and gap.size:
                            player.push(gap, tier.sample_rate)
                            total_samples += gap.size
                        produced_sr = tier.sample_rate
                        if sr and render_s:
                            log.info("live chunk %d: %d chars -> %.2fs audio in "
                                     "%.2fs render (%.2fx realtime)",
                                     index + 1, len(sentence), audio.size / sr,
                                     render_s, (audio.size / sr) / max(render_s, 1e-3))
                        player.push(audio, produced_sr)
                        total_samples += audio.size
                        continue
                    for chunk, sr in engine.synthesize(
                            sentence, streaming=True,
                            fragment_interval=tier.fragment_interval, **common):
                        if self._stop.is_set():
                            break
                        if sr != tier.sample_rate:
                            chunk = wavmod.resample(chunk, sr, tier.sample_rate)
                        if live_gain != 1.0:
                            chunk = np.clip(chunk * live_gain, -1.0, 1.0).astype(np.float32)
                        produced_sr = tier.sample_rate
                        player.push(chunk, produced_sr)
                        total_samples += chunk.size
                # never block forever if the output device stops consuming
                limit = total_samples / float(tier.sample_rate or 1) * 2.0 + 15.0
                if not player.wait(timeout=limit):
                    log.warning("playback did not finish in %.1fs; stopping", limit)
                    player.stop()
        except Exception as exc:  # noqa: BLE001
            log.exception("synthesis failed")
            result.error = f"{type(exc).__name__}: {exc}"
            return result
        finally:
            try:
                self._lock.release()
            except RuntimeError:
                pass
        result.sample_rate = produced_sr
        result.seconds = total_samples / float(produced_sr or 1)
        log.info("speak %s: %.1fs audio in %.1fs (%d Hz)", mode, result.seconds,
                 time.perf_counter() - start, produced_sr)
        return result

    def _render_sentence(self, engine, sentence: str, common: dict,
                         lang: str, tier, cfg_tts) -> tuple[np.ndarray, int]:
        """Render one sentence, retrying obviously broken output (project A)."""
        kwargs = {k: v for k, v in common.items() if k != "fragment_interval"}
        audio, sr = engine.synthesize_all(sentence, streaming=False, **kwargs)
        if not cfg_tts.retry_bad_sentence or audio.size == 0:
            return audio, sr
        seconds = audio.size / float(sr or 1)
        peak = float(np.max(np.abs(audio)))
        expected = max(0.6, len(sentence) * float(cfg_tts.max_sec_per_char))
        bad = peak < 0.02 or seconds > expected * 1.8
        if not bad:
            return audio, sr
        log.info("retrying sentence (peak=%.3f, %.2fs vs expected %.1fs): %r",
                 peak, seconds, expected, sentence[:28])
        retry = dict(kwargs)
        retry["top_k"] = 15
        retry["temperature"] = 0.7
        retry["seed"] = int(time.time()) % 99991
        audio2, sr2 = engine.synthesize_all(sentence, streaming=False, **retry)
        if audio2.size == 0:
            return audio, sr
        return audio2, sr2

    def synthesize_file(self, text: str, mode: str, path: str | Path,
                        text_lang: str | None = None) -> Path:
        profile = self.current_voice()
        if profile is None:
            raise TTSError("no voice selected")
        tier = self.config.tier(mode)
        engine = self._engine(mode, profile)
        lang = text_lang or detect_language(text)
        audio, sr = engine.synthesize_all(
            text, str(profile.reference_path), profile.reference_text or "",
            lang, profile.reference_lang,
            streaming=False, speed=self.config.tts.speed,
            temperature=self.config.tts.temperature, top_k=self.config.tts.top_k,
            top_p=self.config.tts.top_p,
            repetition_penalty=self.config.tts.repetition_penalty,
            sample_steps=tier.sample_steps, split_method=tier.split_method)
        audio = wavmod.resample(audio, sr, tier.sample_rate)
        return wavmod.write_wav(path, audio, tier.sample_rate)

    def _save_recording(self, audio: np.ndarray, sr: int,
                        subdir: str = "rec") -> Path | None:
        base = self.models.results or Path("results")
        folder = base / subdir
        folder.mkdir(parents=True, exist_ok=True)
        name = time.strftime("%Y%m%d-%H%M%S") + f"-{sr // 1000}k.wav"
        return wavmod.write_wav(folder / name, audio, sr)


def _merge_for_live(sentences: list[str], first_limit: int,
                    rest_limit: int | None = None) -> list[str]:
    """Short first chunk (fast start), long later chunks (better prosody).

    The first chunk only has to be rendered before playback can start; every
    following chunk is generated while the previous one plays, so it can afford
    two to four sentences of context and one shared prompt pass.
    """
    rest = max(first_limit, int(rest_limit or first_limit))
    if len(sentences) <= 1:
        return sentences
    merged: list[str] = []
    current = ""
    limit = first_limit
    for sentence in sentences:
        candidate = (current + sentence) if current else sentence
        if current and len(candidate) > limit:
            merged.append(current)
            current = sentence
            limit = rest
        else:
            current = candidate
    if current:
        merged.append(current)
    return merged


def _apply_fades(samples: np.ndarray, samplerate: int,
                 fade_in_ms: float, fade_out_ms: float) -> np.ndarray:
    """Raised-cosine edge fades; project A uses 12 ms in / 25 ms out."""
    data = np.asarray(samples, dtype=np.float32).copy()
    if data.size == 0 or samplerate <= 0:
        return data
    fin = int(samplerate * max(0.0, float(fade_in_ms)) / 1000.0)
    fout = int(samplerate * max(0.0, float(fade_out_ms)) / 1000.0)
    fin = min(fin, data.size // 2)
    fout = min(fout, data.size - fin)
    if fin > 1:
        window = 0.5 - 0.5 * np.cos(np.linspace(0.0, np.pi, fin, dtype=np.float32))
        data[:fin] *= window
    if fout > 1:
        window = 0.5 + 0.5 * np.cos(np.linspace(0.0, np.pi, fout, dtype=np.float32))
        data[-fout:] *= window
    return data


__all__ = ["TTSRuntime", "SpeechResult"]
