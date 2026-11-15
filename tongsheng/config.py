"""Configuration model for TongSheng.

The config is a single YAML file (``config.yaml`` next to the project or in
``%APPDATA%\\TongSheng``). Every section has defaults that work on the
development machine, so a missing file simply means "use the defaults".
"""

from __future__ import annotations

import copy
import os
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any, get_type_hints

import yaml

from . import paths as path_mod

# --------------------------------------------------------------------------- #
# constants
# --------------------------------------------------------------------------- #
LANGUAGES: dict[str, str] = {"zh": "中文", "en": "English"}
LANGUAGE_NAMES_EN: dict[str, str] = {"zh": "Chinese", "en": "English"}

# Everything Index-Translate can output. The last column says whether the
# cloned voice can actually speak it (GPT-SoVITS front-ends: zh/en/ja/ko/yue).
OUTPUT_LANGUAGES: list[tuple[str, str, str, bool]] = [
    ("zh", "中文", "Chinese", True),
    ("en", "English", "English", True),
    ("ja", "日本語", "Japanese", True),
    ("ko", "한국어", "Korean", True),
    ("es", "Español", "Spanish", False),
    ("fr", "Français", "French", False),
    ("de", "Deutsch", "German", False),
    ("ru", "Русский", "Russian", False),
    ("pt", "Português", "Portuguese", False),
    ("it", "Italiano", "Italian", False),
    ("ar", "العربية", "Arabic", False),
    ("vi", "Tiếng Việt", "Vietnamese", False),
    ("th", "ไทย", "Thai", False),
    ("id", "Bahasa Indonesia", "Indonesian", False),
    ("tr", "Türkçe", "Turkish", False),
]
OUTPUT_LANGUAGE_CODES: list[str] = [code for code, _n, _e, _s in OUTPUT_LANGUAGES]
TTS_LANGUAGES: set[str] = {"zh", "en", "ja", "ko", "yue"}


def output_languages(ui_language: str = "zh") -> list[tuple[str, str, bool]]:
    """(code, label, speaks) list for the UI, native names included."""
    ui_language = normalize_language(ui_language)
    out: list[tuple[str, str, bool]] = []
    for code, native, english, speaks in OUTPUT_LANGUAGES:
        if native == english:
            label = native
        elif ui_language == "zh":
            label = f"{native} ({english})"
        else:
            label = f"{english} ({native})"
        out.append((code, label, speaks))
    return out


def output_language_label(code: str, ui_language: str = "zh") -> str:
    for item_code, label, _speaks in output_languages(ui_language):
        if item_code == code:
            return label
    return code


def output_language_prompt_name(code: str) -> str:
    """Name handed to the translation prompt (never a bare code)."""
    for item_code, native, english, _speaks in OUTPUT_LANGUAGES:
        if item_code == code:
            return english if native == english else f"{english} ({native})"
    return code


def speaks_target(code: str) -> bool:
    return normalize_language_output(code) in TTS_LANGUAGES


def normalize_language_output(code: str | None) -> str:
    """Accept any of the 15 output languages; empty means "auto"."""
    raw = (code or "").strip().lower()
    if not raw:
        return ""
    aliases = {"cn": "zh", "zh-cn": "zh", "chinese": "zh", "中文": "zh",
               "english": "en", "英文": "en", "英语": "en",
               "japanese": "ja", "日语": "ja", "日本語": "ja",
               "korean": "ko", "韩语": "ko", "한국어": "ko",
               "spanish": "es", "español": "es", "french": "fr", "français": "fr",
               "german": "de", "deutsch": "de", "russian": "ru", "русский": "ru",
               "portuguese": "pt", "italian": "it", "arabic": "ar",
               "vietnamese": "vi", "thai": "th", "indonesian": "id", "turkish": "tr"}
    raw = aliases.get(raw, raw)
    return raw if raw in OUTPUT_LANGUAGE_CODES else ""

MODES: tuple[str, str] = ("live", "rec")
MODE_LABELS: dict[str, dict[str, str]] = {
    "live": {"zh": "同声传译（LIVE）", "en": "Live interpreting (LIVE)"},
    "rec": {"zh": "录音模式（REC）", "en": "Recording mode (REC)"},
}
MODE_HINTS: dict[str, dict[str, str]] = {
    "live": {"zh": "低延迟 · v4 十二步 · 分块渲染", "en": "Low latency · v4, 12 steps · chunked"},
    "rec": {"zh": "高保真 · v4 十二步 · 48 kHz", "en": "High fidelity · v4, 12 steps · 48 kHz"},
}

TIER_SAMPLE_RATES: dict[str, int] = {"live": 48000, "rec": 48000}


def normalize_language(code: str | None) -> str:
    raw = (code or "").strip().lower()
    aliases = {"cn": "zh", "zh-cn": "zh", "chinese": "zh", "中文": "zh",
               "en-us": "en", "en-gb": "en", "english": "en", "英文": "en", "英语": "en"}
    raw = aliases.get(raw, raw)
    return raw if raw in LANGUAGES else "zh"


def other_language(code: str) -> str:
    return "en" if normalize_language(code) == "zh" else "zh"


# --------------------------------------------------------------------------- #
# sections
# --------------------------------------------------------------------------- #
@dataclass
class PathsConfig:
    gpt_sovits: str = "auto"
    characters: str = ""          # empty -> <project>/voices
    asr_cache: str = "auto"
    gguf: str = "auto"
    private_voice: str = "auto"
    alt_voice: str = "auto"


@dataclass
class AudioConfig:
    input_device: str | None = None
    output_device: str | None = None
    sample_rate: int = 16000
    channels: int = 1
    max_seconds: float = 40.0
    trim_silence: bool = True
    silence_threshold: float = 0.012
    normalize: bool = True


@dataclass
class ASRConfig:
    zh_engine: str = "funasr"       # funasr | fake
    en_engine: str = "whisper"      # whisper | funasr | fake
    device: str = "cuda"
    allow_cpu_fallback: bool = False   # never silently drop to CPU ASR
    gpu_fallback: str = "whisper"      # funasr -> whisper on the same GPU; "" disables
    whisper_size: str = "small"
    whisper_dir: str = "auto"
    funasr_model: str = "paraformer-zh"
    beam_size: int = 5
    warmup: bool = True


@dataclass
class TierConfig:
    """One audio-quality tier of the cloned voice."""

    version: str = "v3"             # v3 -> 32 kHz, v4 -> 48 kHz
    sample_rate: int = 32000
    streaming: bool = True
    fragment_interval: float = 0.32
    split_method: str = "cut5"
    sample_steps: int = 4
    batch_size: int = 1

    def describe(self) -> str:
        return f"{self.version} · {self.sample_rate // 1000} kHz"


@dataclass
class TTSConfig:
    device: str = "cuda"
    speed: float = 1.0
    temperature: float = 0.6
    top_k: int = 5
    top_p: float = 1.0
    repetition_penalty: float = 1.9
    max_chars_per_sentence: int = 40
    min_chars_per_sentence: int = 6
    sentence_gap_ms: int = 80          # breathing room between spoken sentences
    fade_in_ms: float = 12.0           # project A's edge fades: avoid clicks
    fade_out_ms: float = 25.0
    max_sec_per_char: float = 0.55     # runaway-sentence guard (project A)
    retry_bad_sentence: bool = True    # retry quiet / over-long renders
    live_first_chunk_chars: int = 24   # first chunk stays short: earliest audio
    live_chunk_chars: int = 96         # later chunks are long: richer prosody context,
                                       # fewer engine calls (less fixed overhead)
    keep_both_tiers_loaded: bool = False
    warmup: bool = True             # preload the selected tier at startup
    voice: str = ""                 # selected voice profile id
    emotion: str = "natural"        # default prosody preset
    live_volume: float = 1.0        # 0.0 - 1.5, LIVE tier only
    live_fragments: bool = False    # True = stream fragments (lower latency,
                                    # risk of stitched syllables); False = whole
                                    # sentence first, smooth playback
    tiers: dict[str, TierConfig] = field(default_factory=lambda: {
        "live": TierConfig(version="v4", sample_rate=48000, streaming=True,
                           fragment_interval=0.32, split_method="cut5",
                           sample_steps=12, batch_size=4),
        "rec": TierConfig(version="v4", sample_rate=48000, streaming=False,
                          fragment_interval=0.0, split_method="cut5", sample_steps=12),
    })

    def tier(self, mode: str) -> TierConfig:
        return self.tiers.get(mode) or self.tiers["live"]


# Prosody presets. GPT-SoVITS has no true emotion conditioning, so each preset
# shifts temperature / top_k / speed in a direction that audibly changes delivery.
EMOTIONS: list[tuple[str, str, str, float, int, float]] = [
    # key, zh, en, temperature, top_k, speed multiplier
    ("natural", "自然", "Natural", 0.60, 5, 1.00),
    ("gentle", "温柔", "Gentle", 0.50, 4, 0.96),
    ("lively", "活泼", "Lively", 0.80, 9, 1.06),
    ("calm", "平静", "Calm", 0.45, 4, 0.94),
    ("serious", "严肃", "Serious", 0.40, 3, 0.98),
]
EMOTION_KEYS = [item[0] for item in EMOTIONS]


def emotion_preset(key: str) -> tuple[float, int, float]:
    for item in EMOTIONS:
        if item[0] == key:
            return item[3], item[4], item[5]
    return EMOTIONS[0][3], EMOTIONS[0][4], EMOTIONS[0][5]


def emotions(ui_language: str = "zh") -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for key, zh, en, _t, _k, _s in EMOTIONS:
        out.append((key, zh if normalize_language(ui_language) == "zh" else en))
    return out


@dataclass
class LLMEndpoint:
    enabled: bool = True
    base_url: str = "http://127.0.0.1:8093/v1"
    model: str = "qwen3-1.7b-instruct"
    api_key: str = "EMPTY"
    model_path: str = "auto"
    autostart: bool = True
    timeout_s: float = 30.0
    max_tokens: int = 512


@dataclass
class ServersConfig:
    enabled: bool = True
    binary: str = "llama-server"
    host: str = "127.0.0.1"
    context_size: int = 4096
    gpu_layers: int = 99
    startup_timeout_s: float = 90.0


@dataclass
class LLMConfig:
    corrector: LLMEndpoint = field(default_factory=lambda: LLMEndpoint(
        base_url="http://127.0.0.1:8093/v1", model="qwen3-1.7b-instruct", max_tokens=512))
    translator: LLMEndpoint = field(default_factory=lambda: LLMEndpoint(
        base_url="http://127.0.0.1:8094/v1", model="Index-Translate-9B", max_tokens=384))
    servers: ServersConfig = field(default_factory=ServersConfig)


@dataclass
class TranslateConfig:
    enabled: bool = True
    style: str = "daily"
    correct: bool = True
    max_edit_ratio: float = 0.35
    glossary: dict[str, str] = field(default_factory=dict)
    target_language: str = ""       # "" = auto (the opposite of the input language)


@dataclass
class UIConfig:
    language: str = "zh"            # zh | en: INPUT language (ASR) and UI language
    mode: str = "rec"               # legacy: the synthesis pipeline is now single-tier
    record_output: bool = False     # save every synthesised wav to results/rec
    hotkey: str = "lalt"            # lalt | ralt | alt | ctrl+alt | ctrl+shift+space …
    hotkey_mode: str = "smart"      # smart (tap latch / hold talk) | hold | toggle
    hotkey_threshold_ms: int = 280  # below this a tap is a toggle, above it a PTT
    start_minimized: bool = False   # False = show the control window on launch
    notify_translation: bool = True


@dataclass
class PipelineConfig:
    inject_text: bool = False       # also paste the translation into the focused app
    sentence_gap_ms: int = 60
    max_sentences: int = 40


@dataclass
class AppConfig:
    paths: PathsConfig = field(default_factory=PathsConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    asr: ASRConfig = field(default_factory=ASRConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    translate: TranslateConfig = field(default_factory=TranslateConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)

    # -- derived -----------------------------------------------------------
    @property
    def language(self) -> str:
        return normalize_language(self.ui.language)

    @property
    def target_language(self) -> str:
        """Output language: explicit choice, or the opposite of the input."""
        chosen = normalize_language_output(self.translate.target_language)
        return chosen or other_language(self.language)

    @property
    def mode(self) -> str:
        # 1.1.0: LIVE and REC share one synthesis pipeline (the former REC
        # parameters). Only the "save the audio" switch remains user-visible.
        return "rec"

    def tier(self, mode: str | None = None) -> TierConfig:
        return self.tts.tier(mode or self.mode)

    # -- io ----------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "AppConfig":
        cfg = cls()
        if not data:
            return cfg
        for key, value in data.items():
            if not hasattr(cfg, key):
                continue
            current = getattr(cfg, key)
            if is_dataclass(current) and isinstance(value, dict):
                setattr(cfg, key, _merge_dataclass(type(current), current, value))
            else:
                setattr(cfg, key, value)
        cfg.normalize()
        return cfg

    def normalize(self) -> None:
        self.ui.language = normalize_language(self.ui.language)
        self.ui.mode = "rec"
        if self.ui.hotkey_mode not in ("smart", "hold", "toggle"):
            self.ui.hotkey_mode = "smart"
        if self.tts.emotion not in EMOTION_KEYS:
            self.tts.emotion = "natural"
        self.tts.live_volume = max(0.0, min(1.5, float(self.tts.live_volume or 1.0)))
        # our own ports: 8091/8092 belong to ALT-VoiceType on this machine
        for endpoint, old_port, new_port in (
                (self.llm.corrector, 8091, 8093), (self.llm.translator, 8092, 8094)):
            url = endpoint.base_url
            if f"127.0.0.1:{old_port}/" in url:
                endpoint.base_url = url.replace(f"127.0.0.1:{old_port}/",
                                                f"127.0.0.1:{new_port}/")
        # empty target means "auto = the other language"
        self.translate.target_language = normalize_language_output(self.translate.target_language)
        # 1.0.6: the LIVE tier used to fall back to a v3 base model because the
        # trained voices only ship v4 LoRA — that made the low tier sound like a
        # different person. Both tiers now speak with the *trained* v4 voice.
        live_tier = self.tts.tiers.get("live")
        if isinstance(live_tier, TierConfig):
            if live_tier.version == "v3":
                live_tier.version = "v4"
            if live_tier.sample_rate == 24000:
                live_tier.sample_rate = 48000

        # tiers may arrive as plain dicts from YAML
        normalized: dict[str, TierConfig] = {}
        for name in MODES:
            raw = self.tts.tiers.get(name)
            if isinstance(raw, TierConfig):
                tier = raw
            elif isinstance(raw, dict):
                allowed = {f.name for f in fields(TierConfig)}
                tier = TierConfig(**{k: v for k, v in raw.items() if k in allowed})
            else:
                tier = TierConfig()
            expected = TIER_SAMPLE_RATES.get(name)
            if expected:
                tier.sample_rate = expected
            normalized[name] = tier
        self.tts.tiers = normalized

    def save(self, path: str | Path | None = None) -> Path:
        target = Path(path) if path else default_config_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = self.to_dict()
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
                       encoding="utf-8")
        tmp.replace(target)
        return target

    @classmethod
    def load(cls, path: str | Path | None = None) -> "AppConfig":
        target = Path(path) if path else default_config_path()
        if not target.exists():
            example = ROOT_EXAMPLE_CONFIG
            if example.exists():
                try:
                    data = yaml.safe_load(example.read_text(encoding="utf-8")) or {}
                    cfg = cls.from_dict(data)
                    cfg.normalize()
                    return cfg
                except Exception:
                    pass
            return cls()
        try:
            data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
        except Exception as exc:  # corrupt file: never block startup
            raise ValueError(f"config file is not valid YAML: {target}: {exc}") from exc
        cfg = cls.from_dict(data if isinstance(data, dict) else {})
        cfg.normalize()
        return cfg

    # -- resolved model locations -------------------------------------------
    def resolve_models(self) -> path_mod.ModelPaths:
        found = path_mod.discover(self.paths.private_voice, self.paths.alt_voice)
        if self.paths.gpt_sovits and self.paths.gpt_sovits != "auto":
            found.gpt_sovits = Path(self.paths.gpt_sovits)
            pretrained = found.gpt_sovits / "GPT_SoVITS" / "pretrained_models"
            found.pretrained = pretrained if pretrained.is_dir() else None
        if self.paths.characters:
            found.characters = Path(self.paths.characters)
        elif found.characters is None:
            found.characters = path_mod.ROOT / "voice-repository"
        if self.paths.asr_cache and self.paths.asr_cache != "auto":
            cache = Path(self.paths.asr_cache)
            found.asr_cache = cache if cache.is_dir() else None
            whisper = cache / "whisper"
            found.whisper_dir = whisper if whisper.is_dir() else None
        if self.asr.whisper_dir and self.asr.whisper_dir != "auto":
            found.whisper_dir = Path(self.asr.whisper_dir)
        if self.paths.gguf and self.paths.gguf != "auto":
            gguf = Path(self.paths.gguf)
            found.gguf_dir = gguf if gguf.is_dir() else None
        return found

    def endpoint_model_path(self, endpoint: LLMEndpoint, models: path_mod.ModelPaths) -> str:
        if endpoint.model_path and endpoint.model_path != "auto":
            return endpoint.model_path
        return path_mod.find_gguf(endpoint.model, models.gguf_dir)


def _merge_dataclass(cls: type, current: Any, data: dict[str, Any]) -> Any:
    hints = get_type_hints(cls)
    for key, value in data.items():
        if not hasattr(current, key):
            continue
        hint = hints.get(key)
        if is_dataclass(hint) and isinstance(value, dict):
            setattr(current, key, _merge_dataclass(hint, getattr(current, key), value))
        else:
            setattr(current, key, value)
    return current


ROOT_EXAMPLE_CONFIG = path_mod.ROOT / "config.example.yaml"


def default_config_path() -> Path:
    override = os.environ.get("TONGSHENG_CONFIG")
    if override:
        return Path(override)
    # portable first: keep the config next to the project so a copy of the
    # folder carries its settings; fall back to %LOCALAPPDATA% when the
    # installation directory is read-only (Program Files)
    if path_mod._writable(path_mod.ROOT):
        return path_mod.ROOT / "config.yaml"
    return path_mod.user_root() / "config.yaml"


def load_config(path: str | Path | None = None) -> AppConfig:
    return AppConfig.load(path)


def default_config_dict() -> dict[str, Any]:
    return copy.deepcopy(AppConfig().to_dict())


__all__ = [
    "LANGUAGES", "MODES", "MODE_LABELS", "MODE_HINTS", "TIER_SAMPLE_RATES",
    "OUTPUT_LANGUAGES", "OUTPUT_LANGUAGE_CODES", "TTS_LANGUAGES",
    "output_languages", "output_language_label", "speaks_target",
    "normalize_language_output",
    "AppConfig", "UIConfig", "TTSConfig", "TierConfig", "ASRConfig",
    "AudioConfig", "LLMConfig", "LLMEndpoint", "ServersConfig",
    "TranslateConfig", "PipelineConfig", "PathsConfig",
    "load_config", "default_config_path", "normalize_language", "other_language",
]
