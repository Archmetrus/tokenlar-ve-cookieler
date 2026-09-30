# Tokenlar ve cookieler

`ödev_yap` dosyasındaki ilk üç madde ve konuşmadaki açıklama için yerel laboratuvar:

1. Tarayıcı/curl GET isteklerinin başlıklarını, URL parametrelerini ve gövdesini dök.
2. `User-Agent` ve `Sec-CH-UA` başlıklarıyla curl isteklerini filtrele.
3. Kendi korunan sunucuna curl ile istek gönder; başlık taklidi, giriş, cookie ve bearer token kullanımını canlı izle.

## Çalıştırma

Python 3.10+ ve curl gerekir. Ek paket veya kurulum yok.

```bash
cd /home/ykk/Desktop/codex/PROJE/tokenlar-ve-cookieler
python3 server.py
```

Arayüz: **http://127.0.0.1:8000**. Başlık filtresini tarayıcıyla denemek için Chrome, Chromium veya Edge kullan. Sunucu yalnızca `127.0.0.1` üzerinde dinler. Port doluysa `python3 server.py --port 8001` kullan. Kapatmak için Ctrl+C.

Sunucu ve testler geliştirme sırasında çalıştırılmadı; testleri kullanıcı yapacak.

## Arayüzde ders sırası

1. **Tarayıcı GET gönder** ile `/echo` çıktısını gör. Aşağıdaki curl isteğiyle karşılaştır.
2. **Başlık** modunu seç ve altı deneyi çalıştır: normal curl ve yalnızca UA değişikliği 403; iki başlığın taklidi 200. Sahte token da bu modda 200 alır çünkü oturum kontrolü kapalıdır.
3. **Oturum** modunu seç ve deneyleri tekrarla: taklit başlık ve sahte token yeterli olmaz (401). Girişten alınan cookie veya bearer token ile 200 alınır.
4. **Giriş yap** ardından **Tarayıcıyla korunan adresi çağır**: tarayıcı HttpOnly cookieyi otomatik gönderir. **Çıkış yap** ile cookie oturumu iptal edilir.

Panel, `/echo`, `/login` ve yönetim yolları koruma filtresinin dışında; filtre `/protected` için uygulanır. Böylece filtre curlü engellese de deney paneli kullanılabilir. Yönetim POST isteklerinde yerel Origin ve özel kontrol başlığı aranır.

Canlı akış SSE ile aktarılır: sunucu isteği/kararı, çalıştırılan gerçek curl komutu, `-v` stderr ve cevap stdout. Terminal de sunucu olaylarını JSON satırları olarak gösterir. Son 300 olay bellekte tutulur. Akış kontrol bağlantıları günlüğe eklenmez. Deneyler tek tek çalışır; sınırsız döngü veya yük saldırısı yok.

## Elle curl kullanımı

Parametreli GET ve gövdeli POST dökümü:

```bash
curl -v 'http://127.0.0.1:8000/echo?isim=ogrenci&ders=cookie' -H 'X-Ders: ilk-madde'
curl -v http://127.0.0.1:8000/echo -H 'Content-Type: application/json' --data '{"mesaj":"merhaba"}'
```

Başlık modunda normal curl ile ret, sonra başlık taklidi:

```bash
curl -v http://127.0.0.1:8000/protected
curl -v http://127.0.0.1:8000/protected \
  -A 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140.0.0.0 Safari/537.36' \
  -H 'Sec-CH-UA: "Chromium";v="140", "Google Chrome";v="140"'
```

Giriş ve cookie kullanımı (`-c` kaydeder, `-b` gönderir):

```bash
curl -v http://127.0.0.1:8000/login \
  -H 'Content-Type: application/json' \
  --data '{"username":"ogrenci","password":"lab123"}' -c cookies.txt
curl -v http://127.0.0.1:8000/protected \
  -A 'Mozilla/5.0 Chrome/140.0.0.0' \
  -H 'Sec-CH-UA: "Chromium";v="140"' -b cookies.txt
```

Giriş cevabındaki `access_token` değerini kopyalayarak bearer kullan:

```bash
TOKEN='giris-cevabindaki-access_token'
curl -v http://127.0.0.1:8000/protected \
  -A 'Mozilla/5.0 Chrome/140.0.0.0' \
  -H 'Sec-CH-UA: "Chromium";v="140"' \
  -H "Authorization: Bearer $TOKEN"
```

`curl -v` istek/cevap başlıklarını stderr'e, cevap gövdesini stdout'a yazar. Curl çıkış kodu 0, HTTP 200 anlamına gelmez; 401/403 durumlarında da 0 olabilir. HTTP durum satırını incele.

## Deneyin anlattığı fark

`User-Agent` ve `Sec-CH-UA` istemcinin beyanıdır; curl bunları ayarlayabilir. Buradaki basit filtre, curlün varsayılan isteğini engeller; bütün curl isteklerini ayırt edemez. Chromium başlığını zorunlu tutmak Firefox/Safari gibi gerçek tarayıcıları da reddedebilir. [MDN Sec-CH-UA](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Sec-CH-UA).

Cookie bir saklama/gönderme mekanizmasıdır; bearer token bir yetkilendirme kullanım biçimidir. Burada ikisi de sunucuda tutulan, 15 dakikalık ayrı rastgele oturum değerleri kullanır; JWT uygulanmadı. Cookie tarayıcı tarafından otomatik gönderilir, bearer token `Authorization` başlığıyla açıkça gönderilir. Çıkış yalnızca istekte gönderilen cookie/tokenı iptal eder; diğer girişleri kapatmaz. Sunucu yeniden başlayınca tüm oturumlar kaybolur.

Demo bilgileri `ogrenci / lab123`. İstek gövdeleri, cookie ve Authorization başlıkları öğrenme amacıyla açıkça gösterilir. Cookie yerel HTTP için `HttpOnly; SameSite=Strict` kullanır; gerçek HTTPS uygulamasında `Secure` ve üretime uygun kimlik doğrulama gerekir. Bu uygulama bir üretim sunucusu değildir. [Python http.server](https://docs.python.org/3/library/http.server.html).
