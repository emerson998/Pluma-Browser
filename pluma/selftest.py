"""Frozen-package test using only a loopback fixture, never public browsing."""
import json
import base64
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from PySide6.QtCore import QTimer, QUrl


VIDEO_FIXTURE = 'GkXfo59ChoEBQveBAULygQRC84EIQoKEd2VibUKHgQJChYECGFOAZwEAAAAAAAP5EU2bdLpNu4tTq4QVSalmU6yBoU27i1OrhBZUrmtTrIHYTbuMU6uEElTDZ1OsggEeTbuMU6uEHFO7a1OsggPj7AEAAAAAAABZAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAVSalmsirXsYMPQkBNgI1MYXZmNjAuMTYuMTAwV0GNTGF2ZjYwLjE2LjEwMESJiECfQAAAAAAAFlSua8GuAQAAAAAAADjXgQFzxYhKxy9NWIdtm5yBACK1nIN1bmSIgQCGhVZfVlA4g4EBI+ODhAX14QDgibCBoLqBWpqBAhJUw2f8c3OgY8CAZ8iaRaOHRU5DT0RFUkSHjUxhdmY2MC4xNi4xMDBzc9ZjwItjxYhKxy9NWIdtm2fIoUWjh0VOQ09ERVJEh5RMYXZjNjAuMzEuMTAyIGxpYnZweGfIoUWjiERVUkFUSU9ORIeTMDA6MDA6MDIuMDAwMDAwMDAwAB9DtnVCPueBAKPNgQAAgHAFAJ0BKqAAWgAARwiFhYiFhIgCAgJ08kDoLGqpNdxDqqTXcQ6qk13EOqpNdxDqqTXcQ6YA/v0+AGkQg//s7v/+nd//07v73wCjmIEAZAARAgABEBAAGAAYWC/0AAiAgQAAAKOYgQDIABECAAEQEAAYABhYL/QACICBAAAAo5iBASwAEQIAARAQABgAGFgv9AAIgIEAAACjmIEBkAARAgABEBAAGAAYWC/0AAiAgQAAAKOYgQH0ABECAAEQEAAYABhYL/QACICBAAAAo5iBAlgAEQIAARAQABgAGFgv9AAIgIEAAACjl4ECvADxAQABEBAUYABhYL/QACICBAAAo5iBAyAAEQIAARAQABgAGFgv9AAIgIEAAACjmIEDhAARAgABEBAAGAAYWC/0AAiAgQAAAKOYgQPoABECAAEQEAAYABhYL/QACICBAAAAo5iBBEwAEQIAARAQABgAGFgv9AAIgIEAAACjmIEEsAARAgABEBAAGAAYWC/0AAiAgQAAAKOYgQUUABECAAEQEAAYABhYL/QACICBAAAAo5iBBXgAEQIAARAQABgAGFgv9AAIgIEAAACjmIEF3AARAgABEBAAGAAYWC/0AAiAgQAAAKOYgQZAABECAAEQEAAYABhYL/QACICBAAAAo5iBBqQAEQIAARAQABgAGFgv9AAIgIEAAACjl4EHCADxAQABEBAUYABhYL/QACICBAAAo5iBB2wAEQIAARAQABgAGFgv9AAIgIEAAAAcU7trkbuPs4EAt4r3gQHxggGf8IED'

def run(app, report_path):
    from .app import Window
    window = Window(private=True)
    window.show()
    report = Path(report_path)
    outcome = {'success': False, 'checks': []}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            clip = self.path == '/clip.webm'
            self.send_header('Content-Type', 'video/webm' if clip else 'text/html')
            self.end_headers()
            self.wfile.write(base64.b64decode(VIDEO_FIXTURE) if clip else
                b'<title>Packaged Pluma</title><h1>Frozen Chromium works</h1><video width="320" height="180" muted src="/clip.webm"></video>')
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
        if not outcome['success']:
            finish(1)
            return
        from .floating_video import FOCUS_VIDEO, WORLD
        view.page().runJavaScript(FOCUS_VIDEO, WORLD, floating)

    def floating(found):
        try:
            if not found:
                raise ValueError('Bundled video detection failed')
            from .floating_video import FloatingVideoWindow
            tab = window.current()
            original_page = view.page()
            frame = FloatingVideoWindow(tab)
            frame.show()
            frame.resize(480, 310)
            assert frame.view is view and frame.view.page() is original_page
            frame.close()
            assert tab.floating_window is None and tab.view is view
            outcome['checks'].extend(['floating video', 'same Chromium page', 'return to tab'])
            finish(0)
        except Exception as exc:
            outcome['success'] = False
            outcome['error'] = str(exc)
            finish(1)

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
