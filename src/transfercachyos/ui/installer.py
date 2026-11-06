import codecs
import os
import platform
import shutil
from pathlib import Path

from PySide6.QtCore import QLocale, QProcess, QSettings, QTemporaryDir, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel,
    QPlainTextEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from ..catalog import APPS
from ..i18n import LANGUAGES, translate, translator
from ..services.packages import (
    PACMAN_IN_TERMINAL, interactive_terminal, missing_packages, read_packages, supported_system,
)

from .read_task import ReadTask

PROFILES = ("custom", "daily", "office", "coding")
text = translator("installer")


class TransferWindow(QWidget):
    busy_changed = Signal(bool)
    language_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("TransferCachyOS")
        self.resize(820, 730)
        self.settings = QSettings("TransferCachyOS", "TransferCachyOS")
        saved_language = self.settings.value("language", QLocale.system().name().split("_")[0])
        self.language = saved_language if saved_language in LANGUAGES else "en"
        self.supported = supported_system()
        self.installed = None
        self.requested_package = None
        self.query = ReadTask(self)
        self.query.completed.connect(self.packages_loaded)
        self.attempted = set()
        self.status_key = ""
        self.busy = False

        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.finished.connect(self.finished)
        self.process.errorOccurred.connect(self.process_error)

        layout = QVBoxLayout(self)
        self.intro = QLabel()
        self.intro.setWordWrap(True)
        self.system_info = QLabel()
        self.system_info.setWordWrap(True)
        layout.addWidget(self.intro)
        layout.addWidget(self.system_info)

        controls = QHBoxLayout()
        self.language_box = QComboBox()
        self.language_box.addItems(("Türkçe", "English", "Français", "Deutsch"))
        self.language_box.setCurrentIndex(LANGUAGES.index(self.language))
        self.profile_label = QLabel()
        self.profile_box = QComboBox()
        self.profile_box.addItems(PROFILES)
        self.profile_label.setBuddy(self.profile_box)
        controls.addWidget(self.profile_label)
        controls.addWidget(self.profile_box, 1)
        layout.addLayout(controls)

        self.app_list = QWidget()
        app_layout = QVBoxLayout(self.app_list)
        self.rows = []
        for app in APPS:
            row = QHBoxLayout()
            check = QCheckBox(app.name)
            check.setMinimumWidth(160)
            description = QLabel()
            description.setWordWrap(True)
            status = QLabel()
            status.setWordWrap(True)
            status.setMinimumWidth(105)
            row.addWidget(check)
            row.addWidget(description, 1)
            row.addWidget(status)
            app_layout.addLayout(row)
            self.rows.append((app, check, description, status))
            check.toggled.connect(self.manual_selection)
        app_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.app_list)
        layout.addWidget(scroll, 1)

        actions = QHBoxLayout()
        self.scan_button = QPushButton()
        self.preview_button = QPushButton()
        actions.addWidget(self.scan_button)
        actions.addStretch()
        actions.addWidget(self.preview_button)
        layout.addLayout(actions)

        self.status = QLabel()
        self.status.setWordWrap(True)
        self.log_label = QLabel()
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2500)
        self.log.setMaximumHeight(135)
        self.log_label.setBuddy(self.log)
        self.log.hide()
        self.log_label.hide()
        self.log.textChanged.connect(self.update_log_visibility)
        layout.addWidget(self.status)
        layout.addWidget(self.log_label)
        layout.addWidget(self.log)

        self.language_box.currentIndexChanged.connect(self.change_language)
        self.profile_box.activated.connect(self.apply_profile)
        self.scan_button.clicked.connect(self.scan)
        self.preview_button.clicked.connect(self.show_plan)
        self.refresh()

    def update_log_visibility(self):
        visible = self.log.document().characterCount() > 1
        self.log.setVisible(visible)
        self.log_label.setVisible(visible)

    def t(self, key):
        return text(key, self.language)

    def change_language(self, index):
        self.language = LANGUAGES[index]
        self.settings.setValue("language", self.language)
        self.refresh()
        self.language_changed.emit(self.language)

    def refresh(self):
        self.intro.setText(self.t("intro"))
        self.profile_label.setText(self.t("profile"))
        for index, profile in enumerate(PROFILES):
            self.profile_box.setItemText(index, self.t(profile))
        self.system_info.setText(self.t("system").format(
            desktop=os.environ.get("XDG_CURRENT_DESKTOP") or "—",
            arch=platform.machine(),
            free=shutil.disk_usage("/").free / (1024 ** 3),
        ))
        self.scan_button.setText(self.t("scan"))
        self.preview_button.setText(self.t("preview"))
        self.log_label.setText(self.t("output"))
        self.status.setText(self.t(self.status_key) if self.status_key else "")
        self.scan_button.setEnabled(self.supported and not self.busy and not self.query.running)
        self.profile_box.setEnabled(not self.busy)

        for app, check, description, status in self.rows:
            description.setText(translate("app_descriptions", app.packages[0], self.language))
            missing = self.installed is not None and bool(missing_packages([app], self.installed))
            if self.installed is None:
                key = "loading" if self.query.running else "unknown"
            elif not missing:
                key = "ready"
                check.setChecked(False)
            elif app.name in self.attempted:
                key = "failed_app"
            else:
                key = "missing"
            check.setEnabled(missing and not self.busy)
            status.setText(self.t(key))
        self.update_preview_button()

    def scan(self):
        if not self.busy:
            self.status_key = ""
            self.reload_packages("scan")

    def reload_packages(self, purpose):
        if not self.supported:
            self.status_key = "unsupported"
        elif not self.query.running:
            self.query_purpose = purpose
            self.query.start(read_packages)
        self.refresh()

    def packages_loaded(self, installed, error):
        purpose = self.query_purpose
        self.installed = installed if error is None else None
        if error is not None:
            self.status_key = "scan_error"
            self.log.appendPlainText(str(getattr(error, "stderr", None) or error))
        if purpose == "result":
            self.busy = False
            if self.installed is not None:
                self.attempted = {
                    app.name for app in self.installing if missing_packages([app], self.installed)
                }
                if self.attempted:
                    self.status_key = "failure"
            self.busy_changed.emit(False)
        self.refresh()
        if self.installed is not None and self.requested_package:
            self.select_package(self.requested_package)
        if purpose == "preview" and self.isVisible() and self.isEnabled():
            self.preview_packages(self.preview_selection)

    def select_package(self, package):
        self.requested_package = package if self.installed is None and self.supported else None
        for app, check, _, _ in self.rows:
            if app.packages == (package,) and check.isEnabled():
                check.setChecked(True)
                check.setFocus()
                break

    def manual_selection(self):
        self.profile_box.setCurrentIndex(0)
        self.update_preview_button()

    def apply_profile(self, index):
        if index == 0:
            return
        profile = PROFILES[index]
        for app, check, _, _ in self.rows:
            check.blockSignals(True)
            check.setChecked(check.isEnabled() and profile in app.profiles)
            check.blockSignals(False)
        self.update_preview_button()

    def selected_apps(self):
        return [app for app, check, _, _ in self.rows if check.isChecked()]

    def update_preview_button(self):
        self.preview_button.setEnabled(
            not self.busy and not self.query.running and self.installed is not None and bool(self.selected_apps())
        )

    def show_plan(self):
        if self.busy or self.query.running:
            return
        self.preview_selection = self.selected_apps()
        self.reload_packages("preview")

    def preview_packages(self, selected):
        if self.installed is None:
            return
        packages = missing_packages(selected, self.installed)
        if not packages:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(self.t("preview"))
        dialog.resize(540, 350)
        layout = QVBoxLayout(dialog)
        explanation = QLabel(self.t("plan"))
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        details = QPlainTextEdit("\n".join(packages))
        details.setReadOnly(True)
        layout.addWidget(details)
        buttons = QHBoxLayout()
        cancel = QPushButton(self.t("cancel"))
        apply = QPushButton(self.t("apply"))
        cancel.clicked.connect(dialog.reject)
        apply.clicked.connect(dialog.accept)
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(apply)
        layout.addLayout(buttons)
        cancel.setFocus()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.install(selected, packages)

    def install(self, selected, packages):
        terminal = interactive_terminal()
        if terminal is None or not os.access("/usr/bin/sudo", os.X_OK):
            self.status_key = "terminal_missing"
            self.refresh()
            return
        self.transaction_dir = QTemporaryDir()
        if not self.transaction_dir.isValid():
            self.status_key = "failure"
            self.log.setPlainText(self.transaction_dir.errorString())
            self.refresh()
            return
        executable, options = terminal
        self.result_file = Path(self.transaction_dir.path()) / "exit-status"
        self.attempted.clear()
        self.installing = selected
        self.busy = True
        self.busy_changed.emit(True)
        self.status_key = "running"
        self.log.clear()
        self.decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self.refresh()
        self.process.start(executable, [
            *options, "/usr/bin/bash", "-c", PACMAN_IN_TERMINAL, "transfercachyos",
            str(self.result_file), self.t("close_terminal"), *packages,
        ])

    def read_output(self, final=False):
        chunk = bytes(self.process.readAllStandardOutput())
        text = self.decoder.decode(chunk, final=final)
        self.log.moveCursor(QTextCursor.MoveOperation.End)
        self.log.insertPlainText(text)
        self.log.ensureCursorVisible()

    def finished(self, code, exit_status):
        self.read_output(final=True)
        try:
            success = self.result_file.read_text(encoding="ascii").strip() == "0"
        except (OSError, UnicodeError):
            success = False
        self.transaction_dir.remove()
        self.status_key = "done" if success else "failure"
        self.reload_packages("result")

    def process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.transaction_dir.remove()
            self.log.appendPlainText(self.process.errorString())
            self.busy = False
            self.status_key = "failure"
            self.refresh()
            self.busy_changed.emit(False)
