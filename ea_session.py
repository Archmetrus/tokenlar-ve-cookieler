"""Curl ve Playwright için ortak, yerel EA cookie dosyası okuyucusu."""
import json
import math
import re
import time
from pathlib import Path


def header_value(value):
    return isinstance(value, str) and not any(ord(c) < 32 or ord(c) == 127 for c in value)


def load_session(path):
    try:
        raw = json.loads(Path(path).expanduser().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise ValueError('Oturum dosyası okunamadı veya geçerli JSON değil.') from None
    data = {'cookies': raw} if isinstance(raw, list) else raw
    if not isinstance(data, dict) or not isinstance(data.get('cookies'), list):
        raise ValueError('Dosyada cookies listesi bulunmalı.')
    cookies = []
    for item in data['cookies']:
        if not isinstance(item, dict):
            raise ValueError('Cookie kayıtları JSON nesnesi olmalı.')
        name, value = item.get('name'), item.get('value')
        domain, path = item.get('domain'), item.get('path')
        if not isinstance(name, str) or not re.fullmatch(r'[!#$%&\x27*+.^_`|~0-9A-Za-z-]+', name):
            raise ValueError('Geçersiz cookie adı.')
        if not header_value(value) or any(ord(c) > 126 or c == ';' for c in value):
            raise ValueError('Cookie değeri geçersiz karakter içeriyor.')
        if not isinstance(domain, str) or not re.fullmatch(r'\.?[A-Za-z0-9.-]+', domain):
            raise ValueError('Cookie domain bilgisi gerekli.')
        host = domain.lstrip('.').lower()
        if host != 'ea.com' and not host.endswith('.ea.com'):
            raise ValueError('Dosyada EA dışındaki bir domain var; yalnızca EA cookielerini ekleyin.')
        if not header_value(path) or not path.startswith('/'):
            raise ValueError('Cookie path bilgisi / ile başlamalı.')
        cookie = {'name': name, 'value': value, 'domain': domain.lower(), 'path': path}
        for flag in ('secure', 'httpOnly'):
            if flag in item:
                if not isinstance(item[flag], bool):
                    raise ValueError('secure/httpOnly değerleri true veya false olmalı.')
                cookie[flag] = item[flag]
        if item.get('sameSite'):
            aliases = {'strict': 'Strict', 'lax': 'Lax', 'none': 'None', 'no_restriction': 'None'}
            same_site = aliases.get(str(item['sameSite']).lower())
            if same_site:
                cookie['sameSite'] = same_site
        expiry = item.get('expires', item.get('expirationDate', -1))
        if isinstance(expiry, bool) or not isinstance(expiry, (int, float)) or not math.isfinite(expiry):
            raise ValueError('Cookie expires bilgisi Unix zamanı olarak sayı olmalı.')
        if expiry > 0:
            if expiry <= time.time():
                continue
            cookie['expires'] = expiry
        cookies.append(cookie)
    if not cookies:
        raise ValueError('Dosyada süresi geçmemiş EA cookie kaydı yok.')
    result = {'cookies': cookies}
    for key in ('userAgent', 'secChUa', 'acceptLanguage', 'csrfToken', 'csrfHeaderName'):
        if key in data:
            if not header_value(data[key]):
                raise ValueError('Oturum başlıkları geçerli metin olmalı.')
            result[key] = data[key]
    if not re.fullmatch(r'[A-Za-z0-9_-]+', result.get('csrfHeaderName', 'X-CSRF-TOKEN')):
        raise ValueError('Geçersiz CSRF başlık adı.')
    return result


def write_cookie_jar(path, cookies):
    lines = ['# Netscape HTTP Cookie File']
    for cookie in cookies:
        domain = cookie['domain']
        prefix = '#HttpOnly_' if cookie.get('httpOnly') else ''
        lines.append('\t'.join([
            prefix + domain, 'TRUE' if domain.startswith('.') else 'FALSE',
            cookie['path'], 'TRUE' if cookie.get('secure') else 'FALSE',
            str(int(cookie.get('expires', 0))), cookie['name'], cookie['value'],
        ]))
    Path(path).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    Path(path).chmod(0o600)
