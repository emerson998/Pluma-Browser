"""Offline integration fixture; never navigates to or signs in to YouTube."""
import json
import os
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
folder = tempfile.TemporaryDirectory()
os.environ['XDG_DATA_HOME'] = folder.name
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineCore import QWebEngineScript
from pluma.app import Window
from pluma.youtube import DATA_SCRIPT, DOM_SCRIPT, source

app = QApplication([])
app.setApplicationName('PlumaYouTubeFixture')
browser = Window(private=True)
# Extend the hostname guard ONLY in these test copies, to use loopback fixtures.
for index, (text, injection, world) in enumerate([
    (DATA_SCRIPT, QWebEngineScript.InjectionPoint.DocumentCreation, 0),
    (DOM_SCRIPT, QWebEngineScript.InjectionPoint.DocumentReady, 1),
]):
    script = QWebEngineScript()
    script.setName('Offline fixture ' + str(index))
    script.setWorldId(world)
    script.setInjectionPoint(injection)
    script.setSourceCode(source(text).replace("'www.youtube.com'", "'127.0.0.1'"))
    browser.profile.scripts().insert(script)

html = b"""<html><head><script>
window.ytInitialPlayerResponse={videoDetails:{videoId:'real'},streamingData:{url:'keep'},
  playerAds:[{}],adPlacements:[{}],adSlots:[{}]};
window.fixtureParsed=JSON.parse('{"videoDetails":{"videoId":"json"},"playerAds":[1]}');
</script></head><body>
<h1 id="content">Normal video page</h1>
<div id="movie_player" class="html5-video-player ad-showing">
<video width="320" height="180"></video>
<button class="ytp-skip-ad-button" onclick="window.skipped=true;this.parentElement.classList.remove('ad-showing')"
style="width:150px;height:40px">Skip ad</button></div>
<ytd-ad-slot-renderer id="banner">Sponsored</ytd-ad-slot-renderer>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(html)
    def log_message(self, *args):
        pass


server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
result = {'success': False, 'state': None}
started = time.monotonic()
view = browser.current().ensure_view()
browser.show()


def inspect():
    view.page().runJavaScript("""JSON.stringify({
        initial:window.ytInitialPlayerResponse,parsed:window.fixtureParsed,skipped:!!window.skipped,
        hidden:getComputedStyle(document.getElementById('banner')).display==='none',
        content:getComputedStyle(document.getElementById('content')).display!=='none'
    })""", checked)


def checked(value):
    try:
        state = json.loads(value)
    except (ValueError, TypeError):
        state = {}
    result['state'] = state
    if (state.get('skipped') and state.get('hidden') and state.get('content')
        and 'playerAds' not in state.get('initial', {})
        and 'adSlots' not in state.get('initial', {})
        and state.get('initial', {}).get('streamingData', {}).get('url') == 'keep'
        and 'playerAds' not in state.get('parsed', {})):
        result['success'] = True
        browser.close()
        app.quit()
    elif time.monotonic() - started < 10:
        QTimer.singleShot(100, inspect)
    else:
        browser.close()
        app.quit()


view.loadFinished.connect(lambda ok: inspect() if ok else app.quit())
view.setUrl(QUrl(f'http://127.0.0.1:{server.server_port}/watch'))
QTimer.singleShot(15000, app.quit)
app.exec()
server.shutdown()
assert result['success'], result['state']
print('PASS: early player data filtering, visible skip button, ad cosmetics and normal content preservation')
