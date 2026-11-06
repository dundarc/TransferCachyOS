from dataclasses import dataclass


@dataclass(frozen=True)
class App:
    name: str
    packages: tuple[str, ...]
    profiles: frozenset[str]


APPS = (
    App('Firefox', ('firefox',), frozenset({'daily'})),
    App('LibreOffice', ('libreoffice-fresh',), frozenset({'office'})),
    App('Okular', ('okular',), frozenset({'office'})),
    App('Thunderbird', ('thunderbird',), frozenset({'office'})),
    App('VLC', ('vlc', 'vlc-plugins-all'), frozenset({'daily'})),
    App('KeePassXC', ('keepassxc',), frozenset({'daily'})),
    App('GIMP', ('gimp',), frozenset()),
    App('Skanpage', ('skanpage',), frozenset()),
    App('Remmina', ('remmina', 'freerdp'), frozenset()),
    App('Git', ('git',), frozenset({'coding'})),
    App('Code – OSS', ('code',), frozenset({'coding'})),
    App('Python + uv', ('python', 'uv'), frozenset({'coding'})),
    App('Node.js LTS + npm', ('nodejs-lts-krypton', 'npm'), frozenset()),
    App('Restic', ('restic',), frozenset()),
    App('OBS Studio', ('obs-studio',), frozenset()),
)
