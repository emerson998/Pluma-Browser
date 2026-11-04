"""Reuse one Chromium host process for OS URL launches (same OS user only)."""
import hashlib
import json
from PySide6.QtCore import QStandardPaths
from PySide6.QtNetwork import QLocalServer, QLocalSocket


def connect_instance(urls, private):
    root = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    name = 'pluma-' + hashlib.sha256(root.encode()).hexdigest()[:24]
    socket = QLocalSocket()
    socket.connectToServer(name)
    if socket.waitForConnected(250):
        socket.write(json.dumps({'urls': urls[:30], 'private': private}).encode())
        socket.waitForBytesWritten(500)
        socket.disconnectFromServer()
        return None, True
    server = QLocalServer()
    server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    if not server.listen(name):
        # Only remove stale endpoints after a failed connection attempt.
        QLocalServer.removeServer(name)
        if not server.listen(name):
            return None, False
    return server, False


def bind(server, window):
    if server is None:
        return
    clients = set()
    def accepted():
        while server.hasPendingConnections():
            client = server.nextPendingConnection()
            clients.add(client)
            client.buffer = b''
            def receive(c=client):
                c.buffer += bytes(c.readAll())
                data = c.buffer
                if len(data) > 65536:
                    c.disconnectFromServer()
                    return
                try:
                    values = json.loads(data)
                except ValueError:
                    return
                if not isinstance(values, dict):
                    c.disconnectFromServer()
                    return
                if values.get('private'):
                    window.new_private()
                    target = window.child_windows[-1]
                elif window.private:
                    if not getattr(window, 'normal_window', None):
                        from .app import Window
                        window.normal_window = Window()
                    target = window.normal_window
                else:
                    target = window
                target.close_pending = False
                target.timer.start()
                target.stats_timer.start()
                target.activate(target.tabs.currentIndex())
                urls = values.get('urls', [])
                for url in urls[:30] if isinstance(urls, list) else []:
                    if isinstance(url, str) and url.startswith(('https://', 'http://')) and len(url) < 8192:
                        target.add_tab(url)
                target.showNormal()
                target.raise_()
                target.activateWindow()
                c.disconnectFromServer()
            client.readyRead.connect(receive)
            def removed(c=client):
                clients.discard(c)
                c.deleteLater()
            client.disconnected.connect(removed)
    server.newConnection.connect(accepted)
