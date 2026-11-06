import os
import shutil
import subprocess
from pathlib import Path

from .desktop import desktop_family

PACMAN = "/usr/bin/pacman"
PKEXEC = "/usr/bin/pkexec"
PROTECTED = frozenset({
    "base", "filesystem", "glibc", "systemd", "systemd-sysvcompat", "pacman",
    "bash", "sudo", "polkit", "python", "pyside6", "networkmanager", "grub",
    "plasma-desktop", "plasma-workspace", "sddm",
})


TERMINALS = {
    "konsole": ("--separate", "-e"),
    "gnome-terminal": ("--wait", "--"),
    "xfce4-terminal": ("--disable-server", "--execute"),
    "alacritty": ("-e",),
    "xterm": ("-e",),
}
SESSION_TERMINALS = {"kde": "konsole", "gnome": "gnome-terminal", "xfce": "xfce4-terminal"}
PACMAN_IN_TERMINAL = """
result_file=$1
close_prompt=$2
shift 2
/usr/bin/sudo -- /usr/bin/pacman -Syu --needed -- "$@"
result=$?
printf '%s\n' "$result" > "$result_file"
if (( result != 0 )) && [[ -t 0 ]]; then
    read -r -p "$close_prompt" || true
fi
exit "$result"
"""


def interactive_terminal():
    preferred = SESSION_TERMINALS.get(desktop_family())
    for name in dict.fromkeys((preferred, *TERMINALS)):
        if name and (executable := shutil.which(name)):
            return executable, TERMINALS[name]
    return None


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


def removable(name, explicit):
    return (
        name in explicit and name not in PROTECTED
        and name != "linux" and not name.startswith("linux-")
    )


def dependency_conflict(output):
    return any(phrase in output.casefold() for phrase in (
        "could not satisfy dependencies", "breaks dependency",
    ))
