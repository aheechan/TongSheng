"""Post-install self test: models, GPU, audio devices, synthesis, training.

Run after installing (the setup offers it) or any time:

    runtime\\python.exe tools\\selftest.py

Exit code 0 = everything required works. A report is written to
``<data>\\logs\\selftest.txt`` and printed to the console.
"""

from __future__ import annotations

import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tongsheng import __version__  # noqa: E402
from tongsheng.config import load_config  # noqa: E402
from tongsheng.paths import resolve_llama_binary, user_root  # noqa: E402

rows: list[tuple[str, bool, str]] = []


def check(name: str, fn) -> bool:  # noqa: ANN001
    start = time.perf_counter()
    try:
        detail = fn() or ""
        ok = True
    except Exception as exc:  # noqa: BLE001
        ok = False
        detail = f"{type(exc).__name__}: {exc}"
        if "--verbose" in sys.argv:
            detail += "\n" + traceback.format_exc()
    took = time.perf_counter() - start
    rows.append((name, ok, f"{detail}  [{took:.1f}s]"))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    return ok


def main() -> int:
    print(f"TongSheng {__version__} self test")
    print(f"application : {ROOT}")
    print(f"data folder : {user_root()}")
    print("-" * 72)

    cfg = load_config()
    models = cfg.resolve_models()

    # ---- runtime & hardware ----
    def runtime() -> str:
        import torch

        return (f"python {sys.version.split()[0]} / torch {torch.__version__} / "
                f"{'CUDA ' + torch.version.cuda if torch.cuda.is_available() else 'CPU only'}")

    def gpu() -> str:
        import torch

        if not torch.cuda.is_available():
            raise RuntimeError("no CUDA device (this build needs an NVIDIA GPU)")
        name = torch.cuda.get_device_name(0)
        total = torch.cuda.get_device_properties(0).total_memory / 1024**3
        cap = torch.cuda.get_device_capability(0)
        if total < 5:
            raise RuntimeError(f"only {total:.1f} GB VRAM - 6 GB is the minimum")
        return f"{name}, {total:.1f} GB free {torch.cuda.mem_get_info(0)[0] / 1024**3:.1f}, sm_{cap[0]}{cap[1]}"

    def models_present() -> str:
        missing = models.missing_core()
        for label, path in (("gpt_sovits", models.gpt_sovits),
                            ("pretrained", models.pretrained),
                            ("asr cache", models.asr_cache),
                            ("gguf", models.gguf_dir),
                            ("voices", models.characters)):
            if path is None:
                missing.append(label)
        if missing:
            raise RuntimeError("missing: " + ", ".join(missing))
        needed = [models.pretrained / "gsv-v4-pretrained" / "s2Gv4.pth",
                  models.pretrained / "chinese-hubert-base",
                  models.pretrained / "chinese-roberta-wwm-ext-large"]
        for path in needed:
            if not path.exists():
                raise RuntimeError(f"missing weight: {path}")
        return "GPT-SoVITS + v4 weights + ASR + GGUF + voices"

    def llama() -> str:
        binary = resolve_llama_binary(cfg.llm.servers.binary)
        if not binary:
            raise RuntimeError("llama-server not found")
        return binary

    def audio() -> str:
        import sounddevice as sd

        inputs = [d["name"] for d in sd.query_devices() if d["max_input_channels"] > 0]
        outputs = [d["name"] for d in sd.query_devices() if d["max_output_channels"] > 0]
        if not inputs:
            raise RuntimeError("no microphone")
        if not outputs:
            raise RuntimeError("no playback device")
        return f"{len(inputs)} input / {len(outputs)} output endpoints"

    def english_frontend() -> str:
        import os

        data = os.environ.get("NLTK_DATA", "")
        if not data or not Path(data).is_dir():
            raise RuntimeError("NLTK data not found (English synthesis will fail)")
        import nltk

        nltk.data.find("corpora/cmudict")
        return f"cmudict ok ({data})"

    def asr() -> str:
        from tongsheng.asr import create_engine, engine_kind_for_language
        import numpy as np

        kind = engine_kind_for_language(cfg, cfg.language)
        engine = create_engine(kind, cfg, cfg.language, models)
        engine.load()
        active = getattr(engine, "active", engine)
        result = engine.transcribe(np.zeros(16000, dtype=np.float32), 16000)
        if result.error:
            raise RuntimeError(result.error)
        device = str(getattr(active, "device", getattr(engine, "device", "?")))
        if kind == "funasr" and not device.startswith("cuda"):
            raise RuntimeError(
                f"FunASR fell back to {device}; the GPU path must work (see logs)")
        name = getattr(active, "name", kind)
        return f"{name} loaded on {device}"

    def synthesis() -> str:
        from tongsheng.tts import TTSRuntime

        runtime_tts = TTSRuntime(cfg, models)
        if cfg.tts.voice:
            runtime_tts.set_voice(cfg.tts.voice)
        out = user_root() / "logs" / "selftest_voice.wav"
        path = runtime_tts.synthesize_file("Hello, this is the TongSheng self test.",
                                           "rec", out, text_lang="en")
        size = Path(path).stat().st_size / 1024
        if size < 20:
            raise RuntimeError(f"output too small ({size:.0f} KB)")
        return f"{path.name}, {size:.0f} KB"

    def voices() -> str:
        from tongsheng.tts.voices import VoiceStore

        store = VoiceStore(models.characters)
        found = store.list()
        if not found:
            raise RuntimeError("no voices installed - reinstall or import one")
        names = ", ".join(v.name for v in found[:6])
        has_default = any(v.id.lower().startswith("default") for v in found)
        return f"{len(found)} voice(s): {names}" + ("" if has_default else " (Default_Voice missing)")

    def training() -> str:
        from tongsheng.tts.trainer import CloneTrainer

        trainer = CloneTrainer(cfg, models)
        ok, reason = trainer.available()
        if not ok:
            raise RuntimeError(reason)
        return "project A training backend ready"

    ok = True
    ok &= check("Python / torch runtime", runtime)
    ok &= check("NVIDIA GPU + VRAM", gpu)
    ok &= check("Model folders and v4 weights", models_present)
    ok &= check("llama-server binary", llama)
    ok &= check("Audio endpoints", audio)
    ok &= check("English front-end (NLTK)", english_frontend)
    ok &= check("ASR engine loads", asr)
    ok &= check("Voice synthesis", synthesis)
    ok &= check("Voice library", voices)
    ok &= check("Voice training backend", training)

    report = [f"TongSheng {__version__} self test",
              f"app: {ROOT}", f"data: {user_root()}", ""]
    report += [f"[{'PASS' if flag else 'FAIL'}] {name}: {detail}"
               for name, flag, detail in rows]
    report.append("")
    report.append("RESULT: " + ("OK" if ok else "PROBLEMS FOUND"))

    log_dir = user_root() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    report_path = log_dir / "selftest.txt"
    report_path.write_text("\n".join(report), encoding="utf-8")

    print("-" * 72)
    print("RESULT:", "OK" if ok else "PROBLEMS FOUND")
    print("report:", report_path)
    if not ok:
        print("\nCopy the FAIL lines above when reporting a problem.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
