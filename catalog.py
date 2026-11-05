from dataclasses import dataclass

LANGUAGES = ("tr", "en", "fr", "de")


@dataclass(frozen=True)
class App:
    name: str
    packages: tuple[str, ...]
    profiles: frozenset[str]
    descriptions: tuple[str, str, str, str]


APPS = (
    App("Firefox", ("firefox",), frozenset({"daily"}), (
        "Web tarayıcısı", "Web browser", "Navigateur web", "Webbrowser")),
    App("LibreOffice", ("libreoffice-fresh",), frozenset({"office"}), (
        "Word, Excel ve PowerPoint dosyaları", "Word, Excel and PowerPoint files",
        "Fichiers Word, Excel et PowerPoint", "Word-, Excel- und PowerPoint-Dateien")),
    App("Okular", ("okular",), frozenset({"office"}), (
        "PDF okuma ve not alma", "Read and annotate PDFs", "Lire et annoter les PDF",
        "PDFs lesen und kommentieren")),
    App("Thunderbird", ("thunderbird",), frozenset({"office"}), (
        "Masaüstü e-posta", "Desktop email", "Messagerie de bureau", "Desktop-E-Mail")),
    App("VLC", ("vlc", "vlc-plugins-all"), frozenset({"daily"}), (
        "Video, müzik ve altyazı", "Video, music and subtitles",
        "Vidéo, musique et sous-titres", "Video, Musik und Untertitel")),
    App("KeePassXC", ("keepassxc",), frozenset({"daily"}), (
        "Yerel parola kasası", "Local password vault", "Coffre de mots de passe local",
        "Lokaler Passworttresor")),
    App("GIMP", ("gimp",), frozenset(), (
        "Fotoğraf ve görsel düzenleme", "Photo and image editing",
        "Retouche photo et image", "Foto- und Bildbearbeitung")),
    App("Skanpage", ("skanpage",), frozenset(), (
        "Tarayıcıdan çok sayfalı PDF", "Scan multiple pages to PDF",
        "Numériser plusieurs pages en PDF", "Mehrere Seiten als PDF scannen")),
    App("Remmina", ("remmina", "freerdp"), frozenset(), (
        "Windows Uzak Masaüstü (RDP)", "Windows Remote Desktop (RDP)",
        "Bureau à distance Windows (RDP)", "Windows-Remotedesktop (RDP)")),
    App("Git", ("git",), frozenset({"coding"}), (
        "Sürüm takibi", "Version control", "Gestion de versions", "Versionsverwaltung")),
    App("Code – OSS", ("code",), frozenset({"coding"}), (
        "Kod düzenleyici", "Code editor", "Éditeur de code", "Code-Editor")),
    App("Python + uv", ("python", "uv"), frozenset({"coding"}), (
        "Python geliştirme ortamı", "Python development environment",
        "Environnement de développement Python", "Python-Entwicklungsumgebung")),
    App("Node.js LTS + npm", ("nodejs-lts-krypton", "npm"), frozenset(), (
        "JavaScript geliştirme ortamı", "JavaScript development environment",
        "Environnement de développement JavaScript", "JavaScript-Entwicklungsumgebung")),
    App("Restic", ("restic",), frozenset(), (
        "Dosya yedekleme. Kurulumdan sonra hedefi ayarla.",
        "File backups. Configure a destination after installation.",
        "Sauvegarde de fichiers. Configurez une destination après l’installation.",
        "Dateisicherung. Nach der Installation ein Ziel einrichten.")),
    App("OBS Studio", ("obs-studio",), frozenset(), (
        "Ekran kaydı", "Screen recording", "Enregistrement d’écran", "Bildschirmaufnahme")),
)

TEXT = {
    "intro": ("Yeni bilgisayarında yapmak istediğin işlere göre uygulama seç.",
              "Choose apps for the things you want to do on your new computer.",
              "Choisissez les applications selon vos besoins sur votre nouvel ordinateur.",
              "Wähle Anwendungen für deine Aufgaben am neuen Computer."),
    "profile": ("Profil", "Profile", "Profil", "Profil"),
    "custom": ("Özel seçim", "Custom selection", "Sélection personnalisée", "Eigene Auswahl"),
    "daily": ("Günlük kullanım", "Everyday use", "Usage quotidien", "Alltag"),
    "office": ("Ofis ve okul", "Office and school", "Bureau et études", "Büro und Schule"),
    "coding": ("Kodlama", "Coding", "Développement", "Programmierung"),
    "ready": ("Hazır", "Ready", "Prêt", "Bereit"),
    "missing": ("Eksik", "Missing", "Manquant", "Fehlt"),
    "failed_app": ("Kurulum tamamlanmadı", "Installation incomplete",
                   "Installation incomplète", "Installation unvollständig"),
    "unknown": ("Durum bilinmiyor", "Status unknown", "État inconnu", "Status unbekannt"),
    "scan": ("Yeniden tara", "Rescan", "Analyser à nouveau", "Erneut prüfen"),
    "preview": ("Kurulum planı", "Installation plan", "Plan d’installation", "Installationsplan"),
    "apply": ("Güncelle ve kur", "Update and install", "Mettre à jour et installer",
              "Aktualisieren und installieren"),
    "cancel": ("Vazgeç", "Cancel", "Annuler", "Abbrechen"),
    "output": ("İşlem çıktısı", "Operation log", "Journal des opérations", "Vorgangsprotokoll"),
    "system": ("Masaüstü: {desktop}  •  Mimari: {arch}  •  Boş sistem alanı: {free:.1f} GiB",
               "Desktop: {desktop}  •  Architecture: {arch}  •  Free system space: {free:.1f} GiB",
               "Bureau : {desktop}  •  Architecture : {arch}  •  Espace système libre : {free:.1f} Gio",
               "Desktop: {desktop}  •  Architektur: {arch}  •  Freier Systemplatz: {free:.1f} GiB"),
    "unsupported": ("Kurulum için CachyOS, pacman ve pkexec gerekli.",
                    "Installation requires CachyOS, pacman and pkexec.",
                    "L’installation nécessite CachyOS, pacman et pkexec.",
                    "Die Installation benötigt CachyOS, pacman und pkexec."),
    "scan_error": ("Paket listesi okunamadı. Yeniden tara veya işlem çıktısına bak.",
                   "Could not read installed packages. Rescan or check the operation log.",
                   "Lecture des paquets installés impossible. Relancez l’analyse ou consultez le journal.",
                   "Installierte Pakete konnten nicht gelesen werden. Erneut prüfen oder das Protokoll öffnen."),
    "plan": (
        "Eksik paketler CachyOS/Arch depolarından kurulacak. Aynı işlem tüm sistemi günceller. Pacman sorularında varsayılan yanıtlar kullanılır.",
        "Missing packages will be installed from CachyOS/Arch repositories. This operation updates the whole system and uses pacman’s default answers.",
        "Les paquets manquants seront installés depuis les dépôts CachyOS/Arch. L’opération met à jour tout le système et utilise les réponses par défaut de pacman.",
        "Fehlende Pakete werden aus den CachyOS-/Arch-Repositorys installiert. Der Vorgang aktualisiert das gesamte System und verwendet die Standardantworten von pacman."),
    "running": ("Sistem güncelleniyor ve paketler kuruluyor…",
                "Updating the system and installing packages…",
                "Mise à jour du système et installation des paquets…",
                "System wird aktualisiert und Pakete werden installiert…"),
    "done": ("İşlem tamamlandı.", "Operation completed.", "Opération terminée.", "Vorgang abgeschlossen."),
    "failure": (
        "İşlem tamamlanamadı. Çıktıyı incele, ardından kalan paketler için yeniden dene.",
        "The operation did not complete. Review the log, then retry the remaining packages.",
        "L’opération n’a pas abouti. Consultez le journal, puis réessayez pour les paquets restants.",
        "Der Vorgang wurde nicht abgeschlossen. Protokoll prüfen und für die übrigen Pakete erneut versuchen."),
    "auth": ("Yönetici onayı verilmedi.", "Administrator authorization was declined.",
             "L’autorisation administrateur a été refusée.", "Administratorfreigabe wurde abgelehnt."),
    "close": ("Kurulum devam ediyor. Pencere işlem bittikten sonra kapatılabilir.",
              "Installation is running. Close the window after it finishes.",
              "L’installation est en cours. Fermez la fenêtre à la fin de l’opération.",
              "Die Installation läuft. Das Fenster kann nach Abschluss geschlossen werden."),
}
