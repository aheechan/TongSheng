"""Main control window.

The tray icon is the primary switchboard, but a tray-only app is easy to lose
on Windows 11 (new icons start in the hidden overflow). This window makes the
app visible and gives the same controls a bigger surface.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QSlider, QTextEdit, QVBoxLayout, QWidget,
)

from .. import APP_NAME, __version__, i18n
from ..config import (LANGUAGES, MODE_LABELS, output_language_label,
                      output_languages, speaks_target)
from ..service import State, TurnResult
from . import palette
from .meter import LevelMeter

t = i18n.t


class ToggleRow(QWidget):
    """A tiny segmented control: N checkable buttons, one active."""

    def __init__(self, options: list[tuple[str, str]], on_change, parent=None) -> None:
        super().__init__(parent)
        self._buttons: dict[str, QPushButton] = {}
        self._on_change = on_change
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        for key, label in options:
            button = QPushButton(label)
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.setProperty("seg", True)
            button.clicked.connect(lambda _c=False, k=key: self._select(k))
            layout.addWidget(button)
            self._buttons[key] = button

    def _select(self, key: str) -> None:
        for name, button in self._buttons.items():
            button.setChecked(name == key)
        self._on_change(key)

    def set_current(self, key: str) -> None:
        for name, button in self._buttons.items():
            button.setChecked(name == key)

    def retranslate(self, options: list[tuple[str, str]]) -> None:
        for key, label in options:
            if key in self._buttons:
                self._buttons[key].setText(label)


class MainWindow(QWidget):
    def __init__(self, tray: Any) -> None:
        super().__init__()
        self.tray = tray
        self.service = tray.service
        self.config = tray.config
        self.setWindowTitle(f"{t('app.name')} · TongSheng {__version__}")
        self.setWindowIcon(tray.window_icon())
        self.setMinimumWidth(560)
        self.setStyleSheet(palette.STYLESHEET)
        self._build()
        self._connect()
        self.retranslate()

    # -- layout ---------------------------------------------------------
    def _build(self) -> None:
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        left = QWidget()
        root = QVBoxLayout(left)
        root.setContentsMargins(22, 20, 12, 18)
        root.setSpacing(14)
        outer.addWidget(left, 1)

        self.meter = LevelMeter(self.service.mic_level)
        self.meter.setToolTip(t("meter.tooltip"))
        meter_box = QVBoxLayout()
        meter_box.setContentsMargins(0, 18, 12, 18)
        meter_box.addWidget(self.meter, 1)
        outer.addLayout(meter_box)

        header = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(self.tray.window_icon().pixmap(48, 48))
        header.addWidget(logo)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        self.title = QLabel()
        self.title.setObjectName("title")
        self.subtitle = QLabel()
        self.subtitle.setObjectName("subtitle")
        titles.addWidget(self.title)
        titles.addWidget(self.subtitle)
        header.addLayout(titles, 1)
        self.train_button = QPushButton()
        self.train_button.setObjectName("ghost")
        self.train_button.clicked.connect(self.tray.open_training)
        header.addWidget(self.train_button)
        self.state_label = QLabel()
        self.state_label.setObjectName("state")
        self.state_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header.addWidget(self.state_label)
        root.addLayout(header)

        root.addWidget(_divider())

        # recording switch (single synthesis pipeline)
        row, _ = self._setting_row("quality")
        self.record_box = QCheckBox(t("menu.record"))
        self.record_box.setChecked(self.config.ui.record_output)
        self.record_box.toggled.connect(self._on_record)
        row.addWidget(self.record_box, 1)
        root.addLayout(row)

        # input language (ASR + UI)
        row, _ = self._setting_row("language")
        self.lang_row = ToggleRow(
            [(code, label) for code, label in LANGUAGES.items()], self._on_input_language)
        row.addWidget(self.lang_row, 1)
        root.addLayout(row)

        # output language (everything Index-Translate can produce)
        row, _ = self._setting_row("output")
        self.output_box = QComboBox()
        self.output_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.output_box.currentIndexChanged.connect(self._on_output_language)
        row.addWidget(self.output_box, 1)
        root.addLayout(row)

        # voice
        row, _ = self._setting_row("voice")
        self.voice_box = QComboBox()
        self.voice_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.voice_box.currentIndexChanged.connect(self._on_voice)
        row.addWidget(self.voice_box, 1)
        root.addLayout(row)

        # speed (quick access, persists on release)
        row, _ = self._setting_row("speed")
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(70, 130)
        self.speed_slider.setValue(int(round(self.config.tts.speed * 100)))
        self.speed_slider.valueChanged.connect(self._on_speed)
        self.speed_slider.sliderReleased.connect(self.tray._save)
        self.speed_value = QLabel(f"{self.config.tts.speed:.2f}x")
        self.speed_value.setMinimumWidth(46)
        self.speed_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(self.speed_slider, 1)
        row.addWidget(self.speed_value)
        root.addLayout(row)

        self.hint = QLabel()
        self.hint.setObjectName("hint")
        root.addWidget(self.hint)

        root.addWidget(_divider())

        # transcript
        self.transcript = QTextEdit()
        self.transcript.setReadOnly(True)
        self.transcript.setMinimumHeight(150)
        self.transcript.setObjectName("transcript")
        root.addWidget(self.transcript, 1)

        # warm-up sits right above the talk button
        self.warmup_button = QPushButton()
        self.warmup_button.setObjectName("ghost")
        self.warmup_button.setMinimumHeight(32)
        self.warmup_button.clicked.connect(self.tray.warmup_models)
        root.addWidget(self.warmup_button)

        # actions
        actions = QHBoxLayout()
        self.talk_button = QPushButton()
        self.talk_button.setObjectName("primary")
        self.talk_button.setMinimumHeight(42)
        self.talk_button.clicked.connect(self._toggle_talk)
        actions.addWidget(self.talk_button, 2)

        self.settings_button = QPushButton()
        self.settings_button.clicked.connect(self.tray._open_settings)
        actions.addWidget(self.settings_button)
        self.history_button = QPushButton()
        self.history_button.clicked.connect(self.tray._open_history)
        actions.addWidget(self.history_button)
        self.results_button = QPushButton()
        self.results_button.clicked.connect(self.tray._open_results)
        actions.addWidget(self.results_button)
        root.addLayout(actions)

        self._fill_voices()
        self._fill_output_languages()

    def _setting_row(self, key: str) -> tuple[QHBoxLayout, Any]:
        row = QHBoxLayout()
        row.setSpacing(12)
        label = QLabel()
        label.setObjectName("rowlabel")
        label.setMinimumWidth(72)
        setattr(self, f"{key}_label", label)
        row.addWidget(label)
        return row, label

    # -- wiring ---------------------------------------------------------
    def _connect(self) -> None:
        bridge = self.tray.bridge
        bridge.state.connect(self._on_state)
        bridge.turn.connect(self._on_turn)
        bridge.error.connect(self._on_error)
        bridge.status.connect(self._on_status)

    def _fill_voices(self) -> None:
        self.voice_box.blockSignals(True)
        self.voice_box.clear()
        voices = self.service.tts.voices()
        if not voices:
            self.voice_box.addItem(t("notify.no_voice"), "")
        for voice in voices:
            self.voice_box.addItem(voice.name, voice.id)
        index = self.voice_box.findData(self.config.tts.voice)
        if index >= 0:
            self.voice_box.setCurrentIndex(index)
        self.voice_box.blockSignals(False)

    def _fill_output_languages(self) -> None:
        self.output_box.blockSignals(True)
        self.output_box.clear()
        current = self.config.target_language
        for code, label, speaks in output_languages(self.config.language):
            text = label if speaks else f"{label} · {t('menu.text_only')}"
            self.output_box.addItem(text, code)
        index = self.output_box.findData(current)
        if index >= 0:
            self.output_box.setCurrentIndex(index)
        self.output_box.blockSignals(False)

    # -- user actions ---------------------------------------------------
    def _on_record(self, enabled: bool) -> None:
        self.config.ui.record_output = enabled
        self.tray._save()
        self.tray.set_record_output(enabled)
        self._update_hint()

    def _on_input_language(self, language: str) -> None:
        self.tray._set_input_language(language)
        self.lang_row.set_current(self.config.language)
        self._fill_output_languages()
        self.retranslate()

    def _on_output_language(self, _index: int) -> None:
        code = self.output_box.currentData()
        if not code:
            return
        self.tray._set_output_language(code)
        self._update_hint()

    def _on_voice(self, _index: int) -> None:
        voice_id = self.voice_box.currentData()
        if voice_id:
            self.tray._set_voice(voice_id)

    def _on_speed(self, value: int) -> None:
        self.config.tts.speed = value / 100.0
        self.speed_value.setText(f"{value / 100:.2f}x")

    def refresh_sliders(self) -> None:
        """Re-sync widgets after settings/training changed the config."""
        self.speed_slider.blockSignals(True)
        self.speed_slider.setValue(int(round(self.config.tts.speed * 100)))
        self.speed_slider.blockSignals(False)
        self.speed_value.setText(f"{self.config.tts.speed:.2f}x")
        self._fill_voices()

    def _toggle_talk(self) -> None:
        if self.service.state == State.LISTENING:
            self.service.end()
        else:
            self.service.begin()

    def set_warming(self, warming: bool) -> None:
        self.warmup_button.setEnabled(not warming)
        self.warmup_button.setText(t("warmup.running") if warming else t("menu.warmup"))

    # -- service signals ------------------------------------------------
    def _on_state(self, state: str, _message: str) -> None:
        if hasattr(self, "meter"):
            self.meter.set_recording(state == "listening")
        mapping = {
            "idle": t("state.idle"), "listening": t("state.listening"),
            "working": t("state.asr"), "speaking": t("state.playing"),
            "error": t("state.error"),
        }
        self.state_label.setText(mapping.get(state, state))
        self.state_label.setProperty("busy", state in ("working", "listening", "speaking"))
        self.state_label.style().unpolish(self.state_label)
        self.state_label.style().polish(self.state_label)
        if state == "listening":
            self.talk_button.setText("⏹  " + t("menu.stop"))
        else:
            self.talk_button.setText("🎙  " + t("menu.start"))

    def _on_turn(self, turn: TurnResult) -> None:
        lines = [self.transcript.toPlainText()] if self.transcript.toPlainText() else []
        block = [f"{turn.source_lang.upper()}  {turn.raw}"]
        if turn.corrected and turn.corrected != turn.raw:
            block.append(f"    ✎ {turn.corrected}")
        block.append(f"{turn.target_lang.upper()}  {turn.translation}")
        if turn.error:
            block.append(f"    ! {turn.error}")
        lines.append("\n".join(block))
        self.transcript.setPlainText("\n\n".join(lines[-8:]))
        self.transcript.verticalScrollBar().setValue(
            self.transcript.verticalScrollBar().maximum())

    def _on_error(self, message: str) -> None:
        self.hint.setText(t("error.generic", message=message))

    def _on_status(self, message: str) -> None:
        if message == "ready":
            self._update_hint()
        elif message.startswith("asr-warming:"):
            language = message.split(":", 1)[1]
            self.hint.setText(t("notify.asr_warming", lang=language))
        elif message.startswith("asr-ready:"):
            self._update_hint()
        elif message == "warmup:start":
            self.set_warming(True)
            self.hint.setText(t("warmup.running"))
        elif message == "warmup:done":
            self.set_warming(False)
            self._update_hint()
        elif message.startswith("warmup:failed:"):
            self.set_warming(False)
            self.hint.setText(t("warmup.failed", message=message.split(":", 2)[-1]))

    # -- i18n -----------------------------------------------------------
    def _update_hint(self) -> None:
        hint = t("notify.record_on") if self.config.ui.record_output else t("notify.record_off")
        target = self.config.target_language
        if not speaks_target(target):
            label = output_language_label(target, i18n.language())
            hint = f"{hint}  ·  " + t("notify.text_only", lang=label)
        self.hint.setText(hint)

    def retranslate(self) -> None:
        self.title.setText("同声 · TongSheng" if i18n.language() == "zh" else "TongSheng")
        self.subtitle.setText(t("app.desc"))
        self.state_label.setText(t("state.idle"))
        for attr, key in (("quality_label", "menu.mode"),
                          ("language_label", "settings.input_language"),
                          ("output_label", "settings.output_language"),
                          ("voice_label", "menu.voice"),
                          ("speed_label", "settings.speed")):
            label = getattr(self, attr, None)
            if label is not None:
                label.setText(t(key))
        self.record_box.setText(t("menu.record"))
        self.record_box.setChecked(self.config.ui.record_output)
        self.lang_row.set_current(self.config.language)
        self._fill_output_languages()
        self.talk_button.setText("🎙  " + t("menu.start"))
        self.warmup_button.setText(t("menu.warmup"))
        self.train_button.setText(t("train.title"))
        self.settings_button.setText(t("menu.settings").replace("…", ""))
        self.history_button.setText(t("menu.history").replace("…", ""))
        self.results_button.setText(t("menu.open_results"))
        if not self.transcript.toPlainText():
            self.transcript.setPlaceholderText(t("window.transcript_empty"))
        self._update_hint()
        self.setWindowTitle(f"{t('app.name')} · TongSheng {__version__}")

    # -- window behaviour -----------------------------------------------
    def closeEvent(self, event) -> None:  # noqa: N802
        event.ignore()
        self.hide()
        if self.config.ui.notify_translation:
            self.tray.notify(t("window.still_running_title"), t("window.still_running"))

    def show_and_raise(self) -> None:
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        self.raise_()
        self.activateWindow()

    def center_on_primary(self) -> None:
        """Keep the window on the main display, never on a detached monitor."""
        from PySide6.QtGui import QGuiApplication

        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        width = min(max(self.width(), 560), max(480, area.width() - 80))
        height = min(max(self.height(), 520), max(420, area.height() - 120))
        self.resize(width, height)
        self.move(area.center().x() - width // 2, area.center().y() - height // 2)

    def ensure_on_screen(self) -> None:
        from PySide6.QtGui import QGuiApplication

        frame = self.frameGeometry()
        for screen in QGuiApplication.screens():
            if screen.availableGeometry().intersects(frame):
                return
        self.center_on_primary()


def _divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setObjectName("divider")
    return line


__all__ = ["MainWindow", "ToggleRow"]
