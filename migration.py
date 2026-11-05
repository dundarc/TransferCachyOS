import codecs
import json
import os
import re
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QProcess, QProcessEnvironment, QSettings, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QPlainTextEdit, QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

from catalog import LANGUAGES

RESTIC = "/usr/bin/restic"

TEXT = {
    "migration": ("Windows’tan geçiş", "Moving from Windows", "Quitter Windows", "Wechsel von Windows"),
    "backup": ("Yedekleme", "Backup", "Sauvegarde", "Datensicherung"),
    "intro": ("Windows’ta yaptığın işe göre CachyOS’ta nereden başlayacağını bul.",
              "Find where to start on CachyOS based on what you did on Windows.",
              "Trouvez vos repères sur CachyOS selon vos usages sous Windows.",
              "Finde je nach bisheriger Aufgabe den passenden Einstieg in CachyOS."),
    "office": ("Office dosyaları → LibreOffice veya ONLYOFFICE",
               "Office files → LibreOffice or ONLYOFFICE",
               "Fichiers Office → LibreOffice ou ONLYOFFICE",
               "Office-Dateien → LibreOffice oder ONLYOFFICE"),
    "office_note": ("Önemli belgelerin görünümünü ve Excel makrolarını geçişten önce kontrol et.",
                    "Check the layout of important documents and test Excel macros before switching.",
                    "Vérifiez la mise en page des documents importants et testez les macros Excel avant la migration.",
                    "Prüfe das Layout wichtiger Dokumente und teste Excel-Makros vor dem Wechsel."),
    "desktop": ("Dosya Gezgini, ZIP ve ekran alıntısı → Dolphin, Ark ve Spectacle",
                "File Explorer, ZIP and Snipping Tool → Dolphin, Ark and Spectacle",
                "Explorateur, ZIP et capture d’écran → Dolphin, Ark et Spectacle",
                "Datei-Explorer, ZIP und Snipping Tool → Dolphin, Ark und Spectacle"),
    "desktop_note": ("Bu araçları KDE uygulama menüsünde adlarıyla ara.",
                     "Search for these tools by name in the KDE application menu.",
                     "Recherchez ces outils par leur nom dans le menu KDE.",
                     "Suche diese Werkzeuge im KDE-Anwendungsmenü nach Namen."),
    "onedrive": ("OneDrive → Önce dosyalarının nerede olduğunu kontrol et",
                 "OneDrive → Check where your files are stored",
                 "OneDrive → Vérifiez où sont stockés vos fichiers",
                 "OneDrive → Prüfe, wo deine Dateien gespeichert sind"),
    "onedrive_note": ("Windows’ta yalnızca çevrimiçi duran dosyaları yerel bir yedeğe dahil etmeden önce indir.",
                      "Download online-only files on Windows before including them in a local backup.",
                      "Téléchargez les fichiers uniquement en ligne sous Windows avant de les sauvegarder localement.",
                      "Lade unter Windows reine Onlinedateien vor einer lokalen Sicherung herunter."),
    "transfer": ("Dosya aktarımı → Harici disk veya LocalSend",
                 "File transfer → External drive or LocalSend",
                 "Transfert de fichiers → Disque externe ou LocalSend",
                 "Dateiübertragung → Externes Laufwerk oder LocalSend"),
    "transfer_note": ("LocalSend ile aynı ağdaki cihazlardan dosya gönder. Aktarımdan sonra önemli dosyaları açıp kontrol et.",
                      "Use LocalSend to send files over the same network. Open important files after transferring them.",
                      "Utilisez LocalSend sur le même réseau. Ouvrez les fichiers importants après le transfert.",
                      "Übertrage Dateien im selben Netzwerk mit LocalSend. Öffne wichtige Dateien nach der Übertragung."),
    "apps": ("Uygulamaları göster", "Show apps", "Afficher les applications", "Anwendungen anzeigen"),
    "backup_intro": ("Kaynak klasörleri ve yedek için ayrı bir hedef seç. Harici diskte özel bir klasör kullanabilirsin.",
                     "Choose source folders and a separate backup destination. You can use a dedicated folder on an external drive.",
                     "Choisissez les dossiers source et une destination distincte. Un dossier dédié sur un disque externe convient.",
                     "Wähle Quellordner und ein getrenntes Sicherungsziel, etwa einen eigenen Ordner auf einem externen Laufwerk."),
    "add": ("Kaynak klasör ekle", "Add source folder", "Ajouter un dossier source", "Quellordner hinzufügen"),
    "remove": ("Seçimi çıkar", "Remove selection", "Retirer la sélection", "Auswahl entfernen"),
    "target": ("Yedek hedefi seç", "Choose backup destination", "Choisir la destination", "Sicherungsziel wählen"),
    "password": ("Yedek parolası", "Backup password", "Mot de passe de sauvegarde", "Sicherungspasswort"),
    "repeat": ("Parolayı tekrar yaz", "Repeat password", "Confirmer le mot de passe", "Passwort wiederholen"),
    "preview": ("Yedekleme planı", "Backup plan", "Plan de sauvegarde", "Sicherungsplan"),
    "new_backup": ("Yeni yedek", "New backup", "Nouvelle sauvegarde", "Neue Sicherung"),
    "start": ("Yedekle", "Back up", "Sauvegarder", "Sichern"),
    "cancel": ("Vazgeç", "Cancel", "Annuler", "Abbrechen"),
    "missing": ("Restic gerekli. Uygulamalar sekmesinden kurabilirsin.",
                "Restic is required. You can install it from the Apps tab.",
                "Restic est nécessaire. Installez-le depuis l’onglet Applications.",
                "Restic wird benötigt. Installiere es über den Reiter Anwendungen."),
    "invalid": ("Var olan kaynak ve hedef klasörleri seç. Hedef, bir kaynakla aynı ya da iç içe olamaz.",
                "Choose existing source and destination folders. They must not overlap.",
                "Choisissez des dossiers source et une destination existants et distincts.",
                "Wähle vorhandene Quell- und Zielordner, die sich nicht überschneiden."),
    "target_error": ("Hedef boş bir klasör veya mevcut bir Restic deposu olmalı.",
                     "The destination must be an empty folder or an existing Restic repository.",
                     "La destination doit être vide ou contenir un dépôt Restic existant.",
                     "Das Ziel muss leer sein oder ein vorhandenes Restic-Repository enthalten."),
    "bad_password": ("Parolayı gir. Yeni depo için iki parola aynı olmalı.",
                     "Enter the password. Both entries must match for a new repository.",
                     "Saisissez le mot de passe. Les deux saisies doivent correspondre pour un nouveau dépôt.",
                     "Gib das Passwort ein. Für ein neues Repository müssen beide Eingaben übereinstimmen."),
    "new": ("Yeni şifreli depo oluşturulacak. Parolanı sakla. Parola olmadan yedek açılamaz.",
            "A new encrypted repository will be created. Keep the password. It is required to access the backup.",
            "Un nouveau dépôt chiffré sera créé. Conservez le mot de passe pour accéder à la sauvegarde.",
            "Ein neues verschlüsseltes Repository wird erstellt. Bewahre das Passwort für den Zugriff auf."),
    "existing": ("Mevcut depoya yeni bir yedek eklenecek.",
                 "A new backup will be added to the existing repository.",
                 "Une nouvelle sauvegarde sera ajoutée au dépôt existant.",
                 "Eine neue Sicherung wird dem vorhandenen Repository hinzugefügt."),
    "running": ("Yedekleme çalışıyor…", "Backup in progress…", "Sauvegarde en cours…", "Sicherung läuft…"),
    "done": ("Yedek tamamlandı.", "Backup complete.", "Sauvegarde terminée.", "Sicherung abgeschlossen."),
    "partial": ("Yedek eksik. Bazı dosyalar okunamadı. Ayrıntıları incele.",
                "Backup incomplete. Some files could not be read. Review the log.",
                "Sauvegarde incomplète. Certains fichiers sont illisibles. Consultez le journal.",
                "Sicherung unvollständig. Einige Dateien konnten nicht gelesen werden. Prüfe das Protokoll."),
    "snapshots": ("Depodaki yedekler", "Repository snapshots", "Instantanés du dépôt", "Sicherungen im Repository"),
    "list": ("Yedekleri listele", "List backups", "Lister les sauvegardes", "Sicherungen anzeigen"),
    "list_running": ("Yedekler okunuyor…", "Reading backups…", "Lecture des sauvegardes…", "Sicherungen werden gelesen…"),
    "list_empty": ("Depoda yedek yok.", "The repository has no backups.", "Le dépôt ne contient aucune sauvegarde.", "Das Repository enthält keine Sicherungen."),
    "list_ready": ("Yedekler listelendi. Geri yüklemek için bir yedek seç ve parolanı gir.",
                   "Backups listed. Select one and enter your password to restore it.",
                   "Sauvegardes listées. Sélectionnez-en une et saisissez votre mot de passe pour la restaurer.",
                   "Sicherungen aufgelistet. Wähle eine aus und gib das Passwort zur Wiederherstellung ein."),
    "restore": ("Geri yükle", "Restore", "Restaurer", "Wiederherstellen"),
    "restore_target": ("Boş geri yükleme klasörünü seç", "Choose an empty restore folder",
                       "Choisir un dossier de restauration vide", "Leeren Wiederherstellungsordner wählen"),
    "restore_invalid": ("Geri yükleme için depodan ayrı, var olan ve boş bir klasör seç.",
                        "Choose an existing empty folder separate from the repository.",
                        "Choisissez un dossier existant, vide et distinct du dépôt.",
                        "Wähle einen vorhandenen leeren Ordner außerhalb des Repositorys."),
    "restore_plan": ("Seçilen yedekteki tüm dosyalar bu boş klasöre çıkarılacak.",
                     "All files in the selected backup will be restored to this empty folder.",
                     "Tous les fichiers de la sauvegarde sélectionnée seront restaurés dans ce dossier vide.",
                     "Alle Dateien der gewählten Sicherung werden in diesen leeren Ordner wiederhergestellt."),
    "restore_running": ("Dosyalar geri yükleniyor…", "Restoring files…", "Restauration des fichiers…", "Dateien werden wiederhergestellt…"),
    "restore_done": ("Dosyalar geri yüklendi.", "Files restored.", "Fichiers restaurés.", "Dateien wiederhergestellt."),
    "restore_failed": ("Geri yükleme tamamlanamadı. Hedefte kısmi dosyalar kalmış olabilir.",
                       "Restore did not complete. The destination may contain partially restored files.",
                       "La restauration a échoué. Des fichiers partiels peuvent subsister dans le dossier cible.",
                       "Wiederherstellung fehlgeschlagen. Im Ziel können teilweise wiederhergestellte Dateien liegen."),
    "password_required": ("Depo parolasını gir.", "Enter the repository password.", "Saisissez le mot de passe du dépôt.", "Gib das Repository-Passwort ein."),
    "remember": ("Kaynakları ve yedek hedefini hatırla",
                 "Remember source folders and backup destination",
                 "Mémoriser les sources et la destination de sauvegarde",
                 "Quellordner und Sicherungsziel merken"),
    "history": ("Yedekleme geçmişi", "Backup history", "Historique des sauvegardes", "Sicherungsverlauf"),
    "history_empty": ("Kayıtlı işlem yok.", "No recorded operations.", "Aucune opération enregistrée.", "Keine Vorgänge aufgezeichnet."),
    "close": ("Kapat", "Close", "Fermer", "Schließen"),
    "failed": ("İşlem tamamlanamadı. Ayrıntıları incele.", "Operation failed. Review the log.",
               "L’opération a échoué. Consultez le journal.", "Vorgang fehlgeschlagen. Prüfe das Protokoll."),
}


def text(key, language):
    return TEXT[key][LANGUAGES.index(language)]


def backup_plan(sources, destination):
    try:
        paths = tuple(dict.fromkeys(Path(source).resolve(strict=True) for source in sources))
        target = Path(destination).resolve(strict=True)
        if not paths or not target.is_dir() or not all(path.is_dir() for path in paths):
            raise ValueError("invalid")
        if any(target.is_relative_to(path) or path.is_relative_to(target) for path in paths):
            raise ValueError("invalid")
        if (target / "config").is_file():
            return paths, target, False
        if not any(target.iterdir()):
            return paths, target, True
    except (OSError, RuntimeError) as error:
        raise ValueError("invalid") from error
    raise ValueError("target_error")


def restore_destination(path, repository):
    try:
        destination = Path(path).resolve(strict=True)
        if (
            destination.is_dir()
            and not destination.is_relative_to(repository)
            and not repository.is_relative_to(destination)
            and not any(destination.iterdir())
        ):
            return destination
    except (OSError, RuntimeError):
        pass
    raise ValueError("restore_invalid")


def snapshot_rows(payload):
    snapshots = json.loads(payload)
    if not isinstance(snapshots, list):
        raise ValueError("Invalid snapshot list")
    rows = []
    for snapshot in snapshots:
        ref = snapshot["id"]
        if not re.fullmatch(r"[0-9a-f]{64}", ref):
            raise ValueError("Invalid snapshot ID")
        timestamp = datetime.fromisoformat(snapshot["time"]).astimezone()
        paths = ", ".join(snapshot["paths"])
        rows.append((timestamp, ref, paths))
    return sorted(rows, reverse=True)


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
        self.intro.setText(text("intro", self.language))
        for key, (heading, detail) in self.cards.items():
            heading.setText(text(key, self.language))
            detail.setText(text(f"{key}_note", self.language))
        for key, button in self.buttons.items():
            button.setText(key if key == "Flathub" else text(key, self.language))


class BackupPanel(QWidget):
    def __init__(self, language, show_apps):
        super().__init__()
        self.language = language
        self.busy = False
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
        snapshot_actions.addWidget(self.list_button)
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
        layout.addWidget(self.apps, 0, Qt.AlignmentFlag.AlignLeft)
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
        self.restore_button.setText(self.t("restore"))
        self.history_button.setText(self.t("history"))
        self.remember.setText(self.t("remember"))
        self.remember.setEnabled(not self.busy)
        repository = self.repository()
        existing = repository is not None
        self.list_button.setEnabled(available and not self.busy and existing)
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
        self.paths = sources
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
        if normal and code == 0 and self.phase == "init":
            self.run("backup")
            return
        if self.phase == "snapshots":
            status = self.finish_snapshot_list() if normal and code == 0 else "failed"
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
            _, _, create = backup_plan(*recipe)
            return not create
        except ValueError:
            return False

    def restore_recipe(self):
        if self.busy or not self.saved_recipe_ready() or self.sources.count() or self.target.text():
            return
        sources, destination = self.saved_recipe()
        self.sources.addItems(sources)
        self.target.setText(destination)
        self.refresh()

    def remember_toggled(self, enabled):
        if not enabled:
            self.settings.remove("backup_recipe")

    def history(self):
        try:
            entries = json.loads(self.settings.value("backup_history", "[]", type=str))
            return [
                entry for entry in entries if isinstance(entry, list) and len(entry) == 3
                and all(isinstance(value, str) for value in entry)
                and entry[1] in ("start", "restore") and entry[2] in TEXT
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
            self.complete("failed")

    def complete(self, status):
        self.secret = b""
        self.busy = False
        if self.phase == "backup" and status == "done" and self.remember.isChecked():
            self.settings.setValue("backup_recipe", json.dumps([
                list(map(str, self.paths)), str(self.destination),
            ]))
        if self.phase in ("init", "backup", "restore"):
            action = "restore" if self.phase == "restore" else "start"
            entry = [datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z"), action, status]
            self.settings.setValue("backup_history", json.dumps([entry, *self.history()[:29]]))
        self.set_status(status)

    def set_status(self, key):
        self.status_key = key
        self.refresh()
