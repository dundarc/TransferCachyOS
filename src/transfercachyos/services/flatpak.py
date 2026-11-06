import subprocess

from .commands import command, probe

FLATPAK = "/usr/bin/flatpak"
SCOPES = ("user", "system")
FLATHUB_URLS = {"https://dl.flathub.org/repo", "https://flathub.org/repo"}
FLATHUB_APPS = (
    ("org.onlyoffice.desktopeditors", "ONLYOFFICE", "office"),
    ("net.cozic.joplin_desktop", "Joplin", "notes"),
    ("org.localsend.localsend_app", "LocalSend", "share"),
)


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
