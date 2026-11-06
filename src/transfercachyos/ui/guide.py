from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..i18n import translator
from ..services.checklist import checklist_snapshot, desktop_name
from ..services.desktop import open_settings, settings_command
from .read_task import ReadTask

text = translator("setup")
migration_text = translator("backup")


class ChecklistPanel(QWidget):
    def __init__(self, language, show_apps):
        super().__init__()
        self.language = language
        self.snapshot = None
        self.query = ReadTask(self)
        self.query.completed.connect(self.loaded)
        layout = QVBoxLayout(self)
        self.intro = QLabel()
        self.intro.setWordWrap(True)
        layout.addWidget(self.intro)
        grid = QGridLayout()
        self.rows = {}
        for index, key in enumerate(("keyboard", "browser", "pdf", "printer", "updates", "backup")):
            title, value = QLabel(), QLabel()
            value.setTextFormat(Qt.TextFormat.PlainText)
            value.setWordWrap(True)
            grid.addWidget(title, index, 0)
            grid.addWidget(value, index, 1)
            self.rows[key] = title, value
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        row = QHBoxLayout()
        self.settings = QPushButton()
        self.keyboard_settings = QPushButton()
        self.apps = QPushButton()
        self.refresh_button = QPushButton()
        self.settings.clicked.connect(lambda: open_settings("general"))
        self.keyboard_settings.clicked.connect(lambda: open_settings("keyboard"))
        self.apps.clicked.connect(show_apps)
        self.refresh_button.clicked.connect(self.refresh)
        for button in (self.keyboard_settings, self.settings, self.apps, self.refresh_button):
            row.addWidget(button)
        layout.addLayout(row)
        layout.addStretch()
        self.render()

    def t(self, key):
        return text(key, self.language)

    def refresh(self):
        if self.query.start(checklist_snapshot):
            self.render()

    def loaded(self, result, error):
        self.snapshot = result if error is None else None
        self.render()

    def render(self):
        values = {}
        if self.snapshot is not None:
            (layouts, default), browser, pdf, printer, queues, updates, restic = self.snapshot
            values = {
                "keyboard": self.t("keyboard_default").format(layouts=layouts) if default else layouts,
                "browser": desktop_name(browser, self.language),
                "pdf": desktop_name(pdf, self.language),
                "printer": queues or self.t(printer),
                "updates": self.t("cached_updates").format(count=updates) if updates is not None else self.t("updates_unknown"),
                "backup": self.t("restic" if restic else "restic_missing"),
            }
        self.intro.setText(self.t("intro"))
        self.settings.setText(self.t("settings"))
        self.keyboard_settings.setText(self.t("keyboard_settings"))
        self.keyboard_settings.setEnabled(settings_command("keyboard") is not None)
        self.settings.setEnabled(settings_command("general") is not None)
        self.apps.setText(self.t("apps"))
        self.refresh_button.setText(self.t("refresh"))
        self.refresh_button.setEnabled(not self.query.running)
        for key, (title, value) in self.rows.items():
            title.setText(self.t(key))
            value.setText(values.get(key) or self.t("loading" if self.query.running else "review"))


class MigrationPanel(QWidget):
    def __init__(self, language, show_apps, show_flathub, show_backup):
        super().__init__()
        self.language = language
        layout = QVBoxLayout(self)
        self.intro = QLabel()
        self.intro.setWordWrap(True)
        layout.addWidget(self.intro)
        self.cards = {}
        for key in ("office", "desktop", "onedrive", "transfer"):
            heading, detail = QLabel(), QLabel()
            font = heading.font()
            font.setBold(True)
            heading.setFont(font)
            heading.setWordWrap(True)
            detail.setWordWrap(True)
            layout.addWidget(heading)
            layout.addWidget(detail)
            layout.addSpacing(8)
            self.cards[key] = heading, detail
        row = QHBoxLayout()
        self.buttons = {}
        for label, callback in (("apps", show_apps), ("Flathub", show_flathub), ("backup", show_backup)):
            button = QPushButton()
            button.clicked.connect(callback)
            row.addWidget(button)
            self.buttons[label] = button
        layout.addLayout(row)
        layout.addStretch()
        self.translate()

    def translate(self):
        self.intro.setText(migration_text("intro", self.language))
        for key, (heading, detail) in self.cards.items():
            heading.setText(migration_text(key, self.language))
            detail.setText(migration_text(f"{key}_note", self.language))
        for key, button in self.buttons.items():
            button.setText(key if key == "Flathub" else migration_text(key, self.language))
