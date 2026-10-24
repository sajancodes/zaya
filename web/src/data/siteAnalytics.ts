const consentKey = 'zaya-site-analytics';
const visitorKey = 'zaya-site-visitor';
const sessionKey = 'zaya-site-session';
let lastPage = '';
export const preference = () => { try { return localStorage.getItem(consentKey) || 'unset'; } catch { return 'no'; } };
export const privacySignal = () => typeof navigator !== 'undefined' && (navigator.doNotTrack === '1' || (navigator as Navigator & {globalPrivacyControl?:boolean}).globalPrivacyControl === true);
export function setPreference(value: string) {
  try {
    localStorage.setItem(consentKey, value);
    if (value !== 'yes') { localStorage.removeItem(visitorKey); localStorage.removeItem(sessionKey); lastPage = ''; }
  } catch { /* Storage denied: analytics stays disabled. */ }
}

function sourceCategory(): string {
  try {
    const host = new URL(document.referrer).hostname.toLowerCase();
    if (host === location.hostname) return 'direct';
    if (/(^|\.)(google\.[a-z.]+|bing\.com|duckduckgo\.com|search\.yahoo\.com|baidu\.com|yandex\.[a-z]+)$/.test(host)) return 'search';
    if (/(^|\.)(facebook\.com|instagram\.com|linkedin\.com|twitter\.com|x\.com|tiktok\.com|youtube\.com|whatsapp\.com)$/.test(host)) return 'social';
    return 'referral';
  } catch { return 'direct'; }
}

function context() {
  const now = Date.now();
  const valid = (value: unknown) => typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
  let visitor; let session;
  try { visitor = JSON.parse(localStorage.getItem(visitorKey) || 'null'); } catch { /* Replace invalid local state. */ }
  if (!visitor || !valid(visitor.id) || !Number.isFinite(visitor.created) || now - visitor.created > 30*86400000) {
    visitor = {id: crypto.randomUUID(), created: now};
    localStorage.setItem(visitorKey, JSON.stringify(visitor));
  }
  try { session = JSON.parse(localStorage.getItem(sessionKey) || 'null'); } catch { /* Replace invalid local state. */ }
  if (!session || !valid(session.id) || !Number.isFinite(session.last) || now - session.last > 30*60000) session = {id: crypto.randomUUID(), source: sourceCategory()};
  session.last = now;
  localStorage.setItem(sessionKey, JSON.stringify(session));
  return {visitor_id: visitor.id, session_id: session.id, source: session.source};
}

function send(path: string, kind: 'view' | 'download', platform = 'none') {
  if (privacySignal() || preference() !== 'yes' || path.startsWith('/admin')) return;
  try {
    void fetch('/api/site-events', {method:'POST', credentials:'omit', referrerPolicy:'no-referrer', keepalive:true,
      headers:{'Content-Type':'application/json'}, body:JSON.stringify({consent:true, event_id:crypto.randomUUID(), ...context(), path, kind, platform})}).catch(() => {});
  } catch { /* Tracking must never break navigation or downloads. */ }
}

export function trackPage(path: string) {
  if (path.startsWith('/admin')) { lastPage = ''; return; }
  if (preference() !== 'yes' || privacySignal() || lastPage === path) return;
  lastPage = path;
  send(path, 'view');
}

export function trackDownload(event: MouseEvent, path: string) {
  const anchor = (event.target as Element | null)?.closest?.('a');
  if (!anchor) return;
  try {
    const url = new URL(anchor.href);
    const internal = url.origin === location.origin ? /^\/(?:download|api\/downloads\/beta)\/(windows|linux|android)(?:\/(?:exe|deb|rpm|portable))?$/.exec(url.pathname) : null;
    const official = url.hostname === 'github.com' && url.pathname.startsWith('/sajancodes/zaya-companion-releases/releases/download/');
    const platform = internal?.[1] || (official ? /\.exe$/i.test(url.pathname) ? 'windows' : /\.apk$/i.test(url.pathname) ? 'android' : /\.(deb|rpm|AppImage|tar\.gz)$/i.test(url.pathname) ? 'linux' : '' : '');
    if (platform) send(path, 'download', platform);
  } catch { /* Ignore non-download links. */ }
}
