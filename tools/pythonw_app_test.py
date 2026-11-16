"""Run tools/dev_run.py under pythonw and record how it exits."""
import os
import runpy
import sys
import threading
import time
import traceback

OUT = r"C:\Users\liang\Documents\deepseek-harness\default-workspace\pythonw_app_report.txt"


def w(msg: str) -> None:
    with open(OUT, "a", encoding="utf-8") as fh:
        fh.write(msg + "\n")


w("=== start " + time.strftime("%H:%M:%S") + " ===")
w(f"stdout={sys.stdout!r} stderr={sys.stderr!r}")

import tongsheng  # noqa: E402

w(f"after import tongsheng: stdout={sys.stdout!r} stderr={sys.stderr!r}")


def watchdog() -> None:
    time.sleep(45)
    w("APP STILL RUNNING after 45 s -> startup OK")
    os._exit(0)


threading.Thread(target=watchdog, daemon=True).start()

try:
    runpy.run_path(r"D:\TongSheng\tools\dev_run.py", run_name="__main__")
except SystemExit as exc:
    w(f"SystemExit: {exc.code!r}")
except BaseException:
    w("EXCEPTION:\n" + traceback.format_exc())

w("=== end ===")
os._exit(0)
