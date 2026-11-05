# TransferCachyOS

CachyOS’a yeni geçenler için uygulama seçme ve kurma aracı.

## Kademe 1

- Türkçe, İngilizce, Fransızca ve Almanca arayüz. Dil tercihi sonraki açılış için saklanır.
- Günlük kullanım, ofis ve okul, kodlama profilleri.
- Kurulu paketleri algılama, eksikleri önizleme, toplu kurulum ve işlem çıktısı.
- İşlem sonrasında paketleri tekrar tarama. Eksik kalan paketler aynı seçimden yeniden denenebilir.

## Kademe 2

- **Sistem** sekmesi üretici ve modeli, erişilebilir fan devirlerini ve donanım
  profilini gösterir. Sistem hizmeti erişilebilirse güç profili değiştirilebilir.
  Özel fan eğrileri için model ve sürücü bazında doğrulama gerekir.
- **Paketler** sekmesi kurulu pacman paketlerini ve sürümlerini aratır. Açıkça
  kurulmuş ve uygulamanın koruma listesi dışında kalan paketler, önizleme ve
  onaydan sonra tek tek kaldırılabilir. Pacman bağımlılık kontrolünü yapar.

## Kademe 3

- **Başlangıç** sekmesi klavye, varsayılan tarayıcı, PDF okuyucu, yazıcı, güncelleme
  ve yedekleme bilgilerini gösterir. Güncelleme sayısı yerel paket listesine
  dayanır. Yedek hedefi ve son yedekleme durumu bu ekranda doğrulanmaz.
- **Flathub** sekmesi seçilmiş uygulamaları önizleme ve onayla yükler. Var olan
  etkin Flathub kaynağını kullanır ve kurulum kapsamını gösterir. Hem kullanıcı
  hem sistem kaynağı varsa kullanıcı kaynağı seçilir. Kurulu uygulamalar
  **Aç** düğmesiyle başlatılabilir.

## Kademe 4

- **Windows’tan geçiş** sekmesi Office dosyaları, OneDrive dosyaları ve cihazlar
  arası aktarım için başlangıç adımlarını gösterir.
- **Yedekleme** sekmesi Restic ile seçilen klasörleri şifreli yerel depoya
  yedekler. Hedef boş bir klasör veya mevcut Restic deposu olabilir. Parola
  Restic’e işlem sırasında aktarılır ve uygulama ayarlarına kaydedilmez.
  Eksik yedekler ayrı durumla gösterilir.

## Kademe 5

- Mevcut depoyu seçip parolayı girerek yedekleri tarih, kimlik ve kaynak
  klasörleriyle listeleyebilirsin.
- Bir yedeği seçip parolayı yeniden girerek tüm dosyalarını depodan ayrı,
  boş bir klasöre geri yükleyebilirsin.
- Son 30 yedekleme ve geri yükleme sonucu yerel geçmişte tutulur. Geçmişe
  parola, klasör yolu veya işlem çıktısı yazılmaz.

## Kademe 6

- **Sistem** sekmesi açıkken pil seviyesi, şarj durumu, adaptör ve fan devri
  iki saniyede bir yenilenir. Güç hizmeti destekliyorsa pil ve adaptör
  olaylarına göre güç ayarlarını uyarlama seçeneği de açılır.
- Şarj üst sınırı sunan ASUS pillerde %60–100 aralığı seçilebilir.
  Değişiklik onay ve yönetici yetkisi gerektirir. Başlangıçta yeniden
  uygulama yapılmaz. KDE güç ayarlarından uyku ve ekran davranışları açılabilir.

## Kademe 7

1. **Bugün** ekranı pil, boş alan, güç profili, İndirilenler ve LocalSend
   kısayollarını bir araya getirir.
2. Son başarılı yedek ve son yedekleme sorunu görünür. Kullanıcı izin verirse
   başarılı yedeğin kaynakları ve hedefi hatırlanır. Hedef yeniden
   erişilebilir olduğunda yedek ekranı önceden doldurulabilir.
3. **Disk alanı** seçilen klasörde beş seviye derinliğe kadar 100 MiB üzeri
   dosyaları arar ve en büyük 100 sonucu gösterir. Dosyalar ayrı onayla
   Çöp Kutusu’na taşınır. Paket önbelleği dosya yöneticisinde açılır.
4. **Güncellemeler ve favoriler** sistem paketlerini ve kullanıcı/sistem
   Flatpak güncellemelerini ayrı sorgular. Favoriler Bugün ekranından açılır.
5. **Dizüstü** pil ve priz profillerini uygulama açıkken uygular. Bu ayar,
   güç hizmetinin kendi otomatik uyarlaması kapalıyken kullanılabilir.
   Desteklenen ASUS pillerde seyahat modu eski sınırı aynı açılış oturumunda
   sekiz saat sonra geri yüklemeyi planlar. Yeniden başlatma zamanlayıcıyı siler.
6. **Aygıtlar** Bluetooth, ses, ekran, ağ ve yazıcı ayarlarına erişim sağlar.
   KDE Plasma, GNOME, Xfce ve Cinnamon oturumlarında ilgili masaüstü
   araçları kullanılır. Uygun olduğunda kurulu bağımsız araçlar devreye
   girer. Araç bulunamadığında durum ekranda belirtilir.

## Arayüz

Ana gezinme beş bölümden oluşur: **Bugün**, **Uygulamalar**, **Sistem**,
**Yedekleme** ve **Rehber**. Dil seçimi pencerenin sağ üstündedir.
Yedekleme ekranında yeni yedek ve geri yükleme ayrı sekmelerdedir.
**Uygulamalar → Yüklü uygulamalar** doğrudan kurulan masaüstü uygulamalarını ve
Flatpak'leri adları, sürümleri ve kaynaklarıyla gösterir. Teknik sistem paketleri ayrı
görünümde açılabilir. Kaldırma işlemi bir öğeyle sınırlıdır ve onay ister.

## Sisteme kurma

Masaüstündeki TransferCachyOS klasöründe:

```bash
sudo ./install.sh
```

Kurulumdan sonra KDE uygulama menüsünden **TransferCachyOS**’u aç veya
`transfercachyos` komutunu çalıştır. Betik dosyaları `/usr/local` altına kopyalar.
Kaynak kodu değiştirdikten sonra kurulu kopyayı güncellemek için aynı komutu yeniden
çalıştır.

## Kaynak koddan çalıştırma

CachyOS masaüstü oturumunda, bu klasörün içinde:

```bash
/usr/bin/python3 main.py
```

Uygulama sistem Python’u ve PySide6 kullanır. PySide6 eksikse CachyOS’ta
`sudo pacman -Syu --needed pyside6` komutuyla kurulabilir. Kurulum için çalışan bir
Polkit doğrulama arayüzü gerekir. Uygulama normal kullanıcı olarak açılır ve paket
işlemi için `pkexec` üzerinden yetki ister.

## Kurulum davranışı

Plan ekranı seçilen uygulamaların eksik paketlerini listeler. Pacman bağımlılıkları
çözer ve paketlerle birlikte sistemin tamamını günceller. Pacman’ın varsayılan
yanıtları kullanılır. Kurulum sırasında pencere açık kalır.

Dört dil desteği TransferCachyOS
arayüzü içindir. Kurulan uygulamalar kendi dil ayarlarını kullanır.

## Sonraki kademe

İsteğe bağlı otomatik yedekleme zamanlaması.
