"""Desktop smoke test. Requires a display; use xvfb-run on Linux CI."""
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Keep test profile separate from the real user's data.
temp = tempfile.TemporaryDirectory()
os.environ['XDG_DATA_HOME'] = temp.name
os.environ['XDG_CACHE_HOME'] = temp.name
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtWidgets import QApplication
from pluma.app import Window, STYLE

app = QApplication([])
app.setApplicationName('PlumaSmoke')
app.setStyleSheet(STYLE)
window = Window(private=True)
window.show()
assert window.profile.isOffTheRecord()
assert window.tabs.count() == 1
assert window.current().view is None  # Home creates no web renderer.
window.add_tab()
assert window.tabs.count() == 2
window.close_tab(1)
window.toggle_ai()
assert window.ai_panel is not None
assert not window.ai_panel.busy
window.toggle_ai()
tab = window.current()
view = tab.ensure_view()
result = {'loaded': False}


def loaded(ok):
    if not ok:
        app.quit()
        return
    view.page().toPlainText(verify_content)


def verify_content(text):
    result['loaded'] = 'Rendering OK' in text
    assert result['loaded']
    assert window.tabs.count() == 1
    window.add_tab()
    window.tabs.setCurrentWidget(tab)
    window.sync_toolbar()
    if os.environ.get('PLUMA_SCREENSHOT'):
        window.tabs.setCurrentIndex(1)
        window.toggle_ai()
        app.processEvents()
        window.grab().save(os.environ['PLUMA_SCREENSHOT'])
    window.close()
    app.quit()


view.loadFinished.connect(loaded)
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(b'<html><title>Pluma smoke</title><body><h1>Rendering OK</h1></body></html>')

    def log_message(self, *args):
        pass

server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
view.setUrl(QUrl(f'http://127.0.0.1:{server.server_port}'))
QTimer.singleShot(15000, app.quit)
app.exec()
server.shutdown()
assert result['loaded'], 'Chromium failed to render the smoke page'
print('PASS: native UI, tabs, lazy AI, private profile and Chromium rendering')
