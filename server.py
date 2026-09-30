#!/usr/bin/env python3
"""Yerel HTTP, curl, cookie ve token laboratuvarı. Harici bağımlılık yok."""
import argparse
import http.cookies
import json
import secrets
import subprocess
import tempfile
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).parent
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'
CH = '"Chromium";v="140", "Google Chrome";v="140", "Not_A Brand";v="99"'
events = deque(maxlen=300)
condition = threading.Condition()
state_lock = threading.Lock()
run_lock = threading.Lock()
sessions = {}
mode = 'headers'
sequence = 0


def emit(kind, **data):
    global sequence
    with condition:
        sequence += 1
        event = dict(id=sequence, time=time.strftime('%H:%M:%S'), kind=kind, **data)
        events.append(event)
        condition.notify_all()
    print(json.dumps(event, ensure_ascii=False), flush=True)


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *_):
        pass

    def reply(self, status, data, headers=None):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode()
        self.send_bytes(status, body, 'application/json; charset=utf-8', headers)

    def send_bytes(self, status, body, content_type, headers=None):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Accept-CH', 'Sec-CH-UA')
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.handle_request()

    def do_POST(self):
        self.handle_request()

    def handle_request(self):
        global mode
        # Loopback binding plus Host validation prevents use through DNS rebinding.
        if self.headers.get('Host') not in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}:
            self.reply(403, {'error': 'Yerel Host gerekli.'})
            return
        path = urlsplit(self.path).path
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 0 or length > 16384 or self.headers.get('Transfer-Encoding'):
                self.reply(413, {'error': 'En fazla 16 KB gövde kabul edilir.'})
                self.close_connection = True
                return
            self.connection.settimeout(10)
            body = self.rfile.read(length).decode('utf-8', errors='replace')
        except (ValueError, TimeoutError):
            self.reply(400, {'error': 'Geçersiz istek gövdesi.'})
            self.close_connection = True
            return
        if path == '/events' and self.command == 'GET':
            self.stream()
            return
        if path in {'/jwt-cookie.html', '/scraping-user-agent.html'} and self.command == 'GET':
            self.send_bytes(200, (ROOT / path.lstrip('/')).read_bytes(), 'text/html; charset=utf-8')
            return
        assets = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'), '/style.css': ('style.css', 'text/css; charset=utf-8')}
        if path in assets and self.command == 'GET':
            file, mime = assets[path]
            self.send_bytes(200, (ROOT / 'static' / file).read_bytes(), mime)
            return
        if path == '/api/state' and self.command == 'GET':
            self.reply(200, {'mode': mode, 'running': run_lock.locked()})
            return
        if path in {'/api/mode', '/api/run'} and self.command == 'POST':
            expected = {f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'}
            if self.headers.get('Origin') not in expected or self.headers.get('X-Lab-Control') != '1':
                self.reply(403, {'error': 'Kontrolü yerel arayüzden yapın.'})
                return
            try:
                data = json.loads(body)
                if not isinstance(data, dict):
                    raise ValueError()
            except ValueError:
                self.reply(400, {'error': 'JSON nesnesi gerekli.'})
                return
            if path == '/api/mode':
                with state_lock:
                    if run_lock.locked():
                        self.reply(409, {'error': 'Çalışan deneyin bitmesini bekleyin.'})
                        return
                    if data.get('mode') not in {'open', 'headers', 'session'}:
                        self.reply(400, {'error': 'Geçersiz mod.'})
                        return
                    mode = data['mode']
                emit('mode', mode=mode, message='Koruma modu değiştirildi.')
                self.reply(200, {'mode': mode})
                return
            scenario = data.get('scenario')
            if scenario not in {'plain', 'ua', 'spoof', 'fake', 'cookie', 'bearer', 'suite'}:
                self.reply(400, {'error': 'Geçersiz senaryo.'})
                return
            with state_lock:
                if not run_lock.acquire(blocking=False):
                    self.reply(409, {'error': 'Bir deney zaten çalışıyor.'})
                    return
            threading.Thread(target=run_scenario, args=(scenario, self.server.server_port), daemon=True).start()
            self.reply(202, {'message': 'Deney başladı.'})
            return
        if path not in {'/echo', '/protected', '/login', '/logout'}:
            self.reply(404, {'error': 'Adres bulunamadı.'})
            return
        dump = {'method': self.command, 'path': self.path, 'headers': dict(self.headers.items()), 'body': body}
        status, reason, result, extra = 200, 'İstek kabul edildi.', {}, {}
        with state_lock:
            current_mode = mode
        if path == '/echo':
            result = {'request': dump}
        elif path == '/login':
            if self.command != 'POST':
                status, reason = 405, 'Giriş için POST kullanın.'
            else:
                try:
                    credentials = json.loads(body)
                    valid = isinstance(credentials, dict) and credentials.get('username') == 'ogrenci' and credentials.get('password') == 'lab123'
                except ValueError:
                    valid = False
                if not valid:
                    status, reason = 401, 'Kullanıcı adı veya parola yanlış.'
                else:
                    cookie, token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
                    with state_lock:
                        now = time.time()
                        for key in list(sessions):
                            if sessions[key]['expires'] <= now:
                                del sessions[key]
                        if len(sessions) >= 1000:
                            sessions.clear()
                        sessions[cookie] = {'expires': now + 900, 'type': 'cookie'}
                        sessions[token] = {'expires': now + 900, 'type': 'bearer'}
                    extra['Set-Cookie'] = f'lab_session={cookie}; HttpOnly; SameSite=Strict; Path=/; Max-Age=900'
                    result = {'access_token': token, 'token_type': 'Bearer', 'expires_in': 900}
                    reason = 'Giriş başarılı; cookie ve bearer token üretildi.'
        else:
            jar = http.cookies.SimpleCookie()
            try:
                jar.load(self.headers.get('Cookie', ''))
            except http.cookies.CookieError:
                pass
            cookie = jar['lab_session'].value if 'lab_session' in jar else ''
            auth = self.headers.get('Authorization', '')
            token = auth[7:] if auth.startswith('Bearer ') else ''
            with state_lock:
                now = time.time()
                authenticated = any(sessions.get(key, {}).get('expires', 0) > now and sessions[key]['type'] == kind for key, kind in [(cookie, 'cookie'), (token, 'bearer')])
                if path == '/logout' and self.command == 'POST':
                    sessions.pop(cookie, None)
                    sessions.pop(token, None)
            if path == '/logout':
                if self.command != 'POST':
                    status, reason = 405, 'Çıkış için POST kullanın.'
                else:
                    extra['Set-Cookie'] = 'lab_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'
                    reason = 'Gönderilen oturum bilgileri iptal edildi.'
            elif current_mode != 'open':
                ua = self.headers.get('User-Agent', '')
                ch = self.headers.get('Sec-CH-UA', '')
                if not ua.startswith('Mozilla/5.0') or 'curl/' in ua.lower():
                    status, reason = 403, 'User-Agent tarayıcı filtresini geçemedi.'
                elif '"Chromium"' not in ch and '"Google Chrome"' not in ch:
                    status, reason = 403, 'Sec-CH-UA Chromium/Chrome başlığı eksik.'
                elif current_mode == 'session' and not authenticated:
                    status, reason = 401, 'Geçerli cookie veya bearer token gerekli.'
            result = {'mode': current_mode, 'authenticated': authenticated, 'request': dump}
        emit('request', status=status, reason=reason, request=dump, mode=current_mode)
        self.reply(status, {'ok': status < 400, 'message': reason, **result}, extra)

    def stream(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.close_connection = True
        try:
            last = int(self.headers.get('Last-Event-ID', '0'))
        except ValueError:
            last = 0
        try:
            while True:
                with condition:
                    batch = [event for event in events if event['id'] > last]
                    if not batch:
                        condition.wait(timeout=10)
                        batch = [event for event in events if event['id'] > last]
                for event in batch:
                    self.wfile.write(f"id: {event['id']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n".encode())
                    last = event['id']
                if not batch:
                    self.wfile.write(b': heartbeat\n\n')
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            return


def curl(args):
    command = ['curl', '--noproxy', '*', '--connect-timeout', '3', '--max-time', '8', '-sS', '-v', *args]
    emit('command', command=command, message='curl çalıştırılıyor.')
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')
    chunks = []

    def drain(pipe, channel):
        for line in pipe:
            emit('output', channel=channel, text=line.rstrip('\n'))
            if channel == 'stdout':
                chunks.append(line)
        pipe.close()

    readers = [threading.Thread(target=drain, args=(process.stdout, 'stdout')), threading.Thread(target=drain, args=(process.stderr, 'stderr'))]
    for reader in readers:
        reader.start()
    code = process.wait()
    for reader in readers:
        reader.join()
    emit('exit', code=code, message=f'curl işlem çıkış kodu: {code}. HTTP durumunu çıktıdan kontrol edin.')
    return ''.join(chunks)


def run_scenario(scenario, port):
    base = f'http://127.0.0.1:{port}'
    browser = ['-A', UA, '-H', f'Sec-CH-UA: {CH}']
    try:
        emit('start', scenario=scenario, message='Yerel deney başladı.')
        for step in (['plain', 'ua', 'spoof', 'fake', 'cookie', 'bearer'] if scenario == 'suite' else [scenario]):
            emit('step', scenario=step, message=step)
            if step == 'plain':
                curl([base + '/protected'])
            elif step == 'ua':
                curl(['-A', UA, base + '/protected'])
            elif step == 'spoof':
                curl([*browser, base + '/protected'])
            elif step == 'fake':
                curl([*browser, '-H', 'Authorization: Bearer uydurma-token', base + '/protected'])
            else:
                with tempfile.TemporaryDirectory(prefix='cookie-lab-') as folder:
                    jar = str(Path(folder) / 'cookies.txt')
                    login = curl(['-c', jar, '-H', 'Content-Type: application/json', '--data', '{"username":"ogrenci","password":"lab123"}', base + '/login'])
                    if step == 'cookie':
                        curl([*browser, '-b', jar, base + '/protected'])
                    else:
                        token = json.loads(login)['access_token']
                        curl([*browser, '-H', f'Authorization: Bearer {token}', base + '/protected'])
    except Exception as error:
        emit('error', message=str(error))
    finally:
        run_lock.release()
        emit('done', message='Deney tamamlandı.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'Arayüz: http://127.0.0.1:{server.server_port}\nDemo giriş: ogrenci / lab123', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nSunucu kapatıldı.')
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
