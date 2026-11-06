import os
import shutil
import subprocess
from pathlib import Path

from PySide6.QtCore import QProcess, QSettings, QStandardPaths, QTimer, QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

from ..i18n import messages, translator
from ..services.commands import command, error_text, probe
from ..services.desktop import desktop_family, open_settings, settings_command
from ..services.flatpak import FLATPAK
from ..services.power import POWER, power_supplies

from .read_task import ReadTask

text = translator("daily")
word = translator("system")

GIB = 1024 ** 3
GIO = "/usr/bin/gio"
APPS = {
    "Dolphin": "org.kde.dolphin.desktop",
    "Firefox": "firefox.desktop",
    "Chrome": "google-chrome.desktop",
    "LibreOffice Writer": "libreoffice-writer.desktop",
    "Okular": "org.kde.okular.desktop",
    "VLC": "vlc.desktop",
    "Thunderbird": "thunderbird.desktop",
}
DEVICES = ("bluetooth", "audio", "display", "network", "printer")


def desktop_path(name):
    return QStandardPaths.locate(QStandardPaths.StandardLocation.GenericDataLocation, f"applications/{name}")


def ask(parent, title, details, action, cancel):
    dialog = QMessageBox(parent)
    dialog.setWindowTitle(title)
    dialog.setTextFormat(Qt.TextFormat.PlainText)
    dialog.setText(details)
    confirm = dialog.addButton(action, QMessageBox.ButtonRole.AcceptRole)
    reject = dialog.addButton(cancel, QMessageBox.ButtonRole.RejectRole)
    dialog.setDefaultButton(reject)
    dialog.exec()
    return dialog.clickedButton() is confirm


def audio_devices():
    return (
        probe("/usr/bin/pactl", "get-default-sink"),
        probe("/usr/bin/pactl", "get-default-source"),
    )


class DailyPanel(QWidget):
    def __init__(self, language, system, backup, flatpak, show_backup, show_system):
        super().__init__()
        self.language = language
        self.system = system
        self.backup = backup
        self.flatpak = flatpak
        self.settings = QSettings("TransferCachyOS", "TransferCachyOS")
        self.previous_power = None
        self.scan_root = None
        self.jobs = []
        self.job = None
        self.busy = False
        self.cancelled = False
        self.audio_query = ReadTask(self)
        self.audio_query.completed.connect(self.audio_loaded)
        self.audio_state = None
        self.worker = QProcess(self)
        self.worker.finished.connect(self.finished)
        self.worker.errorOccurred.connect(self.process_error)
        self.job_timeout = QTimer(self)
        self.job_timeout.setSingleShot(True)
        self.job_timeout.setInterval(45000)
        self.job_timeout.timeout.connect(self.worker.kill)
        self.timer = QTimer(self)
        self.timer.setInterval(5000)
        self.timer.timeout.connect(self.tick)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        self.labels = []
        self.pages = {}
        self.heading = QLabel()
        font = self.heading.font()
        font.setPointSizeF(font.pointSizeF() * 1.6)
        font.setBold(True)
        self.heading.setFont(font)
        layout.addWidget(self.heading)

        status_card, status = self.card("overview")
        self.summary = QLabel()
        self.summary.setTextFormat(Qt.TextFormat.PlainText)
        self.summary.setWordWrap(True)
        self.summary.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.summary.setMinimumHeight(self.summary.fontMetrics().lineSpacing() * 4 + 8)
        status.addWidget(self.summary)
        self.button(status, "backup", show_backup)

        actions_card, actions = self.card("quick")
        row = QHBoxLayout()
        self.profile = QComboBox()
        row.addWidget(self.profile, 1)
        self.quick_apply = self.button(row, "apply", self.apply_quick, system_word=True)
        actions.addLayout(row)
        shortcuts = QHBoxLayout()
        self.button(shortcuts, "downloads", lambda: self.open_url(QUrl.fromLocalFile(self.downloads())))
        self.localsend = self.button(shortcuts, "LocalSend", self.launch_localsend)
        actions.addLayout(shortcuts)
        self.button(actions, "power_management", show_system)
        self.favorite_launch = QComboBox()
        self.favorite_row = QWidget()
        favorites = QHBoxLayout(self.favorite_row)
        favorites.setContentsMargins(0, 0, 0, 0)
        favorites.addWidget(self.favorite_launch, 1)
        self.open_favorite = self.button(favorites, "launch", self.launch_favorite)
        actions.addWidget(self.favorite_row)
        self.quick_status = QLabel()
        self.quick_status.setTextFormat(Qt.TextFormat.PlainText)
        self.quick_status.setWordWrap(True)
        actions.addWidget(self.quick_status)

        cards = QHBoxLayout()
        cards.setSpacing(16)
        cards.addWidget(status_card, 1, Qt.AlignmentFlag.AlignTop)
        cards.addWidget(actions_card, 1, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(cards)
        layout.addStretch()

        disk = self.page("storage")
        self.disk_status = QLabel()
        disk.addWidget(self.disk_status)
        self.files = QListWidget()
        disk.addWidget(self.files, 1)
        row = QHBoxLayout()
        self.scan_button = self.button(row, "scan", self.scan)
        self.cancel_scan = self.button(row, "cancel", self.cancel_jobs, system_word=True)
        self.cancel_scan.hide()
        self.trash_button = self.button(row, "move_trash", self.trash)
        self.files.currentRowChanged.connect(self.update_trash)
        disk.addLayout(row)
        row = QHBoxLayout()
        self.button(row, "trash", lambda: self.open_url(QUrl("trash:/")))
        self.button(row, "cache", lambda: self.open_url(QUrl.fromLocalFile("/var/cache/pacman/pkg")))
        disk.addLayout(row)
        self.update_trash()

        updates = self.page("updates")
        update_actions = QHBoxLayout()
        self.update_button = self.button(update_actions, "check", self.check_updates)
        self.cancel_updates = self.button(update_actions, "cancel", self.cancel_jobs, system_word=True)
        self.cancel_updates.hide()
        updates.addLayout(update_actions)
        self.update_results = QPlainTextEdit()
        self.update_results.setReadOnly(True)
        updates.addWidget(self.update_results, 1)
        self.favorite_label = QLabel()
        updates.addWidget(self.favorite_label)
        self.favorites = {}
        for name, entry in APPS.items():
            check = QCheckBox(name)
            check.setEnabled(bool(desktop_path(entry)))
            check.setChecked(self.settings.value(f"favorite/{entry}", False, type=bool))
            check.toggled.connect(lambda enabled, key=entry: self.save_favorite(key, enabled))
            updates.addWidget(check)
            self.favorites[entry] = check

        laptop = self.page("laptop")
        form = QFormLayout()
        self.battery_label, self.plugged_label = QLabel(), QLabel()
        self.battery_profile, self.plugged_profile = QComboBox(), QComboBox()
        form.addRow(self.battery_label, self.battery_profile)
        form.addRow(self.plugged_label, self.plugged_profile)
        laptop.addLayout(form)
        self.automatic = QCheckBox()
        self.automatic.setChecked(self.settings.value("daily_auto_power", False, type=bool))
        laptop.addWidget(self.automatic)
        self.button(laptop, "save", self.save_power)
        self.travel_button = self.button(laptop, "travel", self.start_travel)
        self.travel_note = QLabel()
        self.travel_note.setWordWrap(True)
        laptop.addWidget(self.travel_note)
        self.laptop_status = QLabel()
        self.laptop_status.setTextFormat(Qt.TextFormat.PlainText)
        self.laptop_status.setWordWrap(True)
        laptop.addWidget(self.laptop_status)
        laptop.addStretch()

        devices = self.page("devices")
        for key in DEVICES:
            self.button(devices, key, lambda _checked=False, section=key: self.open_device(section))
        self.device_status = QLabel()
        self.device_status.setWordWrap(True)
        devices.addWidget(self.device_status)
        self.audio = QLabel()
        self.audio.setTextFormat(Qt.TextFormat.PlainText)
        self.audio.setWordWrap(True)
        devices.addWidget(self.audio)
        devices.addStretch()
        self.refresh()
        self.timer.start()

    def t(self, key):
        return text(key, self.language)

    def page(self, key):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.pages[key] = widget
        return layout

    def card(self, key):
        frame = QFrame(self)
        frame.setObjectName("dailyCard")
        frame.setStyleSheet("QFrame#dailyCard { border: 1px solid palette(mid); border-radius: 8px; }")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(9)
        title = QLabel()
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)
        self.labels.append((title, key, False))
        return frame, layout

    def button(self, layout, key, callback, system_word=False):
        button = QPushButton()
        button.clicked.connect(callback)
        layout.addWidget(button)
        self.labels.append((button, key, system_word))
        return button

    def downloads(self):
        return QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)

    def refresh(self):
        self.heading.setText(self.t("today"))
        self.profile.setAccessibleName(self.t("profile"))
        for button, key, system_word in self.labels:
            button.setText(word(key, self.language) if system_word else self.t(key) if key in messages("en")["daily"] else key)
        self.battery_label.setText(self.t("battery"))
        self.plugged_label.setText(self.t("plugged"))
        self.automatic.setText(self.t("auto"))
        self.travel_note.setText(self.t("travel_note"))
        self.favorite_label.setText(self.t("favorites"))
        for entry, check in self.favorites.items():
            check.setEnabled(bool(desktop_path(entry)))
        self.load_favorites()
        self.load_profiles()
        self.render_audio()
        self.tick()

    def tick(self):
        batteries, online = power_supplies()
        if self.isVisible():
            history = [entry for entry in self.backup.history() if entry[1] == "start"]
            last = next((entry[0] for entry in history if entry[2] == "done"), "—")
            parts = [f"{word('battery', self.language)}: " + (", ".join(
                f"{name} {capacity} %" for name, (capacity, _, _) in batteries.items() if capacity.isdigit()
            ) or "—")]
            if online is not None:
                parts.append(word("adapter" if online else "battery_power", self.language))
            parts.extend((f"{self.t('free')}: {shutil.disk_usage('/').free / GIB:.1f} GiB", f"{self.t('last')}: {last}"))
            if history and history[0][2] != "done":
                parts.append(self.t("issue"))
            if self.backup.saved_recipe():
                parts.append(self.t("ready" if self.backup.saved_recipe_ready() else "unavailable"))
            self.summary.setText("\n".join(parts))
            self.localsend.setVisible("org.localsend.localsend_app" in self.flatpak.installed)
        if self.isVisible() or self.pages["laptop"].isVisible():
            self.system.refresh_hardware()
            self.travel_button.setEnabled(bool(self.system.travel_battery()))
        if online is not None and self.settings.value("daily_auto_power", False, type=bool):
            if online != self.previous_power:
                self.previous_power = online
                self.apply_source_profile(online)

    def load_profiles(self):
        profiles = [self.system.power.itemData(i) for i in range(self.system.power.count())]
        for combo, selected in (
            (self.profile, self.system.power.currentData()),
            (self.battery_profile, self.settings.value("daily_battery_profile", "power-saver")),
            (self.plugged_profile, self.settings.value("daily_plugged_profile", "balanced")),
        ):
            combo.clear()
            for key in profiles:
                combo.addItem(word(key, self.language), key)
            index = combo.findData(selected)
            if index >= 0:
                combo.setCurrentIndex(index)
        self.profile.setVisible(bool(profiles))
        self.quick_apply.setVisible(bool(profiles))
        self.localsend.setVisible("org.localsend.localsend_app" in self.flatpak.installed)

    def apply_quick(self):
        index = self.system.power.findData(self.profile.currentData())
        if index >= 0:
            self.system.power.setCurrentIndex(index)
            self.system.apply_power()
            self.quick_status.setText(self.system.status.text() or self.profile.currentText())

    def save_power(self):
        enabled = self.automatic.isChecked()
        if enabled and (not self.battery_profile.currentData() or not self.plugged_profile.currentData()
                        or not self.system.auto_power.isEnabled() or self.system.auto_power.isChecked()):
            self.laptop_status.setText(self.t("auto_note"))
            return
        self.settings.setValue("daily_auto_power", enabled)
        for key, combo in (("daily_battery_profile", self.battery_profile), ("daily_plugged_profile", self.plugged_profile)):
            if combo.currentData():
                self.settings.setValue(key, combo.currentData())
        self.previous_power = None
        self.laptop_status.setText(self.t("saved"))
        self.tick()

    def apply_source_profile(self, online):
        key = "daily_plugged_profile" if online else "daily_battery_profile"
        profile = self.settings.value(key, "")
        if profile not in ("power-saver", "balanced", "performance"):
            return
        try:
            automatic = command(POWER, "query-battery-aware").rpartition(":")[2].strip().casefold()
            if automatic == "false":
                command(POWER, "set", profile)
            else:
                self.laptop_status.setText(self.t("auto_note"))
        except (OSError, subprocess.SubprocessError) as error:
            self.laptop_status.setText(error_text(error))

    def start_travel(self):
        name = self.system.travel_battery()
        if not name:
            return
        limit = self.system.batteries[name][2]
        details = f"{self.t('travel_note')}\n\n{name}: {limit} % → 100 %"
        if ask(self, self.t("travel"), details, word("apply", self.language), word("cancel", self.language)):
            self.system.apply_travel(name)
            self.travel_button.setEnabled(False)

    def open_url(self, url):
        QDesktopServices.openUrl(url)

    def launch_localsend(self):
        self.flatpak.launch("org.localsend.localsend_app")

    def save_favorite(self, entry, enabled):
        self.settings.setValue(f"favorite/{entry}", enabled)
        self.load_favorites()

    def load_favorites(self):
        previous = self.favorite_launch.currentData()
        self.favorite_launch.clear()
        for name, entry in APPS.items():
            if self.favorites[entry].isChecked() and desktop_path(entry):
                self.favorite_launch.addItem(name, entry)
        self.favorite_launch.setPlaceholderText(self.t("choose"))
        if self.favorite_launch.count():
            self.favorite_launch.setCurrentIndex(max(0, self.favorite_launch.findData(previous)))
        self.favorite_row.setVisible(self.favorite_launch.count() > 0)

    def launch_favorite(self):
        entry = self.favorite_launch.currentData()
        path = desktop_path(entry) if entry else ""
        if path:
            QProcess.startDetached(GIO, ["launch", path])

    def scan(self):
        if self.busy:
            return
        selected = QFileDialog.getExistingDirectory(self, self.t("scan"), self.downloads())
        if not selected:
            return
        self.scan_root = Path(selected).resolve()
        self.files.clear()
        self.disk_status.setText(self.t("scanning"))
        self.start_jobs([("scan", "/usr/bin/find", [
            str(self.scan_root), "-xdev", "-maxdepth", "5", "-type", "f", "-size", "+100M",
            "-printf", "%D\t%i\t%s\t%p\\0",
        ])])

    def show_files(self, output):
        matches = []
        for line in output.split(b"\0"):
            fields = line.split(b"\t", 3)
            if len(fields) == 4 and all(field.isdigit() for field in fields[:3]):
                device, inode, size, path = fields
                matches.append((int(size), os.fsdecode(path), int(device), int(inode)))
        for size, path, device, inode in sorted(matches, reverse=True)[:100]:
            item = QListWidgetItem(f"{size / (1024 ** 2):.0f} MiB · {path}")
            item.setData(Qt.ItemDataRole.UserRole, (size, path, device, inode))
            self.files.addItem(item)

    def update_trash(self):
        self.trash_button.setEnabled(not self.busy and self.files.currentItem() is not None)

    def trash(self):
        item = self.files.currentItem()
        if self.busy or item is None:
            return
        size, raw_path, device, inode = item.data(Qt.ItemDataRole.UserRole)
        path = Path(raw_path)
        def unchanged():
            try:
                stat = path.stat()
                return (path.resolve(strict=True) == path and path.is_relative_to(self.scan_root)
                        and path.is_file() and (stat.st_size, stat.st_dev, stat.st_ino) == (size, device, inode))
            except (OSError, RuntimeError):
                return False
        if not unchanged() or not ask(self, self.t("trash"), f"{self.t('trash_confirm')}\n\n{item.text()}",
                                     self.t("move_trash"), word("cancel", self.language)):
            return
        if not unchanged():
            self.disk_status.setText(word("error", self.language))
            return
        try:
            command(GIO, "trash", "--", str(path))
        except (OSError, subprocess.SubprocessError) as error:
            self.disk_status.setText(error_text(error))
        else:
            self.files.takeItem(self.files.row(item))

    def check_updates(self):
        if self.busy:
            return
        self.update_results.setPlainText(self.t("checking"))
        self.update_sections = []
        self.start_jobs([
            ("system_updates", "/usr/bin/checkupdates", []),
            ("user_flatpak", FLATPAK, ["remote-ls", "--user", "--updates", "--app", "--columns=application"]),
            ("system_flatpak", FLATPAK, ["remote-ls", "--system", "--updates", "--app", "--columns=application"]),
        ])

    def start_jobs(self, jobs):
        self.jobs = list(jobs)
        self.cancelled = False
        self.busy = True
        self.scan_button.setEnabled(False)
        self.update_button.setEnabled(False)
        self.update_trash()
        self.next_job()

    def next_job(self):
        if self.jobs:
            self.job, binary, arguments = self.jobs.pop(0)
            self.cancel_scan.setVisible(self.job == "scan")
            self.cancel_updates.setVisible(self.job != "scan")
            self.job_timeout.start()
            self.worker.start(binary, arguments)
        else:
            self.busy = False
            self.cancel_scan.hide()
            self.cancel_updates.hide()
            self.scan_button.setEnabled(True)
            self.update_button.setEnabled(True)
            self.update_trash()

    def cancel_jobs(self):
        if self.busy and not self.cancelled:
            self.cancelled = True
            self.jobs.clear()
            self.worker.kill()

    def finished(self, code, exit_status):
        stdout = bytes(self.worker.readAllStandardOutput())
        stderr = bytes(self.worker.readAllStandardError()).decode(errors="replace").strip()
        if exit_status != QProcess.ExitStatus.NormalExit:
            code = -1
        self.handle_result(code, stdout, stderr)

    def process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.handle_result(-1, b"", self.worker.errorString())

    def handle_result(self, code, stdout, stderr):
        self.job_timeout.stop()
        if self.cancelled:
            if self.job == "scan":
                self.disk_status.setText(self.t("cancelled"))
            else:
                self.update_sections.append(self.t("cancelled"))
                self.update_results.setPlainText("\n\n".join(self.update_sections))
            self.next_job()
            return
        if self.job == "scan":
            self.show_files(stdout)
            self.disk_status.setText(str(self.scan_root) if code == 0 else self.t("partial_scan"))
        else:
            valid = code == 0 or (self.job == "system_updates" and code == 2)
            result = (stdout.decode(errors="replace").strip() or self.t("none")) if valid else (
                f"{word('error', self.language)}\n{stderr}".strip())
            self.update_sections.append(f"{self.t(self.job)}\n{result}")
            self.update_results.setPlainText("\n\n".join(self.update_sections))
        self.next_job()

    def refresh_audio(self):
        self.audio_query.start(audio_devices)

    def audio_loaded(self, devices, error):
        self.audio_state = devices if error is None else ("", "")
        self.render_audio()

    def render_audio(self):
        devices = self.audio_state or ("", "")
        self.audio.setText("\n".join(
            f"{self.t(key)}: {name or '—'}"
            for key, name in zip(("audio_out", "audio_in"), devices)
        ))

    def open_device(self, section):
        if settings_command(section) is None:
            key = ("printer_module_missing" if section == "printer" and desktop_family() == "kde"
                   else "device_module_missing")
            self.device_status.setText(self.t(key))
            return
        self.device_status.setText("" if open_settings(section) else word("error", self.language))
