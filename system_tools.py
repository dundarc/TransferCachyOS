import os
import re
import subprocess
from pathlib import Path

from PySide6.QtCore import QProcess, QTimer, Signal, Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from catalog import LANGUAGES
from desktop_settings import open_settings, settings_command

PACMAN = "/usr/bin/pacman"
PKEXEC = "/usr/bin/pkexec"
POWER = "/usr/bin/powerprofilesctl"
FIRMWARE = Path("/sys/firmware/acpi")
POWER_SUPPLIES = Path("/sys/class/power_supply")
CHARGE_HELPER = "/usr/local/lib/transfercachyos/set-charge-limit"
PROTECTED = frozenset({
    "base", "filesystem", "glibc", "systemd", "systemd-sysvcompat", "pacman",
    "bash", "sudo", "polkit", "python", "pyside6", "networkmanager", "grub",
    "plasma-desktop", "plasma-workspace", "sddm",
})

WORDS = {
    "apps": ("Uygulamalar", "Apps", "Applications", "Anwendungen"),
    "system": ("Sistem", "System", "Système", "System"),
    "packages": ("Paketler", "Packages", "Paquets", "Pakete"),
    "refresh": ("Yenile", "Refresh", "Actualiser", "Aktualisieren"),
    "device": ("Cihaz", "Device", "Appareil", "Gerät"),
    "firmware": ("Donanım profili", "Firmware profile", "Profil matériel", "Firmware-Profil"),
    "fan": ("Fan hızı", "Fan speed", "Vitesse du ventilateur", "Lüfterdrehzahl"),
    "no_fan": ("Fan sensörü görünmüyor.", "No fan sensor detected.",
               "Aucun capteur de ventilateur détecté.", "Kein Lüftersensor erkannt."),
    "fan_note": ("Fan hızları izlenebilir. Özel fan eğrisi denetimi bu sürümde mevcut değil.",
                 "Fan speeds can be monitored. Custom fan curve control is unavailable in this version.",
                 "Les vitesses peuvent être surveillées. Le réglage des courbes de ventilation est indisponible dans cette version.",
                 "Lüfterdrehzahlen sind ablesbar. Eigene Lüfterkurven sind in dieser Version nicht verfügbar."),
    "power": ("Güç profili", "Power profile", "Profil d’alimentation", "Energieprofil"),
    "power-saver": ("Güç tasarrufu", "Power saver", "Économie d’énergie", "Energiesparmodus"),
    "balanced": ("Dengeli", "Balanced", "Équilibré", "Ausgeglichen"),
    "performance": ("Performans", "Performance", "Performances", "Leistung"),
    "power_off": ("Güç profili hizmetine erişilemiyor.",
                  "The power profile service is unavailable.",
                  "Le service de profils d’alimentation est indisponible.",
                  "Der Energieprofildienst ist nicht verfügbar."),
    "apply": ("Uygula", "Apply", "Appliquer", "Anwenden"),
    "battery": ("Pil", "Battery", "Batterie", "Akku"),
    "no_battery": ("Pil algılanmadı.", "No battery detected.", "Aucune batterie détectée.", "Kein Akku erkannt."),
    "charging": ("Şarj oluyor", "Charging", "En charge", "Wird geladen"),
    "discharging": ("Pille çalışıyor", "Discharging", "En décharge", "Wird entladen"),
    "not_charging": ("Şarj olmuyor", "Not charging", "Ne charge pas", "Wird nicht geladen"),
    "full": ("Dolu", "Full", "Pleine", "Voll"),
    "power_source": ("Güç kaynağı", "Power source", "Source d’alimentation", "Stromquelle"),
    "adapter": ("Adaptör bağlı", "Adapter connected", "Adaptateur branché", "Netzteil angeschlossen"),
    "battery_power": ("Adaptör bağlı değil", "Adapter disconnected", "Adaptateur débranché", "Netzteil getrennt"),
    "charge_limit": ("Şarj üst sınırı", "Charge limit", "Limite de charge", "Ladegrenze"),
    "limit_hint": ("Desteklenen ASUS cihazlarda %60–100. %100 tam şarja izin verir. Sistem bu ayarı yeniden başlatınca değiştirebilir.",
                   "60–100% on supported ASUS devices. 100% allows a full charge. The system may reset this setting after reboot.",
                   "60–100 % sur les appareils ASUS compatibles. 100 % autorise une charge complète. Le système peut réinitialiser ce réglage au redémarrage.",
                   "60–100 % auf unterstützten ASUS-Geräten. 100 % erlaubt eine volle Ladung. Das System kann die Einstellung beim Neustart zurücksetzen."),
    "limit_unsupported": ("Bu cihazda TransferCachyOS üzerinden şarj sınırı değiştirilemiyor.",
                          "TransferCachyOS cannot change the charge limit on this device.",
                          "TransferCachyOS ne peut pas modifier la limite de charge sur cet appareil.",
                          "TransferCachyOS kann die Ladegrenze auf diesem Gerät nicht ändern."),
    "limit_install": ("Şarj sınırını değiştirmek için install.sh ile kurulu kopyayı güncelle.",
                      "Update the installed copy with install.sh to change the charge limit.",
                      "Mettez à jour la copie installée avec install.sh pour modifier la limite de charge.",
                      "Aktualisiere die installierte Kopie mit install.sh, um die Ladegrenze zu ändern."),
    "limit_changed": ("Şarj sınırı güncellendi.", "Charge limit updated.", "Limite de charge mise à jour.", "Ladegrenze aktualisiert."),
    "limit_confirm": ("Bu pil için şarj üst sınırı değiştirilsin mi?",
                      "Change the charge limit for this battery?",
                      "Modifier la limite de charge de cette batterie ?",
                      "Ladegrenze für diesen Akku ändern?"),
    "auto_power": ("Pil ve adaptör durumuna göre güç ayarlarını uyarla",
                   "Adapt power settings to battery and charger events",
                   "Adapter la gestion de l’énergie à la batterie et au chargeur",
                   "Energieeinstellungen an Akku und Netzteil anpassen"),
    "power_settings": ("Masaüstü güç ayarları", "Desktop power settings", "Gestion de l’énergie du bureau", "Energieeinstellungen des Desktops"),
    "search": ("Paket adı veya sürümü ara", "Search by package name or version",
               "Rechercher un nom ou une version", "Paketname oder Version suchen"),
    "remove": ("Paketi kaldır", "Remove package", "Supprimer le paquet", "Paket entfernen"),
    "cancel": ("Vazgeç", "Cancel", "Annuler", "Abbrechen"),
    "remove_plan": (
        "Şu paket kaldırılsın mı? Başka bir paket buna bağımlıysa pacman işlemi durdurur.",
        "Remove this package? Pacman will stop if another package requires it.",
        "Supprimer ce paquet ? Pacman s’arrêtera si un autre paquet en dépend.",
        "Dieses Paket entfernen? Pacman bricht ab, wenn ein anderes Paket davon abhängt."),
    "remove_rule": (
        "Yalnızca doğrudan yüklenen, koruma dışındaki paketler kaldırılabilir.",
        "Only explicitly installed, unprotected packages can be removed.",
        "Seuls les paquets installés explicitement et non protégés peuvent être supprimés.",
        "Nur explizit installierte, ungeschützte Pakete können entfernt werden."),
    "removed": ("Paket kaldırıldı.", "Package removed.", "Paquet supprimé.", "Paket entfernt."),
    "error": ("İşlem tamamlanamadı.", "Operation failed.", "L’opération a échoué.", "Vorgang fehlgeschlagen."),
}


def word(key, language):
    return WORDS[key][LANGUAGES.index(language)]


def command(*args):
    return subprocess.run(
        args, capture_output=True, text=True, errors="replace",
        timeout=5, check=True, env={**os.environ, "LC_ALL": "C"},
    ).stdout.strip()


def error_text(error):
    return getattr(error, "stderr", None) or str(error)


def read_text(path):
    try:
        return path.read_text().strip()
    except OSError:
        return ""


def fan_speeds():
    return [
        (read_text(sensor.parent / "name") or sensor.parent.name,
         sensor.stem.split("_")[0], speed)
        for sensor in sorted(Path("/sys/class/hwmon").glob("hwmon*/fan*_input"))
        if (speed := read_text(sensor)).isdigit()
    ]


def removable(name, explicit):
    return (
        name in explicit and name not in PROTECTED
        and name != "linux" and not name.startswith("linux-")
    )


def power_supplies():
    batteries = {}
    adapters = []
    for supply in sorted(POWER_SUPPLIES.glob("*")):
        if read_text(supply / "type") == "Battery":
            batteries[supply.name] = (
                read_text(supply / "capacity"), read_text(supply / "status"),
                read_text(supply / "charge_control_end_threshold"),
            )
        else:
            online = read_text(supply / "online")
            if online in ("0", "1"):
                adapters.append(online == "1")
    return batteries, any(adapters) if adapters else None


class SystemPanel(QWidget):
    charge_completed = Signal(str)

    def __init__(self, language):
        super().__init__()
        self.language = language
        self.busy = False
        self.charge_process = QProcess(self)
        self.charge_process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.charge_process.finished.connect(self.charge_finished)
        self.charge_process.errorOccurred.connect(self.charge_error)
        self.telemetry = QTimer(self)
        self.telemetry.setInterval(2000)
        self.telemetry.timeout.connect(self.refresh_hardware)
        layout = QVBoxLayout(self)
        self.hardware = QLabel()
        self.hardware.setTextFormat(Qt.TextFormat.PlainText)
        self.hardware.setWordWrap(True)
        self.note = QLabel()
        self.note.setWordWrap(True)
        layout.addWidget(self.hardware)
        layout.addWidget(self.note)
        row = QHBoxLayout()
        self.power_label = QLabel()
        self.power = QComboBox()
        self.apply = QPushButton()
        self.refresh_button = QPushButton()
        self.power_label.setBuddy(self.power)
        for widget in (self.power_label, self.power, self.apply, self.refresh_button):
            row.addWidget(widget)
        layout.addLayout(row)
        self.auto_power = QCheckBox()
        self.auto_power.clicked.connect(self.apply_auto_power)
        layout.addWidget(self.auto_power)

        self.battery_details = QLabel()
        self.battery_details.setTextFormat(Qt.TextFormat.PlainText)
        self.battery_details.setWordWrap(True)
        layout.addWidget(self.battery_details)
        charge_row = QHBoxLayout()
        self.charge_label = QLabel()
        self.charge_battery = QComboBox()
        self.charge_battery.currentTextChanged.connect(self.select_battery)
        self.charge_value = QSpinBox()
        self.charge_value.setRange(60, 100)
        self.charge_value.setSuffix(" %")
        self.charge_apply = QPushButton()
        self.charge_apply.clicked.connect(self.apply_charge)
        for widget in (self.charge_label, self.charge_battery, self.charge_value, self.charge_apply):
            charge_row.addWidget(widget)
        layout.addLayout(charge_row)
        self.charge_hint = QLabel()
        self.charge_hint.setWordWrap(True)
        layout.addWidget(self.charge_hint)
        self.settings_button = QPushButton()
        self.settings_button.clicked.connect(self.open_settings)
        layout.addWidget(self.settings_button)
        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addStretch()
        self.refresh_button.clicked.connect(self.refresh)
        self.apply.clicked.connect(self.apply_power)
        self.refresh()

    def t(self, key):
        return word(key, self.language)

    def refresh(self):
        self.note.setText(self.t("fan_note"))
        self.power_label.setText(self.t("power"))
        self.apply.setText(self.t("apply"))
        self.refresh_button.setText(self.t("refresh"))
        self.auto_power.setText(self.t("auto_power"))
        self.charge_label.setText(self.t("charge_limit"))
        self.charge_apply.setText(self.t("apply"))
        self.settings_button.setText(self.t("power_settings"))
        self.settings_button.setEnabled(settings_command("power") is not None)
        self.refresh_hardware()
        self.status.clear()
        self.power.clear()
        try:
            profiles = re.findall(r"(?m)^\s*\*?\s*(power-saver|balanced|performance):", command(POWER, "list"))
            active = command(POWER, "get")
        except (OSError, subprocess.SubprocessError):
            profiles = []
            active = ""
        for profile in dict.fromkeys(profiles):
            self.power.addItem(self.t(profile), profile)
        self.power.setCurrentIndex(self.power.findData(active))
        self.power.setEnabled(bool(profiles))
        self.apply.setEnabled(bool(profiles))
        self.refresh_auto_power()
        if not profiles:
            self.status.setText(self.t("power_off"))

    def showEvent(self, event):
        self.telemetry.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.telemetry.stop()
        super().hideEvent(event)

    def refresh_hardware(self):
        dmi = Path("/sys/class/dmi/id")
        device = " ".join(filter(None, (read_text(dmi / "sys_vendor"), read_text(dmi / "product_name"))))
        fans = fan_speeds()
        fan_text = ", ".join(f"{driver} {fan}: {rpm} RPM" for driver, fan, rpm in fans)
        profile = read_text(FIRMWARE / "platform_profile")
        choices = read_text(FIRMWARE / "platform_profile_choices").split()
        profile_text = profile or "—"
        if choices:
            profile_text += f" ({', '.join(choices)})"
        self.hardware.setText(
            f"{self.t('device')}: {device or '—'}\n"
            f"{self.t('firmware')}: {profile_text}\n"
            f"{self.t('fan')}: {fan_text or self.t('no_fan')}"
        )
        self.batteries, adapter = power_supplies()
        states = {"Charging": "charging", "Discharging": "discharging",
                  "Not charging": "not_charging", "Full": "full"}
        lines = []
        for name, (capacity, state, threshold) in self.batteries.items():
            details = [f"{capacity} %" if capacity.isdigit() else "—"]
            if state in states:
                details.append(self.t(states[state]))
            if threshold.isdigit():
                details.append(f"{self.t('charge_limit')}: {threshold} %")
            lines.append(f"{self.t('battery')} {name}: " + " · ".join(details))
        if not lines:
            lines.append(self.t("no_battery"))
        source = "unknown" if adapter is None else ("adapter" if adapter else "battery_power")
        lines.append(f"{self.t('power_source')}: {self.t(source)}")
        self.battery_details.setText("\n".join(lines))

        is_asus = read_text(dmi / "sys_vendor").casefold().startswith("asustek")
        supported = [
            name for name, (_, _, threshold) in self.batteries.items()
            if is_asus and re.fullmatch(r"BAT[0-9]+", name) and threshold.isdigit()
        ]
        if [self.charge_battery.itemText(i) for i in range(self.charge_battery.count())] != supported:
            previous = self.charge_battery.currentText()
            self.charge_battery.blockSignals(True)
            self.charge_battery.clear()
            self.charge_battery.addItems(supported)
            if previous in supported:
                self.charge_battery.setCurrentText(previous)
            self.charge_battery.blockSignals(False)
            self.select_battery(self.charge_battery.currentText())
        installed = os.access(CHARGE_HELPER, os.X_OK)
        for widget in (self.charge_battery, self.charge_value, self.charge_apply):
            widget.setEnabled(bool(supported) and installed and not self.busy)
        hint = ("limit_hint" if installed else "limit_install") if supported else "limit_unsupported"
        self.charge_hint.setText(self.t(hint))

    def select_battery(self, name):
        if name in self.batteries:
            self.charge_value.setValue(int(self.batteries[name][2]))

    def apply_charge(self):
        name = self.charge_battery.currentText()
        limit = self.charge_value.value()
        if not name or self.busy or not self.charge_apply.isEnabled():
            return
        dialog = QMessageBox(self)
        dialog.setWindowTitle(self.t("charge_limit"))
        dialog.setText(f"{self.t('limit_confirm')}\n\n{name} → {limit} %")
        apply = dialog.addButton(self.t("apply"), QMessageBox.ButtonRole.AcceptRole)
        cancel = dialog.addButton(self.t("cancel"), QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(cancel)
        dialog.exec()
        if dialog.clickedButton() is apply:
            self.busy = True
            self.status.clear()
            self.refresh_hardware()
            self.charge_process.start(PKEXEC, [CHARGE_HELPER, name, str(limit)])

    def travel_battery(self):
        if self.busy or not self.charge_apply.isEnabled():
            return ""
        for name, (_, _, limit) in self.batteries.items():
            if (self.charge_battery.findText(name) >= 0 and limit.isdigit()
                    and 60 <= int(limit) < 100):
                return name
        return ""

    def apply_travel(self, name):
        if not name or name != self.travel_battery():
            return
        self.busy = True
        self.status.clear()
        self.refresh_hardware()
        self.charge_process.start(PKEXEC, [CHARGE_HELPER, name, "travel"])

    def charge_finished(self, code, exit_status):
        output = bytes(self.charge_process.readAllStandardOutput()).decode(errors="replace").strip()
        ok = code == 0 and exit_status == QProcess.ExitStatus.NormalExit
        self.busy = False
        self.refresh_hardware()
        message = self.t("limit_changed" if ok else "error")
        self.status.setText(f"{message} {output}".strip())
        self.charge_completed.emit(self.status.text())

    def charge_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.busy = False
            self.refresh_hardware()
            self.status.setText(f"{self.t('error')} {self.charge_process.errorString()}")
            self.charge_completed.emit(self.status.text())

    def open_settings(self):
        if not open_settings("power"):
            self.status.setText(self.t("error"))

    def refresh_auto_power(self):
        try:
            result = command(POWER, "query-battery-aware").rpartition(":")[2].strip().casefold()
        except (OSError, subprocess.SubprocessError):
            result = ""
        self.auto_power.setEnabled(result in ("true", "false"))
        self.auto_power.setChecked(result == "true")

    def apply_auto_power(self, enabled):
        try:
            command(POWER, "configure-battery-aware", "--enable" if enabled else "--disable")
        except (OSError, subprocess.SubprocessError) as error:
            self.status.setText(f"{self.t('error')} {error_text(error)}")
        self.refresh_auto_power()

    def apply_power(self):
        profile = self.power.currentData()
        if not profile:
            return
        try:
            command(POWER, "set", profile)
        except (OSError, subprocess.SubprocessError) as error:
            self.status.setText(f"{self.t('error')} {error_text(error)}")
            return
        self.refresh()

