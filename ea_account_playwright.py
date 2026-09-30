#!/usr/bin/env python3
"""EA sayfasını görünür Chromium penceresinde açar; DOM ve ekran görüntüsü kaydeder."""
import argparse
import asyncio
import getpass
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from ea_session import load_session

URL = 'https://myaccount.ea.com/am/ui/account-information?gameId=ebisu'


def private_write(path, content):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as file:
        file.write(content)


async def run(args, session, session_data):
    try:
        from playwright.async_api import async_playwright, Error, TimeoutError as PlaywrightTimeout
    except ImportError:
        print('Playwright bu Python ortamında bulunamadı. Sistem Python ile çalıştır: /usr/bin/python ea_account_playwright.py')
        return 1

    async with async_playwright() as playwright:
        options = {'headless': False}
        if args.browser != 'playwright':
            executable = shutil.which(args.browser)
            if not executable:
                print(f'Tarayıcı bulunamadı: {args.browser}')
                return 1
            options['executable_path'] = executable
        browser = None
        try:
            browser = await playwright.chromium.launch(**options)
            context_options = {'viewport': {'width': 1440, 'height': 1000}, 'locale': 'tr-TR'}
            if session_data.get('userAgent'):
                context_options['user_agent'] = session_data['userAgent']
            context = await browser.new_context(**context_options)
            if session_data.get('cookies'):
                await context.add_cookies(session_data['cookies'])
                print(f'{len(session_data["cookies"])} cookie yerel dosyadan yüklendi; değerleri gizlendi.')
            if session:
                await context.add_cookies([{
                    'name': 'JSESSIONID', 'value': session,
                    'domain': 'myaccount.ea.com', 'path': '/',
                    'httpOnly': True, 'secure': True, 'sameSite': 'Lax',
                }])
            page = await context.new_page()
            account_responses = []

            def response_info(response):
                parsed = urlsplit(response.url)
                if parsed.hostname == 'myaccount.ea.com' and parsed.path.startswith('/am/data/'):
                    print(f'[API] HTTP {response.status} {response.request.method} {parsed.path}', flush=True)
                    if parsed.path == '/am/data/1/account-information' and response.request.method == 'GET':
                        account_responses.append(response)

            def failed_request(request):
                parsed = urlsplit(request.url)
                if parsed.hostname in {'myaccount.ea.com', 'eacommerce.akamaized.net', 'eaaccounts.akamaized.net'}:
                    print(f'[İstek tamamlanamadı] {parsed.hostname}{parsed.path}', flush=True)

            page.on('response', response_info)
            page.on('requestfailed', failed_request)
            print('Chromium açılıyor. Cookie dosyasında varsa User-Agent uygulanır; diğer başlıkları tarayıcı yönetir.', flush=True)
            try:
                response = await page.goto(URL, wait_until='domcontentloaded', timeout=60000)
                print(f'[Sayfa] HTTP {response.status if response else "alınamadı"}', flush=True)
            except PlaywrightTimeout:
                print('İlk yükleme zaman aşımına uğradı; açık penceredeki durumu inceleyebilirsin.', flush=True)
            print('\nJavaScript ve CSS dosyaları bu pencerede çalışır. Sayfanın yüklenmesini bekle.')
            print('Giriş ekranı gelirse aktarılan oturum yeterli olmamış olabilir; açık pencerede kendi hesabına giriş yapabilirsin.')
            print('Sayfa istediğin görünüme gelince terminalde Enter bas. Kaydetmeden çıkmak için q yaz.')
            choice = await asyncio.to_thread(input, '> ')
            if choice.strip().lower() == 'q':
                return 0
            if page.is_closed():
                print('Tarayıcı sayfası kapatılmış; kayıt alınamadı.')
                return 1
            directory = Path(tempfile.mkdtemp(prefix='ea-browser-', dir=Path(__file__).parent))
            # Screenshot: tarayıcının çizdiği görünüm. HTML: JavaScript sonrası DOM.
            html = (await page.content()).encode('utf-8')
            image = await page.screenshot(full_page=True, timeout=30000)
            private_write(directory / 'sayfa.html', html)
            private_write(directory / 'ekran.png', image)
            if account_responses:
                try:
                    data = await account_responses[-1].json()
                    private_write(directory / 'hesap.json', (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
                    print(f'Tarayıcının aldığı hesap API cevabı: {directory / "hesap.json"}')
                except (ValueError, Error):
                    print('Hesap API cevabı JSON olarak kaydedilemedi; ekran ve HTML kaydedildi.')
            else:
                print('Hesap API cevabı görülmedi. Sayfa henüz yüklenmemiş veya giriş tamamlanmamış olabilir.')
            print(f'\nEkran görüntüsü: {directory / "ekran.png"}\nİşlenmiş HTML: {directory / "sayfa.html"}')
            print('HTML, çevrimdışı çalışan tam site arşivi değildir. Görünümü kontrol etmek için ekran.png dosyasını aç.')
            await asyncio.to_thread(input, '\nTarayıcıyı kapatmak için terminalde Enter bas: ')
            return 0
        except Error as error:
            # Hata çıktısındaki yönlendirme URL sorgularında oturum kodları bulunabilir.
            message = str(error)
            if session:
                message = message.replace(session, '[OTURUM GİZLENDİ]')
            for cookie in session_data.get('cookies', []):
                if cookie['value']:
                    message = message.replace(cookie['value'], '[COOKIE GİZLENDİ]')
            message = re.sub(r'https?://[^\s<>"\']+', '[URL GİZLENDİ]', message)
            print(f'Playwright hatası: {message}', file=sys.stderr)
            return 1
        finally:
            if browser and browser.is_connected():
                await browser.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jsessionid', '--session-id', help='Yalnızca JSESSIONID değeri; verilmezse gizli girişten sorulur.')
    parser.add_argument('--manual-login', action='store_true', help='Cookie ekleme; açılan tarayıcıda normal giriş yap.')
    parser.add_argument('--cookies-file', type=Path, help='Curl ile ortak kullanılan yerel EA cookie JSON dosyası.')
    parser.add_argument('--browser', default='/usr/bin/chromium', help='Chromium yolu veya Playwright tarayıcısı için playwright.')
    args = parser.parse_args()
    if sum(bool(value) for value in (args.manual_login, args.jsessionid, args.cookies_file)) > 1:
        parser.error('--manual-login, --jsessionid ve --cookies-file seçeneklerinden yalnızca birini kullan.')
    session = None
    session_data = {}
    if args.cookies_file:
        try:
            session_data = load_session(args.cookies_file)
        except ValueError as error:
            parser.error(str(error))
    elif not args.manual_login:
        if args.jsessionid is None and not sys.stdin.isatty():
            parser.error('Terminalden çalıştırın; JSESSIONID gizli girişle sorulacak.')
        session = args.jsessionid if args.jsessionid is not None else getpass.getpass('JSESSIONID değeri (gizli giriş): ')
        if not session or session.startswith('JSESSIONID=') or len(session) > 4096 or any(ord(char) < 33 or ord(char) > 126 or char in ';,"\\' for char in session):
            parser.error('Yalnızca geçerli cookie değerini girin; JSESSIONID= önekini eklemeyin.')
    try:
        return asyncio.run(run(args, session, session_data))
    except (KeyboardInterrupt, EOFError):
        print('\nİşlem iptal edildi.')
        return 130
    except OSError as error:
        print(f'Dosya veya tarayıcı işlemi yapılamadı: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
