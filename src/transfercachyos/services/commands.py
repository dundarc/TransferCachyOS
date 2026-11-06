import os
import subprocess


def command(*args):
    return subprocess.run(
        args, capture_output=True, text=True, errors="replace",
        timeout=5, check=True, env={**os.environ, "LC_ALL": "C"},
    ).stdout.strip()


def error_text(error):
    return getattr(error, "stderr", None) or str(error)


def probe(*args):
    try:
        return command(*args)
    except (OSError, subprocess.SubprocessError):
        return ""
