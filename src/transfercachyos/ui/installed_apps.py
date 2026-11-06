import subprocess

from PySide6.QtCore import QProcess, Signal, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
    QPushButton, QStyle, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from ..i18n import translator
from ..services.commands import command, error_text
from ..services.flatpak import FLATPAK
from ..services.installed_apps import Entry, installed_inventory, native_entries
from ..services.packages import PACMAN, PKEXEC, dependency_conflict, removable

from .read_task import ReadTask

text = translator("installed")
word = translator("system")


class PackagePanel(QWidget):
    busy_changed = Signal(bool)
    packages_changed = Signal()

    def __init__(self, language):
        super().__init__()
        self.language = language
        self.busy = False
        self.query = ReadTask(self)
        self.query.completed.connect(self.loaded)
        self.preflight = ReadTask(self)
        self.preflight.completed.connect(self.checked_removal)
        self.versions = {}
        self.explicit = set()
        self.native_listing = ""
        self.apps = []
        self.flatpaks = []
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.finished.connect(self.finished)
        self.process.errorOccurred.connect(self.process_error)

        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.refresh_button = QPushButton()
        row.addWidget(self.search, 1)
        row.addWidget(self.refresh_button)
        layout.addLayout(row)
        self.intro = QLabel()
        self.intro.setWordWrap(True)
        layout.addWidget(self.intro)

        self.list = QTreeWidget()
        self.list.setColumnCount(3)
        self.list.setRootIsDecorated(False)
        self.list.setAlternatingRowColors(True)
        self.list.setStyleSheet("QTreeWidget::item { padding: 5px 3px; }")
        self.fallback_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        self.list.setUniformRowHeights(True)
        self.list.setIndentation(0)
        self.list.setSortingEnabled(True)
        self.list.sortItems(0, Qt.SortOrder.AscendingOrder)
        self.list.setColumnWidth(0, 370)
        self.list.setColumnWidth(1, 145)
        layout.addWidget(self.list, 1)
        self.empty = QLabel()
        layout.addWidget(self.empty)

        actions = QHBoxLayout()
        self.technical = QCheckBox()
        self.open = QPushButton()
        self.remove = QPushButton()
        actions.addWidget(self.technical)
        actions.addStretch()
        actions.addWidget(self.open)
        actions.addWidget(self.remove)
        layout.addLayout(actions)
        self.status = QPlainTextEdit()
        self.status.setReadOnly(True)
        self.status.setMaximumHeight(105)
        self.status.hide()
        self.status.textChanged.connect(lambda: self.status.setVisible(not self.status.document().isEmpty()))
        layout.addWidget(self.status)
        self.search.textChanged.connect(self.filter)
        self.technical.toggled.connect(self.filter)
        self.refresh_button.clicked.connect(self.reload)
        self.list.currentItemChanged.connect(self.update_actions)
        self.open.clicked.connect(self.launch)
        self.remove.clicked.connect(self.confirm_remove)
        self.translate()

    def t(self, key):
        return text(key, self.language)

    def translate(self):
        self.refresh_button.setText(word("refresh", self.language))
        self.intro.setText(self.t("intro"))
        self.technical.setText(self.t("technical"))
        self.open.setText(self.t("open"))
        self.remove.setText(self.t("remove"))
        if self.native_listing:
            self.apps = native_entries(self.versions, self.explicit, self.native_listing, self.language)
        self.filter()

    def reload(self):
        if self.query.start(installed_inventory):
            self.refresh_button.setEnabled(False)
            self.filter()

    def loaded(self, result, error):
        self.refresh_button.setEnabled(not self.busy)
        if error is None:
            self.versions, self.explicit, self.native_listing, self.flatpaks, error = result
            self.apps = native_entries(self.versions, self.explicit, self.native_listing, self.language)
        if error is not None:
            self.status.setPlainText(f"{word('error', self.language)}\n{error_text(error)}")
        self.filter()

    def filter(self):
        technical = self.technical.isChecked()
        self.search.setPlaceholderText(word("search", self.language) if technical else self.t("search"))
        self.list.setHeaderLabels([self.t("package" if technical else "name"), self.t("version"), self.t("source")])
        self.list.clear()
        self.list.setSortingEnabled(False)
        query = self.search.text().strip().casefold()
        entries = (
            [Entry(name, version, name) for name, version in self.versions.items()]
            if technical else [*self.apps, *self.flatpaks]
        )
        for entry in entries:
            if query and not any(query in value.casefold() for value in (entry.name, entry.package, entry.version)):
                continue
            source = f"Flatpak · {self.t(entry.scope)}" if entry.scope else self.t("system")
            item = QTreeWidgetItem([entry.name, entry.version or "—", source])
            if not technical:
                icon = QIcon(entry.icon) if entry.icon.startswith("/") else QIcon.fromTheme(entry.icon)
                if icon.isNull():
                    icon = QIcon.fromTheme("application-x-executable")
                item.setIcon(0, self.fallback_icon if icon.isNull() else icon)
            item.setData(0, Qt.ItemDataRole.UserRole, entry)
            self.list.addTopLevelItem(item)
        self.list.setSortingEnabled(True)
        empty = self.list.topLevelItemCount() == 0
        self.empty.setText(self.t("loading" if self.query.running else ("empty_packages" if technical else "empty")))
        self.empty.setVisible(empty)
        self.update_actions()

    def selection(self):
        item = self.list.currentItem()
        return item.data(0, Qt.ItemDataRole.UserRole) if item else None

    def can_remove(self, entry):
        return bool(entry and (entry.scope or removable(entry.package, self.explicit)))

    def update_actions(self):
        entry = self.selection()
        self.open.setEnabled(not self.busy and bool(entry and (entry.launcher or entry.scope)))
        self.remove.setEnabled(not self.busy and not self.query.running and not self.preflight.running and self.can_remove(entry))
        self.remove.setToolTip(self.t("blocked") if entry and not self.can_remove(entry) else "")

    def launch(self):
        entry = self.selection()
        if not entry or self.busy:
            return
        if entry.scope:
            started, _ = QProcess.startDetached(FLATPAK, ["run", f"--{entry.scope}", entry.package])
        elif entry.launcher:
            started, _ = QProcess.startDetached("/usr/bin/gio", ["launch", entry.launcher])
        else:
            return
        if not started:
            self.status.setPlainText(word("error", self.language))

    def confirm_remove(self):
        entry = self.selection()
        if self.busy or not self.can_remove(entry):
            return
        if self.query.running or self.preflight.running:
            return
        if entry.scope:
            self.show_removal(entry, FLATPAK, ["uninstall", f"--{entry.scope}", "--app", "--assumeyes", entry.package])
        else:
            self.pending_removal = entry
            self.preflight.start(command, PACMAN, "-R", "--print", "--print-format", "%n", "--", entry.package)
            self.update_actions()

    def checked_removal(self, plan, error):
        self.update_actions()
        if not self.isVisible() or not self.isEnabled() or self.selection() != self.pending_removal:
            return
        entry = self.pending_removal
        if isinstance(error, subprocess.TimeoutExpired):
            key = "timeout"
        elif error is not None:
            detail = error_text(error)
            key = "required" if isinstance(error, subprocess.CalledProcessError) and dependency_conflict(detail) else "query_failed"
        elif plan != entry.package:
            key = "query_failed"
        else:
            self.show_removal(entry, PKEXEC, [PACMAN, "-R", "--noconfirm", "--", entry.package])
            return
        detail = error_text(error) if error is not None else ""
        self.status.setPlainText(f"{self.t(key)}\n{detail}".strip())

    def show_removal(self, entry, program, arguments):
        dialog = QMessageBox(self)
        dialog.setTextFormat(Qt.TextFormat.PlainText)
        dialog.setWindowTitle(self.t("remove"))
        question = self.t("confirm_package" if self.technical.isChecked() else "confirm")
        details = f"{entry.name} {entry.version}".strip()
        if entry.scope:
            details += f"\nFlatpak · {self.t(entry.scope)}"
        dialog.setText(f"{question}\n\n{details}")
        approve = dialog.addButton(self.t("remove"), QMessageBox.ButtonRole.DestructiveRole)
        cancel = dialog.addButton(word("cancel", self.language), QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(cancel)
        dialog.exec()
        if dialog.clickedButton() is approve:
            self.removing = entry
            self.set_busy(True)
            self.status.clear()
            self.process.start(program, arguments)

    def set_busy(self, busy):
        self.busy = busy
        self.refresh_button.setEnabled(not busy and not self.query.running)
        self.update_actions()
        self.busy_changed.emit(busy)

    def finished(self, code, exit_status):
        output = bytes(self.process.readAllStandardOutput()).decode(errors="replace").strip()
        normal = exit_status == QProcess.ExitStatus.NormalExit
        if normal and code == 0:
            message = word("removed", self.language)
        elif normal and not self.removing.scope and code == 126:
            message = self.t("authorization")
        elif not self.removing.scope and dependency_conflict(output):
            message = self.t("required")
        else:
            message = word("error", self.language)
        self.status.setPlainText(f"{message}\n{output}".strip())
        self.reload()
        self.packages_changed.emit()
        self.set_busy(False)

    def process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.status.setPlainText(f"{word('error', self.language)}\n{self.process.errorString()}")
            self.set_busy(False)
