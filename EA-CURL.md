# EA sayfasını JSESSIONID ile alma

Birden fazla cookieyi curl ve Playwright arasında paylaşmak için [ortak oturum yönergelerini](EA-SESSION.md) kullan. İki script de `--cookies-file ea-session.json` destekler.

Script varsayılan olarak şu adrese bir GET gönderir:

`https://myaccount.ea.com/am/ui/account-information?gameId=ebisu`

Python 3.10+ ve curl 7.63+ gerekir. Script geliştirme sırasında çalıştırılmadı; EA oturumuyla test edilmedi.

## Hesap verisini JSON olarak almak

```bash
python3 ea_account_curl.py --api --verbose
```

Parametre ile:

```bash
python3 ea_account_curl.py --api --jsessionid 'KENDI_JSESSIONID_DEGERIN' --verbose
```

Script önce HTML sayfasını alır. Gelen Set-Cookie güncellemelerini geçici cookie deposuna kaydeder; meta etiketlerinden CSRF başlık adı ve değerini okur. Ardından aynı cookie deposuyla `GET https://myaccount.ea.com/am/data/1/account-information` çağrısını yapar. `X-Requested-With: XMLHttpRequest`, JSON başlıkları, CSRF başlığı ve Referer eklenir. CSRF değeri terminal çıktısında gizlenir; süreç argümanlarına yazılmaz.

Cevap `ea-output-TARIH-SAAT.json` dosyasına kaydedilir. Özel isim için `--output ea-hesabim.json` ekle. Script yalnızca bu iki GET isteğini yapar; hesap ayarlarını değiştirmez. Bootstrap veya CSRF alımı başarısızsa API çağrısı yapılmaz; sonsuz tekrar yoktur.

API yolu ve başlıklar, indirilen sayfanın kullandığı [EA JavaScript dosyası](https://eacommerce.akamaized.net/statics_am/551.0.20260829.931.ee9990a110d7/statics/index.js) incelenerek bulundu: `Za` fonksiyonu account-information GET yolunu, `Be` fonksiyonu ortak başlıkları, `ps` değişkeni meta etiketlerinden CSRF okumasını tanımlıyor. Kimlik doğrulanmış API isteği geliştirme sırasında çalıştırılmadı. HTTP 200 JSON içinde de uygulama hatası bulunabilir; cevabı incele.

## Kullanım

```bash
cd "$(git rev-parse --show-toplevel)"
python3 ea_account_curl.py --verbose
```

JSESSIONID sorulunca **yalnızca değerini** yapıştır. Yazdığın değer ekranda görünmez.

İstediğin gibi parametre ile de verebilirsin:

```bash
python3 ea_account_curl.py --jsessionid 'BURAYA_KENDI_JSESSIONID_DEGERIN' --verbose
```

Parametreyle yazılan değer terminal geçmişinde ve süreç argümanlarında görünebilir. Gizli giriş istemi bu yüzden varsayılan yöntemdir.

Çıktı dosyası ve User-Agent seçmek için:

```bash
python3 ea_account_curl.py \
  --user-agent 'TARAYICINDAKI_USER_AGENT_DEGERI' \
  --output ea-hesabim.html --verbose
```

İstersen tarayıcıdaki Sec-CH-UA değerini `--sec-ch-ua 'DEGER'` ile ekleyebilirsin. Bu başlığın EA tarafından zorunlu olduğu doğrulanmadı; otomatik eklenmez.

## Öğrendiklerimizle ilişkisi

- `gameId=ebisu` URL sorgu parametresidir.
- `JSESSIONID` cookie adı; verdiğin değer oturum kimliğidir. JWT veya bearer olduğu varsayılmaz.
- İstekte `Cookie: JSESSIONID=...` gönderilir; değer URL'ye konmaz. Curl bunu geçici cookie dosyasından okur. [curl cookie seçeneği](https://curl.se/docs/manpage.html#-b).
- `--user-agent` curlün `-A` seçeneğine karşılık gelir. UA değiştirmek geçerli oturum üretmez.
- `--verbose`, curlün `-v` çıktısını gösterir; script cookie, Authorization ve Location satırlarındaki değerleri gizler.

Yanıt gövdesi `ea-output-TARIH-SAAT.html` dosyasına kaydedilir. Bu dosya kişisel hesap bilgileri içerebilir; Linux'ta yalnızca kullanıcı okuyabilir. Cookie dosyası işlem sonunda silinir. Çıktılar `.gitignore` içine eklenmiştir; özel isimli dosyaları ayrıca takip et.

Yönlendirmeler takip edilmez. 3xx, 401 veya 403 cevabında başka bir giriş cookie'si gerekebilir veya oturum bitmiş olabilir. 200 cevabı da giriş yapıldığını tek başına kanıtlamaz. Curl JavaScript çalıştırmadığı için sayfanın sonradan API ile aldığı hesap bilgileri HTML'de bulunmayabilir. API istek yapısı JavaScript'ten bulundu; kendi oturumunla çalışması henüz doğrulanmadı.
