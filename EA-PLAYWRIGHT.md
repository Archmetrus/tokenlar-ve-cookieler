# EA sayfasını gerçek tarayıcıda açma

Birden fazla cookieyle çalışmak ve curl ile aynı oturumu kullanmak için [EA-SESSION.md](EA-SESSION.md) yönergelerini takip et. `--cookies-file ea-session.json` kullanıldığında yalnızca JSESSIONID yerine dosyadaki EA cookieleri yüklenir.

Kurulum (Arch Linux):

```bash
sudo pacman -Syu python-playwright chromium
```

Çalıştırma:

```bash
cd /home/ykk/Desktop/codex/PROJE/tokenlar-ve-cookieler
/usr/bin/python ea_account_playwright.py
```

JSESSIONID sorulunca yalnızca değerini yapıştır. Değer ekranda gösterilmez. Script sistem Chromium'unu görünür pencerede açar ve JSESSIONID cookie'sini `myaccount.ea.com` için ekler. Tarayıcı normal şekilde JavaScript, CSS ve sayfanın API isteklerini çalıştırır. [Playwright cookie API](https://playwright.dev/python/docs/api/class-browsercontext#browser-context-add-cookies).

1. Açılan pencerede sayfanın görünmesini bekle.
2. Terminalde Enter bas: ekran görüntüsü ve JavaScript sonrası HTML kaydedilir.
3. Tarayıcıyı kapatmak için terminalde tekrar Enter bas.

Kaydetmeden çıkmak için ilk istemde `q` yaz. Pencereyi erken kapattıysan terminalde Enter basarak scripti sonlandır.

Parametreyle de çalıştırabilirsin:

```bash
/usr/bin/python ea_account_playwright.py --jsessionid 'KENDI_JSESSIONID_DEGERIN'
```

Bu yöntem değeri terminal geçmişine ve süreç argümanlarına yazabilir; varsayılan gizli giriş yöntemini kullanabilirsin.

JSESSIONID ile giriş ekranına yönlendirilirsen normal giriş seçeneği:

```bash
/usr/bin/python ea_account_playwright.py --manual-login
```

Bu durumda açılan tarayıcıda kendi hesabına giriş yap; script parola veya doğrulama kodu istemez. Bir JSESSIONID her zaman tam giriş oturumunu taşımayabilir. Script oturumun geçerli olduğunu veya tarayıcıda tam olarak aynı ekranın oluşacağını varsaymaz.

## Kaydedilen dosyalar

Her çalıştırmada proje altında `ea-browser-...` klasörü açılır:

- `ekran.png`: tarayıcının oluşturduğu sayfanın tam ekran görüntüsü.
- `sayfa.html`: o andaki işlenmiş DOM. JavaScript dosyaları, resimler ve oturumla birlikte tam çevrimdışı arşiv değildir. Aynı görünümü incelemek için PNG'yi aç.

Klasör 0700, dosyalar 0600 izinleriyle kaydedilir; kişisel hesap bilgileri içerebilir. Klasör `.gitignore` ile dışlanır. Cookie ve tarayıcı oturumu ayrı bir kalıcı profile kaydedilmez. Terminalde yalnızca EA API yolları ve HTTP durumları gösterilir; cookie ve cevap gövdeleri yazdırılmaz.

Script kendi başına hesap ayarlarını değiştiren bir düğmeye tıklamaz. Tarayıcıda yaptığın işlemler canlı EA oturumunda gerçekleşir. Geliştirme sırasında script ve EA oturum testi çalıştırılmadı.

## Sistem Chromium'u uyumsuzluk gösterirse

Playwright'ın kendi Chromium sürümünü indirip kullanabilirsin:

```bash
/usr/bin/python -m playwright install chromium
/usr/bin/python ea_account_playwright.py --browser playwright
```

Playwright, kendi tarayıcı sürümleriyle çalışacak şekilde geliştirilir; başka executable seçimi uyumluluğu etkileyebilir. [Tarayıcı başlatma belgeleri](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch).
