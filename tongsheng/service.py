"""Application service: capture → ASR → correct → translate → cloned speech.

The service owns threads and model lifecycles; the tray only renders state and
forwards user intent. All callbacks fire on worker threads — the Qt layer
marshals them onto the GUI thread.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from .asr import ASREngine, create_engine, engine_kind_for_language
from .audio import MicMonitor, Recorder, StreamingPlayer
from .config import (AppConfig, normalize_language, normalize_language_output,
                     other_language, speaks_target)
from .correct import Corrector, NullCorrector
from .llm import ChatClient, ServerManager
from .llm.servers import ServerManager as _ServerManager
from .logs import get_logger
from .paths import ModelPaths
from .translate import Translator, TranslationError
from .tts import TTSRuntime

log = get_logger("service")


class State(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    WORKING = "working"
    SPEAKING = "speaking"
    ERROR = "error"


@dataclass
class TurnResult:
    raw: str = ""
    corrected: str = ""
    translation: str = ""
    source_lang: str = "zh"
    target_lang: str = "en"
    mode: str = "live"
    asr_ms: float = 0.0
    correct_ms: float = 0.0
    translate_ms: float = 0.0
    tts_ms: float = 0.0
    error: str = ""
    audio_path: str = ""
    spoken: bool = True

    def as_record(self) -> dict[str, Any]:
        data = asdict(self)
        data["ts"] = time.strftime("%Y-%m-%d %H:%M:%S")
        return data


class TongShengService:
    def __init__(self, config: AppConfig, models: ModelPaths,
                 on_state: Callable[[State, str], None] | None = None,
                 on_turn: Callable[[TurnResult], None] | None = None,
                 on_error: Callable[[str], None] | None = None,
                 on_status: Callable[[str], None] | None = None) -> None:
        self.config = config
        self.models = models
        self.on_state = on_state or (lambda _s, _m: None)
        self.on_turn = on_turn or (lambda _t: None)
        self.on_error = on_error or (lambda _e: None)
        self.on_status = on_status or (lambda _m: None)

        self._state = State.IDLE
        self._lock = threading.Lock()
        self._worker: threading.Thread | None = None
        self._engines: dict[str, ASREngine] = {}
        self._asr_ready: set[str] = set()
        self._asr_failed: set[str] = set()
        self._servers: ServerManager | None = None
        self._corrector: Corrector | NullCorrector = NullCorrector()
        self._translator: Translator | None = None
        self._ready = threading.Event()
        self._warming = False

        self.recorder = Recorder(sample_rate=config.audio.sample_rate,
                                 device=config.audio.input_device,
                                 max_seconds=config.audio.max_seconds)
        self.monitor = MicMonitor(device=config.audio.input_device)
        self.player = StreamingPlayer(device=config.audio.output_device)
        self.tts = TTSRuntime(config, models, on_status=on_status)
        self.history: list[TurnResult] = []

    # -- state ----------------------------------------------------------
    @property
    def state(self) -> State:
        return self._state

    def _set_state(self, state: State, message: str = "") -> None:
        self._state = state
        try:
            self.on_state(state, message)
        except Exception:
            log.exception("state callback failed")

    @property
    def ready(self) -> bool:
        return self._ready.is_set()

    # -- lifecycle ------------------------------------------------------
    def start(self) -> None:
        self._set_state(State.IDLE, "starting")
        if self.config.llm.servers.enabled:
            self._servers = ServerManager.from_config(self.config, self.models)
        thread = threading.Thread(target=self._prepare, name="ts-prepare", daemon=True)
        thread.start()

    def warmup(self) -> None:
        """Explicit warm-up button: reload/preload every model in the chain."""
        if self._warming:
            return
        self._warming = True
        self.on_status("warmup:start")
        threading.Thread(target=self._warm_models, name="ts-warmup", daemon=True).start()

    def _warm_models(self) -> None:
        try:
            if self._servers is None and self.config.llm.servers.enabled:
                self._servers = ServerManager.from_config(self.config, self.models)
            if self._servers is not None and self._servers.servers:
                self.on_status("warmup:servers")
                errors = self._servers.start_all(self.on_status)
                for err in errors:
                    log.warning("server: %s", err)
            self._build_pipeline()
            language = self.config.language
            self.on_status(f"asr-warming:{language}")
            self.asr_engine(language).warmup()
            self._asr_ready.add(language)
            self._ready.set()
            self.on_status(f"asr-ready:{language}")
            self.on_status("warmup:tts")
            self.tts.warmup(self.config.mode)
            self.on_status("warmup:done")
        except Exception as exc:  # noqa: BLE001
            log.exception("warmup failed")
            self.on_status(f"warmup:failed:{exc}")
        finally:
            self._warming = False

    def _prepare(self) -> None:
        if self._servers is not None and self._servers.servers:
            errors = self._servers.start_all(self.on_status)
            for err in errors:
                log.warning("server: %s", err)
        self._build_pipeline()
        if self.config.asr.warmup:
            try:
                language = self.config.language
                self.asr_engine(language).warmup()
                self._asr_ready.add(language)
                self.on_status(f"asr-ready:{language}")
            except Exception as exc:  # noqa: BLE001
                log.warning("ASR warmup failed: %s", exc)
        if self.config.tts.warmup:
            try:
                self.tts.warmup(self.config.mode)
            except Exception as exc:  # noqa: BLE001
                log.warning("TTS warmup failed: %s", exc)
        self._ready.set()
        self.on_status("ready")
        self._set_state(State.IDLE, "ready")
        self.monitor.start()

    # -- input level ----------------------------------------------------
    def mic_level(self) -> float:
        return self.monitor.level_db

    def _build_pipeline(self) -> None:
        cfg = self.config.llm
        if cfg.corrector.enabled:
            self._corrector = Corrector(
                ChatClient(cfg.corrector.base_url, cfg.corrector.model,
                           cfg.corrector.api_key, cfg.corrector.timeout_s),
                max_tokens=cfg.corrector.max_tokens,
                max_edit_ratio=self.config.translate.max_edit_ratio)
        else:
            self._corrector = NullCorrector()
        if cfg.translator.enabled and self.config.translate.enabled:
            self._translator = Translator(
                ChatClient(cfg.translator.base_url, cfg.translator.model,
                           cfg.translator.api_key, cfg.translator.timeout_s),
                max_tokens=cfg.translator.max_tokens,
                style=self.config.translate.style)

    # -- GPU handover (training needs the VRAM) ---------------------------
    def pause_models(self) -> None:
        """Unload ASR/TTS before a training run so it gets the whole GPU."""
        log.info("pausing models for training")
        try:
            self.tts.unload()
        except Exception:
            pass
        for engine in self._engines.values():
            try:
                engine.close()
            except Exception:
                pass
        self._engines.clear()
        self._asr_ready.clear()

    def resume_models(self) -> None:
        language = self.config.language
        try:
            self.asr_engine(language).warmup()
            self._asr_ready.add(language)
        except Exception as exc:  # noqa: BLE001
            log.warning("ASR reload after training failed: %s", exc)
        if self.config.tts.warmup:
            try:
                self.tts.warmup(self.config.mode)
            except Exception as exc:  # noqa: BLE001
                log.warning("TTS reload after training failed: %s", exc)

    def shutdown(self) -> None:
        self.cancel()
        try:
            self.tts.unload()
        except Exception:
            pass
        for engine in self._engines.values():
            try:
                engine.close()
            except Exception:
                pass
        self._engines.clear()
        try:
            self.player.close()
        except Exception:
            pass
        if self._servers is not None:
            self._servers.stop_all()

    # -- models ---------------------------------------------------------
    def asr_engine(self, language: str | None = None) -> ASREngine:
        lang = normalize_language(language or self.config.language)
        kind = engine_kind_for_language(self.config, lang)
        key = f"{lang}:{kind}"
        engine = self._engines.get(key)
        if engine is None:
            engine = create_engine(kind, self.config, lang, self.models)
            self._engines[key] = engine
        return engine

    # -- settings -------------------------------------------------------
    def set_input_language(self, language: str) -> None:
        """Switch ASR language (and the UI language) and preload that model."""
        lang = normalize_language(language)
        changed = lang != self.config.language
        self.config.ui.language = lang
        if self.config.translate.target_language in ("", other_language(lang)):
            # keep "auto" pointing at the opposite language
            pass
        self.on_status(f"input-language:{lang}")
        if not changed and lang in self._asr_ready:
            return
        threading.Thread(target=self._warm_asr, args=(lang,),
                         name=f"ts-asr-{lang}", daemon=True).start()

    # kept for older call sites
    set_language = set_input_language

    def set_output_language(self, code: str) -> None:
        code = normalize_language_output(code)
        self.config.translate.target_language = code
        self.on_status(f"output-language:{code or 'auto'}")

    def _warm_asr(self, lang: str) -> None:
        self.on_status(f"asr-warming:{lang}")
        try:
            engine = self.asr_engine(lang)
            started = time.perf_counter()
            engine.warmup()
            self._asr_ready.add(lang)
            log.info("ASR %s warmed in %.1fs", lang, time.perf_counter() - started)
            self.on_status(f"asr-ready:{lang}")
        except Exception as exc:  # noqa: BLE001
            log.exception("warming ASR %s failed", lang)
            self._asr_failed.add(lang)
            self.on_status(f"asr-failed:{lang}:{exc}")

    def set_mode(self, mode: str) -> None:
        if mode not in ("live", "rec"):
            return
        self.config.ui.mode = mode
        self.on_status(f"mode: {mode}")
        if self.config.tts.warmup and self.ready:
            threading.Thread(target=self._warm_tier, args=(mode,),
                             name="ts-warm", daemon=True).start()

    def _warm_tier(self, mode: str) -> None:
        try:
            self.tts.warmup(mode)
            self.on_status(f"tier ready: {mode}")
            self._set_state(State.IDLE, "ready")
        except Exception as exc:  # noqa: BLE001
            log.warning("warming tier %s failed: %s", mode, exc)

    def set_voice(self, voice_id: str) -> None:
        if self.tts.set_voice(voice_id) is not None:
            self.on_status(f"voice: {voice_id}")

    # -- capture --------------------------------------------------------
    def begin(self) -> bool:
        if self._state in (State.WORKING,):
            return False
        if not self.ready:
            self.on_error("模型还在加载")
            return False
        self.player.stop()
        self.monitor.stop()          # the recorder owns the mic now
        try:
            self.recorder.start()
        except Exception as exc:  # noqa: BLE001
            self.on_error(f"麦克风打开失败：{exc}")
            self.monitor.start()
            return False
        self._set_state(State.LISTENING, "listening")
        return True

    def end(self) -> None:
        if not self.recorder.recording:
            return
        samples = self.recorder.stop()
        if samples.size < self.config.audio.sample_rate * 0.25:
            self._set_state(State.IDLE, "too short")
            self.monitor.start()
            return
        self._run_async(samples)

    def abort_listening(self) -> None:
        """Drop the current take without transcribing (gesture was cancelled)."""
        try:
            self.recorder.abort()
        except Exception:
            pass
        if self._state == State.LISTENING:
            self._set_state(State.IDLE, "cancelled")
        self.monitor.start()

    def cancel(self) -> None:
        try:
            self.recorder.abort()
        except Exception:
            pass
        self.player.stop()
        self.tts.stop()
        self.monitor.start()

    # -- processing -----------------------------------------------------
    def _run_async(self, samples) -> None:  # noqa: ANN001
        if self._worker is not None and self._worker.is_alive():
            self.on_error("上一段还在处理中")
            return
        self._worker = threading.Thread(target=self._process, args=(samples,),
                                        name="ts-turn", daemon=True)
        self._worker.start()

    def _process(self, samples) -> None:  # noqa: ANN001
        cfg = self.config
        source = cfg.language
        target = cfg.target_language
        result = TurnResult(source_lang=source, target_lang=target, mode=cfg.mode)
        self._set_state(State.WORKING, "asr")
        started = time.perf_counter()
        try:
            asr_start = time.perf_counter()
            asr = self.asr_engine(source).transcribe(samples, cfg.audio.sample_rate)
            result.asr_ms = (time.perf_counter() - asr_start) * 1000.0
            if asr.error and not asr.text:
                raise RuntimeError(f"ASR: {asr.error}")
            result.raw = asr.text.strip()
            if not result.raw:
                self._set_state(State.IDLE, "no speech")
                return

            self._set_state(State.WORKING, "correct")
            correct_start = time.perf_counter()
            correction = self._corrector.correct(
                result.raw, source, glossary=cfg.translate.glossary)
            result.corrected = correction.text or result.raw
            result.correct_ms = (time.perf_counter() - correct_start) * 1000.0

            self._set_state(State.WORKING, "translate")
            translate_start = time.perf_counter()
            translation = result.corrected
            if target != source and self._translator is not None:
                try:
                    translation = self._translator.translate(
                        result.corrected, target, source,
                        glossary=cfg.translate.glossary)
                except TranslationError as exc:
                    result.error = str(exc)
                    self.on_error(str(exc))
            result.translation = translation
            result.translate_ms = (time.perf_counter() - translate_start) * 1000.0

            if speaks_target(target):
                self._set_state(State.SPEAKING, "speak")
                tts_start = time.perf_counter()
                speech = self.tts.speak(translation, cfg.mode, self.player,
                                        text_lang=target)
                result.tts_ms = (time.perf_counter() - tts_start) * 1000.0
                if speech.error and not result.error:
                    result.error = speech.error
                if speech.path is not None:
                    result.audio_path = str(speech.path)
            else:
                # GPT-SoVITS cannot voice this language yet: keep the text,
                # skip the speech so nobody hears a mispronounced sentence.
                result.spoken = False
                self.on_status(f"text-only:{target}")
                log.info("target %s has no TTS voice; text only", target)

            if cfg.pipeline.inject_text:
                try:
                    from .inject import paste_text

                    paste_text(translation)
                except Exception as exc:  # noqa: BLE001
                    log.warning("inject failed: %s", exc)

            self.history.append(result)
            self._append_history(result)
            self.on_turn(result)
            log.info("turn %.1fs: %s -> %s", (time.perf_counter() - started),
                     result.raw[:30], result.translation[:30])
        except Exception as exc:  # noqa: BLE001
            result.error = f"{type(exc).__name__}: {exc}"
            log.exception("turn failed")
            self.on_error(result.error)
            self._set_state(State.ERROR, str(exc))
            time.sleep(0.2)
        finally:
            self._set_state(State.IDLE, "ready")
            self.monitor.start()

    def _append_history(self, result: TurnResult) -> None:
        base = self.models.results or Path("results")
        try:
            base.mkdir(parents=True, exist_ok=True)
            with (base / "history.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(result.as_record(), ensure_ascii=False) + "\n")
        except OSError as exc:
            log.warning("history write failed: %s", exc)

    def read_history(self, limit: int = 50) -> list[dict[str, Any]]:
        base = self.models.results or Path("results")
        path = base / "history.jsonl"
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        except OSError:
            return []
        return rows


__all__ = ["TongShengService", "State", "TurnResult"]
