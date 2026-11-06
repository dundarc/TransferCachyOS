import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..catalog import APPS
from .commands import command
from .desktop import read_config
from .flatpak import FLATPAK, SCOPES
from .packages import PACMAN, PROTECTED

APP_DIR = Path("/usr/share/applications")
APP_NAMES = {app.packages[0]: app.name for app in APPS}
PREFERRED_LAUNCHERS = {"libreoffice-fresh": "libreoffice-startcenter.desktop",
                       "libreoffice-still": "libreoffice-startcenter.desktop"}


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


def installed_inventory():
    versions, explicit, listing, error = {}, set(), "", None
    try:
        versions = dict(line.split(maxsplit=1) for line in command(PACMAN, "-Q").splitlines())
        explicit = set(command(PACMAN, "-Qqe").splitlines())
        listing = "\n".join(
            line for line in command(PACMAN, "-Ql").splitlines()
            if line.endswith(".desktop") and f" {APP_DIR}/" in line
        )
    except (OSError, subprocess.SubprocessError) as exception:
        error = exception
    return versions, explicit, listing, flatpak_entries(), error
