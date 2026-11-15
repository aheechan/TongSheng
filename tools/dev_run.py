"""Launcher: ``python tools/dev_run.py [command]``.

Works with the bundled runtime (isolated ``._pth``), which does not add the
project folder to ``sys.path`` automatically. Any failure is written to
``logs/crash.log`` and shown in a dialog, because the desktop shortcut runs
``pythonw.exe`` and has no console.
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _report(exc: BaseException) -> None:
    log_dir = ROOT / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "crash.log"
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write("\n===== launcher failure =====\n")
            handle.write("".join(traceback.format_exception(exc)))
    except OSError:
        log_file = ROOT / "crash.log"

    message = (
        "TongSheng could not start.\n\n"
        f"{type(exc).__name__}: {exc}\n\n"
        f"Details: {log_file}\n\n"
        "Run  run.bat doctor  for an environment report."
    )
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, "TongSheng - startup failed", 0x10)
    except Exception:  # noqa: BLE001
        print(message, file=sys.stderr)


def main() -> int:
    from tongsheng.__main__ import main as app_main

    return app_main(sys.argv[1:])


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001
        _report(exc)
        raise SystemExit(3) from None
