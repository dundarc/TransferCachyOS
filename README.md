# TransferCachyOS

TransferCachyOS helps people set up and maintain a CachyOS desktop, with a
getting-started guide for users moving from Windows. The interface is available
in English, Turkish, French, and German.

> **Beta — development is ongoing.** Use this application with caution. Review
> each operation before confirming package installations, package removals, or
> hardware setting changes. Back up important files before making system changes.

## Install

From the project directory on CachyOS:

```bash
sudo ./install.sh
```

Open **TransferCachyOS** from your desktop's application menu or run
`transfercachyos`. The installer copies the application to `/usr/local`.
Run it again to update the installed copy after changing the source.

The application uses the system Python and PySide6. If PySide6 is missing:

```bash
sudo pacman -Syu --needed pyside6
```

To run directly from the source directory:

```bash
/usr/bin/python3 main.py
```

Run the application as your normal user. System package operations and
supported charge limit changes request administrator authorization through
Polkit. A desktop Polkit authentication agent is required for those prompts.

## Features

| Section | What you can do |
| --- | --- |
| **Today** | See battery status, free disk space, and the last successful backup. Open Downloads, favorites, or LocalSend when available. |
| **Apps** | Select apps by profile, review installation plans, install selected Flathub apps, and manage installed apps by name. Turn on **Show technical packages** to see the full pacman package list. Check system and Flatpak updates separately. |
| **System** | Monitor battery, charger, and reported fan speed. Select available power profiles, find large files, and open device settings. |
| **Backup** | Back up selected folders to an encrypted local Restic repository, list snapshots, and restore a snapshot to a separate empty folder. Review the last 30 backup and restore results. |
| **Guide** | Check keyboard layout, default apps, and printer availability. Find starting points for Office files, OneDrive files, and file transfers. |

## How system changes work

- **System packages.** Installing selected pacman packages also refreshes the
  package databases and upgrades the system. Pacman resolves dependencies and
  uses its default answers. Removal targets one selected item and is subject to
  pacman's dependency checks and the app's protection rules.
- **Flatpak.** Installation uses an existing enabled Flathub remote. The
  confirmation shows the installation scope. If both user and system remotes
  are available, new installations use the user remote.
- **Power and hardware.** Available power profiles depend on the system's power
  profile service. Fan speeds are read from available sensors. Custom fan
  curves are outside the current feature set. Supported ASUS batteries can
  use a charge limit from 60% to 100%. Travel mode schedules the previous limit
  to return after eight hours in the same boot. Restarting clears its timer.
- **Desktop settings.** Shortcuts support KDE Plasma, GNOME, Xfce, and
  Cinnamon. Other sessions can use compatible standalone tools when installed.
- **Backups.** Restic is required. Keep the repository password somewhere safe.
  TransferCachyOS does not save it. Backup paths are remembered only when you
  enable that preference. History stores the operation time and result.
  Backups are started manually.
- **Disk cleanup.** The large-file scan shows up to 100 results. After
  confirmation, the selected file moves to Trash. Disk space is reclaimed
  when Trash is emptied.
