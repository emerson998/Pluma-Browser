"""Frozen-package test using only a loopback fixture, never public browsing."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from PySide6.QtCore import QTimer, QUrl


def run(app, report_path):
    from .app import Window
    window = Window(private=True)
    window.show()
    report = Path(report_path)
    outcome = {'success': False, 'checks': []}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<title>Packaged Pluma</title><h1>Frozen Chromium works</h1>')
        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    view = window.current().ensure_view()

    def finish(code):
        report.write_text(json.dumps(outcome), encoding='utf-8')
        window.close()
        app.exit(code)

    def verify(text):
        outcome['success'] = 'Frozen Chromium works' in text and window.profile.isOffTheRecord()
        outcome['checks'] = ['private profile', 'bundled Qt', 'loopback navigation', 'Chromium text']
        finish(0 if outcome['success'] else 1)

    def loaded(ok):
        if ok:
            view.page().toPlainText(verify)
        else:
            finish(1)

    view.loadFinished.connect(loaded)
    view.setUrl(QUrl(f'http://127.0.0.1:{server.server_port}'))
    QTimer.singleShot(20000, lambda: finish(1))
    code = app.exec()
    server.shutdown()
    return code
