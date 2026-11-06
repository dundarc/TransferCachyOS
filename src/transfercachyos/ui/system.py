import os
import re
import subprocess
from pathlib import Path

from PySide6.QtCore import QProcess, QTimer, Signal, Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from ..i18n import translator
from ..services.commands import command, error_text
from ..services.desktop import open_settings, settings_command
from ..services.packages import PKEXEC
from ..services.power import CHARGE_HELPER, FIRMWARE, POWER, fan_speeds, power_snapshot, power_supplies, read_text

from .read_task import ReadTask

word = translator("system")


class SystemPanel(QWidget):
    charge_completed = Signal(str)
    profiles_changed = Signal()

    def __init__(self, language):
        super().__init__()
        self.language = language
        self.busy = False
        self.power_state = None
        self.query = ReadTask(self)
        self.query.completed.connect(self.loaded)
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
        self.power_status = QLabel()
        self.power_status.setWordWrap(True)
        layout.addWidget(self.power_status)

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
        self.render()

    def t(self, key):
        return word(key, self.language)

    def refresh(self):
        if self.query.start(power_snapshot):
            self.render()

    def loaded(self, state, error):
        self.power_state = state if error is None else ((), "", None)
        self.render()
        self.profiles_changed.emit()

    def render(self):
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
        profiles, active, automatic = self.power_state or ((), "", None)
        self.power.clear()
        for profile in profiles:
            self.power.addItem(self.t(profile), profile)
        self.power.setCurrentIndex(self.power.findData(active))
        ready = not self.query.running
        self.refresh_button.setEnabled(ready)
        self.power.setEnabled(ready and bool(profiles))
        self.apply.setEnabled(ready and bool(profiles))
        self.auto_power.setEnabled(ready and automatic is not None)
        self.auto_power.setChecked(automatic is True)
        key = "loading" if not ready else "power_off" if not profiles else ""
        self.power_status.setText(self.t(key) if key else "")
        self.power_status.setVisible(bool(key))

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

    def apply_auto_power(self, enabled):
        try:
            command(POWER, "configure-battery-aware", "--enable" if enabled else "--disable")
        except (OSError, subprocess.SubprocessError) as error:
            self.status.setText(f"{self.t('error')} {error_text(error)}")
        self.refresh()

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
