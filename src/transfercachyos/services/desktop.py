import configparser
import os
import shutil
from pathlib import Path

from PySide6.QtCore import QLibraryInfo, QProcess

KDE_MODULES = {
    "bluetooth": "kcm_bluetooth",
    "audio": "kcm_pulseaudio",
    "display": "kcm_kscreen",
    "network": "kcm_networkmanagement",
    "printer": "kcm_printer_manager",
    "keyboard": "kcm_keyboard",
    "power": "kcm_powerdevilprofilesconfig",
}
GNOME_PANELS = {
    "bluetooth": "bluetooth",
    "audio": "sound",
    "display": "display",
    "network": "network",
    "printer": "printers",
    "keyboard": "keyboard",
    "power": "power",
}
XFCE_TOOLS = {
    "general": "xfce4-settings-manager",
    "display": "xfce4-display-settings",
    "keyboard": "xfce4-keyboard-settings",
    "power": "xfce4-power-manager-settings",
}
CINNAMON_PANELS = {
    "audio": "sound",
    "display": "display",
    "network": "network",
    "keyboard": "keyboard",
    "power": "power",
}
STANDALONE = {
    "bluetooth": ("blueman-manager",),
    "audio": ("pavucontrol", "pavucontrol-qt"),
    "network": ("nm-connection-editor",),
    "printer": ("system-config-printer",),
}


def desktop_family():
    session = os.environ.get("XDG_CURRENT_DESKTOP") or os.environ.get("XDG_SESSION_DESKTOP", "")
    names = [name.strip().casefold() for name in session.split(":")]
    for name in names:
        if name in ("kde", "plasma"):
            return "kde"
        if name == "gnome" or name.startswith("gnome-"):
            return "gnome"
        if name == "xfce":
            return "xfce"
        if name in ("x-cinnamon", "cinnamon"):
            return "cinnamon"
    return ""


def kde_module_installed(module):
    plugins = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)) / "plasma/kcms"
    return any((directory / f"{module}.so").is_file() for directory in plugins.glob("systemsettings*"))


def settings_command(section):
    desktop = desktop_family()
    candidates = []
    if desktop == "kde":
        if section == "general":
            candidates.append(("systemsettings",))
        elif (module := KDE_MODULES.get(section)) and kde_module_installed(module):
            candidates.append(("kcmshell6", module))
    elif desktop in ("gnome", "cinnamon"):
        binary, panels = (
            ("gnome-control-center", GNOME_PANELS) if desktop == "gnome"
            else ("cinnamon-settings", CINNAMON_PANELS)
        )
        if section == "general":
            candidates.append((binary,))
        elif section in panels:
            candidates.append((binary, panels[section]))
    elif desktop == "xfce" and section in XFCE_TOOLS:
        candidates.append((XFCE_TOOLS[section],))

    candidates.extend((tool,) for tool in STANDALONE.get(section, ()))
    for program, *arguments in candidates:
        if executable := shutil.which(program):
            return executable, arguments
    return None


def open_settings(section):
    target = settings_command(section)
    if target is None:
        return False
    started, _ = QProcess.startDetached(*target)
    return started


def read_config(path):
    config = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        config.read(path, encoding="utf-8")
    except (configparser.Error, OSError, UnicodeError):
        config.clear()
    return config
