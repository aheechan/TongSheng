"""Reproduce TongSheng's exact ASR threading pattern.

App does:  thread "ts-prepare" -> engine.warmup()  (which loads FunASR + runs one generate)
           thread "ts-turn"    -> engine.transcribe()  (generate again, other thread)

If FunASR's CUDA context is bound to the loading thread, the second call deadlocks.
"""
from __future__ import annotations

import os
import sys
import threading
import time

ROOT = r"D:\TongSheng"
sys.path.insert(0, ROOT)
os.environ.setdefault("FUNASR_DISABLE_UPDATE", "1")

import numpy as np  # noqa: E402

from tongsheng.asr.funasr_zh import FunASREngine  # noqa: E402

MODELSCOPE = os.path.join(ROOT, "models", "asr", "modelscope")

eng = FunASREngine(model="paraformer-zh", device="cuda",
                   model_cache=MODELSCOPE, allow_cpu_fallback=False)

box: dict = {}


def prepare_thread() -> None:  # mimics service._prepare
    t0 = time.time()
    try:
        eng.warmup()  # base ASREngine.warmup -> transcribe -> load() + generate()
        box["prep"] = ("ok", round(time.time() - t0, 1))
    except BaseException as exc:  # noqa: BLE001
        box["prep"] = ("error", repr(exc))


print("== step 1: warmup on a background thread (like ts-prepare) ==", flush=True)
th = threading.Thread(target=prepare_thread, name="ts-prepare", daemon=True)
th.start()
th.join(240)
print("   prepare done:", box.get("prep", "TIMEOUT"), "| alive =", th.is_alive(), flush=True)
print("   model loaded:", eng._model is not None, flush=True)


def turn_thread() -> None:  # mimics service._process -> transcribe
    t0 = time.time()
    try:
        res = eng.transcribe(np.zeros(16000 * 2, dtype=np.float32), 16000)
        box["turn"] = (round(time.time() - t0, 1), res.engine, res.error,
                       (res.text or "")[:40])
    except BaseException as exc:  # noqa: BLE001
        box["turn"] = ("exception", repr(exc))


print("== step 2: first real utterance on ANOTHER thread (like ts-turn) ==", flush=True)
tu = threading.Thread(target=turn_thread, name="ts-turn", daemon=True)
tu.start()
tu.join(120)
print("   turn finished:", not tu.is_alive(), flush=True)
print("   result:", box.get("turn", "HUNG / no result after 120s"), flush=True)

print("== step 3: control - same thread as load? re-issue on main thread ==", flush=True)
try:
    res = eng.transcribe(np.zeros(16000 * 2, dtype=np.float32), 16000)
    print("   ok:", round(res.latency_ms, 1), "ms |", repr((res.text or "")[:40]),
          "| error:", res.error, flush=True)
except BaseException as exc:  # noqa: BLE001
    print("   raised:", repr(exc), flush=True)

print("DONE", flush=True)
os._exit(0)
