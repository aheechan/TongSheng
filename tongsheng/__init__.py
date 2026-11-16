"""TongSheng (同声) — real-time voice translation in your own voice."""

import os
import sys

__version__ = "1.1.11"
APP_NAME = "TongSheng"
APP_NAME_ZH = "同声"
APP_ID = "TongSheng.Tray.App"

_NULL_STREAM = None


def _repair_std_streams() -> None:
    """pythonw.exe starts us with ``sys.stdout``/``sys.stderr`` set to None.

    FunASR and tqdm write progress bars to stderr, so the very first
    ``AutoModel.generate()`` dies with
    ``AttributeError: 'NoneType' object has no attribute 'write'``. The model
    still reports as loaded, the error is swallowed by the ASR wrapper, and the
    tray says "recogniser ready" — while nothing ever gets transcribed and
    app.log stays clean. Give those streams a real sink before any model code
    (or ``logging``, which also binds stderr at setup time) touches them.
    """
    global _NULL_STREAM
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        _NULL_STREAM = open(os.devnull, "w", encoding="utf-8", errors="replace")
    except OSError:
        return
    if sys.stdout is None:
        sys.stdout = _NULL_STREAM
    if sys.stderr is None:
        sys.stderr = _NULL_STREAM


_repair_std_streams()

__all__ = ["__version__", "APP_NAME", "APP_NAME_ZH", "APP_ID"]
