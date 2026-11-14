"""Bootstrap: single instance check, Qt application, tray."""

from __future__ import annotations

import sys
from pathlib import Path

from . import APP_ID, APP_NAME
from .config import AppConfig, load_config
from .logs import get_logger, setup_logging
from .paths import ModelPaths

log = get_logger("app")


def _single_instance_guard() -> tuple[bool, object]:
    """Return (is_primary, holder). The holder must stay alive."""
    try:
        from PySide6.QtNetwork import QLocalServer, QLocalSocket
    except Exception:
        return True, None
    socket = QLocalSocket()
    socket.connectToServer(APP_ID)
    if socket.waitForConnected(200):
        socket.write(b"ping")
        socket.flush()
        socket.disconnectFromServer()
        return False, None
    from PySide6.QtNetwork import QLocalServer as Server

    Server.removeServer(APP_ID)
    server = Server()
    if not server.listen(APP_ID):
        log.warning("cannot create single-instance server: %s", server.errorString())
    return True, server


def _set_app_user_model_id() -> None:
    """Tell Windows this is TongSheng, not "Python" (tray label, taskbar grouping)."""
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass


def run() -> int:
    _set_app_user_model_id()
    config = load_config()
    models = config.resolve_models()
    setup_logging(models.logs)

    from PySide6.QtWidgets import QApplication

    from . import i18n
    from .tray import TongShengTray, make_icon

    i18n.set_language(config.language)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName("同声 TongSheng")
    app.setOrganizationName("TongSheng")
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(make_icon())

    primary, holder = _single_instance_guard()
    if not primary:
        log.info("another instance is running; exiting")
        return 0

    tray = TongShengTray(app, config, models)

    from .ui.main_window import MainWindow

    window = MainWindow(tray)
    tray.attach_window(window)
    window.center_on_primary()
    if not config.ui.start_minimized:
        window.show()
    else:
        tray.notify("同声 TongSheng", "已在托盘运行，双击图标打开窗口")

    tray.service.start()
    _holder = holder  # keep the QLocalServer alive
    log.info("TongSheng started (mode=%s lang=%s)", config.mode, config.language)
    return app.exec()


def doctor(config: AppConfig | None = None) -> int:
    """Print a human readable environment report (no Qt)."""
    from .asr import available_engines
    from .config import MODE_LABELS
    from .paths import resolve_llama_binary

    cfg = config or load_config()
    models = cfg.resolve_models()
    print("== TongSheng doctor ==")
    print(f"gpt_sovits  : {models.gpt_sovits}")
    print(f"pretrained  : {models.pretrained}")
    print(f"voices      : {models.characters}")
    print(f"asr cache   : {models.asr_cache}")
    print(f"whisper     : {models.whisper_dir}")
    print(f"funasr      : {models.funasr_dir}")
    print(f"gguf        : {models.gguf_dir}")
    print(f"llama-server: {resolve_llama_binary(cfg.llm.servers.binary) or '(not found)'}")
    print(f"mode        : {cfg.mode} ({MODE_LABELS[cfg.mode].get(cfg.language, '')})")
    print(f"language    : {cfg.language} -> target {cfg.target_language}")
    print(f"engines     : {available_engines()}")
    try:
        import torch

        if torch.cuda.is_available():
            print(f"gpu         : {torch.cuda.get_device_name(0)} "
                  f"({torch.cuda.get_device_properties(0).total_memory / 2**30:.1f} GB)")
        else:
            print("gpu         : CPU only")
    except Exception as exc:  # noqa: BLE001
        print(f"gpu         : unavailable ({exc})")

    from .tts.voices import VoiceStore

    store = VoiceStore(models.characters or Path("voices"))
    voices = store.list()
    print(f"voices      : {len(voices)}")
    for voice in voices:
        state = "ready" if not voice.missing_files() else f"missing {voice.missing_files()}"
        print(f"  - {voice.name} [{voice.id}] {voice.mode} {state}")
    return 0


__all__ = ["run", "doctor"]
