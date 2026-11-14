"""System tray UI: LIVE/REC quality switch, zh/en switch, voice picker."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QLabel, QMenu, QPlainTextEdit, QPushButton, QSlider, QSystemTrayIcon, QVBoxLayout,
)

from . import APP_NAME, __version__, i18n
from .config import (AppConfig, LANGUAGES, MODE_LABELS, normalize_language,
                     output_language_label, output_languages, speaks_target)
from .logs import get_logger
from .paths import ModelPaths
from .service import State, TongShengService, TurnResult

log = get_logger("tray")
t = i18n.t

ASSETS = Path(__file__).resolve().parent / "assets"


def make_icon(size: int = 64) -> QIcon:
    """Render the TS-mic mark, with a painted fallback."""
    svg = ASSETS / "TS-mic.svg"
    if svg.exists():
        try:
            from PySide6.QtSvg import QSvgRenderer

            renderer = QSvgRenderer(str(svg))
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            if not pixmap.isNull():
                return QIcon(pixmap)
        except Exception as exc:  # noqa: BLE001
            log.warning("SVG icon failed: %s", exc)
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor("#0A1728"))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(0, 0, size, size, size // 4, size // 4)
    painter.setPen(QPen(QColor("#7AF5FF"), max(2, size // 14)))
    painter.drawLine(size * 0.3, size * 0.3, size * 0.7, size * 0.3)
    painter.drawLine(size * 0.5, size * 0.3, size * 0.5, size * 0.72)
    painter.end()
    return QIcon(pixmap)


class Bridge(QObject):
    state = Signal(str, str)
    turn = Signal(object)
    error = Signal(str)
    status = Signal(str)
    train = Signal(str, str)


class SettingsDialog(QDialog):
    """Only the things that are not already on the main window."""

    HOTKEYS = [
        ("lalt", "左 Alt / Left Alt"),
        ("ralt", "右 Alt / Right Alt"),
        ("alt", "Alt（左右均可）"),
        ("ctrl+alt", "Ctrl + Alt"),
        ("ctrl+shift+space", "Ctrl + Shift + Space"),
        ("ctrl+q", "Ctrl + Q"),
    ]

    def __init__(self, config: AppConfig, voices: list[Any] | None = None, parent=None) -> None:
        super().__init__(parent)
        from .audio.capture import list_input_devices
        from .audio.player import list_output_devices
        from .config import emotions

        self.config = config
        self.setWindowTitle(t("settings.title"))
        self.setMinimumWidth(520)
        from .ui import palette

        self.setStyleSheet(palette.STYLESHEET)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        # -- hotkey ------------------------------------------------------
        self.hotkey = QComboBox()
        for code, label in self.HOTKEYS:
            self.hotkey.addItem(label, code)
        index = self.hotkey.findData(config.ui.hotkey)
        if index < 0:
            self.hotkey.addItem(config.ui.hotkey, config.ui.hotkey)
            index = self.hotkey.count() - 1
        self.hotkey.setCurrentIndex(index)
        form.addRow(t("settings.hotkey"), self.hotkey)

        self.hotkey_mode = QComboBox()
        for code, label in (("smart", t("settings.hotkey.smart")),
                            ("hold", t("settings.hotkey.hold")),
                            ("toggle", t("settings.hotkey.toggle"))):
            self.hotkey_mode.addItem(label, code)
        index = self.hotkey_mode.findData(config.ui.hotkey_mode)
        self.hotkey_mode.setCurrentIndex(max(0, index))
        form.addRow(t("settings.hotkey_mode"), self.hotkey_mode)

        # -- audio routing ----------------------------------------------
        self.input_device = QComboBox()
        self.input_device.addItem(t("settings.default_device"), None)
        for device in list_input_devices():
            self.input_device.addItem(device.name, device.index)
        index = self.input_device.findData(config.audio.input_device)
        self.input_device.setCurrentIndex(max(0, index))
        form.addRow(t("settings.input"), self.input_device)

        self.output_device = QComboBox()
        self.output_device.addItem(t("settings.default_device"), None)
        for device_id, name in list_output_devices():
            self.output_device.addItem(name, device_id)
        index = self.output_device.findData(config.audio.output_device)
        self.output_device.setCurrentIndex(max(0, index))
        form.addRow(t("settings.output"), self.output_device)

        # -- voice rendering --------------------------------------------
        self.emotion = QComboBox()
        for code, label in emotions(config.language):
            self.emotion.addItem(label, code)
        index = self.emotion.findData(config.tts.emotion)
        self.emotion.setCurrentIndex(max(0, index))
        form.addRow(t("settings.emotion"), self.emotion)

        self.live_volume = QSlider(Qt.Horizontal)
        self.live_volume.setRange(0, 150)
        self.live_volume.setValue(int(float(config.tts.live_volume) * 100))
        self.volume_label = QLabel(f"{self.live_volume.value()}%")
        self.live_volume.valueChanged.connect(
            lambda value: self.volume_label.setText(f"{value}%"))
        form.addRow(t("settings.live_volume"), self.live_volume)
        form.addRow("", self.volume_label)

        self.inject = QCheckBox(t("settings.inject"))
        self.inject.setChecked(config.pipeline.inject_text)
        form.addRow(self.inject)

        layout.addLayout(form)
        hint = QLabel(i18n.mode_hint(config.mode))
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#666;")
        layout.addWidget(hint)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText(t("settings.save"))
        buttons.button(QDialogButtonBox.Cancel).setText(t("settings.cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def apply(self) -> None:
        self.config.ui.hotkey = self.hotkey.currentData() or "lalt"
        self.config.ui.hotkey_mode = self.hotkey_mode.currentData() or "smart"
        self.config.audio.input_device = self.input_device.currentData()
        self.config.audio.output_device = self.output_device.currentData()
        self.config.tts.emotion = self.emotion.currentData() or "natural"
        self.config.tts.live_volume = self.live_volume.value() / 100.0
        self.config.pipeline.inject_text = self.inject.isChecked()


class HistoryDialog(QDialog):
    def __init__(self, rows: list[dict[str, Any]], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("menu.history"))
        self.resize(720, 480)
        layout = QVBoxLayout(self)
        box = QPlainTextEdit()
        box.setReadOnly(True)
        lines: list[str] = []
        for row in rows:
            lines.append(f"[{row.get('ts', '')}] {row.get('source_lang')}->{row.get('target_lang')}"
                         f" ({row.get('mode')})")
            lines.append(f"  ASR : {row.get('raw', '')}")
            if row.get("corrected") != row.get("raw"):
                lines.append(f"  纠错: {row.get('corrected', '')}")
            lines.append(f"  译文: {row.get('translation', '')}")
            if row.get("error"):
                lines.append(f"  错误: {row['error']}")
            lines.append("")
        box.setPlainText("\n".join(lines) or "—")
        layout.addWidget(box)
        close = QPushButton("OK")
        close.clicked.connect(self.accept)
        layout.addWidget(close)


class TongShengTray(QObject):
    def __init__(self, app: QApplication, config: AppConfig, models: ModelPaths) -> None:
        super().__init__()
        self.app = app
        self.config = config
        self.models = models
        self.bridge = Bridge()
        self.service = TongShengService(
            config, models,
            on_state=lambda state, msg: self.bridge.state.emit(state.value, msg),
            on_turn=lambda turn: self.bridge.turn.emit(turn),
            on_error=lambda message: self.bridge.error.emit(message),
            on_status=lambda message: self.bridge.status.emit(message),
        )
        self.tray = QSystemTrayIcon(make_icon(), app)
        self.tray.setToolTip(t("tray.tooltip.idle"))
        self.menu = QMenu()
        self.tray.setContextMenu(self.menu)
        self.window = None
        self.app_argv: list[str] = []
        self._restart_guard = False
        self._press_at = 0.0
        self._stop_after_release = False
        self._build_menu()
        self.tray.activated.connect(self._on_tray_activated)

        self.bridge.state.connect(self._on_state)
        self.bridge.turn.connect(self._on_turn)
        self.bridge.error.connect(self._on_error)
        self.bridge.status.connect(self._on_status)
        self.bridge.train.connect(self._on_train)

        i18n.set_language(config.language)
        self._hotkey = None
        self._install_hotkey()
        self.tray.show()

    # -- menu -----------------------------------------------------------
    def _build_menu(self) -> None:
        self.menu.clear()
        self.status_action = QAction(t("menu.status") + f" · {t('state.idle')}", self.menu)
        self.status_action.setEnabled(False)
        self.menu.addAction(self.status_action)
        self.menu.addSeparator()

        self.talk_action = QAction("🎙 " + t("menu.start"), self.menu)
        self.talk_action.triggered.connect(self._toggle_talk)
        self.menu.addAction(self.talk_action)

        self.hotkey_pause_action = QAction(t("menu.hotkey_pause"), self.menu)
        self.hotkey_pause_action.setCheckable(True)
        self.hotkey_pause_action.triggered.connect(self._toggle_hotkey_pause)
        self.menu.addAction(self.hotkey_pause_action)
        self.menu.addSeparator()

        # quality tier switch
        self.mode_menu = QMenu(t("menu.mode"), self.menu)
        self.mode_group = QActionGroup(self.mode_menu)
        self.mode_group.setExclusive(True)
        self.mode_actions: dict[str, QAction] = {}
        for mode in ("live", "rec"):
            label = MODE_LABELS[mode].get(i18n.language(), mode)
            action = QAction(label, self.mode_menu)
            action.setCheckable(True)
            action.setChecked(self.config.mode == mode)
            action.setStatusTip(i18n.mode_hint(mode))
            action.triggered.connect(lambda _checked=False, m=mode: self._set_mode(m))
            self.mode_group.addAction(action)
            self.mode_menu.addAction(action)
            self.mode_actions[mode] = action
        self.menu.addMenu(self.mode_menu)

        # input language (UI + ASR model)
        self.lang_menu = QMenu(t("menu.language"), self.menu)
        self.lang_group = QActionGroup(self.lang_menu)
        self.lang_group.setExclusive(True)
        self.lang_actions: dict[str, QAction] = {}
        for code, label in LANGUAGES.items():
            action = QAction(label, self.lang_menu)
            action.setCheckable(True)
            action.setChecked(self.config.language == code)
            action.triggered.connect(lambda _checked=False, c=code: self._set_input_language(c))
            self.lang_group.addAction(action)
            self.lang_menu.addAction(action)
            self.lang_actions[code] = action
        self.menu.addMenu(self.lang_menu)

        # output language (everything Index-Translate can produce)
        self.output_menu = QMenu(t("menu.output_language"), self.menu)
        self.output_group = QActionGroup(self.output_menu)
        self.output_group.setExclusive(True)
        self.output_actions: dict[str, QAction] = {}
        current_output = self.config.target_language
        for code, label, speaks in output_languages(self.config.language):
            text = label if speaks else f"{label} · {t('menu.text_only')}"
            action = QAction(text, self.output_menu)
            action.setCheckable(True)
            action.setChecked(current_output == code if self.config.translate.target_language
                              else current_output == code)
            action.triggered.connect(lambda _checked=False, c=code: self._set_output_language(c))
            self.output_group.addAction(action)
            self.output_menu.addAction(action)
            self.output_actions[code] = action
        self.menu.addMenu(self.output_menu)

        # voices
        self.voice_menu = QMenu(t("menu.voice"), self.menu)
        self._fill_voices()
        self.menu.addMenu(self.voice_menu)

        self.menu.addSeparator()
        self.warmup_action = QAction(t("menu.warmup"), self.menu)
        self.warmup_action.triggered.connect(self.warmup_models)
        self.menu.addAction(self.warmup_action)

        self.train_action = QAction(t("train.title"), self.menu)
        self.train_action.triggered.connect(self.open_training)
        self.menu.addAction(self.train_action)

        self.open_action = QAction(t("menu.open_window"), self.menu)
        self.open_action.triggered.connect(self.show_window)
        self.menu.addAction(self.open_action)

        self.settings_action = QAction(t("menu.settings"), self.menu)
        self.settings_action.triggered.connect(self._open_settings)
        self.menu.addAction(self.settings_action)

        self.history_action = QAction(t("menu.history"), self.menu)
        self.history_action.triggered.connect(self._open_history)
        self.menu.addAction(self.history_action)

        self.results_action = QAction(t("menu.open_results"), self.menu)
        self.results_action.triggered.connect(self._open_results)
        self.menu.addAction(self.results_action)

        self.menu.addSeparator()
        self.quit_action = QAction(t("menu.quit"), self.menu)
        self.quit_action.triggered.connect(self._quit)
        self.menu.addAction(self.quit_action)

    def _retranslate(self) -> None:
        for mode, action in self.mode_actions.items():
            action.setText(MODE_LABELS[mode].get(i18n.language(), mode))
        self.mode_menu.setTitle(t("menu.mode"))
        self.lang_menu.setTitle(t("menu.language"))
        self.output_menu.setTitle(t("menu.output_language"))
        self.voice_menu.setTitle(t("menu.voice"))
        self.talk_action.setText("🎙 " + t("menu.start"))
        self.status_action.setText(f"{t('menu.status')} · {t('state.idle')}")
        self.train_action.setText(t("train.title"))
        self.warmup_action.setText(t("menu.warmup"))
        self.hotkey_pause_action.setText(t("menu.hotkey_pause"))
        self.open_action.setText(t("menu.open_window"))
        self.settings_action.setText(t("menu.settings"))
        self.history_action.setText(t("menu.history"))
        self.results_action.setText(t("menu.open_results"))
        self.quit_action.setText(t("menu.quit"))
        self._rebuild_output_menu()
        if self.window is not None:
            try:
                self.window.retranslate()
            except Exception:
                pass

    # -- window ---------------------------------------------------------
    def attach_window(self, window) -> None:  # noqa: ANN001
        self.window = window

    def window_icon(self) -> QIcon:
        return make_icon(128)

    def show_window(self) -> None:
        window = self.window
        if window is None:
            return
        window.ensure_on_screen()
        window.show_and_raise()

    def _on_tray_activated(self, reason) -> None:  # noqa: ANN001
        if reason in (QSystemTrayIcon.DoubleClick, QSystemTrayIcon.Trigger):
            self.show_window()

    def _toggle_hotkey_pause(self, paused: bool) -> None:
        if paused:
            if self._hotkey is not None:
                self._hotkey.stop()
                self._hotkey = None
            self._notify(t("app.name"), t("menu.hotkey_pause"))
        else:
            self._install_hotkey()
            self._notify(t("app.name"), t("settings.hotkey"))

    def notify(self, title: str, message: str) -> None:
        self._notify(title, message)

    def _fill_voices(self) -> None:
        self.voice_menu.clear()
        voices = self.service.tts.voices()
        current = self.config.tts.voice
        if not voices:
            empty = QAction(t("notify.no_voice"), self.voice_menu)
            empty.setEnabled(False)
            self.voice_menu.addAction(empty)
            return
        group = QActionGroup(self.voice_menu)
        group.setExclusive(True)
        for voice in voices:
            action = QAction(voice.name, self.voice_menu)
            action.setCheckable(True)
            action.setChecked(voice.id == current)
            action.triggered.connect(lambda _c=False, v=voice.id: self._set_voice(v))
            group.addAction(action)
            self.voice_menu.addAction(action)

    # -- actions --------------------------------------------------------
    def _set_mode(self, mode: str) -> None:
        if mode == self.config.mode:
            return
        self.config.ui.mode = mode
        self.service.set_mode(mode)
        self._save()
        hint = i18n.mode_hint(mode)
        self._notify(f"{t('menu.mode')}: {MODE_LABELS[mode].get(i18n.language(), mode)}", hint)
        log.info("mode -> %s", mode)

    def _set_input_language(self, language: str) -> None:
        language = normalize_language(language)
        self.config.ui.language = language
        self.service.set_input_language(language)
        i18n.set_language(language)
        self.lang_actions[language].setChecked(True)
        # output language list is localised too; rebuild the menu label
        self._rebuild_output_menu()
        self._save()
        self._retranslate()
        self._notify(t("app.name"),
                     t("notify.asr_warming", lang=LANGUAGES.get(language, language)))
        log.info("input language -> %s", language)

    def _set_output_language(self, code: str) -> None:
        self.config.translate.target_language = code
        self.service.set_output_language(code)
        self._save()
        self._update_output_checks()
        label = output_language_label(code, self.config.language)
        if speaks_target(code):
            self._notify(t("menu.output_language"), label)
        else:
            self._notify(t("menu.output_language"),
                         t("notify.text_only", lang=label))
        if self.window is not None:
            self.window.retranslate()
        log.info("output language -> %s", code)

    def _rebuild_output_menu(self) -> None:
        self.output_menu.clear()
        self.output_actions.clear()
        current = self.config.translate.target_language
        for code, label, speaks in output_languages(self.config.language):
            text = label if speaks else f"{label} · {t('menu.text_only')}"
            action = QAction(text, self.output_menu)
            action.setCheckable(True)
            action.setChecked(code == (current or self.config.target_language))
            action.triggered.connect(lambda _c=False, c=code: self._set_output_language(c))
            self.output_group.addAction(action)
            self.output_menu.addAction(action)
            self.output_actions[code] = action

    def _update_output_checks(self) -> None:
        current = self.config.translate.target_language or self.config.target_language
        for code, action in self.output_actions.items():
            action.setChecked(code == current)

    def _set_voice(self, voice_id: str) -> None:
        self.service.set_voice(voice_id)
        self._save()
        profile = self.service.tts.current_voice()
        if profile is not None:
            self._notify(t("menu.voice"), profile.name)

    def _toggle_talk(self) -> None:
        if self.service.state == State.LISTENING:
            self.service.end()
            self.talk_action.setText("🎙 " + t("menu.start"))
        else:
            if self.service.begin():
                self.talk_action.setText("⏹ " + t("menu.stop"))

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.config, self.service.tts.voices())
        if dialog.exec() == QDialog.Accepted:
            dialog.apply()
            self._save()
            # a changed output device needs a fresh audio stream
            try:
                self.service.player.close()
                from .audio import StreamingPlayer

                self.service.player = StreamingPlayer(
                    device=self.config.audio.output_device)
            except Exception as exc:  # noqa: BLE001
                log.warning("reopening output device failed: %s", exc)
            self._install_hotkey()
            self._build_menu()
            self._retranslate()
            if self.window is not None:
                self.window.refresh_sliders()

    def open_training(self) -> None:
        from .ui.training import TrainingDialog

        dialog = TrainingDialog(self)
        dialog.exec()
        self.refresh_voices()
        if self.window is not None:
            self.window.refresh_sliders()

    def refresh_voices(self) -> None:
        self._fill_voices()
        if self.window is not None:
            try:
                self.window._fill_voices()
            except Exception:
                pass

    def warmup_models(self) -> None:
        self.service.warmup()
        if self.window is not None:
            self.window.set_warming(True)

    def _open_history(self) -> None:
        HistoryDialog(self.service.read_history(80)).exec()

    def _open_results(self) -> None:
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl

        folder = (self.models.results or Path("results"))
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _save(self) -> None:
        try:
            self.config.save()
        except Exception as exc:  # noqa: BLE001
            log.warning("cannot save config: %s", exc)

    def _notify(self, title: str, message: str) -> None:
        """Non-activating toast — never steal the caret from the target app."""
        if not message:
            return
        try:
            from .ui.toast import Toast

            Toast.push(title, message)
        except Exception:  # noqa: BLE001
            log.debug("toast failed, falling back to tray balloon", exc_info=True)
            self.tray.showMessage(title, message, QSystemTrayIcon.Information, 4000)

    # -- hotkey ---------------------------------------------------------
    def _install_hotkey(self) -> None:
        try:
            from .hotkey import HotkeyListener

            if self._hotkey is not None:
                self._hotkey.stop()
            self._hotkey = HotkeyListener(
                self.config.ui.hotkey,
                on_press=lambda: self.bridge.status.emit("hotkey-press"),
                on_release=lambda: self.bridge.status.emit("hotkey-release"),
                on_cancel=lambda: self.bridge.status.emit("hotkey-cancel"),
                on_escape=lambda: self.bridge.status.emit("hotkey-escape"),
            )
            self._hotkey.start()
        except Exception as exc:  # noqa: BLE001
            log.warning("hotkey unavailable: %s", exc)
            self._hotkey = None

    # -- service callbacks (GUI thread) ---------------------------------
    def _on_state(self, state: str, message: str) -> None:
        mapping = {
            "idle": t("state.idle"), "listening": t("state.listening"),
            "working": t("state.working") if i18n.has("state.working") else t("state.asr"),
            "speaking": t("state.playing"), "error": t("state.error"),
        }
        label = mapping.get(state, state)
        self.status_action.setText(f"{t('menu.status')} · {label}")
        tips = {
            "listening": t("tray.tooltip.recording"),
            "working": t("tray.tooltip.busy"),
            "speaking": t("tray.tooltip.speaking"),
        }
        self.tray.setToolTip(tips.get(state, t("tray.tooltip.idle")))
        if state != "listening":
            self.talk_action.setText("🎙 " + t("menu.start"))

    def _on_turn(self, turn: TurnResult) -> None:
        # When the text is pasted straight into the focused field, do not pop a
        # toast on top of it — that is what makes the caret jump/steal focus.
        if self.config.pipeline.inject_text:
            return
        if self.config.ui.notify_translation and turn.translation:
            body = turn.translation
            if len(body) > 180:
                body = body[:177] + "…"
            self._notify(t("notify.title"), body)

    def _on_error(self, message: str) -> None:
        self._notify(t("state.error"), message)
        log.warning("service error: %s", message)

    def _on_status(self, message: str) -> None:
        if message == "hotkey-press":
            self._on_hotkey_press()
        elif message == "hotkey-release":
            self._on_hotkey_release()
        elif message == "ready":
            self._notify(t("app.name"), t("state.ready"))
        elif message.startswith("asr-warming:"):
            language = message.split(":", 1)[1]
            self._notify(t("app.name"),
                         t("notify.asr_warming", lang=LANGUAGES.get(language, language)))
        elif message.startswith("asr-ready:"):
            language = message.split(":", 1)[1]
            self._notify(t("app.name"),
                         t("notify.asr_ready", lang=LANGUAGES.get(language, language)))
        elif message.startswith("asr-failed:"):
            self._handle_asr_failure(message)
        elif message.startswith("text-only:"):
            code = message.split(":", 1)[1]
            self._notify(t("app.name"),
                         t("notify.text_only",
                           lang=output_language_label(code, self.config.language)))
        elif message == "warmup:start":
            self._notify(t("app.name"), t("warmup.running"))
        elif message == "warmup:done":
            self._notify(t("app.name"), t("warmup.done"))
            if self.window is not None:
                self.window.set_warming(False)
        elif message.startswith("warmup:failed:"):
            self._notify(t("state.error"), t("warmup.failed", message=message.split(":", 2)[-1]))
            if self.window is not None:
                self.window.set_warming(False)
        elif message == "hotkey-cancel":
            self._cancel_gesture()
        elif message == "hotkey-escape":
            self._escape_cancel()

    # -- hotkey gesture (project B style: tap latches, hold talks) --------
    def _cancel_gesture(self) -> None:
        self._stop_after_release = False
        self.service.abort_listening()
        self.talk_action.setText("🎙 " + t("menu.start"))

    def _escape_cancel(self) -> None:
        """ESC: drop the take / stop the speech, whatever stage we are in."""
        if self.service.state == State.IDLE and not self.service.player.busy:
            return
        log.info("ESC pressed — cancelling")
        self._stop_after_release = False
        self.tray.setToolTip(t("tray.tooltip.idle"))
        self.service.cancel()
        self.talk_action.setText("🎙 " + t("menu.start"))
        self.status_action.setText(f"{t('menu.status')} · {t('state.idle')}")

    def _on_hotkey_press(self) -> None:
        import time as _time

        mode = self.config.ui.hotkey_mode
        if mode == "toggle":
            self._toggle_talk()
            return
        self._press_at = _time.monotonic()
        if self.service.state == State.LISTENING:
            # second tap while latched → stop on release
            self._stop_after_release = True
            return
        self._stop_after_release = False
        if self.service.begin():
            self.talk_action.setText("⏹ " + t("menu.stop"))

    def _on_hotkey_release(self) -> None:
        import time as _time

        mode = self.config.ui.hotkey_mode
        if mode == "toggle":
            return
        if self._stop_after_release:
            self._stop_after_release = False
            self.service.end()
            self.talk_action.setText("🎙 " + t("menu.start"))
            return
        held_ms = (_time.monotonic() - self._press_at) * 1000.0
        threshold = float(self.config.ui.hotkey_threshold_ms or 280)
        if mode == "hold" or held_ms >= threshold:
            self.service.end()
            self.talk_action.setText("🎙 " + t("menu.start"))
        # smart + short tap → keep recording (latched) until the next tap

    def _handle_asr_failure(self, message: str) -> None:
        parts = message.split(":", 2)
        language = parts[1] if len(parts) > 1 else ""
        reason = parts[2] if len(parts) > 2 else ""
        log.error("ASR %s failed: %s", language, reason)
        label = LANGUAGES.get(language, language)
        self._notify(t("app.name"), t("notify.asr_restart", lang=label))
        # Requirement: if the model cannot be warmed up in-process, restart the
        # app so the new language is the only thing it loads at startup.
        if not self._restart_guard:
            self._restart_guard = True
            QTimer.singleShot(1200, self._restart_app)

    def _restart_app(self) -> None:
        import sys

        from PySide6.QtCore import QProcess

        self._save()
        try:
            argv = list(getattr(self, "app_argv", []) or sys.argv)
            started = QProcess.startDetached(sys.executable, argv)
            log.info("restarting application: %s (ok=%s)", argv, started)
        except Exception as exc:  # noqa: BLE001
            log.warning("restart failed: %s", exc)
        finally:
            self._quit()

    def _on_train(self, stage: str, message: str) -> None:
        self._notify(f"{t('train.title')} · {stage}", message)

    # -- shutdown -------------------------------------------------------
    def _quit(self) -> None:
        try:
            if self._hotkey is not None:
                self._hotkey.stop()
        except Exception:
            pass
        if self.window is not None:
            try:
                self.window.hide()
            except Exception:
                pass
        self.tray.hide()
        self.service.shutdown()
        self.app.quit()


__all__ = ["TongShengTray", "SettingsDialog", "HistoryDialog", "make_icon"]
