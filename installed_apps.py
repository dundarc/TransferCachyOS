import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QProcess, Signal, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
    QPushButton, QStyle, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from catalog import APPS, LANGUAGES
from setup_tools import FLATPAK, SCOPES, read_config
from system_tools import PACMAN, PKEXEC, PROTECTED, command, error_text, removable, word

APP_DIR = Path("/usr/share/applications")
APP_NAMES = {app.packages[0]: app.name for app in APPS}
PREFERRED_LAUNCHERS = {"libreoffice-fresh": "libreoffice-startcenter.desktop",
                       "libreoffice-still": "libreoffice-startcenter.desktop"}

TEXT = {
    "title": ("Yüklü uygulamalar", "Installed apps", "Applications installées", "Installierte Apps"),
    "name": ("Uygulama", "App", "Application", "Anwendung"),
    "package": ("Paket", "Package", "Paquet", "Paket"),
    "version": ("Sürüm", "Version", "Version", "Version"),
    "source": ("Kaynak", "Source", "Source", "Quelle"),
    "system": ("Sistem", "System", "Système", "System"),
    "user": ("Kullanıcı", "User", "Utilisateur", "Benutzer"),
    "search": ("Uygulama ara", "Search apps", "Rechercher une application", "Apps suchen"),
    "technical": ("Teknik paketleri göster", "Show technical packages", "Afficher les paquets techniques", "Technische Pakete anzeigen"),
    "intro": ("Yüklü bir uygulamayı seçerek açabilir veya kaldırabilirsin.",
              "Select an installed app to open or uninstall it.",
              "Sélectionnez une application installée pour l’ouvrir ou la désinstaller.",
              "Wähle eine installierte App zum Öffnen oder Deinstallieren."),
    "empty": ("Eşleşen uygulama bulunamadı.", "No matching apps.", "Aucune application correspondante.", "Keine passenden Apps gefunden."),
    "empty_packages": ("Eşleşen paket bulunamadı.", "No matching packages.", "Aucun paquet correspondant.", "Keine passenden Pakete gefunden."),
    "open": ("Aç", "Open", "Ouvrir", "Öffnen"),
    "remove": ("Kaldır", "Uninstall", "Désinstaller", "Deinstallieren"),
    "confirm": ("Bu uygulama kaldırılsın mı?", "Uninstall this app?", "Désinstaller cette application ?", "Diese App deinstallieren?"),
    "confirm_package": ("Bu paket kaldırılsın mı?", "Remove this package?", "Supprimer ce paquet ?", "Dieses Paket entfernen?"),
    "blocked": ("Bu öğe bir sistem bileşeni veya bağımlılık olarak yönetiliyor.",
                "This item is managed as a system component or dependency.",
                "Cet élément est géré comme composant système ou dépendance.",
                "Dieser Eintrag wird als Systemkomponente oder Abhängigkeit verwaltet."),
    "required": ("Başka paketler bu öğeyi kullanıyor. Kaldırma yapılamadı.",
                 "Other packages require this item. It could not be removed.",
                 "D’autres paquets utilisent cet élément. Sa suppression a échoué.",
                 "Andere Pakete benötigen diesen Eintrag. Er konnte nicht entfernt werden."),
}


def text(key, language):
    return TEXT[key][LANGUAGES.index(language)]


@dataclass(frozen=True)
class Entry:
    package: str
    version: str
    name: str
    launcher: str = ""
    icon: str = ""
    scope: str = ""


def desktop_entry(path, desktops, language):
    config = read_config(path)
    if not config.has_section("Desktop Entry"):
        return None
    data = config["Desktop Entry"]
    if data.get("Type") != "Application" or not data.get("Exec"):
        return None
    if any(data.get(key, "").casefold() in ("true", "1") for key in ("Hidden", "NoDisplay")):
        return None
    allowed = set(data.get("OnlyShowIn", "").casefold().split(";")) - {""}
    excluded = set(data.get("NotShowIn", "").casefold().split(";")) - {""}
    if (allowed and not allowed.intersection(desktops)) or excluded.intersection(desktops):
        return None
    name = data.get(f"Name[{language}]", data.get("Name", "")).strip()
    if name:
        return name, data.get("Icon", "")


def native_entries(versions, explicit, listing, language):
    desktops = set(os.environ.get("XDG_CURRENT_DESKTOP", "").casefold().split(":"))
    grouped = {}
    for line in listing.splitlines():
        package, _, filename = line.partition(" ")
        if package not in versions or package not in explicit or package in PROTECTED or not filename.endswith(".desktop"):
            continue
        path = Path(filename)
        if path.parent != APP_DIR:
            continue
        details = desktop_entry(path, desktops, language)
        if details is None:
            continue
        name, icon = details
        rank = (path.name != PREFERRED_LAUNCHERS.get(package),
                path.stem.casefold().split(".")[-1] != package.casefold(),
                name.casefold())
        entry = Entry(package, versions[package], APP_NAMES.get(package, name), str(path), icon)
        if package not in grouped or rank < grouped[package][0]:
            grouped[package] = rank, entry
    return [entry for _, entry in grouped.values()]


def flatpak_entries():
    apps = []
    for scope in SCOPES:
        try:
            output = command(FLATPAK, "list", f"--{scope}", "--app", "--columns=application,name,version")
        except (OSError, subprocess.SubprocessError):
            continue
        for line in output.splitlines():
            app_id, _, rest = line.partition("\t")
            name, _, version = rest.partition("\t")
            if app_id:
                apps.append(Entry(app_id, version, name or app_id, icon=app_id, scope=scope))
    return apps


class PackagePanel(QWidget):
    busy_changed = Signal(bool)
    packages_changed = Signal()

    def __init__(self, language):
        super().__init__()
        self.language = language
        self.busy = False
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
        self.versions = {}
        self.explicit = set()
        self.native_listing = ""
        try:
            self.versions = dict(line.split(maxsplit=1) for line in command(PACMAN, "-Q").splitlines())
            self.explicit = set(command(PACMAN, "-Qqe").splitlines())
            self.native_listing = "\n".join(
                line for line in command(PACMAN, "-Ql").splitlines()
                if line.endswith(".desktop") and f" {APP_DIR}/" in line
            )
        except (OSError, subprocess.SubprocessError) as error:
            self.status.setPlainText(f"{word('error', self.language)}\n{error_text(error)}")
        self.apps = native_entries(self.versions, self.explicit, self.native_listing, self.language)
        self.flatpaks = flatpak_entries()
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
        self.empty.setText(self.t("empty_packages" if technical else "empty"))
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
        self.remove.setEnabled(not self.busy and self.can_remove(entry))
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
        if entry.scope:
            program = FLATPAK
            arguments = ["uninstall", f"--{entry.scope}", "--app", "--assumeyes", entry.package]
        else:
            try:
                plan = command(PACMAN, "-R", "--print", "--print-format", "%n", "--", entry.package)
            except (OSError, subprocess.SubprocessError) as error:
                self.status.setPlainText(f"{self.t('required')}\n{error_text(error)}")
                return
            if plan != entry.package:
                self.status.setPlainText(word("error", self.language))
                return
            program = PKEXEC
            arguments = [PACMAN, "-R", "--noconfirm", "--", entry.package]
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
            self.set_busy(True)
            self.status.clear()
            self.process.start(program, arguments)

    def set_busy(self, busy):
        self.busy = busy
        self.refresh_button.setEnabled(not busy)
        self.update_actions()
        self.busy_changed.emit(busy)

    def finished(self, code, exit_status):
        output = bytes(self.process.readAllStandardOutput()).decode(errors="replace").strip()
        ok = code == 0 and exit_status == QProcess.ExitStatus.NormalExit
        self.status.setPlainText(f"{word('removed' if ok else 'error', self.language)}\n{output}".strip())
        self.reload()
        self.packages_changed.emit()
        self.set_busy(False)

    def process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.status.setPlainText(f"{word('error', self.language)}\n{self.process.errorString()}")
            self.set_busy(False)
