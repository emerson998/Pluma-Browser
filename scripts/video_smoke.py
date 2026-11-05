"""Actual VP8 playback, reparenting, resize and cleanup; local HTTP only."""
import base64
import json
import os
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
temp = tempfile.TemporaryDirectory()
os.environ['XDG_DATA_HOME'] = temp.name
os.environ['XDG_CACHE_HOME'] = temp.name

from PySide6.QtCore import QTimer, QUrl, QEvent, QCoreApplication, Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineCore import QWebEnginePage
from pluma.app import Window, STYLE
from pluma.selftest import VIDEO_FIXTURE
from pluma.floating_video import WORLD

app = QApplication([])
app.setApplicationName('PlumaVideoSmoke')
app.setStyleSheet(STYLE)
browser = Window(private=True)
browser.show()
tab = browser.current()
view = tab.ensure_view()
page = view.page()
result = {'done': False, 'error': None}
started = time.monotonic()

html = b"""<html><head><title>Video fixture</title></head>
<body style="margin:30px"><button style="position:fixed;top:0;left:0;width:80px;height:30px" onclick="document.querySelector(\'video\').play()">Play</button><h1 id="outside">Site content</h1>
<div style="transform:translateX(10px);contain:paint">
<video width="320" height="180" muted loop autoplay playsinline src="/clip.webm"></video>
</div><p>More site content</p></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        data = base64.b64decode(VIDEO_FIXTURE) if self.path == '/clip.webm' else html
        self.send_response(200)
        self.send_header('Content-Type', 'video/webm' if self.path == '/clip.webm' else 'text/html')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    def log_message(self, *args):
        pass


server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()


def fail(error):
    result['error'] = str(error)
    browser.close()
    app.quit()


def guarded(callback):
    def call(*args):
        try:
            if args and isinstance(args[0], str) and args[0].startswith('{'):
                args=(json.loads(args[0]),)+args[1:]
            callback(*args)
        except Exception as exc:
            fail(exc)
    return call


def wait_for_video():
    if time.monotonic() - started > 15:
        fail('Video did not start: ' + str(result.get('last_state')))
        return
    page.runJavaScript("(()=>{const v=document.querySelector('video');return JSON.stringify({playing:!v.paused&&v.readyState>=2,time:v.currentTime,ready:v.readyState,error:v.error&&v.error.code});})()",
                       guarded(playing))


def playing(state):
    result['last_state'] = state
    if not state or not state.get('playing'):
        QTimer.singleShot(100, wait_for_video)
        return
    result['time'] = state['time']
    browser.float_video()
    # Repeated clicks must not create another frame or disturb the CSS state.
    browser.float_video()
    QTimer.singleShot(200, guarded(detached))


def detached():
    frame = tab.floating_window
    assert frame is not None, 'No floating window'
    assert frame.view is view and frame.view.page() is page, 'Player was duplicated'
    assert frame.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    frame.resize(480, 310)
    frame.set_on_top(False)
    assert not frame.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    frame.set_on_top(True)
    browser.add_tab()
    tab.last_active = time.monotonic() - 86400
    browser.suspend_tabs()
    assert page.lifecycleState() == QWebEnginePage.LifecycleState.Active
    browser.showMinimized()
    assert frame.isVisible(), 'Minimizing browser hid floating video'
    page.runJavaScript(
        "(()=>{const v=document.querySelector('video');return JSON.stringify({playing:!v.paused,time:v.currentTime,focused:v.hasAttribute('data-pluma-floating-video'),hidden:getComputedStyle(document.getElementById('outside')).visibility==='hidden'});})()",
        guarded(verify_detached))


def verify_detached(state):
    assert state['playing'] and state['focused'] and state['hidden'], state
    frame = tab.floating_window
    frame.command('mute')
    page.runJavaScript("document.querySelector('video').muted", guarded(muted))


def muted(value):
    assert value is False, 'Mute control did not reach the same video'
    frame = tab.floating_window
    frame.command('play')
    page.runJavaScript("document.querySelector('video').paused", guarded(paused))


def paused(value):
    assert value is True
    tab.floating_window.command('play')
    tab.floating_window.return_to_tab()
    QTimer.singleShot(200, guarded(returned))


def returned():
    assert tab.floating_window is None
    assert tab.view is view and view.parentWidget() is tab
    page.runJavaScript(
        "(()=>{const v=document.querySelector('video');return JSON.stringify({playing:!v.paused,controls:v.controls,marked:v.hasAttribute('data-pluma-floating-video'),visibility:getComputedStyle(document.getElementById('outside')).visibility});})()",
        guarded(verify_returned))


def verify_returned(state):
    assert state['playing'] and not state['controls'] and not state['marked'], state
    assert state['visibility'] == 'visible', state
    browser.float_video()
    QTimer.singleShot(100, guarded(close_source))


def close_source():
    assert tab.floating_window
    import shiboken6
    frame = tab.floating_window
    browser.close_tab(browser.tabs.indexOf(tab))
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not shiboken6.isValid(frame), 'Closing the source left an orphan player'
    result['done'] = True
    browser.close()
    app.quit()


def loaded(ok):
    if not ok:
        fail('Page failed')
        return
    target = view.focusProxy() or view
    QTest.mouseClick(target, Qt.MouseButton.LeftButton, pos=QPoint(40,15))
    QTimer.singleShot(100, wait_for_video)
view.loadFinished.connect(loaded)
view.setUrl(QUrl(f'http://127.0.0.1:{server.server_port}/'))
QTimer.singleShot(20000, lambda: fail('Test timeout') if not result['done'] else None)
app.exec()
server.shutdown()
assert result['error'] is None, result['error']
assert result['done'], 'Video smoke did not finish'
print('PASS: actual video playback, same page, resize, topmost, background/minimize, controls, restore and teardown')
