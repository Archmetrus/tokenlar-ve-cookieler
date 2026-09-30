#!/usr/bin/env python3
"""Başarılı Network isteğinin cookie ve başlıklarını gizli girişle yerel dosyaya kaydet."""
import argparse
import getpass
import json
import os
import re
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(__file__).parent / 'ea-session.json')
    args = parser.parse_args()
    print('Normal tarayıcıda çalışan account-information GET isteğinin Request Headers değerlerini kullan.')
    print('Cookie satırının yalnızca değerini kopyala; cookie: önekini ekleme. Değerler ekranda gösterilmeyecek.')
    raw = getpass.getpass('Cookie: ')
    csrf = getpass.getpass('x-csrf-token: ')
    ua = input('User-Agent: ').strip()
    hints = input('Sec-CH-UA (yoksa Enter): ').strip()
    language = input('Accept-Language (yoksa Enter): ').strip()
    cookies = {}
    for part in raw.split(';'):
        name, separator, value = part.strip().partition('=')
        if not separator or not re.fullmatch(r'[!#$%&\x27*+.^_`|~0-9A-Za-z-]+', name):
            parser.error('Cookie satırı geçersiz; yalnızca name=value çiftlerini yapıştır.')
        if name in cookies and cookies[name]['value'] != value:
            parser.error('Aynı isimde farklı değerler var. Domain/path bilgisi içeren JSON cookie listesini kullan.')
        # Request Cookie başlığında scope yoktur. Yalnızca hedef host için dar kapsam oluşturulur.
        cookies[name] = {'name': name, 'value': value, 'domain': 'myaccount.ea.com', 'path': '/', 'secure': True}
    if not csrf or not ua or any(ord(c) < 32 or ord(c) == 127 for c in raw + csrf + ua + hints + language):
        parser.error('Cookie, CSRF ve User-Agent gerekli; kontrol karakteri kullanma.')
    data = {'cookies': list(cookies.values()), 'csrfToken': csrf, 'csrfHeaderName': 'X-CSRF-TOKEN', 'userAgent': ua}
    if hints:
        data['secChUa'] = hints
    if language:
        data['acceptLanguage'] = language
    try:
        fd = os.open(args.output.expanduser(), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        print(f'{len(cookies)} cookie kaydedildi: {args.output}')
        print('Network başlığında domain/path bulunmadığı için bu dosya yalnızca myaccount.ea.com / kapsamına ayarlandı.')
    except FileExistsError:
        parser.error('Dosya zaten var; --output ile yeni ad seç veya eski dosyayı kendin kaldır.')


if __name__ == '__main__':
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print('\nİşlem iptal edildi.')
