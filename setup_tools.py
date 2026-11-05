import ast
import configparser
import os
import re
import shlex
import subprocess
from pathlib import Path

from PySide6.QtCore import QProcess, QStandardPaths, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QGridLayout, QHBoxLayout, QLabel, QMessageBox,
    QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

from catalog import LANGUAGES
from desktop_settings import desktop_family, open_settings, settings_command
from system_tools import PACMAN, command

FLATPAK = "/usr/bin/flatpak"
SCOPES = ("user", "system")
FLATHUB_URLS = {"https://dl.flathub.org/repo", "https://flathub.org/repo"}
FLATHUB_APPS = (
    ("org.onlyoffice.desktopeditors", "ONLYOFFICE", "office"),
    ("net.cozic.joplin_desktop", "Joplin", "notes"),
    ("org.localsend.localsend_app", "LocalSend", "share"),
)

TEXT = {
    "guide": ("Rehber", "Guide", "Guide", "Leitfaden"),
    "install_apps": ("Uygulama kur", "Install apps", "Installer des applications", "Apps installieren"),
    "setup": ("Başlangıç", "Getting started", "Premiers pas", "Erste Schritte"),
    "intro": ("Bilgisayarında hazır olanları ve ilk ayarları gözden geçir.",
              "Review what is ready and what needs setting up.",
              "Vérifiez les éléments prêts et ceux à configurer.",
              "Prüfe, was bereit ist und was noch eingerichtet werden muss."),
    "keyboard": ("Klavye düzeni", "Keyboard layout", "Disposition du clavier", "Tastaturlayout"),
    "keyboard_default": ("Sistem varsayılanı: {layouts}", "System default: {layouts}",
                         "Valeur système : {layouts}", "Systemstandard: {layouts}"),
    "keyboard_settings": ("Klavye ayarları", "Keyboard settings", "Paramètres du clavier", "Tastatureinstellungen"),
    "printer_missing": ("Yazıcı sorgulama aracı kurulu değil.", "The printer query tool is missing.",
                        "L’outil de détection des imprimantes est absent.", "Das Programm zur Druckerabfrage fehlt."),
    "printer_none": ("Yapılandırılmış yazıcı yok.", "No printers configured.",
                     "Aucune imprimante configurée.", "Keine Drucker eingerichtet."),
    "printer_unknown": ("Yazıcı hizmetinden bilgi alınamadı.", "Could not query the printing service.",
                        "Impossible d’interroger le service d’impression.", "Der Druckdienst konnte nicht abgefragt werden."),
    "updates_unknown": ("Yerel paket listesi okunamadı.", "Could not read the local package list.",
                        "Impossible de lire la liste locale des paquets.", "Die lokale Paketliste konnte nicht gelesen werden."),
    "restic_missing": ("Restic kurulu değil.", "Restic is not installed.",
                       "Restic n’est pas installé.", "Restic ist nicht installiert."),
    "browser": ("Varsayılan tarayıcı", "Default browser", "Navigateur par défaut", "Standardbrowser"),
    "pdf": ("Varsayılan PDF okuyucu", "Default PDF reader", "Lecteur PDF par défaut", "Standard-PDF-Programm"),
    "printer": ("Yazıcı", "Printer", "Imprimante", "Drucker"),
    "updates": ("Sistem güncellemeleri", "System updates", "Mises à jour système", "Systemaktualisierungen"),
    "cached_updates": ("Yerel paket listesine göre {count} güncelleme",
                       "{count} updates in the local package list",
                       "{count} mises à jour dans la liste locale",
                       "{count} Aktualisierungen laut lokaler Paketliste"),
    "backup": ("Dosya yedekleme", "File backup", "Sauvegarde des fichiers", "Dateisicherung"),
    "restic": ("Restic kurulu. Yedek hedefini kontrol et.",
               "Restic is installed. Check the backup destination.",
               "Restic est installé. Vérifiez la destination de sauvegarde.",
               "Restic ist installiert. Sicherungsziel prüfen."),
    "backup_review": ("Yedek hedefi doğrulanmadı.", "Backup destination not verified.",
                      "Destination de sauvegarde non vérifiée.", "Sicherungsziel nicht überprüft."),
    "review": ("Kontrol et", "Review", "À vérifier", "Prüfen"),
    "settings": ("Masaüstü ayarları", "Desktop settings", "Paramètres du bureau", "Desktop-Einstellungen"),
    "apps": ("Uygulamalar", "Apps", "Applications", "Anwendungen"),
    "refresh": ("Yenile", "Refresh", "Actualiser", "Aktualisieren"),
    "open": ("Aç", "Open", "Ouvrir", "Öffnen"),
    "ready": ("Kurulu", "Installed", "Installé", "Installiert"),
    "missing": ("Kurulabilir", "Available", "Disponible", "Verfügbar"),
    "unknown": ("Durum bilinmiyor", "Status unknown", "État inconnu", "Status unbekannt"),
    "office": ("Word, Excel ve PowerPoint dosyaları için ofis paketi.",
               "Office suite for Word, Excel and PowerPoint files.",
               "Suite bureautique pour les fichiers Word, Excel et PowerPoint.",
               "Office-Paket für Word-, Excel- und PowerPoint-Dateien."),
    "notes": ("Notlar ve yapılacaklar listesi.", "Notes and to-do lists.",
              "Notes et listes de tâches.", "Notizen und Aufgabenlisten."),
    "share": ("Aynı ağdaki cihazlar arasında dosya gönder.",
              "Send files between devices on the same network.",
              "Envoyez des fichiers entre appareils sur le même réseau.",
              "Dateien zwischen Geräten im selben Netzwerk senden."),
    "source": ("Kaynak: Flathub • Kurulum: {scope}", "Source: Flathub • Installation: {scope}",
               "Source : Flathub • Installation : {scope}", "Quelle: Flathub • Installation: {scope}"),
    "user": ("Yalnızca bu kullanıcı", "Current user", "Utilisateur actuel", "Aktueller Benutzer"),
    "system": ("Tüm kullanıcılar", "All users", "Tous les utilisateurs", "Alle Benutzer"),
    "no_source": ("Etkin bir Flathub kaynağı bulunamadı.",
                  "No enabled Flathub remote was found.",
                  "Aucun dépôt Flathub actif n’a été trouvé.",
                  "Keine aktive Flathub-Quelle gefunden."),
    "install": ("Seçilenleri kur", "Install selected", "Installer la sélection", "Auswahl installieren"),
    "plan": ("Uygulamalar Flathub’dan kurulacak. Gerekli çalışma ortamları da indirilebilir.",
             "Apps will be installed from Flathub. Required runtimes may also be downloaded.",
             "Les applications seront installées depuis Flathub. Les environnements requis pourront aussi être téléchargés.",
             "Die Apps werden von Flathub installiert. Benötigte Laufzeitumgebungen können ebenfalls heruntergeladen werden."),
    "cancel": ("Vazgeç", "Cancel", "Annuler", "Abbrechen"),
    "running": ("Kurulum sürüyor…", "Installation in progress…", "Installation en cours…", "Installation läuft…"),
    "done": ("Kurulum tamamlandı.", "Installation complete.", "Installation terminée.", "Installation abgeschlossen."),
    "error": ("İşlem tamamlanamadı. Ayrıntıları aşağıda görebilirsin.",
              "The operation did not complete. See the details below.",
              "L’opération n’a pas abouti. Consultez les détails ci-dessous.",
              "Der Vorgang wurde nicht abgeschlossen. Details stehen unten."),
}


def text(key, language):
    return TEXT[key][LANGUAGES.index(language)]


def probe(*args):
    try:
        return command(*args)
    except (OSError, subprocess.SubprocessError):
        return ""


def read_config(path):
    config = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        config.read(path, encoding="utf-8")
    except (configparser.Error, OSError, UnicodeError):
        config.clear()
    return config


def format_layouts(layouts, variants):
    variant_codes = variants.split(",")
    result = []
    for index, code in enumerate(layouts.split(",")):
        code = code.strip()
        if re.fullmatch(r"[A-Za-z0-9_+-]+", code):
            variant = variant_codes[index].strip() if index < len(variant_codes) else ""
            result.append(f"{code} ({variant})" if variant else code)
    return ", ".join(result)


def shell_settings(path):
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return {}
    result = {}
    for line in lines:
        key, _, value = line.partition("=")
        if key.strip() in ("XKBLAYOUT", "XKBVARIANT"):
            try:
                parts = shlex.split(value, comments=True)
            except ValueError:
                continue
            result[key.strip()] = parts[0] if parts else ""
    return result


def keyboard_layout():
    desktop = desktop_family()
    if desktop == "kde":
        config_dir = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
        config = read_config(config_dir / "kxkbrc")
        if config.get("Layout", "Use", fallback="").strip().casefold() in ("true", "yes", "on", "1"):
            layout = format_layouts(
                config.get("Layout", "LayoutList", fallback=""),
                config.get("Layout", "VariantList", fallback=""),
            )
            if layout:
                return layout, False
    elif desktop == "gnome":
        raw = probe("/usr/bin/gsettings", "get", "org.gnome.desktop.input-sources", "sources")
        try:
            sources = ast.literal_eval(raw.removeprefix("@a(ss) "))
            if isinstance(sources, list):
                layouts = []
                for kind, identifier in sources:
                    if kind == "xkb" and isinstance(identifier, str):
                        name, _, variant = identifier.partition("+")
                        layout = format_layouts(name, variant)
                        if layout:
                            layouts.append(layout)
                if layouts:
                    return ", ".join(layouts), False
        except (ValueError, SyntaxError, TypeError):
            pass

    if os.environ.get("XDG_SESSION_TYPE") == "x11":
        x11 = dict(line.split(":", 1) for line in probe("/usr/bin/setxkbmap", "-query").splitlines() if ":" in line)
        layout = format_layouts(x11.get("layout", ""), x11.get("variant", ""))
        if layout:
            return layout, False

    layout = format_layouts(os.environ.get("XKB_DEFAULT_LAYOUT", ""), os.environ.get("XKB_DEFAULT_VARIANT", ""))
    if layout:
        return layout, True

    try:
        xorg = Path("/etc/X11/xorg.conf.d/00-keyboard.conf").read_text(encoding="utf-8")
        options = dict(re.findall(r'(?im)^\s*Option\s+"(XkbLayout|XkbVariant)"\s+"([^"]*)"', xorg))
        options = {key.casefold(): value for key, value in options.items()}
        layout = format_layouts(options.get("xkblayout", ""), options.get("xkbvariant", ""))
        if layout:
            return layout, True
    except (OSError, UnicodeError):
        pass
    for path in (Path("/etc/default/keyboard"), Path("/etc/vconsole.conf")):
        values = shell_settings(path)
        layout = format_layouts(values.get("XKBLAYOUT", ""), values.get("XKBVARIANT", ""))
        if layout:
            return layout, True
    return "", False


def desktop_name(app_id, language):
    if not app_id or "/" in app_id:
        return app_id
    path = QStandardPaths.locate(QStandardPaths.StandardLocation.GenericDataLocation, f"applications/{app_id}")
    if not path:
        return app_id
    config = read_config(path)
    name = config.get("Desktop Entry", "Name", fallback=app_id)
    return config.get("Desktop Entry", f"Name[{language}]", fallback=name)


def update_count():
    try:
        return len(command(PACMAN, "-Qu").splitlines())
    except subprocess.CalledProcessError as error:
        if error.returncode == 1 and not error.stdout and not error.stderr:
            return 0
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def flatpak_state():
    installed = {}
    available_scopes = []
    for scope in SCOPES:
        try:
            output = command(FLATPAK, "list", f"--{scope}", "--app", "--columns=application")
            for app_id in output.splitlines():
                installed.setdefault(app_id, scope)
        except (OSError, subprocess.SubprocessError):
            continue
        remotes = probe(FLATPAK, "remotes", f"--{scope}", "--columns=name,options,url")
        for line in remotes.splitlines():
            columns = line.split("\t")
            if len(columns) != 3:
                continue
            name, options, url = (column.strip() for column in columns)
            if name == "flathub" and "disabled" not in options.split(",") and url.rstrip("/") in FLATHUB_URLS:
                available_scopes.append(scope)
                break
    return installed, next(iter(available_scopes), None)


class ChecklistPanel(QWidget):
    def __init__(self, language, show_apps):
        super().__init__()
        self.language = language
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
        self.refresh()

    def t(self, key):
        return text(key, self.language)

    def refresh(self):
        layouts, default = keyboard_layout()
        keyboard = self.t("keyboard_default").format(layouts=layouts) if default else layouts
        updates = update_count()
        printer = self.t("printer_missing")
        if os.access("/usr/bin/lpstat", os.X_OK):
            try:
                queues = command("/usr/bin/lpstat", "-e").splitlines()
                printer = ", ".join(queues) or self.t("printer_none")
            except (OSError, subprocess.SubprocessError):
                printer = self.t("printer_unknown")
        values = {
            "keyboard": keyboard,
            "browser": desktop_name(probe("/usr/bin/xdg-settings", "get", "default-web-browser"), self.language),
            "pdf": desktop_name(probe("/usr/bin/xdg-mime", "query", "default", "application/pdf"), self.language),
            "printer": printer,
            "updates": self.t("cached_updates").format(count=updates) if updates is not None else self.t("updates_unknown"),
            "backup": self.t("restic") if probe(PACMAN, "-Q", "restic") else self.t("restic_missing"),
        }
        self.intro.setText(self.t("intro"))
        self.settings.setText(self.t("settings"))
        self.keyboard_settings.setText(self.t("keyboard_settings"))
        self.keyboard_settings.setEnabled(settings_command("keyboard") is not None)
        self.settings.setEnabled(settings_command("general") is not None)
        self.apps.setText(self.t("apps"))
        self.refresh_button.setText(self.t("refresh"))
        for key, (title, value) in self.rows.items():
            title.setText(self.t(key))
            value.setText(values[key] or self.t("review"))


class FlatpakPanel(QWidget):
    busy_changed = Signal(bool)

    def __init__(self, language):
        super().__init__()
        self.language = language
        self.busy = False
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
        self.refresh_button.clicked.connect(self.reload)
        self.install_button.clicked.connect(self.preview)
        actions.addWidget(self.refresh_button)
        actions.addStretch()
        actions.addWidget(self.install_button)
        layout.addLayout(actions)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log, 1)
        self.reload()

    def t(self, key):
        return text(key, self.language)

    def reload(self):
        self.installed, self.scope = flatpak_state()
        self.render()

    def render(self):
        self.source.setText(self.t("source").format(scope=self.t(self.scope)) if self.scope else self.t("no_source"))
        self.refresh_button.setText(self.t("refresh"))
        self.refresh_button.setEnabled(not self.busy)
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
        self.install_button.setEnabled(bool(self.scope and self.selected()) and not self.busy)

    def preview(self):
        if self.busy:
            return
        self.reload()
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
        output = bytes(self.process.readAllStandardOutput()).decode(errors="replace").strip()
        self.busy = False
        self.reload()
        ok = (exit_status == QProcess.ExitStatus.NormalExit and code == 0
              and all(ref in self.installed for ref in self.targets))
        self.log.setPlainText(f"{self.t('done' if ok else 'error')}\n{output}".strip())
        self.busy_changed.emit(False)

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
