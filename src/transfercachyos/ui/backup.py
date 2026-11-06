import codecs
import json
import os
import signal
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QProcess, QProcessEnvironment, QSettings, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QPlainTextEdit, QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

from ..i18n import messages, translator
from ..services.backup import (
    RESTIC, backup_identity, backup_plan, repository_fingerprint, restore_destination, snapshot_rows,
)

text = translator("backup")


class BackupPanel(QWidget):
    def __init__(self, language, show_apps):
        super().__init__()
        self.language = language
        self.busy = False
        self.cancel_requested = False
        self.phase = ""
        self.secret = b""
        self.status_key = ""
        self.snapshot_repo = None
        self.settings = QSettings("TransferCachyOS", "TransferCachyOS")
        self.process = QProcess(self)
        environment = QProcessEnvironment.systemEnvironment()
        for name in environment.keys():
            if name.startswith("RESTIC_"):
                environment.remove(name)
        self.process.setProcessEnvironment(environment)
        self.process.started.connect(self.send_password)
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.readyReadStandardError.connect(self.read_errors)
        self.process.finished.connect(self.finished)
        self.process.errorOccurred.connect(self.process_error)

        layout = QVBoxLayout(self)
        self.intro = QLabel()
        self.intro.setWordWrap(True)
        layout.addWidget(self.intro)
        self.controls = QWidget()
        controls = QVBoxLayout(self.controls)
        controls.setContentsMargins(0, 0, 0, 0)
        target_row = QHBoxLayout()
        self.choose = QPushButton()
        self.target = QLabel()
        self.target.setTextFormat(Qt.TextFormat.PlainText)
        self.target.setWordWrap(True)
        target_row.addWidget(self.choose)
        target_row.addWidget(self.target, 1)
        self.history_button = QPushButton()
        target_row.addWidget(self.history_button)
        controls.addLayout(target_row)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        controls.addWidget(self.password)

        self.pages = QTabWidget()
        self.pages.setDocumentMode(True)
        new_backup = QWidget()
        backup_layout = QVBoxLayout(new_backup)
        self.sources = QListWidget()
        backup_layout.addWidget(self.sources, 1)
        source_actions = QHBoxLayout()
        self.add = QPushButton()
        self.remove = QPushButton()
        self.preview = QPushButton()
        source_actions.addWidget(self.add)
        source_actions.addWidget(self.remove)
        source_actions.addStretch()
        source_actions.addWidget(self.preview)
        backup_layout.addLayout(source_actions)
        self.remember = QCheckBox()
        self.remember.setChecked(bool(self.saved_recipe()))
        self.remember.toggled.connect(self.remember_toggled)
        backup_layout.addWidget(self.remember)
        self.repeat = QLineEdit()
        self.repeat.setEchoMode(QLineEdit.EchoMode.Password)
        backup_layout.addWidget(self.repeat)
        self.pages.addTab(new_backup, "")

        restore = QWidget()
        restore_layout = QVBoxLayout(restore)
        self.snapshot_label = QLabel()
        self.snapshots = QListWidget()
        self.snapshot_label.setBuddy(self.snapshots)
        restore_layout.addWidget(self.snapshot_label)
        restore_layout.addWidget(self.snapshots, 1)
        snapshot_actions = QHBoxLayout()
        self.list_button = QPushButton()
        self.restore_button = QPushButton()
        self.check_button = QPushButton()
        snapshot_actions.addWidget(self.list_button)
        snapshot_actions.addWidget(self.check_button)
        snapshot_actions.addStretch()
        snapshot_actions.addWidget(self.restore_button)
        restore_layout.addLayout(snapshot_actions)
        self.pages.addTab(restore, "")
        controls.addWidget(self.pages, 1)
        layout.addWidget(self.controls, 1)

        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.apps = QPushButton()
        self.stop = QPushButton()
        action_row = QHBoxLayout()
        action_row.addWidget(self.apps)
        action_row.addWidget(self.stop)
        action_row.addStretch()
        layout.addLayout(action_row)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(1000)
        self.log.setMaximumHeight(150)
        self.log.hide()
        self.log.textChanged.connect(lambda: self.log.setVisible(self.log.document().characterCount() > 1))
        layout.addWidget(self.log)
        self.add.clicked.connect(self.add_source)
        self.remove.clicked.connect(self.remove_source)
        self.choose.clicked.connect(self.choose_target)
        self.sources.currentRowChanged.connect(self.refresh)
        self.apps.clicked.connect(show_apps)
        self.preview.clicked.connect(self.show_plan)
        self.snapshots.currentRowChanged.connect(self.refresh)
        self.list_button.clicked.connect(self.list_snapshots)
        self.check_button.clicked.connect(self.check_repository)
        self.stop.clicked.connect(self.cancel_operation)
        self.restore_button.clicked.connect(self.restore_snapshot)
        self.history_button.clicked.connect(self.show_history)
        self.refresh()

    def t(self, key):
        return text(key, self.language)

    def refresh(self):
        available = os.access(RESTIC, os.X_OK)
        self.intro.setText(self.t("backup_intro"))
        self.intro.setVisible(available)
        self.controls.setVisible(available)
        self.pages.setTabText(0, self.t("new_backup"))
        self.pages.setTabText(1, self.t("restore"))
        self.add.setText(self.t("add"))
        self.remove.setText(self.t("remove"))
        self.choose.setText(self.t("target"))
        self.password.setPlaceholderText(self.t("password"))
        self.repeat.setPlaceholderText(self.t("repeat"))
        self.preview.setText(self.t("preview"))
        self.apps.setText(self.t("apps"))
        self.snapshot_label.setText(self.t("snapshots"))
        self.list_button.setText(self.t("list"))
        self.check_button.setText(self.t("check_repository"))
        self.stop.setText(self.t("stop"))
        self.stop.setVisible(self.busy)
        self.stop.setEnabled(not self.cancel_requested)
        self.restore_button.setText(self.t("restore"))
        self.history_button.setText(self.t("history"))
        self.remember.setText(self.t("remember"))
        self.remember.setEnabled(not self.busy)
        repository = self.repository()
        existing = repository is not None
        self.list_button.setEnabled(available and not self.busy and existing)
        self.check_button.setEnabled(available and not self.busy and existing)
        self.restore_button.setEnabled(available and not self.busy and existing
                                       and self.snapshot_repo == repository
                                       and self.snapshots.currentItem() is not None)
        self.apps.setVisible(not available)
        self.remove.setEnabled(not self.busy and self.sources.currentRow() >= 0)
        for widget in (self.add, self.choose, self.password, self.repeat):
            widget.setEnabled(not self.busy)
        self.repeat.setVisible(bool(self.target.text()) and not (Path(self.target.text()) / "config").is_file())
        self.preview.setEnabled(available and not self.busy and bool(self.sources.count() and self.target.text()))
        status = self.status_key or ("missing" if not available else "")
        self.status.setText(self.t(status) if status else "")
        self.status.setVisible(bool(status))

    def add_source(self):
        selected = QFileDialog.getExistingDirectory(self, self.t("add"), str(Path.home()))
        if selected and all(self.sources.item(i).text() != selected for i in range(self.sources.count())):
            self.sources.addItem(selected)
            self.sources.setCurrentRow(self.sources.count() - 1)
        self.refresh()

    def remove_source(self):
        if self.sources.currentRow() >= 0:
            self.sources.takeItem(self.sources.currentRow())
        self.refresh()

    def choose_target(self):
        selected = QFileDialog.getExistingDirectory(self, self.t("target"), str(Path.home()))
        if selected:
            self.target.setText(selected)
            self.snapshot_repo = None
            self.snapshots.clear()
            self.password.clear()
            self.repeat.clear()
        self.refresh()

    def show_plan(self):
        if self.busy or not self.preview.isEnabled():
            return
        try:
            sources, target, create = backup_plan(
                [self.sources.item(i).text() for i in range(self.sources.count())], self.target.text(),
            )
            identity = backup_identity(sources, target)
            fingerprint = None if create else repository_fingerprint(target)
            if not create and fingerprint is None:
                raise ValueError("target_error")
        except OSError:
            self.set_status("invalid")
            return
        except ValueError as error:
            self.set_status(str(error))
            return
        secret = self.password.text()
        if not secret.strip() or secret != secret.strip() or (create and secret != self.repeat.text()):
            self.set_status("bad_password")
            return
        dialog = QMessageBox(self)
        dialog.setTextFormat(Qt.TextFormat.PlainText)
        dialog.setWindowTitle(self.t("preview"))
        dialog.setText(f"{self.t('new' if create else 'existing')}\n\n{self.t('target')}: {target}\n\n"
                       + "\n".join(map(str, sources)))
        approve = dialog.addButton(self.t("start"), QMessageBox.ButtonRole.AcceptRole)
        cancel = dialog.addButton(self.t("cancel"), QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(cancel)
        dialog.exec()
        if dialog.clickedButton() is not approve:
            return
        try:
            unchanged = (
                backup_plan(sources, target) == (sources, target, create)
                and backup_identity(sources, target) == identity
                and (create or repository_fingerprint(target) == fingerprint)
            )
        except (OSError, ValueError):
            unchanged = False
        if not unchanged:
            self.set_status("backup_changed")
            return
        self.paths = sources
        self.confirmed_identity = identity
        self.confirmed_fingerprint = fingerprint
        self.start_operation(target, secret, "init" if create else "backup", "running")

    def repository(self):
        if not self.target.text():
            return None
        try:
            repository = Path(self.target.text()).resolve(strict=True)
            if (repository / "config").is_file():
                return repository
        except (OSError, RuntimeError):
            pass
        return None

    def list_snapshots(self):
        repository = self.repository()
        if self.busy or repository is None:
            return
        secret = self.password.text()
        if not secret or secret != secret.strip():
            self.set_status("password_required")
            return
        self.snapshots.clear()
        self.snapshot_repo = None
        self.start_operation(repository, secret, "snapshots", "list_running")

    @property
    def read_only(self):
        return self.phase in ("snapshots", "check")

    def check_repository(self):
        repository = self.repository()
        if self.busy or repository is None:
            return
        secret = self.password.text()
        if not secret or secret != secret.strip():
            self.set_status("password_required")
            return
        self.start_operation(repository, secret, "check", "check_running")

    def cancel_operation(self):
        if not self.busy or self.cancel_requested:
            return
        self.cancel_requested = True
        self.set_status("stopping")
        self.interrupt_process()

    def interrupt_process(self):
        if pid := self.process.processId():
            try:
                os.kill(pid, signal.SIGINT)
            except ProcessLookupError:
                pass

    def restore_snapshot(self):
        item = self.snapshots.currentItem()
        repository = self.repository()
        if self.busy or item is None or repository is None or self.snapshot_repo != repository:
            return
        secret = self.password.text()
        if not secret or secret != secret.strip():
            self.set_status("password_required")
            return
        ref = item.data(Qt.ItemDataRole.UserRole)
        selected = QFileDialog.getExistingDirectory(self, self.t("restore_target"), str(Path.home()))
        if not selected:
            return
        try:
            destination = restore_destination(selected, repository)
        except ValueError as error:
            self.set_status(str(error))
            return
        dialog = QMessageBox(self)
        dialog.setTextFormat(Qt.TextFormat.PlainText)
        dialog.setWindowTitle(self.t("restore"))
        dialog.setText(f"{self.t('restore_plan')}\n\n{item.text()}\n\n{destination}")
        apply = dialog.addButton(self.t("restore"), QMessageBox.ButtonRole.AcceptRole)
        cancel = dialog.addButton(self.t("cancel"), QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(cancel)
        dialog.exec()
        if dialog.clickedButton() is not apply:
            return
        try:
            self.restore_target = restore_destination(selected, repository)
            if self.restore_target != destination:
                raise ValueError("restore_invalid")
        except ValueError as error:
            self.set_status(str(error))
            return
        self.restore_ref = ref
        self.start_operation(repository, secret, "restore", "restore_running")

    def start_operation(self, repository, secret, phase, status):
        self.secret = secret.encode("utf-8") + b"\n"
        self.password.clear()
        self.repeat.clear()
        self.destination = repository
        self.busy = True
        self.cancel_requested = False
        self.log.clear()
        self.set_status(status)
        self.run(phase)

    def run(self, phase):
        self.phase = phase
        self.decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self.error_decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        arguments = ["--repo", str(self.destination), "--password-file", "/dev/stdin"]
        if phase == "snapshots":
            self.snapshot_output = bytearray()
            arguments.append("--json")
        arguments.append(phase)
        if phase == "backup":
            arguments.extend(("--", *map(str, self.paths)))
        elif phase == "restore":
            arguments.extend(("--target", str(self.restore_target), "--overwrite", "never", self.restore_ref))
        self.process.start(RESTIC, arguments)

    def send_password(self):
        if self.cancel_requested:
            self.interrupt_process()
        else:
            self.process.write(self.secret)
        self.process.closeWriteChannel()

    def read_output(self, final=False):
        chunk = bytes(self.process.readAllStandardOutput())
        if self.phase == "snapshots":
            self.snapshot_output.extend(chunk)
        else:
            self.append_log(self.decoder.decode(chunk, final=final))

    def read_errors(self, final=False):
        chunk = bytes(self.process.readAllStandardError())
        self.append_log(self.error_decoder.decode(chunk, final=final))

    def append_log(self, output):
        if output:
            self.log.moveCursor(QTextCursor.MoveOperation.End)
            self.log.insertPlainText(output)
            self.log.ensureCursorVisible()

    def finished(self, code, exit_status):
        self.read_output(final=True)
        self.read_errors(final=True)
        normal = exit_status == QProcess.ExitStatus.NormalExit
        if self.cancel_requested and not (normal and code == 0):
            self.complete("restore_cancelled" if self.phase == "restore" else "cancelled")
            return
        if self.cancel_requested and self.phase == "init":
            self.complete("cancelled")
            return
        if normal and code == 0 and self.phase == "init":
            try:
                self.confirmed_fingerprint = repository_fingerprint(self.destination)
                unchanged = (
                    backup_identity(self.paths, self.destination) == self.confirmed_identity
                    and self.confirmed_fingerprint is not None
                )
            except OSError:
                unchanged = False
            if unchanged:
                self.run("backup")
            else:
                self.complete("backup_changed")
            return
        if self.phase == "snapshots":
            status = self.finish_snapshot_list() if normal and code == 0 else "failed"
        elif self.phase == "check":
            status = "check_done" if normal and code == 0 else "failed"
        elif self.phase == "restore":
            status = "restore_done" if normal and code == 0 else "restore_failed"
        elif normal and code == 0:
            status = "done"
            self.snapshots.clear()
            self.snapshot_repo = None
        elif normal and code == 3 and self.phase == "backup":
            status = "partial"
            self.snapshots.clear()
            self.snapshot_repo = None
        else:
            status = "failed"
        self.complete(status)

    def finish_snapshot_list(self):
        try:
            rows = snapshot_rows(self.snapshot_output)
        except (ValueError, KeyError, TypeError, OverflowError, OSError) as error:
            self.log.appendPlainText(str(error))
            return "failed"
        self.snapshot_repo = self.destination
        for timestamp, ref, paths in rows:
            item = QListWidgetItem(f"{timestamp:%Y-%m-%d %H:%M %Z} · {ref[:8]} · {paths}")
            item.setData(Qt.ItemDataRole.UserRole, ref)
            item.setToolTip(paths)
            self.snapshots.addItem(item)
        return "list_ready" if rows else "list_empty"

    def saved_recipe(self):
        try:
            recipe = json.loads(self.settings.value("backup_recipe", "null", type=str))
            if (isinstance(recipe, list) and len(recipe) == 2
                    and isinstance(recipe[0], list) and recipe[0]
                    and all(isinstance(path, str) for path in recipe[0])
                    and isinstance(recipe[1], str)):
                return recipe
        except (TypeError, ValueError):
            pass
        return None

    def saved_recipe_ready(self):
        recipe = self.saved_recipe()
        if not recipe:
            return False
        try:
            _, target, create = backup_plan(*recipe)
            saved = self.settings.value("backup_repository_fingerprint", "", type=str)
            return not create and bool(saved) and repository_fingerprint(target) == saved
        except (OSError, ValueError):
            return False

    def restore_recipe(self):
        recipe = self.saved_recipe()
        if self.busy or recipe is None or self.sources.count() or self.target.text():
            return
        sources, destination = recipe
        self.sources.addItems(sources)
        if self.saved_recipe_ready():
            self.target.setText(destination)
        self.refresh()

    def remember_toggled(self, enabled):
        if not enabled:
            self.settings.remove("backup_recipe")
            self.settings.remove("backup_repository_fingerprint")

    def history(self):
        try:
            entries = json.loads(self.settings.value("backup_history", "[]", type=str))
            return [
                entry for entry in entries if isinstance(entry, list) and len(entry) == 3
                and all(isinstance(value, str) for value in entry)
                and entry[1] in ("start", "restore") and entry[2] in messages("en")["backup"]
            ][:30]
        except (ValueError, TypeError):
            return []

    def show_history(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(self.t("history"))
        dialog.resize(520, 340)
        layout = QVBoxLayout(dialog)
        entries = QListWidget()
        entries.addItems([
            f"{timestamp} · {self.t(action)} · {self.t(status)}"
            for timestamp, action, status in self.history()
        ] or [self.t("history_empty")])
        layout.addWidget(entries)
        close = QPushButton(self.t("close"))
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()

    def process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.log.appendPlainText(self.process.errorString())
            self.complete("cancelled" if self.cancel_requested else "failed")

    def complete(self, status):
        self.secret = b""
        self.busy = False
        self.cancel_requested = False
        if self.phase == "backup" and status == "done" and self.remember.isChecked():
            try:
                fingerprint = repository_fingerprint(self.destination)
            except OSError:
                fingerprint = None
            if fingerprint and fingerprint == self.confirmed_fingerprint:
                self.settings.setValue("backup_recipe", json.dumps([
                    list(map(str, self.paths)), str(self.destination),
                ]))
                self.settings.setValue("backup_repository_fingerprint", fingerprint)
        if self.phase in ("init", "backup", "restore"):
            action = "restore" if self.phase == "restore" else "start"
            entry = [datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z"), action, status]
            self.settings.setValue("backup_history", json.dumps([entry, *self.history()[:29]]))
        self.set_status(status)

    def set_status(self, key):
        self.status_key = key
        self.refresh()
