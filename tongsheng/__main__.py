"""Command line entry point: ``python -m tongsheng``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tongsheng", description="同声 TongSheng — 实时语音翻译 / real-time voice translation")
    parser.add_argument("--config", help="path to config.yaml", default=None)
    parser.add_argument("--version", action="store_true", help="print version")

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("run", help="start the tray application (default)")
    sub.add_parser("doctor", help="print environment / model diagnostics")

    voices = sub.add_parser("voices", help="list, import or inspect voices")
    voices.add_argument("action", nargs="?", default="list",
                        choices=["list", "import", "path"])
    voices.add_argument("--from", dest="source", default="", help="PrivateVoice character folder")
    voices.add_argument("--name", default="", help="display name for the imported voice")

    train = sub.add_parser("train", help="clone a voice from one recording")
    train.add_argument("--audio", required=True, help="wav / mp3 / m4a / flac")
    train.add_argument("--name", required=True, help="voice name")
    train.add_argument("--epochs", type=int, default=0)
    train.add_argument("--profile", default="conservative",
                       choices=["conservative", "balanced", "aggressive"])

    say = sub.add_parser("say", help="synthesize text with the selected voice")
    say.add_argument("--text", required=True)
    say.add_argument("--mode", default="", choices=["", "live", "rec"])
    say.add_argument("--out", default="", help="write a wav here instead of playing")

    translate = sub.add_parser("translate", help="text-only ASR->correct->translate check")
    translate.add_argument("--text", required=True)
    translate.add_argument("--to", default="")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    from . import __version__

    if args.version:
        print(f"TongSheng {__version__}")
        return 0

    from .config import load_config

    config = load_config(args.config) if args.config else load_config()

    command = args.command or "run"
    if command == "run":
        from .app import run

        return run()
    if command == "doctor":
        from .app import doctor

        return doctor(config)
    if command == "voices":
        return _voices(config, args)
    if command == "train":
        return _train(config, args)
    if command == "say":
        return _say(config, args)
    if command == "translate":
        return _translate(config, args)
    print(f"unknown command: {command}")
    return 2


def _voices(config, args) -> int:  # noqa: ANN001
    from .paths import ModelPaths
    from .tts.voices import VoiceStore

    models = config.resolve_models()
    store = VoiceStore(models.characters or Path("voices"))
    if args.action == "import":
        if not args.source:
            print("--from <PrivateVoice character folder> is required")
            return 2
        profile = store.import_private_voice(args.source, args.name or None)
        config.tts.voice = profile.id
        config.save()
        print(f"imported: {profile.name} -> {profile.dir}")
        return 0
    if args.action == "path":
        print(store.root)
        return 0
    voices = store.list()
    if not voices:
        print("no voices yet — import one with `tongsheng voices import --from <dir>`")
        return 0
    for voice in voices:
        missing = voice.missing_files()
        state = "ready" if not missing else f"missing: {', '.join(missing)}"
        print(f"{voice.id:32s} {voice.name:16s} {voice.mode:10s} {state}")
    return 0


def _train(config, args) -> int:  # noqa: ANN001
    from .app import doctor  # noqa: F401  (ensures imports work)
    from .asr import create_engine, engine_kind_for_language
    from .logs import setup_logging
    from .tts.trainer import CloneTrainer, TrainProgress

    models = config.resolve_models()
    setup_logging(models.logs)

    def on_event(event: TrainProgress) -> None:
        prefix = f"[{event.stage}]"
        if event.total_epochs:
            prefix += f" {event.epoch}/{event.total_epochs}"
        print(f"{prefix} {event.message}", flush=True)

    def asr_factory():
        kind = engine_kind_for_language(config, "zh")
        return create_engine(kind, config, "zh", models)

    trainer = CloneTrainer(config, models, asr_factory=asr_factory, on_event=on_event)
    ok, reason = trainer.available()
    if not ok:
        print(f"training unavailable: {reason}")
        return 1
    profile = trainer.train(args.name, args.audio,
                            epochs=args.epochs or None, profile=args.profile)
    config.tts.voice = profile.id
    config.save()
    print(f"voice ready: {profile.name} ({profile.dir})")
    return 0


def _say(config, args) -> int:  # noqa: ANN001
    from .audio import StreamingPlayer, wav
    from .logs import setup_logging
    from .tts import TTSRuntime

    models = config.resolve_models()
    setup_logging(models.logs)
    runtime = TTSRuntime(config, models, on_status=lambda m: print(f"· {m}"))
    if config.tts.voice:
        runtime.set_voice(config.tts.voice)
    mode = args.mode or config.mode
    if args.out:
        path = runtime.synthesize_file(args.text, mode, args.out)
        print(f"wrote {path}")
        return 0
    player = StreamingPlayer(device=config.audio.output_device)
    result = runtime.speak(args.text, mode, player, text_lang=config.target_language)
    player.close()
    if result.error:
        print(f"error: {result.error}")
        return 1
    print(f"{result.seconds:.1f}s @ {result.sample_rate} Hz")
    if result.path:
        print(f"saved {result.path}")
    return 0


def _translate(config, args) -> int:  # noqa: ANN001
    from .correct import Corrector
    from .llm import ChatClient
    from .logs import setup_logging
    from .translate import Translator

    models = config.resolve_models()
    setup_logging(models.logs)
    source = config.language
    target = args.to or config.target_language
    corrector = Corrector(
        ChatClient(config.llm.corrector.base_url, config.llm.corrector.model,
                   config.llm.corrector.api_key, config.llm.corrector.timeout_s))
    translator = Translator(
        ChatClient(config.llm.translator.base_url, config.llm.translator.model,
                   config.llm.translator.api_key, config.llm.translator.timeout_s),
        style=config.translate.style)
    correction = corrector.correct(args.text, source)
    print(f"raw      : {args.text}")
    print(f"corrected: {correction.text}")
    print(f"translated: {translator.translate(correction.text, target, source)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
