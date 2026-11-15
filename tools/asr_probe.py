"""Diagnose the speech recognition backend on this machine.

Run it when Chinese ASR does not start:

    runtime\python.exe tools\asr_probe.py

It prints the GPU/runtime facts, tries FunASR on every CUDA variant with the
*full* traceback, then tries the GPU fallback engine (faster-whisper).
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tongsheng.config import load_config  # noqa: E402
from tongsheng.paths import user_root  # noqa: E402


def banner(text: str) -> None:
    print("\n" + "=" * 72)
    print(text)
    print("=" * 72)


def main() -> int:
    cfg = load_config()
    models = cfg.resolve_models()

    banner("runtime")
    import torch

    print("torch          :", torch.__version__, "| CUDA", torch.version.cuda)
    print("cuda available :", torch.cuda.is_available())
    if torch.cuda.is_available():
        props = torch.cuda.get_device_properties(0)
        print("gpu            :", props.name)
        print("capability     :", torch.cuda.get_device_capability(0))
        print("vram           : %.1f GB" % (props.total_memory / 1024**3))
    print("funasr cache   :", models.funasr_dir)
    print("whisper dir    :", models.whisper_dir)
    print("data folder    :", user_root())

    banner("FunASR on CUDA")
    from tongsheng.asr.funasr_zh import FunASREngine

    engine = FunASREngine(
        model=cfg.asr.funasr_model,
        device=cfg.asr.device,
        model_cache=models.funasr_dir,
        allow_cpu_fallback=False,
    )
    try:
        engine.load()
        print("OK - loaded on", engine.device)
        funasr_ok = True
    except Exception as exc:  # noqa: BLE001
        funasr_ok = False
        print(f"FAILED: {type(exc).__name__}: {exc}")
        traceback.print_exc()

    banner("faster-whisper on CUDA (fallback)")
    from tongsheng.asr.whisper_en import WhisperEngine

    whisper = WhisperEngine(size=cfg.asr.whisper_size, device=cfg.asr.device,
                            model_dir=models.whisper_dir, language="zh")
    try:
        whisper.load()
        print("OK - loaded on", getattr(whisper, "device", "?"))
        whisper_ok = True
    except Exception as exc:  # noqa: BLE001
        whisper_ok = False
        print(f"FAILED: {type(exc).__name__}: {exc}")
        traceback.print_exc()

    banner("verdict")
    if funasr_ok:
        print("Chinese ASR: FunASR (preferred)")
        return 0
    if whisper_ok:
        print("Chinese ASR: whisper GPU fallback will be used automatically")
        print("Send the FunASR traceback above to get the native path fixed.")
        return 0
    print("No GPU ASR engine works. Check the NVIDIA driver (CUDA 12.8 / 570.x+).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
