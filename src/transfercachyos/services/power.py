import re
import subprocess
from pathlib import Path

from .commands import command

POWER = "/usr/bin/powerprofilesctl"
FIRMWARE = Path("/sys/firmware/acpi")
POWER_SUPPLIES = Path("/sys/class/power_supply")
CHARGE_HELPER = "/usr/local/lib/transfercachyos/set-charge-limit"


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


def battery_aware_state():
    try:
        value = command(POWER, "query-battery-aware").rpartition(":")[2].strip().casefold()
    except (OSError, subprocess.SubprocessError):
        return None
    return {"true": True, "false": False}.get(value)


def power_snapshot():
    try:
        profiles = re.findall(r"(?m)^\s*\*?\s*(power-saver|balanced|performance):", command(POWER, "list"))
        active = command(POWER, "get")
    except (OSError, subprocess.SubprocessError):
        return (), "", None
    return tuple(dict.fromkeys(profiles)), active, battery_aware_state()
