from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QMessageBox, QTabWidget

from ..i18n import translator
from .backup import BackupPanel
from .flathub import FlatpakPanel
from .guide import ChecklistPanel, MigrationPanel
from .installed_apps import PackagePanel
from .installer import TransferWindow
from .system import SystemPanel
from .today import DailyPanel

daily_text = translator("daily")
installed_text = translator("installed")
migration_text = translator("backup")
setup_text = translator("setup")
word = translator("system")


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
        self.system.profiles_changed.connect(self.daily.load_profiles)
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
        self.checklist.render()
        self.flatpak.render()
        self.packages.translate()
        self.system.render()
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
        if self.currentWidget() is self.application_pages and self.application_pages.currentWidget() is self.installer:
            self.installer.select_package("restic")

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
        elif panel is self.daily:
            panel.refresh()
            if self.system.power_state is None:
                self.system.refresh()
            if not self.flatpak.loaded_once:
                self.flatpak.reload()
        elif panel is self.installer and self.installer.installed is None:
            self.installer.scan()
        elif panel in (self.system, self.checklist, self.backup):
            panel.refresh()
        elif panel is self.daily.pages["devices"]:
            self.daily.refresh_audio()
        elif panel is self.daily.pages["laptop"]:
            self.daily.tick()

    def closeEvent(self, event):
        mutations = (self.installer, self.packages, self.flatpak, self.system)
        if any(panel.busy for panel in mutations) or (self.backup.busy and not self.backup.read_only):
            event.ignore()
            QMessageBox.information(self, "TransferCachyOS", word("busy_close", self.installer.language))
            return
        if self.daily.busy or self.backup.busy:
            event.ignore()
            self.daily.cancel_jobs()
            self.backup.cancel_operation()
            QTimer.singleShot(100, self.close)
            return
        event.accept()
