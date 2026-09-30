const $ = id => document.getElementById(id);
let stateVersion = 0;
let statePending = false;
let running = false;
const experiments = {
  suite: {title: 'Altı yöntemi karşılaştır', description: 'Sırayla normal curl, yalnızca User-Agent, iki başlık taklidi, sahte token, girişten alınan cookie ve girişten alınan bearer token gönderilir. Cookie ve token deneylerinin her biri önce ayrı bir giriş isteği yapar.', headers: 'Normal curl ve yalnızca User-Agent: 403. Diğer dört deney: 200.', session: 'İlk iki deney: 403. İki başlık taklidi ve sahte token: 401. Geçerli cookie ve token: 200.'},
  plain: {title: 'Curl kendini gizlemeden istekte bulunur', description: 'GET /protected çağrılır. Curlün varsayılan User-Agent başlığı kullanılır; Sec-CH-UA, cookie ve token gönderilmez.', headers: '403 — User-Agent tarayıcı filtresini geçemez.', session: '403 — istek oturum kontrolüne ulaşmadan başlık filtresinde reddedilir.'},
  ua: {title: 'Sadece User-Agent değiştirilir', description: 'GET /protected için curlün User-Agent değeri tarayıcıya benzetilir. Sec-CH-UA hâlâ eksiktir; oturum bilgisi gönderilmez.', headers: '403 — User-Agent geçse de Sec-CH-UA eksiktir.', session: '403 — Sec-CH-UA eksik olduğu için oturum kontrolüne geçilmez.'},
  spoof: {title: 'İki tarayıcı başlığı taklit edilir', description: 'GET /protected isteğine tarayıcı görünümlü User-Agent ve Chromium Sec-CH-UA eklenir. Cookie veya token yoktur. Bu deney başlıkların curl ile taklit edilebildiğini gösterir.', headers: '200 — taklit başlıklar filtreyi aşar.', session: '401 — başlıklar geçer ancak geçerli oturum yoktur.'},
  fake: {title: 'Uydurma bearer token gönderilir', description: 'Taklit tarayıcı başlıklarına Authorization: Bearer uydurma-token eklenir. Bu değer giriş yapılarak alınmadığı için sunucuda kayıtlı değildir.', headers: '200 — bu mod tokenı doğrulamaz; yalnızca başlıkları kontrol eder.', session: '401 — sunucu uydurma tokenı kabul etmez.'},
  cookie: {title: 'Girişten alınan cookie tekrar kullanılır', description: 'Önce POST /login ile ogrenci / lab123 gönderilir. Curl -c ile Set-Cookie değerini dosyaya kaydeder; ardından -b ile GET /protected isteğinde gönderir. Tarayıcı başlıkları da eklenir.', headers: 'Giriş: 200. Korunan adres: 200 — başlıklar geçerlidir.', session: 'Giriş: 200. Korunan adres: 200 — sunucunun ürettiği cookie oturumu doğrular.'},
  bearer: {title: 'Girişten alınan token tekrar kullanılır', description: 'Önce POST /login ile ogrenci / lab123 gönderilir. Cevaptaki access_token alınır ve GET /protected isteğine Authorization: Bearer başlığı olarak eklenir. Tarayıcı başlıkları da eklenir.', headers: 'Giriş: 200. Korunan adres: 200 — başlıklar geçerlidir.', session: 'Giriş: 200. Korunan adres: 200 — sunucunun ürettiği bearer token doğrulanır.'}
};
function describeExperiment() {
  const experiment = experiments[$('scenario').value];
  $('scenarioTitle').textContent = experiment.title;
  $('scenarioHelp').textContent = experiment.description;
  $('scenarioExpected').textContent = $('mode').value === 'open' ? '200 — koruma kapalı; tüm deney istekleri kabul edilir.' : experiment[$('mode').value];
}
const help = {
  open: 'Filtre kapalı. Normal curl isteği de kabul edilir.',
  headers: 'Normal curl engellenir. İki başlığı taklit eden curl bu filtreyi aşabilir. Chromium tabanlı tarayıcı kullan.',
  session: 'Başlık kontrolünden sonra geçerli oturum aranır. Sahte token reddedilir; girişten alınan cookie veya token kabul edilir.'
};
function lock(value) {
  running = value;
  $('run').disabled = value;
  $('mode').disabled = value;
  $('scenario').disabled = value;
  $('run').textContent = value ? 'Deney çalışıyor…' : 'Curl deneyini başlat';
}
async function api(path, data) {
  const options = data === undefined ? {} : {
    method: 'POST', headers: {'Content-Type': 'application/json', 'X-Lab-Control': '1'}, body: JSON.stringify(data)
  };
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);
  let response, result;
  try {
    response = await fetch(path, {...options, signal: controller.signal});
    result = await response.json();
  } finally { clearTimeout(timeout); }
  if (!response.ok) throw new Error(result.error || result.message || `HTTP ${response.status}`);
  return result;
}
async function sync() {
  if (statePending) return;
  statePending = true;
  const version = stateVersion;
  try {
    const result = await api('/api/state');
    // An older state response must not lock controls again after a done event.
    if (version !== stateVersion) return;
    $('mode').value = result.mode;
    $('modeHelp').textContent = help[result.mode];
    describeExperiment();
    lock(result.running);
  } finally {
    statePending = false;
    if (version !== stateVersion) setTimeout(() => act(sync), 0);
  }
}
function append(event) {
  $('empty')?.remove();
  const labels = {request: 'Sunucu • gelen istek ve karar', command: 'Bilgisayar • çalıştırılan curl komutu', start: 'Deney başladı', step: 'Deney adımı', exit: 'curl işlemi tamamlandı', mode: 'Sunucu • koruma modu', done: 'Deney tamamlandı', error: 'Deney hatası'};
  let label = labels[event.kind] || event.kind;
  let type = event.kind;
  if (event.channel === 'stdout') { label = 'Sunucu → curl • cevap gövdesi (stdout)'; type = 'response'; }
  if (event.channel === 'stderr') {
    type = 'trace';
    label = event.text.startsWith('>') ? 'curl → sunucu • gönderilen istek başlığı' : event.text.startsWith('<') ? 'Sunucu → curl • cevap başlığı' : 'curl • bağlantı bilgisi (stderr)';
  }
  let content = event.kind === 'request' ? `${event.reason}\n\n${event.request.method} ${event.request.path}\n\nGelen başlıklar:\n${JSON.stringify(event.request.headers, null, 2)}\n\nGelen gövde:\n${event.request.body || '(boş)'}` :
    event.command ? event.command.map(arg => `'${arg.replaceAll("'", "'\\''")}'`).join(' ') : event.kind === 'step' ? experiments[event.scenario]?.title || event.message : event.text ?? event.message ?? JSON.stringify(event);
  const previous = $('stream').lastElementChild;
  // Consecutive output lines share a labeled block instead of repeating a label per line.
  if (event.kind === 'output' && previous?.dataset.label === label) {
    previous.querySelector('pre').textContent += '\n' + content;
    if ($('follow').checked) $('stream').scrollTop = $('stream').scrollHeight;
    return;
  }
  const row = document.createElement('div');
  row.className = `event ${type}`;
  row.dataset.label = label;
  const title = document.createElement('div');
  title.className = 'event-title';
  title.textContent = `${label}  |  ${event.time}`;
  if (event.status) {
    const badge = document.createElement('span');
    badge.className = `badge ${event.status >= 400 ? 'bad' : ''}`;
    badge.textContent = event.status;
    title.prepend(badge);
  }
  const pre = document.createElement('pre');
  pre.textContent = content;
  row.append(title, pre);
  $('stream').append(row);
  while ($('stream').children.length > 700) $('stream').firstElementChild.remove();
  if ($('follow').checked) $('stream').scrollTop = $('stream').scrollHeight;
}
async function act(task) {
  try { await task(); } catch (error) { $('notice').textContent = error.message; }
}
$('mode').addEventListener('change', () => act(async () => {
  try {
    const result = await api('/api/mode', {mode: $('mode').value});
    $('modeHelp').textContent = help[result.mode];
    describeExperiment();
    $('notice').textContent = 'Koruma modu güncellendi.';
  } catch (error) { await sync(); throw error; }
}));
$('run').addEventListener('click', () => act(async () => {
  stateVersion++;
  lock(true);
  try { await api('/api/run', {scenario: $('scenario').value}); $('notice').textContent = 'curl çıktıları canlı aktarılıyor.'; }
  catch (error) { stateVersion++; lock(false); await sync(); throw error; }
}));
for (const [id, path] of [['echo', '/echo?kaynak=tarayici&ders=tokenlar'], ['browser', '/protected']]) {
  $(id).addEventListener('click', () => act(async () => {
    const response = await fetch(path);
    const result = await response.json();
    $('notice').textContent = `HTTP ${response.status}: ${result.message}`;
  }));
}
$('login').addEventListener('click', () => act(async () => {
  const result = await api('/login', {username: 'ogrenci', password: 'lab123'});
  $('notice').textContent = result.message + ' Tarayıcı cookieyi otomatik kaydetti.';
}));
$('logout').addEventListener('click', () => act(async () => {
  const result = await api('/logout', {}); $('notice').textContent = result.message;
}));
$('clear').addEventListener('click', () => {
  $('stream').replaceChildren(); $('notice').textContent = 'Görünür çıktılar temizlendi. Sunucu geçmişi bellekte tutulur.';
});
const stream = new EventSource('/events');
stream.onopen = () => {
  $('connection').textContent = '● Canlı bağlantı açık'; act(sync);
};
stream.onerror = () => { $('connection').textContent = 'Bağlantı kesildi; yeniden bağlanılıyor…'; };
stream.onmessage = message => {
  const event = JSON.parse(message.data);
  append(event);
  if (event.kind === 'done') { stateVersion++; lock(false); }
  if (event.kind === 'mode') { $('mode').value = event.mode; $('modeHelp').textContent = help[event.mode]; describeExperiment(); }
  if (event.kind === 'done' || event.kind === 'error') $('notice').textContent = event.message;
};
$('scenario').addEventListener('change', describeExperiment);
// Reconcile with the server even if a completion event was lost during a disconnect.
setInterval(() => { if (running) act(sync); }, 1500);
describeExperiment();
act(sync);
