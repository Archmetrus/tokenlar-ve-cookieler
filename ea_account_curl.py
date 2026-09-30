#!/usr/bin/env python3
"""EA hesap HTML'ini veya --api ile hesap verisini curl üzerinden indirir."""
import argparse
import getpass
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from ea_session import load_session, write_cookie_jar

URL = 'https://myaccount.ea.com/am/ui/account-information?gameId=ebisu'
API_URL = 'https://myaccount.ea.com/am/data/1/account-information'
DEFAULT_UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'


def redact(text, secrets):
    for secret in sorted(set(secrets), key=len, reverse=True):
        if secret:
            text = text.replace(secret, '[OTURUM GİZLENDİ]')
    # Verbose çıktısındaki hem gönderilen cookieyi hem yeni sunucu cookielerini gizle.
    return '\n'.join(
        re.sub(r'(?i)^([<>] (?:cookie|set-cookie|authorization|location):).*', r'\1 [GİZLENDİ]', line)
        if not line.startswith('* Added cookie ') and not line.startswith('* Replaced cookie ')
        else '* Cookie güncellendi [GİZLENDİ]'
        for line in text.splitlines()
    )


class MetaHeaders(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == 'meta' and values.get('name'):
            self.meta[values['name']] = values.get('content', '')


def cookie_secrets(cookie_file):
    values = []
    for line in cookie_file.read_text(errors='replace').splitlines():
        columns = line.split('\t')
        if len(columns) == 7:
            values.append(columns[6])
    return values


def report(process, secrets):
    stderr = process.stderr.decode('utf-8', errors='replace')
    match = re.search(r'^EA_HTTP_STATUS=(\d{3})$', stderr, re.MULTILINE)
    status = int(match.group(1)) if match else 0
    diagnostic = re.sub(r'^EA_HTTP_STATUS=\d{3}\n?', '', stderr, flags=re.MULTILINE).strip()
    if diagnostic:
        print(redact(diagnostic, secrets), file=sys.stderr)
    print(f'HTTP durumu: {status or "alınamadı"}')
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jsessionid', '--session-id', help='Yalnızca JSESSIONID değeri. Verilmezse gizli olarak sorulur.')
    parser.add_argument('--user-agent', help='User-Agent değeri; cookie dosyasındaki değeri geçersiz kılar.')
    parser.add_argument('--cookies-file', type=Path, help='EA cookieleri ve isteğe bağlı CSRF/UA başlıklarını içeren yerel JSON.')
    parser.add_argument('--bootstrap', action='store_true', help='Dosyada CSRF olsa bile HTML sayfasından yeni CSRF al (--api ile).')
    parser.add_argument('--sec-ch-ua', help='İsteğe bağlı Sec-CH-UA değeri; EA tarafından zorunlu olduğu varsayılmaz.')
    parser.add_argument('--output', type=Path, help='Cevabın kaydedileceği dosya; mevcut dosya üzerine yazılmaz.')
    parser.add_argument('--verbose', '-v', action='store_true', help='Cookie değerleri gizlenmiş curl -v çıktısı göster.')
    parser.add_argument('--api', action='store_true', help='Sayfadan CSRF ve güncel cookie al; hesap API cevabını JSON dosyasına kaydet.')
    args = parser.parse_args()
    if not shutil.which('curl'):
        parser.error('curl kurulu değil.')
    if args.cookies_file and args.jsessionid:
        parser.error('--cookies-file ve --jsessionid birlikte kullanılamaz.')
    session_data = {}
    session = None
    if args.cookies_file:
        try:
            session_data = load_session(args.cookies_file)
        except ValueError as error:
            parser.error(str(error))
    elif args.jsessionid is None:
        if not sys.stdin.isatty():
            parser.error('Terminalde çalıştırın veya --jsessionid parametresini kullanın.')
        session = getpass.getpass('JSESSIONID değeri (gizli giriş): ')
    else:
        session = args.jsessionid
    if not args.cookies_file and (not session or len(session) > 4096 or any(ord(char) < 33 or ord(char) > 126 or char in ';,"\\' for char in session)):
        parser.error('Geçersiz cookie değeri. JSESSIONID= önekini veya diğer cookieleri eklemeyin.')
    if session and session.startswith('JSESSIONID='):
        parser.error('JSESSIONID= önekini kaldırın; yalnızca değeri girin.')
    args.user_agent = args.user_agent or session_data.get('userAgent') or DEFAULT_UA
    if args.sec_ch_ua is None:
        args.sec_ch_ua = session_data.get('secChUa')
    for name, value in [('User-Agent', args.user_agent), ('Sec-CH-UA', args.sec_ch_ua)]:
        if value is not None and any(ord(char) < 32 or ord(char) == 127 for char in value):
            parser.error(f'{name} değeri kontrol karakteri içeremez.')
    extension = 'json' if args.api else 'html'
    output = (args.output or Path(__file__).parent / f'ea-output-{datetime.now():%Y%m%d-%H%M%S-%f}.{extension}').expanduser().resolve()
    if output.exists():
        parser.error('Çıktı dosyası zaten var; --output ile farklı bir ad seçin.')
    if not output.parent.is_dir():
        parser.error('Çıktı klasörü bulunamadı.')
    print(f'Cookie kaynağı: {"yerel JSON" if args.cookies_file else "JSESSIONID"}\nUser-Agent: {args.user_agent}')
    with tempfile.TemporaryDirectory(prefix='ea-session-') as folder:
        cookie_file = Path(folder) / 'cookie.txt'
        # Netscape cookie dosyası: yalnızca bu host, yalnızca HTTPS, oturum cookie.
        cookies = session_data.get('cookies') or [{'name': 'JSESSIONID', 'value': session, 'domain': 'myaccount.ea.com', 'path': '/', 'secure': True, 'httpOnly': True}]
        write_cookie_jar(cookie_file, cookies)
        print(f'{len(cookies)} cookie yüklendi; değerleri gizlendi.')
        command = [
            'curl', '-q', '--silent', '--show-error', '--compressed',
            '--proto', '=https', '--connect-timeout', '10', '--max-time', '30',
            '--cookie', str(cookie_file), '--cookie-jar', str(cookie_file), '--user-agent', args.user_agent,
            '--header', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            '--write-out', '%{stderr}\nEA_HTTP_STATUS=%{http_code}\n',
        ]
        if args.sec_ch_ua:
            command += ['--header', f'Sec-CH-UA: {args.sec_ch_ua}']
        if session_data.get('acceptLanguage'):
            command += ['--header', f'Accept-Language: {session_data["acceptLanguage"]}']
        if args.verbose:
            command.append('--verbose')
        # -L kullanılmaz: yönlendirme hedefinde oturum cookie'si tekrar gönderilmez.
        command.append(URL)
        secrets = [cookie['value'] for cookie in cookies]
        if session_data.get('csrfToken'):
            secrets.append(session_data['csrfToken'])
        try:
            if args.api:
                header_name = session_data.get('csrfHeaderName', 'X-CSRF-TOKEN')
                csrf = session_data.get('csrfToken', '')
                if not csrf or args.bootstrap:
                    print('1/2: HTML, güncel oturum cookieleri ve CSRF başlığı alınıyor.')
                    bootstrap = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=40)
                    page = MetaHeaders()
                    page.feed(bootstrap.stdout.decode('utf-8', errors='replace'))
                    header_name = page.meta.get('csrf-header-name', 'X-CSRF-TOKEN')
                    csrf = page.meta.get(header_name, '')
                    secrets.extend(cookie_secrets(cookie_file))
                    if csrf:
                        secrets.append(csrf)
                    bootstrap_status = report(bootstrap, secrets)
                    if bootstrap.returncode or not 200 <= bootstrap_status < 300:
                        print('Başlangıç sayfası alınamadı; API çağrısı yapılmadı.')
                        return bootstrap.returncode or 1
                else:
                    print('Yerel dosyadaki CSRF ile doğrudan hesap API isteği gönderiliyor.')
                if not csrf:
                    print('HTML içinde CSRF değeri bulunamadı; API çağrısı yapılmadı. Oturum sayfası yerine giriş ekranı dönmüş olabilir.')
                    return 1
                if not re.fullmatch(r'[A-Za-z0-9_-]+', header_name) or any(ord(char) < 32 or ord(char) == 127 for char in csrf):
                    print('Geçersiz CSRF başlık biçimi; API çağrısı yapılmadı.')
                    return 1
                api_headers = Path(folder) / 'api-headers.txt'
                api_headers.write_text(f'Accept: application/json\nContent-Type: application/json\nX-Requested-With: XMLHttpRequest\n{header_name}: {csrf}\n', encoding='utf-8')
                api_headers.chmod(0o600)
                command = command[:-1]
                # HTML Accept başlığı yerine API başlıkları kullanılır.
                accept_index = command.index('Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8')
                del command[accept_index - 1:accept_index + 1]
                command += ['--header', f'@{api_headers}', '--referer', URL, API_URL]
                print(f'GET {API_URL}\nCSRF başlığı: {header_name}=[GİZLENDİ]')
            else:
                print(f'GET {URL}')
            # Dosya sadece kullanıcı tarafından okunabilir; token curl argv içine konmaz.
            fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as response_file:
                process = subprocess.run(command, stdout=response_file, stderr=subprocess.PIPE, timeout=40)
        except subprocess.TimeoutExpired:
            print(f'İstek zaman aşımına uğradı. Kısmi çıktı: {output}', file=sys.stderr)
            return 1
        except OSError as error:
            print(f'İşlem yapılamadı: {error}', file=sys.stderr)
            return 1
        secrets.extend(cookie_secrets(cookie_file))
        status = report(process, secrets)
        print(f'Cevap dosyası: {output}')
        if process.returncode:
            print(f'curl çıkış kodu: {process.returncode}. Dosya boş veya kısmi olabilir.')
            return process.returncode
        if 300 <= status < 400:
            print('Yönlendirme cevabı geldi; otomatik takip edilmedi. JSESSIONID tek başına oturum için yeterli olmayabilir.')
        elif status in {401, 403}:
            print('Erişim reddedildi. Oturum süresi, cookie alan adı ve gerekli diğer oturum cookielerini tarayıcıda kontrol edin.')
        elif 200 <= status < 300:
            if args.api:
                try:
                    data = json.loads(output.read_text(encoding='utf-8'))
                except (ValueError, UnicodeError):
                    print('API 200 döndü ama cevap JSON değil. Ham cevap dosyaya kaydedildi; giriş veya engelleme sayfası olabilir.')
                    return 1
                output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                print('API JSON cevabı düzenli biçimde kaydedildi. Sonuç/hata alanlarını dosyadan inceleyebilirsin.')
            else:
                print('Cevap kaydedildi. HTTP 200, girişin başarılı olduğunu kanıtlamaz; HTML giriş sayfası veya uygulama kabuğu olabilir.')
        if not args.api:
            print('Hesap verisi için aynı komuta --api ekleyebilirsin.')
        return 0 if 200 <= status < 300 else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, EOFError):
        print('\nİşlem iptal edildi.', file=sys.stderr)
        raise SystemExit(130)
