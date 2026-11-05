#!/usr/bin/bash
set -euo pipefail

source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
stage_dir=${DESTDIR:-}
prefix=/usr/local

if [[ -z "$stage_dir" && "$EUID" -ne 0 ]]; then
    printf '%s\n' 'Sistem kurulumu için sudo ./install.sh çalıştır.' >&2
    exit 1
fi

if [[ -n "$stage_dir" && ( "$stage_dir" != /* || ! -d "$stage_dir" ) ]]; then
    printf '%s\n' 'DESTDIR, var olan bir dizinin mutlak yolu olmalı.' >&2
    exit 1
fi

if [[ -z "$stage_dir" ]]; then
    if ! /usr/bin/python3 -I -c 'from PySide6 import QtWidgets' >/dev/null 2>&1; then
        printf '%s\n' 'PySide6 gerekli. Önce sudo pacman -Syu --needed pyside6 çalıştır.' >&2
        exit 1
    fi
    if [[ ! -x /usr/bin/pacman || ! -x /usr/bin/pkexec ]]; then
        printf '%s\n' 'TransferCachyOS, pacman ve pkexec bulunan bir CachyOS sistemi gerektirir.' >&2
        exit 1
    fi
fi

for file in main.py catalog.py system_tools.py setup_tools.py migration.py daily.py desktop_settings.py installed_apps.py set-charge-limit transfercachyos transfercachyos.desktop; do
    if [[ ! -f "$source_dir/$file" || ! -r "$source_dir/$file" ]]; then
        printf 'Kurulum dosyası eksik veya okunamıyor: %s\n' "$file" >&2
        exit 1
    fi
done

app_dir="$stage_dir$prefix/lib/transfercachyos"
install -Dm644 -- "$source_dir/main.py" "$app_dir/main.py"
install -Dm644 -- "$source_dir/catalog.py" "$app_dir/catalog.py"
install -Dm644 -- "$source_dir/system_tools.py" "$app_dir/system_tools.py"
install -Dm644 -- "$source_dir/setup_tools.py" "$app_dir/setup_tools.py"
install -Dm644 -- "$source_dir/migration.py" "$app_dir/migration.py"
install -Dm644 -- "$source_dir/daily.py" "$app_dir/daily.py"
install -Dm644 -- "$source_dir/desktop_settings.py" "$app_dir/desktop_settings.py"
install -Dm644 -- "$source_dir/installed_apps.py" "$app_dir/installed_apps.py"
install -Dm755 -- "$source_dir/set-charge-limit" "$app_dir/set-charge-limit"
install -Dm755 -- "$source_dir/transfercachyos" "$stage_dir$prefix/bin/transfercachyos"
install -Dm644 -- "$source_dir/transfercachyos.desktop" \
    "$stage_dir$prefix/share/applications/transfercachyos.desktop"

if [[ -n "$stage_dir" ]]; then
    printf 'Kurulum dosyaları hazırlandı: %s%s\n' "$stage_dir" "$prefix"
else
    printf '%s\n' 'TransferCachyOS kuruldu. KDE menüsünden veya transfercachyos komutuyla aç.'
fi
