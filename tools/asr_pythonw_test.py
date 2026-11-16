"""Does FunASR load/infer under pythonw.exe (sys.stdout/stderr = None)?

Run with pythonw.exe and NO redirected handles; the report is written to a file.
"""
from __future__ import annotations

import os
import sys
import time
import traceback

ROOT = r"D:\TongSheng"
OUT = r"C:\Users\liang\Documents\deepseek-harness\default-workspace\pythonw_report.txt"
sys.path.insert(0, ROOT)

lines: list[str] = []


def w(msg: str) -> None:
    lines.append(str(msg))
    try:
        with open(OUT, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    except OSError:
        pass


w("executable : " + sys.executable)
w("sys.stdout : " + repr(sys.stdout))
w("sys.stderr : " + repr(sys.stderr))
w("sys.__stderr__: " + repr(sys.__stderr__))

os.environ.setdefault("FUNASR_DISABLE_UPDATE", "1")

import numpy as np  # noqa: E402

w("=== import FunASREngine ===")
try:
    from tongsheng.asr.funasr_zh import FunASREngine
    w("import ok")
except BaseException:
    w("import FAILED\n" + traceback.format_exc())
    sys.exit(1)

eng = FunASREngine(model="paraformer-zh", device="cuda",
                   model_cache=os.path.join(ROOT, "models", "asr", "modelscope"),
                   allow_cpu_fallback=False)

w("=== load() ===")
t0 = time.time()
try:
    eng.load()
    w(f"load OK in {time.time() - t0:.1f}s on {eng.device}")
except BaseException:
    w("load FAILED\n" + traceback.format_exc())

w("=== transcribe() (2 s of silence, like base.warmup) ===")
t0 = time.time()
try:
    res = eng.transcribe(np.zeros(16000 * 2, dtype=np.float32), 16000)
    w(f"transcribe returned in {time.time() - t0:.1f}s")
    w(f"  error = {res.error!r}")
    w(f"  text  = {res.text[:40]!r}")
except BaseException:
    w("transcribe RAISED\n" + traceback.format_exc())

w("DONE")
os._exit(0)
