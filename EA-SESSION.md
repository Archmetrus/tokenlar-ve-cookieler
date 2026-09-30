# Aynı oturumu curl ve Playwright ile kullan

Scriptler ve oturumlu istekler geliştirme sırasında çalıştırılmadı. Buradaki komutları kendi terminalinde çalıştır.

## 1. Çalışan tarayıcı isteğinden yerel dosya hazırla

Normal tarayıcıda hesabına giriş yap. F12 → Network → Fetch/XHR altında `GET /am/data/1/account-information` isteğini seç. Response içindeki hesap bilgisi, çalışan isteği bulduğunu doğrular.

```bash
cd /home/ykk/Desktop/codex/PROJE/tokenlar-ve-cookieler
/usr/bin/python ea_session_setup.py
```

Program aşağıdaki **Request Headers** değerlerini sırayla sorar:

1. `cookie`: yalnızca değerini, yani tüm `name=value; name=value` satırını yapıştır. Response tarafındaki `set-cookie` satırını kullanma.
2. `x-csrf-token`: aynı istekteki değer. Cookie ile aynı oturumdan olmalı.
3. `user-agent`: aynı istekteki değer.
4. `sec-ch-ua`: varsa değer; yoksa Enter.
5. `accept-language`: varsa değer; yoksa Enter.

Cookie ve CSRF girişleri ekranda görünmez. Sonuç `ea-session.json` dosyasına 0600 izinleriyle kaydedilir; değerleri burada paylaşmana gerek yok. Dosya mevcutsa üzerine yazılmaz; yenisi için `--output ea-session-yeni.json` kullan.

**Bu hızlı yöntem, orijinal cookie kapsamını yeniden oluşturmaz.** HTTP Cookie başlığı domain, path, bitiş veya HttpOnly bilgilerini taşımaz. Script bu değerleri yalnızca `myaccount.ea.com`, `/` ve HTTPS kapsamına yerleştirir. Çalışan hesap isteğini aynı hostta tekrarlamak için kullanılır; diğer EA giriş servislerinin oturumunu da taşıdığı varsayılmaz. Aynı isimde farklı değerler varsa domain/path bilgili JSON yöntemini kullan.

## 2. Curl denemesi

Hesap verisini al:

```bash
/usr/bin/python ea_account_curl.py --cookies-file ea-session.json --api --verbose
```

Bu komut dosyadaki cookie, CSRF, User-Agent, Sec-CH-UA ve dil bilgisiyle hesap API'sine tek GET gönderir. Cookie ve CSRF değerleri terminalde gizlenir. Cevap `ea-output-....json` dosyasına kaydedilir. JSON içinde `result.eaid` ve maskelenmiş e-posta gibi alanların gelmesi hesap verisinin alındığını gösterir; yalnızca HTTP 200'e bakma.

İlk HTML cevabını önceki yöntemle almak için:

```bash
/usr/bin/python ea_account_curl.py --cookies-file ea-session.json --verbose
```

CSRF'yi HTML'den yeniden almak istersen:

```bash
/usr/bin/python ea_account_curl.py --cookies-file ea-session.json --api --bootstrap --verbose
```

İptal olmuş oturumun CSRF'sini yenilemek oturumu yeniden geçerli yapmaz. Yönlendirmeler takip edilmez; sınırsız tekrar yapılmaz. Curl geçici cookie deposunu günceller; asıl JSON dosyan değiştirilmez.

## 3. Playwright denemesi

```bash
/usr/bin/python ea_account_playwright.py --cookies-file ea-session.json
```

Chromium penceresi açılır. Cookie kayıtları yüklenir; dosyada varsa User-Agent uygulanır. CSS, JavaScript ve sayfanın API istekleri normal tarayıcı akışıyla çalışır. CSRF başlığını sayfanın kendi JavaScript'i HTML'den üretir; dosyadaki CSRF değeri bütün tarayıcı isteklerine zorla eklenmez. Sec-CH-UA ve Fetch Metadata başlıklarını tarayıcı yönetir.

Sayfa yüklenince terminalde Enter bas. Oluşan `ea-browser-...` klasöründe:

- `ekran.png`: görünen ekran.
- `sayfa.html`: işlenmiş DOM; tam çevrimdışı site arşivi değildir.
- `hesap.json`: tarayıcının hesap API isteği görülmüş ve cevap JSON ise o cevap.

Terminalde yalnızca API yolları ve HTTP durumları gösterilir. Sonraki Enter tarayıcıyı kapatır. Görünür sonuçla curl JSON'unu karşılaştır. Tarayıcı cookieleri bellekte günceller; kaynak JSON dosyan değiştirilmez.

## Domain/path bilgilerini koruyan JSON yöntemi

Elinde tarayıcıdan alınmış JSON cookie listesi varsa `--cookies-file` aynı dosyayı okuyabilir. Liste doğrudan `[...]` veya `{"cookies": [...]}` biçiminde olabilir. Playwright storage-state dosyasının cookies bölümü de desteklenir; origins/localStorage bölümü aktarılmaz.

[ea-session.example.json](ea-session.example.json) alan biçimini gösterir. Değerleri bilgisayarında doldur ve `ea-session.json` adıyla kaydet. Örnek dosyada yalnızca JSESSIONID vardır; tam oturum için kendi tarayıcındaki gerekli EA kayıtlarını ekle. Domain ve path'i DevTools Application → Cookies sütunlarından aynen al. Rastgele domain veya oturum değeri yazma.

Desteklenen cookie alanları: `name`, `value`, `domain`, `path`, `secure`, `httpOnly`, `sameSite`, `expires` (Unix saniye; oturum cookie'si için -1). `expirationDate` de kabul edilir. Süresi dolmuş kayıtlar kullanılmaz. Yalnızca EA domainleri kabul edilir. Curl formatı SameSite bilgisini temsil etmez; Playwright bu bilgiyi uygular. Partitioned cookie aktarımı bu dosya biçiminde desteklenmez.

Tek bir istekten kopyalanmış cookielerin çalışması garanti değildir; oturum süresi, sunucunun cookie güncellemeleri veya istemci kontrolleri sonucu değiştirebilir. Başlık taklidi geçerli oturum oluşturmaz.

Kaynaklar: [curl cookie dosyası biçimi](https://curl.se/docs/http-cookies.html), [Playwright cookie ekleme](https://playwright.dev/python/docs/api/class-browsercontext#browser-context-add-cookies).
