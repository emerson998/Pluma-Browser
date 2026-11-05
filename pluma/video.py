"""Floating video frame and YouTube ad removal.

Network/cosmetic blocking stays in the open-source Brave adblock-rust engine (EasyList,
EasyPrivacy). YouTube serves ads from the same hosts as the video, so this module adds a
small local script using the technique of uBlock Origin's YouTube filters (json-prune of the
ad fields in the player response) plus a fallback that mutes and skips any ad that slips by.
The script is bundled source code; nothing is downloaded or evaluated from filter lists.
"""
import json
import re
from urllib.parse import urlsplit, parse_qs

from PySide6.QtCore import Qt, QUrl, QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PySide6.QtWebEngineCore import QWebEngineScript, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

YOUTUBE_HOSTS = frozenset({'youtube.com', 'youtube-nocookie.com', 'youtu.be'})
_ID = re.compile(r'^[A-Za-z0-9_-]{11}$')
SCRIPT_NAME = 'pluma-youtube-noads'

# Keys YouTube uses to schedule ads and the anti-adblock dialog in player/next responses.
AD_KEYS = ('adPlacements', 'adSlots', 'playerAds', 'adBreakHeartbeatParams')

YOUTUBE_NOADS = r"""(() => {
  const host = location.hostname;
  if (!/(^|\.)youtube(-nocookie)?\.com$/.test(host) || window.__plumaNoAds) return;
  window.__plumaNoAds = true;
  const KEYS = %KEYS%;
  const prune = (o, depth = 0) => {
    if (!o || typeof o !== 'object' || depth > 4) return o;
    for (const k of KEYS) if (k in o) delete o[k];
    const msg = o.auxiliaryUi && o.auxiliaryUi.messageRenderers;
    if (msg) { delete msg.bkaEnforcementMessageViewModel; delete msg.enforcementMessageViewModel; }
    for (const k of ['playerResponse', 'response']) if (o[k]) prune(o[k], depth + 1);
    if (Array.isArray(o)) for (const x of o.slice(0, 8)) prune(x, depth + 1);
    return o;
  };
  // Initial player response embedded in the page.
  for (const name of ['ytInitialPlayerResponse', 'playerResponse']) {
    let value = window[name];
    try {
      Object.defineProperty(window, name, {
        configurable: true, get: () => value, set: v => { value = prune(v); },
      });
    } catch (e) {}
  }
  const parse = JSON.parse;
  JSON.parse = function () { return prune(parse.apply(this, arguments)); };
  const json = Response.prototype.json;
  Response.prototype.json = function () { return json.apply(this, arguments).then(prune); };
  const isPlayer = u => /\/youtubei\/v1\/(player|next|reel)/.test(String(u && u.url || u));
  const fetch0 = window.fetch;
  window.fetch = function (input) {
    const p = fetch0.apply(this, arguments);
    if (!isPlayer(input)) return p;
    return p.then(r => r.clone().text().then(t => {
      try {
        const body = JSON.stringify(prune(parse(t)));
        return new Response(body, { status: r.status, statusText: r.statusText, headers: r.headers });
      } catch (e) { return r; }
    }).catch(() => r));
  };
  // Hide ad slots/banners and the anti-adblock dialog.
  const css = `#player-ads, #masthead-ad, ytd-ad-slot-renderer, ytd-in-feed-ad-layout-renderer,
    ytd-promoted-sparkles-web-renderer, ytd-promoted-video-renderer, ytd-display-ad-renderer,
    ytd-banner-promo-renderer, ytd-statement-banner-renderer, ytd-companion-slot-renderer,
    ytd-action-companion-ad-renderer, ytd-player-legacy-desktop-watch-ads-renderer,
    ytd-rich-item-renderer:has(ytd-ad-slot-renderer), ytd-enforcement-message-view-model,
    tp-yt-iron-overlay-backdrop:has(+ ytd-enforcement-message-view-model),
    .ytp-ad-overlay-container, .ytp-ad-image-overlay, .ytp-ad-module .ytp-ad-overlay-slot,
    ytm-promoted-sparkles-web-renderer, ad-slot-renderer { display: none !important; }`;
  const addStyle = () => {
    if (document.getElementById('pluma-noads')) return;
    const s = document.createElement('style');
    s.id = 'pluma-noads';
    s.textContent = css;
    (document.head || document.documentElement).append(s);
  };
  addStyle();
  document.addEventListener('DOMContentLoaded', addStyle);
  // Fallback: if an ad still starts, it plays muted at max speed and is skipped at once.
  let muted = null;
  setInterval(() => {
    const player = document.querySelector('#movie_player, .html5-video-player');
    const video = player && player.querySelector('video');
    if (!video) return;
    const ad = player.classList.contains('ad-showing') || player.classList.contains('ad-interrupting');
    if (ad) {
      if (muted === null) muted = video.muted;
      video.muted = true;
      if (isFinite(video.duration) && video.duration > 0) video.currentTime = video.duration;
      video.playbackRate = 16;
      for (const b of document.querySelectorAll('.ytp-ad-skip-button, .ytp-ad-skip-button-modern, .ytp-skip-ad-button, .videoAdUiSkipButton'))
        b.click();
    } else if (muted !== null) {
      video.muted = muted;
      video.playbackRate = 1;
      muted = null;
    }
    const dialog = document.querySelector('ytd-enforcement-message-view-model');
    if (dialog) { dialog.closest('tp-yt-paper-dialog')?.remove(); if (video.paused) video.play(); }
  }, 250);
})();""".replace('%KEYS%', json.dumps(AD_KEYS))

# Makes the main video fill the floating frame. YouTube keeps its own controls.
FIT_SCRIPT = r"""(() => {
  if (window.__plumaFit) return;
  window.__plumaFit = true;
  let start = %START%;
  const css = `html, body { overflow: hidden !important; background: #000 !important; }
    #masthead-container, ytd-masthead, #secondary, #below, #comments, ytd-miniplayer,
    tp-yt-app-drawer, #guide { display: none !important; }
    #movie_player, [data-pluma-fit] { position: fixed !important; inset: 0 !important;
      width: 100vw !important; height: 100vh !important; max-width: none !important;
      max-height: none !important; z-index: 2147483647 !important; background: #000 !important; }
    #movie_player .html5-video-container { position: absolute !important; inset: 0 !important;
      width: 100% !important; height: 100% !important; }
    #movie_player video { position: absolute !important; width: 100% !important;
      height: 100% !important; left: 0 !important; top: 0 !important; object-fit: contain !important; }
    [data-pluma-fit] { object-fit: contain !important; }`;
  let w = 0, h = 0;
  const tick = () => {
    if (!document.getElementById('pluma-fit')) {
      const s = document.createElement('style');
      s.id = 'pluma-fit';
      s.textContent = css;
      (document.head || document.documentElement).append(s);
    }
    const player = document.querySelector('#movie_player');
    let video = player && player.querySelector('video');
    if (!player) {
      video = [...document.querySelectorAll('video')].sort((a, b) =>
        b.clientWidth * b.clientHeight - a.clientWidth * a.clientHeight)[0];
      if (video && !video.hasAttribute('data-pluma-fit')) {
        document.querySelectorAll('[data-pluma-fit]').forEach(n => n.removeAttribute('data-pluma-fit'));
        video.setAttribute('data-pluma-fit', '');
        video.controls = true;
      }
    }
    if (video && start > 0 && video.readyState >= 1 && video.duration > start) {
      video.currentTime = start;
      start = 0;
    }
    if (video && video.paused && video.readyState >= 2 && !video.dataset.plumaStarted) {
      video.dataset.plumaStarted = '1';
      video.play().catch(() => {});
    }
    if (player && (innerWidth !== w || innerHeight !== h)) {
      w = innerWidth; h = innerHeight;
      dispatchEvent(new Event('resize'));
    }
  };
  setInterval(tick, 500);
})();"""

# Reads the main video's position in a tab and pauses it so audio does not play twice.
TAKE_VIDEO = """(() => {
  const v = [...document.querySelectorAll('video')].sort((a, b) =>
    b.clientWidth * b.clientHeight - a.clientWidth * a.clientHeight)[0];
  if (!v) return -1;
  %LIVE%
  const t = live ? 0 : v.currentTime || 0;
  v.pause();
  return t;
})()"""

# Live streams return 0 so they reopen at the live edge instead of seeking into the DVR window.
_LIVE = """const yt = document.getElementById('movie_player');
  let live = !isFinite(v.duration);
  try { live = live || !!(yt && yt.getVideoData && yt.getVideoData().isLive); } catch (e) {}"""
TAKE_VIDEO = TAKE_VIDEO.replace('%LIVE%', _LIVE)

# "Popup" button over the main video of a tab. Runs in an isolated world, so the page cannot
# read the per-page token; clicks are reported to Qt as a console message carrying it.
POPUP_BUTTON = r"""(() => {
  if (window.__plumaPopup || window.top !== window) return;
  window.__plumaPopup = true;
  const TOKEN = %TOKEN%;
  const btn = document.createElement('button');
  btn.textContent = '⧉ Popup';
  btn.title = 'Abrir este vídeo em uma janela flutuante (Ctrl+Shift+P)';
  btn.style.cssText = 'position:fixed;z-index:2147483647;display:none;padding:6px 10px;border:0;' +
    'border-radius:8px;background:rgba(31,31,28,.88);color:#ece6d8;cursor:pointer;' +
    'font:500 12px "Host Grotesk","Segoe UI",sans-serif;box-shadow:0 2px 8px rgba(0,0,0,.4)';
  btn.addEventListener('click', e => {
    if (!e.isTrusted) return;
    e.preventDefault(); e.stopPropagation();
    btn.style.display = 'none';
    console.log(TOKEN);
  }, true);
  const main = () => {
    const p = document.querySelector('#movie_player');
    if (p && p.clientWidth >= 240) return p;
    return [...document.querySelectorAll('video')].filter(v => v.clientWidth >= 240 && v.clientHeight >= 135)
      .sort((a, b) => b.clientWidth * b.clientHeight - a.clientWidth * a.clientHeight)[0];
  };
  let last = 0, hide = 0, target = null;
  document.addEventListener('mousemove', e => {
    const now = performance.now();
    if (now - last < 150 || document.fullscreenElement) return;
    last = now;
    if (e.target !== btn) target = main();
    if (!target) return;
    const r = target.getBoundingClientRect();
    const inside = e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom;
    if (!inside && e.target !== btn) return;
    if (!btn.isConnected) document.documentElement.append(btn);
    btn.style.display = 'block';
    btn.style.top = Math.max(6, r.top + 12) + 'px';
    btn.style.left = Math.max(6, Math.min(innerWidth, r.right) - btn.offsetWidth - 12) + 'px';
    clearTimeout(hide);
    hide = setTimeout(() => { btn.style.display = 'none'; }, 2500);
  }, { passive: true, capture: true });
})();"""

CURRENT_TIME = """(() => { const v = document.querySelector('#movie_player video, [data-pluma-fit], video');
  if (!v) return 0;
  """ + _LIVE + """
  return live ? 0 : v.currentTime || 0; })()"""


def is_youtube(url: str) -> bool:
    from .core import host_matches
    return host_matches(urlsplit(url).hostname or '', YOUTUBE_HOSTS)


def youtube_id(url: str):
    """Video id from watch, youtu.be, shorts, embed and live links; None otherwise."""
    parts = urlsplit(url)
    if not is_youtube(url):
        return None
    path = parts.path.strip('/').split('/')
    candidate = None
    if (parts.hostname or '').endswith('youtu.be'):
        candidate = path[0] if path else None
    elif path and path[0] in ('shorts', 'embed', 'live', 'v') and len(path) > 1:
        candidate = path[1]
    else:
        candidate = (parse_qs(parts.query).get('v') or [None])[0]
    return candidate if candidate and _ID.match(candidate) else None


def floating_url(url: str, seconds: float = 0) -> str:
    """Canonical watch URL for YouTube links (keeps the position); other URLs unchanged."""
    video = youtube_id(url)
    if not video:
        return url
    start = int(max(0, seconds or 0))
    return f'https://www.youtube.com/watch?v={video}' + (f'&t={start}s' if start else '')


def popup_script(token):
    """Per-tab script that shows the Popup button; never installed in the floating frame."""
    script = QWebEngineScript()
    script.setName('pluma-popup')
    script.setSourceCode(POPUP_BUTTON.replace('%TOKEN%', json.dumps(token)))
    script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
    script.setWorldId(QWebEngineScript.ScriptWorldId.ApplicationWorld)
    script.setRunsOnSubFrames(False)
    return script


def install_youtube_script(profile, enabled=True):
    """Install/remove the YouTube ad script for every page of a profile, including embeds."""
    scripts = profile.scripts()
    for script in scripts.find(SCRIPT_NAME):
        scripts.remove(script)
    if not enabled:
        return
    script = QWebEngineScript()
    script.setName(SCRIPT_NAME)
    script.setSourceCode(YOUTUBE_NOADS)
    script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
    script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
    script.setRunsOnSubFrames(True)
    scripts.insert(script)


class FloatingVideo(QWidget):
    """Resizable, always-on-top frame that plays one video with the window's profile."""

    def __init__(self, window):
        # Top-level (no parent): an owned window would be hidden when the browser is minimized.
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.window = window
        self.url = ''
        self.restore_main = True  # Bring the browser back when the frame closes.
        from . import theme
        self.setWindowIcon(theme.app_icon())
        self.setWindowTitle('Pluma · Vídeo flutuante')
        self.setMinimumSize(260, 170)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        bar = QWidget()
        bar.setObjectName('pipbar')
        row = QHBoxLayout(bar)
        row.setContentsMargins(6, 3, 6, 3)
        self.title = QLabel('Vídeo')
        self.title.setObjectName('muted')
        row.addWidget(self.title, 1)
        from . import theme
        self.top = QPushButton(theme.icon('pin', size=15), '')
        self.top.setCheckable(True)
        self.top.setChecked(True)
        self.top.setToolTip('Manter sempre no topo')
        self.top.toggled.connect(self.set_on_top)
        back = QPushButton(theme.icon('undo-2', size=15), '')
        back.setToolTip('Voltar o vídeo para uma aba')
        back.clicked.connect(self.back_to_tab)
        close = QPushButton(theme.icon('x', size=15), '')
        close.setToolTip('Fechar')
        close.clicked.connect(self.close)
        for button in (self.top, back, close):
            button.setObjectName('icon')
            button.setAccessibleName(button.toolTip())
            button.setFixedSize(28, 26)
            row.addWidget(button)
        layout.addWidget(bar)
        from .app import Page
        self.view = QWebEngineView(self)
        page = Page(window.profile, self.view)
        page.settings().setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
        page.settings().setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, False)
        self.view.setPage(page)
        self.view.titleChanged.connect(lambda text: (self.title.setText(text[:60]), self.title.setToolTip(text)))
        page.newWindowRequested.connect(window.new_window)
        layout.addWidget(self.view, 1)
        geometry = None if window.private else window.settings.value('pip_geometry')
        if not (geometry and self.restoreGeometry(geometry)):
            self.resize(480, 300)
            screen = self.screen().availableGeometry()
            self.move(screen.right() - 500, screen.bottom() - 340)

    def play(self, url, seconds=0, minimize=False):
        self.url = floating_url(url, seconds)
        scripts = self.view.page().scripts()
        for script in scripts.find('pluma-fit'):
            scripts.remove(script)
        fit = QWebEngineScript()
        fit.setName('pluma-fit')
        # YouTube already seeks via &t=; other sites get the position applied by the script.
        start = 0 if youtube_id(url) else max(0, seconds or 0)
        fit.setSourceCode(FIT_SCRIPT.replace('%START%', json.dumps(float(start))))
        fit.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
        fit.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        scripts.insert(fit)
        self.view.setUrl(QUrl(self.url))
        self.show()
        self.raise_()
        if minimize:  # Only the small player stays on screen.
            self.window.showMinimized()

    def set_on_top(self, on):
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, on)
        self.show()

    def back_to_tab(self):
        def reopen(seconds):
            url = self.view.url().toString() or self.url
            self.window.add_tab(floating_url(url, seconds if isinstance(seconds, (int, float)) else 0))
            self.close()
        self.view.page().runJavaScript(CURRENT_TIME, reopen)

    def closeEvent(self, event):
        if not self.window.private:
            self.window.settings.setValue('pip_geometry', self.saveGeometry())
        # Stop playback and free the renderer; a new frame is built on next use.
        self.view.setUrl(QUrl('about:blank'))
        self.window.floating = None
        if self.restore_main and self.window.isMinimized():
            self.window.showNormal()
            self.window.activateWindow()
        self.deleteLater()
        super().closeEvent(event)
