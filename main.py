#!/usr/bin/python3
import codecs
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QLocale, QProcess, QSettings, Signal, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel,
    QPlainTextEdit, QPushButton, QScrollArea, QTabWidget, QVBoxLayout, QWidget,
)

from catalog import APPS, LANGUAGES, TEXT
from system_tools import SystemPanel, word
from installed_apps import PackagePanel, text as installed_text
from setup_tools import ChecklistPanel, FlatpakPanel, text as setup_text
from migration import BackupPanel, MigrationPanel, text as migration_text
from daily import DailyPanel, text as daily_text

PACMAN = "/usr/bin/pacman"
PKEXEC = "/usr/bin/pkexec"
PROFILES = ("custom", "daily", "office", "coding")


def supported_system():
    try:
        release = Path("/etc/os-release").read_text()
    except OSError:
        return False
    return (
        any(line.partition("=")[2].strip('"\'') == "cachyos"
            for line in release.splitlines() if line.startswith("ID="))
        and os.access(PACMAN, os.X_OK)
        and os.access(PKEXEC, os.X_OK)
    )


def read_packages():
    result = subprocess.run(
        [PACMAN, "-Qq"], capture_output=True, text=True, timeout=10, check=True,
    )
    return set(result.stdout.splitlines())


def missing_packages(apps, installed):
    return list(dict.fromkeys(
        package for app in apps for package in app.packages if package not in installed
    ))


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
        self.scan()

    def update_log_visibility(self):
        visible = self.log.document().characterCount() > 1
        self.log.setVisible(visible)
        self.log_label.setVisible(visible)

    def t(self, key):
        return TEXT[key][LANGUAGES.index(self.language)]

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
        self.scan_button.setEnabled(self.supported and not self.busy)
        self.profile_box.setEnabled(not self.busy)

        for app, check, description, status in self.rows:
            description.setText(app.descriptions[LANGUAGES.index(self.language)])
            missing = self.installed is not None and bool(missing_packages([app], self.installed))
            if self.installed is None:
                key = "unknown"
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
        self.status_key = ""
        self.reload_packages()
        self.refresh()

    def reload_packages(self):
        if not self.supported:
            self.status_key = "unsupported"
            return
        try:
            self.installed = read_packages()
        except (OSError, subprocess.SubprocessError) as error:
            self.installed = None
            self.status_key = "scan_error"
            self.log.appendPlainText(str(getattr(error, "stderr", None) or error))

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
            not self.busy and self.installed is not None and bool(self.selected_apps())
        )

    def show_plan(self):
        selected = self.selected_apps()
        self.reload_packages()
        self.refresh()
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
        self.attempted.clear()
        self.installing = selected
        self.busy = True
        self.busy_changed.emit(True)
        self.status_key = "running"
        self.log.clear()
        self.decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self.refresh()
        self.process.start(PKEXEC, [PACMAN, "-Syu", "--needed", "--noconfirm", "--", *packages])

    def read_output(self, final=False):
        chunk = bytes(self.process.readAllStandardOutput())
        text = self.decoder.decode(chunk, final=final)
        self.log.moveCursor(QTextCursor.MoveOperation.End)
        self.log.insertPlainText(text)
        self.log.ensureCursorVisible()

    def finished(self, code, exit_status):
        self.read_output(final=True)
        self.busy = False
        normal_exit = exit_status == QProcess.ExitStatus.NormalExit
        if normal_exit and code == 126:
            self.status_key = "auth"
        else:
            self.status_key = "done" if normal_exit and code == 0 else "failure"
        self.reload_packages()
        if self.installed is not None and self.status_key != "auth":
            self.attempted = {
                app.name for app in self.installing if missing_packages([app], self.installed)
            }
            if self.attempted:
                self.status_key = "failure"
        self.refresh()
        self.busy_changed.emit(False)

    def process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.log.appendPlainText(self.process.errorString())
            self.busy = False
            self.status_key = "failure"
            self.refresh()
            self.busy_changed.emit(False)

class MainWindow(QTabWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TransferCachyOS")
        self.resize(840, 700)
        self.setDocumentMode(True)
        self.tabBar().setStyleSheet("QTabBar::tab { padding: 8px 13px; }")
        self.installer = TransferWindow()
        self.setCornerWidget(self.installer.language_box, Qt.Corner.TopRightCorner)
        self.system = SystemPanel(self.installer.language)
        self.packages = PackagePanel(self.installer.language)
        self.checklist = ChecklistPanel(self.installer.language, lambda: self.open_panel(self.installer))
        self.flatpak = FlatpakPanel(self.installer.language)
        self.backup = BackupPanel(self.installer.language, self.show_restic)
        self.daily = DailyPanel(
            self.installer.language, self.system, self.backup, self.flatpak,
            self.show_backup, lambda: self.open_panel(self.system),
        )
        self.system.charge_completed.connect(self.daily.laptop_status.setText)
        self.migration = MigrationPanel(
            self.installer.language,
            lambda: self.open_panel(self.installer),
            lambda: self.open_panel(self.flatpak),
            self.show_backup,
        )
        self.application_pages = self.group(
            self.installer, self.flatpak, self.packages, self.daily.pages["updates"],
        )
        self.system_pages = self.group(
            self.system, self.daily.pages["storage"], self.daily.pages["laptop"], self.daily.pages["devices"],
        )
        self.guide_pages = self.group(self.checklist, self.migration)
        for page in (self.daily, self.application_pages, self.system_pages, self.backup, self.guide_pages):
            self.addTab(page, "")
        self.translate(self.installer.language)
        self.installer.language_changed.connect(self.translate)
        self.installer.busy_changed.connect(self.sync_app_tabs)
        self.packages.busy_changed.connect(self.sync_app_tabs)
        self.flatpak.busy_changed.connect(self.sync_app_tabs)
        self.packages.packages_changed.connect(self.installer.scan)
        self.packages.packages_changed.connect(self.flatpak.reload)
        self.currentChanged.connect(self.refresh_tab)
        self.refresh_tab()

    def group(self, *pages):
        group = QTabWidget()
        group.setDocumentMode(True)
        for page in pages:
            group.addTab(page, "")
        group.currentChanged.connect(self.refresh_tab)
        return group

    def translate(self, language):
        labels = (
            (self, self.daily, daily_text("today", language)),
            (self, self.application_pages, word("apps", language)),
            (self, self.system_pages, word("system", language)),
            (self, self.backup, migration_text("backup", language)),
            (self, self.guide_pages, setup_text("guide", language)),
            (self.application_pages, self.installer, setup_text("install_apps", language)),
            (self.application_pages, self.flatpak, "Flathub"),
            (self.application_pages, self.packages, installed_text("title", language)),
            (self.application_pages, self.daily.pages["updates"], daily_text("updates", language)),
            (self.system_pages, self.system, word("power", language)),
            (self.system_pages, self.daily.pages["storage"], daily_text("storage", language)),
            (self.system_pages, self.daily.pages["laptop"], daily_text("laptop", language)),
            (self.system_pages, self.daily.pages["devices"], daily_text("devices", language)),
            (self.guide_pages, self.checklist, setup_text("setup", language)),
            (self.guide_pages, self.migration, migration_text("migration", language)),
        )
        for group, page, label in labels:
            group.setTabText(group.indexOf(page), label)
        for panel in (self.checklist, self.flatpak, self.system, self.packages, self.migration, self.backup, self.daily):
            panel.language = language
        self.checklist.refresh()
        self.flatpak.render()
        self.packages.translate()
        self.system.refresh()
        self.migration.translate()
        self.backup.refresh()
        self.daily.refresh()

    def open_panel(self, panel):
        for group in (self.application_pages, self.system_pages, self.guide_pages):
            index = group.indexOf(panel)
            if index >= 0:
                if group.isTabEnabled(index):
                    group.setCurrentIndex(index)
                    self.setCurrentWidget(group)
                return
        self.setCurrentWidget(panel)

    def show_backup(self):
        self.open_panel(self.backup)
        self.backup.pages.setCurrentIndex(0)
        self.backup.restore_recipe()

    def show_restic(self):
        self.open_panel(self.installer)
        for app, check, _, _ in self.installer.rows:
            if app.packages == ("restic",) and check.isEnabled():
                check.setChecked(True)
                check.setFocus()
                break

    def sync_app_tabs(self):
        for panel, enabled in (
            (self.installer, not self.packages.busy),
            (self.flatpak, not self.packages.busy),
            (self.packages, not self.installer.busy and not self.flatpak.busy),
        ):
            self.application_pages.setTabEnabled(self.application_pages.indexOf(panel), enabled)

    def refresh_tab(self):
        panel = self.currentWidget()
        if panel in (self.application_pages, self.system_pages, self.guide_pages):
            panel = panel.currentWidget()
        if panel is self.packages and not panel.busy:
            panel.reload()
        elif panel is self.flatpak and not panel.busy:
            panel.reload()
        elif panel in (self.daily, self.system, self.checklist, self.backup):
            panel.refresh()
        elif panel is self.daily.pages["devices"]:
            self.daily.refresh_audio()
        elif panel is self.daily.pages["laptop"]:
            self.daily.tick()

    def closeEvent(self, event):
        if any(panel.busy for panel in (self.installer, self.packages, self.flatpak, self.backup, self.system, self.daily)):
            event.ignore()
        else:
            event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("TransferCachyOS")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
