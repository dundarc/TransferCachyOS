import ast
import os
import re
import shlex
import subprocess
from pathlib import Path

from PySide6.QtCore import QStandardPaths

from .commands import command, probe
from .desktop import desktop_family, read_config
from .packages import PACMAN


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


def checklist_snapshot():
    printer, queues = "printer_missing", ""
    if os.access("/usr/bin/lpstat", os.X_OK):
        try:
            queues = ", ".join(command("/usr/bin/lpstat", "-e").splitlines())
            printer = "printer_none"
        except (OSError, subprocess.SubprocessError):
            printer = "printer_unknown"
    return (
        keyboard_layout(),
        probe("/usr/bin/xdg-settings", "get", "default-web-browser"),
        probe("/usr/bin/xdg-mime", "query", "default", "application/pdf"),
        printer,
        queues,
        update_count(),
        bool(probe(PACMAN, "-Q", "restic")),
    )
