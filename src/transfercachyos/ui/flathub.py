from PySide6.QtCore import QProcess, Signal
from PySide6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit,
    QPushButton, QVBoxLayout, QWidget,
)

from ..i18n import translator
from ..services.flatpak import FLATPAK, FLATHUB_APPS, flatpak_state

from .read_task import ReadTask

text = translator("setup")


class FlatpakPanel(QWidget):
    busy_changed = Signal(bool)

    def __init__(self, language):
        super().__init__()
        self.language = language
        self.busy = False
        self.query = ReadTask(self)
        self.query.completed.connect(self.loaded)
        self.loaded_once = False
        self.scope = None
        self.installed = {}
        self.targets = ()
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.finished.connect(self.finished)
        self.process.errorOccurred.connect(self.failed)
        layout = QVBoxLayout(self)
        self.source = QLabel()
        layout.addWidget(self.source)
        self.rows = {}
        for app_id, name, description in FLATHUB_APPS:
            row = QHBoxLayout()
            check, details, status, launch = QCheckBox(name), QLabel(), QLabel(), QPushButton()
            details.setWordWrap(True)
            check.toggled.connect(self.update_button)
            launch.clicked.connect(lambda _checked=False, ref=app_id: self.launch(ref))
            for widget in (check, details, status, launch):
                row.addWidget(widget, 1 if widget is details else 0)
            layout.addLayout(row)
            self.rows[app_id] = check, details, status, launch, description
        actions = QHBoxLayout()
        self.refresh_button = QPushButton()
        self.install_button = QPushButton()
        self.refresh_button.clicked.connect(lambda: self.reload())
        self.install_button.clicked.connect(self.preview)
        actions.addWidget(self.refresh_button)
        actions.addStretch()
        actions.addWidget(self.install_button)
        layout.addLayout(actions)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log, 1)
        self.render()

    def t(self, key):
        return text(key, self.language)

    def reload(self, purpose="scan"):
        if self.query.running:
            return
        self.query_purpose = purpose
        self.query.start(flatpak_state)
        self.render()

    def loaded(self, state, error):
        self.loaded_once = True
        if error is None:
            self.installed, self.scope = state
        else:
            self.scope = None
            self.log.setPlainText(f"{self.t('error')}\n{error}")
        if self.query_purpose == "result":
            ok = (error is None and self.transaction_succeeded
                  and all(ref in self.installed for ref in self.targets))
            self.log.setPlainText(f"{self.t('done' if ok else 'error')}\n{self.transaction_output}".strip())
            self.busy = False
            self.busy_changed.emit(False)
        self.render()
        if self.query_purpose == "preview" and self.isVisible() and self.isEnabled():
            self.show_plan()

    def render(self):
        if self.scope:
            source = self.t("source").format(scope=self.t(self.scope))
        elif self.loaded_once:
            source = self.t("no_source")
        else:
            source = self.t("loading")
        self.source.setText(source)
        self.refresh_button.setText(self.t("refresh"))
        self.refresh_button.setEnabled(not self.busy and not self.query.running)
        self.install_button.setText(self.t("install"))
        for app_id, (check, details, status, launch, description) in self.rows.items():
            installed_scope = self.installed.get(app_id)
            details.setText(self.t(description))
            state = "missing" if self.scope else "unknown"
            status.setText(f"{self.t('ready')} · {self.t(installed_scope)}" if installed_scope else self.t(state))
            if installed_scope:
                check.setChecked(False)
            check.setEnabled(bool(self.scope) and not installed_scope and not self.busy)
            launch.setText(self.t("open"))
            launch.setEnabled(bool(installed_scope) and not self.busy)
        self.update_button()

    def selected(self):
        return [ref for ref, (check, *_) in self.rows.items() if check.isChecked() and ref not in self.installed]

    def update_button(self):
        self.install_button.setEnabled(bool(self.scope and self.selected()) and not self.busy and not self.query.running)

    def preview(self):
        if not self.busy and not self.query.running:
            self.reload("preview")

    def show_plan(self):
        scope = self.scope
        targets = self.selected()
        if not scope or not targets:
            return
        names = [name for app_id, name, _ in FLATHUB_APPS if app_id in targets]
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Flathub")
        dialog.setText(f"{self.t('plan')}\n{self.source.text()}\n\n" + "\n".join(names))
        apply = dialog.addButton(self.t("install"), QMessageBox.ButtonRole.AcceptRole)
        cancel = dialog.addButton(self.t("cancel"), QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(cancel)
        dialog.exec()
        if dialog.clickedButton() is apply:
            self.targets = tuple(targets)
            self.busy = True
            self.busy_changed.emit(True)
            self.log.setPlainText(self.t("running"))
            self.render()
            self.process.start(FLATPAK, ["install", f"--{scope}", "--assumeyes", "--app", "flathub", *targets])

    def finished(self, code, exit_status):
        self.transaction_output = bytes(self.process.readAllStandardOutput()).decode(errors="replace").strip()
        self.transaction_succeeded = exit_status == QProcess.ExitStatus.NormalExit and code == 0
        self.reload("result")

    def failed(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.busy = False
            self.render()
            self.log.setPlainText(f"{self.t('error')}\n{self.process.errorString()}")
            self.busy_changed.emit(False)

    def launch(self, ref):
        if ref in self.installed:
            started, _ = QProcess.startDetached(FLATPAK, ["run", f"--{self.installed[ref]}", ref])
            if not started:
                self.log.setPlainText(self.t("error"))
