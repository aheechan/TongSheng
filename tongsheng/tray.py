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
from .config import AppConfig, LANGUAGES, MODE_LABELS, normalize_language
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
    def __init__(self, config: AppConfig, voices: list[Any], parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self.setWindowTitle(t("settings.title"))
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.language = QComboBox()
        for code, label in LANGUAGES.items():
            self.language.addItem(label, code)
        index = self.language.findData(config.language)
        self.language.setCurrentIndex(max(0, index))
        form.addRow(t("settings.language"), self.language)

        self.voice = QComboBox()
        self.voice.addItem(t("voice.none"), "")
        for voice in voices:
            self.voice.addItem(voice.name, voice.id)
        index = self.voice.findData(config.tts.voice)
        self.voice.setCurrentIndex(max(0, index))
        form.addRow(t("settings.voice"), self.voice)

        self.speed = QSlider(Qt.Horizontal)
        self.speed.setRange(70, 130)
        self.speed.setValue(int(config.tts.speed * 100))
        self.speed_label = QLabel(f"{config.tts.speed:.2f}x")
        self.speed.valueChanged.connect(
            lambda value: self.speed_label.setText(f"{value / 100:.2f}x"))
        form.addRow(t("settings.speed"), self.speed)
        form.addRow("", self.speed_label)

        self.inject = QCheckBox(t("settings.inject"))
        self.inject.setChecked(config.pipeline.inject_text)
        form.addRow(self.inject)

        layout.addLayout(form)
        hint = QLabel(i18n.mode_hint(config.mode))
        hint.setStyleSheet("color:#666;")
        layout.addWidget(hint)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def apply(self) -> None:
        self.config.ui.language = normalize_language(self.language.currentData())
        self.config.tts.voice = self.voice.currentData() or ""
        self.config.tts.speed = self.speed.value() / 100.0
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
        self._build_menu()

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

        # language switch (UI + ASR model)
        self.lang_menu = QMenu(t("menu.language"), self.menu)
        self.lang_group = QActionGroup(self.lang_menu)
        self.lang_group.setExclusive(True)
        self.lang_actions: dict[str, QAction] = {}
        for code, label in LANGUAGES.items():
            action = QAction(label, self.lang_menu)
            action.setCheckable(True)
            action.setChecked(self.config.language == code)
            action.triggered.connect(lambda _checked=False, c=code: self._set_language(c))
            self.lang_group.addAction(action)
            self.lang_menu.addAction(action)
            self.lang_actions[code] = action
        self.menu.addMenu(self.lang_menu)

        # voices
        self.voice_menu = QMenu(t("menu.voice"), self.menu)
        self._fill_voices()
        self.menu.addMenu(self.voice_menu)

        self.menu.addSeparator()
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
        self.voice_menu.setTitle(t("menu.voice"))
        self.talk_action.setText("🎙 " + t("menu.start"))
        self.status_action.setText(f"{t('menu.status')} · {t('state.idle')}")
        self.settings_action.setText(t("menu.settings"))
        self.history_action.setText(t("menu.history"))
        self.results_action.setText(t("menu.open_results"))
        self.quit_action.setText(t("menu.quit"))

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

    def _set_language(self, language: str) -> None:
        language = normalize_language(language)
        self.config.ui.language = language
        self.service.set_language(language)
        i18n.set_language(language)
        self._save()
        self._retranslate()
        self._notify(t("app.name"), t("app.desc"))
        log.info("language -> %s", language)

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
            self.service.set_language(self.config.language)
            i18n.set_language(self.config.language)
            self.service.set_voice(self.config.tts.voice)
            self._save()
            self._build_menu()
            self._install_hotkey()

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
        if message:
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
            if self.config.ui.hotkey_mode == "hold":
                if self.service.begin():
                    self.talk_action.setText("⏹ " + t("menu.stop"))
            else:
                self._toggle_talk()
        elif message == "hotkey-release":
            if self.config.ui.hotkey_mode == "hold":
                self.service.end()
        elif message == "ready":
            self._notify(t("app.name"), t("state.ready"))

    def _on_train(self, stage: str, message: str) -> None:
        self._notify(f"{t('train.title')} · {stage}", message)

    # -- shutdown -------------------------------------------------------
    def _quit(self) -> None:
        try:
            if self._hotkey is not None:
                self._hotkey.stop()
        except Exception:
            pass
        self.tray.hide()
        self.service.shutdown()
        self.app.quit()


__all__ = ["TongShengTray", "SettingsDialog", "HistoryDialog", "make_icon"]
