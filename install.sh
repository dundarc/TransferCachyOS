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

manifest="$source_dir/packaging/install-manifest.txt"
while read -r mode source destination extra; do
    if [[ "$mode" != 644 && "$mode" != 755 ]] ||
       [[ -z "$source" || -z "$destination" || -n "$extra" ||
          "$source" == /* || "$destination" == /* ||
          "/$source/" == */../* || "/$destination/" == */../* ]]; then
        printf '%s\n' 'Kurulum manifesti geçersiz.' >&2
        exit 1
    fi
    if [[ ! -f "$source_dir/$source" || ! -r "$source_dir/$source" ]]; then
        printf 'Kurulum dosyası eksik veya okunamıyor: %s\n' "$source" >&2
        exit 1
    fi
done < "$manifest"

while read -r mode source destination; do
    install -Dm"$mode" -- "$source_dir/$source" "$stage_dir$prefix/$destination"
done < "$manifest"

if [[ -n "$stage_dir" ]]; then
    printf 'Kurulum dosyaları hazırlandı: %s%s\n' "$stage_dir" "$prefix"
else
    printf '%s\n' 'TransferCachyOS kuruldu. uygulama menüsünden veya transfercachyos komutuyla aç.'
fi
