"""Voice model training window: library management + new voice wizard.

Layout mirrors project A's character pages (library list on one tab, guided
"record → check → train" flow on the other) and follows TongSheng's palette.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QTabWidget,
    QVBoxLayout, QWidget,
)

from .. import i18n
from ..audio import Recorder, wav
from ..logs import get_logger
from ..tts.trainer import CloneTrainer, TrainProgress

log = get_logger("ui.training")
t = i18n.t


class TrainWorker(QThread):
    progress = Signal(str, str, int, int)
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, service, name: str, source: str) -> None:
        super().__init__()
        self.service = service
        self.name = name
        self.source = source
        self.trainer: CloneTrainer | None = None

    def run(self) -> None:  # noqa: D102
        service = self.service
        try:
            budget = getattr(service, "budget", None)
            if budget is not None and not budget.training_allowed:
                self.failed.emit(
                    "本机显存不足（%.0f GB）：音色训练需要 12 GB 以上。\n"
                    "可在 12 GB+ 的机器上训练，然后把 voice-repository/<音色> 整个目录"
                    "拷到本机即可使用。" % budget.total_gb)
                return
            service.pause_models()
            trainer = CloneTrainer(
                service.config, service.models,
                asr_factory=lambda: service.labeling_asr(),
                on_event=lambda event: self.progress.emit(
                    event.stage, event.message, event.epoch, event.total_epochs),
            )
            self.trainer = trainer
            profile = trainer.train(self.name, self.source, profile="conservative")
            self.finished_ok.emit(profile)
        except Exception as exc:  # noqa: BLE001
            log.exception("training failed")
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        finally:
            try:
                service.resume_models()
            except Exception:
                pass

    def cancel(self) -> None:
        if self.trainer is not None:
            self.trainer.cancel()


class VoiceRow(QFrame):
    use = Signal(str)
    make_default = Signal(str)
    delete = Signal(str)
    open_folder = Signal(str)

    def __init__(self, voice, is_default: bool, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("voiceRow")
        self.voice = voice
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 12, 10)
        layout.setSpacing(10)

        text = QVBoxLayout()
        text.setSpacing(2)
        title = QLabel(voice.name)
        title.setObjectName("voiceName")
        missing = voice.missing_files()
        meta = QLabel(
            f"{voice.mode} · {'48 kHz' if voice.sovits_rec else '24 kHz'}"
            + (f"  ·  {t('train.default_badge')}" if is_default else "")
            + ("" if not missing else f"  ·  {t('train.broken_badge')}"))
        meta.setObjectName("voiceMeta")
        text.addWidget(title)
        text.addWidget(meta)
        layout.addLayout(text, 1)

        use_btn = QPushButton(t("train.use"))
        use_btn.clicked.connect(lambda: self.use.emit(voice.id))
        layout.addWidget(use_btn)

        if not is_default:
            default_btn = QPushButton(t("train.set_default"))
            default_btn.clicked.connect(lambda: self.make_default.emit(voice.id))
            layout.addWidget(default_btn)

        folder_btn = QPushButton(t("train.open"))
        folder_btn.clicked.connect(lambda: self.open_folder.emit(voice.id))
        layout.addWidget(folder_btn)

        delete_btn = QPushButton(t("train.delete"))
        delete_btn.setObjectName("danger")
        delete_btn.clicked.connect(lambda: self.delete.emit(voice.id))
        layout.addWidget(delete_btn)


class LibraryTab(QWidget):
    changed = Signal()

    def __init__(self, service) -> None:
        super().__init__()
        self.service = service
        self.config = service.config
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.body = QWidget()
        self.rows = QVBoxLayout(self.body)
        self.rows.setSpacing(8)
        self.rows.addStretch(1)
        self.scroll.setWidget(self.body)
        layout.addWidget(self.scroll, 1)
        self.empty = QLabel(t("train.empty"))
        self.empty.setObjectName("hint")
        layout.addWidget(self.empty)
        self.refresh()

    def refresh(self) -> None:
        while self.rows.count():
            item = self.rows.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        voices = self.service.tts.voices()
        default_id = self.config.tts.voice
        for voice in voices:
            row = VoiceRow(voice, voice.id == default_id)
            row.use.connect(self._use)
            row.make_default.connect(self._make_default)
            row.delete.connect(self._delete)
            row.open_folder.connect(self._open)
            self.rows.addWidget(row)
        self.rows.addStretch(1)
        self.empty.setVisible(not voices)

    def _use(self, voice_id: str) -> None:
        self.service.set_voice(voice_id)
        self.config.tts.voice = voice_id
        self._save()
        self.refresh()
        self.changed.emit()

    def _make_default(self, voice_id: str) -> None:
        self._use(voice_id)

    def _delete(self, voice_id: str) -> None:
        voice = self.service.tts.store.get(voice_id)
        if voice is None:
            return
        answer = QMessageBox.question(self, t("train.title"),
                                      t("train.delete.confirm", name=voice.name))
        if answer != QMessageBox.Yes:
            return
        import shutil

        shutil.rmtree(Path(voice.dir), ignore_errors=True)
        if self.config.tts.voice == voice_id:
            remaining = [v for v in self.service.tts.voices() if v.id != voice_id]
            self.config.tts.voice = remaining[0].id if remaining else ""
            self.service.set_voice(self.config.tts.voice)
        self._save()
        self.refresh()
        self.changed.emit()

    def _open(self, voice_id: str) -> None:
        voice = self.service.tts.store.get(voice_id)
        if voice is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(voice.dir))

    def _save(self) -> None:
        try:
            self.config.save()
        except Exception as exc:  # noqa: BLE001
            log.warning("cannot save config: %s", exc)


class NewVoiceTab(QWidget):
    trained = Signal(object)

    def __init__(self, service, parent=None) -> None:
        super().__init__(parent)
        self.service = service
        self.config = service.config
        self._source: str = ""
        self._recorder: Recorder | None = None
        self._worker: TrainWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(10)

        name_row = QHBoxLayout()
        label = QLabel(t("train.name"))
        label.setObjectName("rowlabel")
        label.setMinimumWidth(72)
        self.name = QLineEdit()
        self.name.setPlaceholderText(t("train.name.ph"))
        name_row.addWidget(label)
        name_row.addWidget(self.name, 1)
        layout.addLayout(name_row)

        source_row = QHBoxLayout()
        label = QLabel(t("train.source"))
        label.setObjectName("rowlabel")
        label.setMinimumWidth(72)
        self.choose = QPushButton(t("train.choose"))
        self.choose.clicked.connect(self._choose_file)
        self.record = QPushButton(t("train.record"))
        self.record.clicked.connect(self._toggle_record)
        source_row.addWidget(label)
        source_row.addWidget(self.choose)
        source_row.addWidget(self.record)
        source_row.addStretch(1)
        layout.addLayout(source_row)

        self.info = QLabel(t("train.info.empty"))
        self.info.setObjectName("hint")
        self.info.setWordWrap(True)
        layout.addWidget(self.info)

        action_row = QHBoxLayout()
        self.start = QPushButton(t("train.start"))
        self.start.setObjectName("primary")
        self.start.setMinimumHeight(38)
        self.start.clicked.connect(self._start)
        self.cancel = QPushButton(t("train.cancel"))
        self.cancel.setEnabled(False)
        self.cancel.clicked.connect(self._cancel)
        action_row.addWidget(self.start, 2)
        action_row.addWidget(self.cancel)
        layout.addLayout(action_row)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        log_label = QLabel(t("train.log"))
        log_label.setObjectName("rowlabel")
        layout.addWidget(log_label)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(160)
        self.log.setObjectName("transcript")
        layout.addWidget(self.log, 1)

    # -- source ---------------------------------------------------------
    def _choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, t("train.choose"), "", "Audio (*.wav *.mp3 *.m4a *.flac *.ogg)")
        if path:
            self.set_source(path)

    def set_source(self, path: str) -> None:
        try:
            samples, sr = wav.read_wav(path)
        except Exception as exc:  # noqa: BLE001
            self.info.setText(t("error.generic", message=str(exc)))
            return
        secs = len(samples) / float(sr or 1)
        self._source = path
        self.info.setText(t("train.info.file", name=Path(path).name, secs=secs, sr=sr))
        if secs < 45:
            self.info.setText(self.info.text() + "\n" + t("train.info.short", secs=secs))

    def _toggle_record(self) -> None:
        if self._recorder is None:
            self._recorder = Recorder(sample_rate=16000,
                                      device=self.config.audio.input_device,
                                      max_seconds=180)
            try:
                self._recorder.start()
            except Exception as exc:  # noqa: BLE001
                self._recorder = None
                QMessageBox.warning(self, t("train.title"), str(exc))
                return
            self.record.setText(t("train.record.stop"))
            self.info.setText(t("train.recording"))
        else:
            samples = self._recorder.stop()
            self._recorder = None
            self.record.setText(t("train.record"))
            target = Path(self.service.models.results or Path("results")) / \
                f"train_src_{time.strftime('%Y%m%d-%H%M%S')}.wav"
            wav.write_wav(target, samples, 16000)
            self.set_source(str(target))

    # -- training -------------------------------------------------------
    def _start(self) -> None:
        name = self.name.text().strip()
        if not name:
            QMessageBox.information(self, t("train.title"), t("train.need_name"))
            return
        if not self._source or not Path(self._source).exists():
            QMessageBox.information(self, t("train.title"), t("train.need_audio"))
            return
        self.log.clear()
        self.start.setEnabled(False)
        self.cancel.setEnabled(True)
        self.progress.setVisible(True)
        self._append(t("train.running"))

        worker = TrainWorker(self.service, name, self._source)
        worker.progress.connect(self._on_progress)
        worker.finished_ok.connect(self._on_done)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(self._on_thread_finished)
        self._worker = worker
        worker.start()

    def _cancel(self) -> None:
        worker = self._worker
        if worker is not None:
            worker.cancel()
            self._append("cancel requested")

    def _wait_worker(self, timeout_ms: int = 5000) -> None:
        """Stop and reap the worker before the dialog (or the object) goes away.

        Dropping the last reference to a running QThread makes Qt abort with
        "QThread: Destroyed while thread is still running" (0xc0000409).
        """
        worker = self._worker
        if worker is None:
            return
        try:
            worker.cancel()
        except Exception:  # noqa: BLE001
            pass
        if worker.isRunning():
            worker.wait(timeout_ms)

    def _on_thread_finished(self) -> None:
        worker = self._worker
        if worker is not None:
            worker.deleteLater()
        self._worker = None

    def _append(self, message: str) -> None:
        self.log.appendPlainText(message)
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def _on_progress(self, stage: str, message: str, epoch: int, total: int) -> None:
        prefix = f"[{stage}]"
        if total:
            prefix += f" {epoch}/{total}"
            self.progress.setRange(0, max(1, total))
            self.progress.setValue(epoch)
        self._append(f"{prefix} {message}")

    def _on_done(self, profile) -> None:
        self._reset()
        self._append(t("train.done", name=profile.name))
        self.trained.emit(profile)

    def _on_failed(self, message: str) -> None:
        self._reset()
        self._append(t("train.failed", message=message))

    def _reset(self) -> None:
        self.start.setEnabled(True)
        self.cancel.setEnabled(False)
        self.progress.setVisible(False)
        self.progress.setRange(0, 0)
        # the worker is reaped by _on_thread_finished(); never None it here


class TrainingDialog(QDialog):
    def closeEvent(self, event) -> None:  # noqa: N802, ANN001
        for tab in self.findChildren(NewVoiceTab):
            tab._wait_worker()
        super().closeEvent(event)

    def __init__(self, tray) -> None:
        super().__init__()
        self.tray = tray
        self.service = tray.service
        self.setWindowTitle(t("train.title"))
        self.setWindowIcon(tray.window_icon())
        self.resize(760, 620)
        from . import palette

        self.setStyleSheet(palette.STYLESHEET)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        self.tabs = QTabWidget()
        self.library = LibraryTab(self.service)
        self.new_voice = NewVoiceTab(self.service)
        self.tabs.addTab(self.library, t("train.tab.library"))
        self.tabs.addTab(self.new_voice, t("train.tab.new"))
        layout.addWidget(self.tabs, 1)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        close = QPushButton(t("train.close"))
        close.clicked.connect(self.accept)
        bottom.addWidget(close)
        layout.addLayout(bottom)

        self.new_voice.trained.connect(self._on_trained)
        self.library.changed.connect(self._notify_tray)

    def _on_trained(self, profile) -> None:
        self.library.refresh()
        self.tabs.setCurrentIndex(0)
        self._notify_tray()

    def _notify_tray(self) -> None:
        try:
            self.tray.refresh_voices()
        except Exception:
            log.debug("tray refresh skipped", exc_info=True)


__all__ = ["TrainingDialog", "LibraryTab", "NewVoiceTab", "TrainWorker"]
