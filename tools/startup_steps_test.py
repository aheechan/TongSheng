"""Step-by-step probe of app.run()'s startup under pythonw.exe."""
import os
import sys
import traceback

OUT = r"C:\Users\liang\Documents\deepseek-harness\default-workspace\startup_steps.txt"


def w(msg: str) -> None:
    with open(OUT, "a", encoding="utf-8") as fh:
        fh.write(msg + "\n")
        fh.flush()
        os.fsync(fh.fileno())


w("stdout=%r stderr=%r" % (sys.stdout, sys.stderr))

import tongsheng  # noqa: E402

w("1 import tongsheng ok; stdout=%r" % (sys.stdout,))

try:
    from tongsheng.config import load_config

    cfg = load_config()
    w(f"2 load_config ok: lang={cfg.language} mode={cfg.mode} hotkey={cfg.ui.hotkey}")

    models = cfg.resolve_models()
    w(f"3 resolve_models ok: logs={models.logs}")
    w(f"   funasr_dir={models.funasr_dir}")
    w(f"   gpt_sovits={models.gpt_sovits} missing={models.missing_core()}")

    from tongsheng.logs import setup_logging

    lg = setup_logging(models.logs)
    w("4 setup_logging ok")
    lg.info("PROBE: logging works from pythonw")
    w("5 log line written")

    from tongsheng.vram import detect

    gpu = detect()
    w(f"6 vram ok: {gpu.describe()}")
except BaseException:
    w("FAILED:\n" + traceback.format_exc())

w("DONE")
os._exit(0)
