"""Native Qt shell. All remote content stays inside Chromium."""
import sys
import time
from pathlib import Path

from PySide6.QtCore import QUrl, Qt, QTimer, QSettings, QStandardPaths, QThread, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QTabWidget, QToolBar, QDockWidget, QTextEdit, QPlainTextEdit,
    QComboBox, QLabel, QCheckBox, QMessageBox, QFileDialog, QDialog,
    QDialogButtonBox, QFormLayout,
)
from PySide6.QtWebEngineCore import (
    QWebEnginePage, QWebEngineProfile, QWebEngineSettings, QWebEngineUrlRequestInterceptor,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from .core import navigation_url, should_block, lifecycle_action, validate_endpoint
from .ai import PRESETS, ask

STYLE = """
QMainWindow, QDialog, QWidget { background: #111416; color: #e7ecea; font: 13px 'Segoe UI'; }
QToolBar { border: none; spacing: 6px; padding: 10px; }
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox { background: #1d2325; border: 1px solid #343d3d; border-radius: 8px; padding: 9px; selection-background-color: #35685b; }
QPushButton, QToolButton { background: #242d2d; border: none; border-radius: 7px; padding: 8px 12px; }
QPushButton:hover, QToolButton:hover { background: #354744; }
QPushButton:disabled { color: #6c7976; }
QTabWidget::pane { border: 0; }
QTabBar::tab { background: #111416; color: #99aaa4; padding: 10px 16px; min-width: 90px; max-width: 220px; }
QTabBar::tab:selected { background: #26332f; color: #a8e8cb; border-top: 2px solid #8bd5b5; }
QDockWidget::title { padding: 12px; background: #1b2321; }
QLabel#hero { font-size: 46px; font-weight: 600; color: #b9efd7; }
QLabel#muted { color: #a5b7af; font-size: 15px; }
QStatusBar { color: #a5b7af; }
"""


class Blocker(QWebEngineUrlRequestInterceptor):
    hit = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.allowed = frozenset()

    def interceptRequest(self, info):
        if should_block(info.requestUrl().toString(), info.firstPartyUrl().toString(), self.allowed):
            info.block(True)
            self.hit.emit()


class Page(QWebEnginePage):
    def __init__(self, profile, parent):
        super().__init__(profile, parent)
        self.certificateError.connect(lambda error: error.rejectCertificate())

    def acceptNavigationRequest(self, url, kind, is_main):
        # No local filesystem, javascript navigation or external protocol launch.
        return url.scheme() in ('http', 'https', 'about') and (
            url.scheme() != 'about' or url.toString() == 'about:blank'
        )


class BrowserTab(QWidget):
    def __init__(self, window, url=None):
        super().__init__()
        self.window = window
        self.last_active = time.monotonic()
        self.protected = False
        self.view = None
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.home = QWidget()
        box = QVBoxLayout(self.home)
        box.setContentsMargins(80, 60, 80, 60)
        box.addStretch()
        title = QLabel('pluma')
        title.setObjectName('hero')
        box.addWidget(title)
        subtitle = QLabel('Menos distração. Mais espaço para navegar.')
        subtitle.setObjectName('muted')
        box.addWidget(subtitle)
        search = QLineEdit()
        search.setPlaceholderText('Pesquisar ou digitar endereço')
        search.returnPressed.connect(lambda: self.navigate(search.text()))
        box.addWidget(search)
        note = QLabel('Proteção nativa • Abas em repouso • IA quando você precisar')
        note.setObjectName('muted')
        note.setWordWrap(True)
        box.addWidget(note)
        box.addStretch()
        self.layout.addWidget(self.home)
        if url:
            self.navigate(url)

    def ensure_view(self):
        if self.view:
            return self.view
        self.home.hide()
        self.view = QWebEngineView(self)
        page = Page(self.window.profile, self.view)
        self.view.setPage(page)
        self.layout.addWidget(self.view)
        self.view.titleChanged.connect(lambda title: self.window.tab_title(self, title))
        self.view.urlChanged.connect(lambda _: self.window.sync_toolbar())
        self.view.loadFinished.connect(lambda ok: self.window.load_done(self, ok))
        page.newWindowRequested.connect(self.window.new_window)
        page.fullScreenRequested.connect(lambda request: request.reject())
        page.featurePermissionRequested.connect(
            lambda origin, feature: self.window.permission(page, origin, feature)
        )
        return self.view

    def navigate(self, text):
        try:
            url = navigation_url(text)
        except ValueError as exc:
            QMessageBox.warning(self, 'Endereço inválido', str(exc))
            return
        self.ensure_view().setUrl(QUrl(url))

    def url(self):
        return self.view.url().toString() if self.view else ''


class Worker(QThread):
    result = Signal(str)
    failed = Signal(str)

    def __init__(self, args, parent):
        super().__init__(parent)
        self.args = args

    def run(self):
        try:
            self.result.emit(ask(**self.args))
        except ValueError as exc:
            self.failed.emit(str(exc))
        except Exception:
            # Do not leak headers, tokens or provider response bodies.
            self.failed.emit('Não foi possível obter resposta. Confira conexão, endpoint e formato da API.')
        finally:
            self.args.clear()


class AIPanel(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.worker = None
        self.busy = False
        box = QVBoxLayout(self)
        intro = QLabel('Sua IA, sua chave. Chamadas são feitas somente ao enviar uma pergunta.')
        intro.setWordWrap(True)
        box.addWidget(intro)
        form = QFormLayout()
        self.provider = QComboBox()
        self.provider.addItems(PRESETS)
        self.endpoint, self.model, self.key = QLineEdit(), QLineEdit(), QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText('Chave de API — somente nesta sessão')
        self.remember = QCheckBox('Salvar chave no cofre do sistema')
        form.addRow('Provedor', self.provider)
        form.addRow('Endpoint', self.endpoint)
        form.addRow('Modelo', self.model)
        form.addRow('Chave', self.key)
        box.addLayout(form)
        box.addWidget(self.remember)
        row = QHBoxLayout()
        load = QPushButton('Carregar chave')
        forget = QPushButton('Apagar chave')
        row.addWidget(load)
        row.addWidget(forget)
        box.addLayout(row)
        load.clicked.connect(self.load_key)
        forget.clicked.connect(self.forget_key)
        self.provider.currentTextChanged.connect(self.preset)
        self.endpoint.textChanged.connect(self.endpoint_changed)
        self.preset(self.provider.currentText())
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText('As respostas aparecem aqui. O chat não é salvo em disco.')
        box.addWidget(self.output, 1)
        self.prompt = QPlainTextEdit()
        self.prompt.setPlaceholderText('O que você quer saber?')
        self.prompt.setMaximumHeight(100)
        box.addWidget(self.prompt)
        self.context = QCheckBox('Incluir texto da página (pedir confirmação)')
        box.addWidget(self.context)
        self.send = QPushButton('Enviar pergunta')
        self.send.clicked.connect(self.submit)
        box.addWidget(self.send)
        clear = QPushButton('Limpar conversa')
        clear.clicked.connect(self.output.clear)
        box.addWidget(clear)

    def endpoint_changed(self):
        self.key.clear()
        self.remember.setChecked(False)

    def preset(self, provider):
        endpoint, model = PRESETS[provider]
        self.endpoint.setText(endpoint)
        self.model.setText(model)
        self.key.clear()

    def vault_id(self):
        return validate_endpoint(self.endpoint.text())

    def load_key(self):
        try:
            import keyring
            self.key.setText(keyring.get_password('Pluma Browser', self.vault_id()) or '')
        except Exception:
            QMessageBox.warning(self, 'Cofre indisponível', 'Use uma chave somente em memória nesta sessão.')

    def forget_key(self):
        self.key.clear()
        self.remember.setChecked(False)
        try:
            import keyring
            account = self.vault_id()
            if keyring.get_password('Pluma Browser', account):
                keyring.delete_password('Pluma Browser', account)
        except Exception:
            QMessageBox.warning(self, 'Cofre indisponível', 'Não foi possível remover a chave do cofre do sistema.')

    def submit(self):
        if self.busy or not self.prompt.toPlainText().strip():
            return
        try:
            endpoint = validate_endpoint(self.endpoint.text())
        except ValueError as exc:
            QMessageBox.warning(self, 'API', str(exc))
            return
        args = dict(provider=self.provider.currentText(), endpoint=endpoint,
                    model=self.model.text().strip(), key=self.key.text(),
                    prompt=self.prompt.toPlainText(), context='')
        if self.remember.isChecked():
            try:
                import keyring
                keyring.set_password('Pluma Browser', endpoint, args['key'])
            except Exception:
                QMessageBox.warning(self, 'Cofre indisponível', 'A chave permanece somente em memória.')
        tab = self.window.current()
        if self.context.isChecked() and tab and tab.view:
            if QMessageBox.question(self, 'Enviar texto à IA?',
                'Até 24.000 caracteres do texto visível desta página serão enviados para:\n'
                + endpoint + '\n\nO conteúdo pode conter dados pessoais. Autoriza este envio?'
            ) != QMessageBox.StandardButton.Yes:
                return
            self.set_busy(True)
            tab.view.page().toPlainText(lambda text: self.start(args, text[:24000]))
        else:
            self.start(args, '')

    def set_busy(self, busy):
        self.busy = busy
        self.send.setEnabled(not busy)
        self.send.setText('Consultando…' if busy else 'Enviar pergunta')

    def start(self, args, context):
        args['context'] = context
        self.set_busy(True)
        self.append_plain('Você: ' + args['prompt'])
        self.worker = Worker(args, self)
        self.worker.result.connect(lambda text: self.append_plain('IA: ' + text))
        self.worker.failed.connect(lambda text: self.append_plain('Erro: ' + text))
        self.worker.finished.connect(self.worker_done)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def worker_done(self):
        self.worker = None
        self.set_busy(False)

    def append_plain(self, text):
        cursor = self.output.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText('\n' + str(text) + '\n\n')
        self.output.setTextCursor(cursor)


class Window(QMainWindow):
    def __init__(self, private=False):
        super().__init__()
        self.setWindowTitle('Pluma Browser' + (' — Privado' if private else ''))
        self.resize(1220, 800)
        self.private = private
        self.blocked = 0
        self.ai_panel = None
        self.child_windows = []
        self.settings = QSettings('Pluma', 'Browser')
        # Separate unnamed profile is off-the-record.
        self.profile = QWebEngineProfile(self) if private else QWebEngineProfile('Pluma', self)
        if not private:
            root = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
            self.profile.setPersistentStoragePath(str(root / 'profile'))
            self.profile.setCachePath(str(root / 'cache'))
        self.profile.setHttpCacheMaximumSize(64 * 1024 * 1024)
        web_settings = self.profile.settings()
        for attribute in (
            QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows,
            QWebEngineSettings.WebAttribute.PluginsEnabled,
            QWebEngineSettings.WebAttribute.FullScreenSupportEnabled,
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls,
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,
        ):
            web_settings.setAttribute(attribute, False)
        web_settings.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, True)
        self.blocker = Blocker(self.profile)
        allowed = self.settings.value('allowed', []) if not private else []
        self.blocker.allowed = frozenset(allowed or [])
        self.profile.setUrlRequestInterceptor(self.blocker)
        self.blocker.hit.connect(self.count_block)
        self.profile.downloadRequested.connect(self.download)
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.activate)
        self.setCentralWidget(self.tabs)
        toolbar = QToolBar('Navegação')
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        self.back_action = toolbar.addAction('←', lambda: self.with_view('back'))
        self.forward_action = toolbar.addAction('→', lambda: self.with_view('forward'))
        toolbar.addAction('↻', lambda: self.with_view('reload'))
        toolbar.addAction('+', lambda: self.add_tab())
        self.address = QLineEdit()
        self.address.setPlaceholderText('Pesquisar ou digitar endereço')
        self.address.returnPressed.connect(lambda: self.current().navigate(self.address.text()))
        toolbar.addWidget(self.address)
        self.shield = toolbar.addAction('Proteção', self.toggle_protection)
        self.keep = toolbar.addAction('Manter ativa', self.toggle_keep)
        self.keep.setCheckable(True)
        toolbar.addAction('IA', self.toggle_ai)
        toolbar.addAction('Privado', self.new_private)
        toolbar.addAction('Favoritos', self.bookmarks)
        self.dock = QDockWidget('Assistente · IA', self)
        self.dock.setMinimumWidth(350)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock)
        self.dock.hide()
        for shortcut, callback in [
            ('Ctrl+T', lambda: self.add_tab()), ('Ctrl+W', lambda: self.close_tab(self.tabs.currentIndex())),
            ('Ctrl+L', self.focus_address), ('Ctrl+R', lambda: self.with_view('reload')),
            ('Alt+Left', lambda: self.with_view('back')), ('Alt+Right', lambda: self.with_view('forward')),
            ('Ctrl+Shift+N', self.new_private), ('Ctrl+J', self.toggle_ai),
        ]:
            action = QAction(self)
            action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(callback)
            self.addAction(action)
        self.timer = QTimer(self)
        self.timer.setInterval(15000)
        self.timer.timeout.connect(self.suspend_tabs)
        self.timer.start()
        self.add_tab()
        self.statusBar().showMessage('Pronto • bloqueio nativo ligado')

    def current(self):
        return self.tabs.currentWidget()

    def add_tab(self, url=None):
        tab = BrowserTab(self)
        self.tabs.addTab(tab, 'Nova aba')
        self.tabs.setCurrentWidget(tab)
        if url:
            tab.navigate(url)
        return tab

    def close_tab(self, index):
        tab = self.tabs.widget(index)
        if tab is None:
            return
        self.tabs.removeTab(index)
        tab.deleteLater()
        if not self.tabs.count():
            self.add_tab()

    def activate(self, index):
        current = self.current()
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if tab == current:
                tab.last_active = time.monotonic()
                if tab.view:
                    tab.view.page().setLifecycleState(QWebEnginePage.LifecycleState.Active)
            elif getattr(tab, 'was_current', False):
                tab.last_active = time.monotonic()
            tab.was_current = tab == current
        self.sync_toolbar()

    def suspend_tabs(self):
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if tab == self.current() or not tab.view:
                continue
            page = tab.view.page()
            if page.lifecycleState() == page.LifecycleState.Discarded and not tab.protected:
                continue
            recommended = page.recommendedState().name.lower()
            state = lifecycle_action(time.monotonic() - tab.last_active, recommended,
                                     page.recentlyAudible(), tab.protected)
            target = {'active': page.LifecycleState.Active, 'frozen': page.LifecycleState.Frozen,
                      'discarded': page.LifecycleState.Discarded}[state]
            if page.lifecycleState() != target:
                page.setLifecycleState(target)

    def tab_title(self, tab, title):
        index = self.tabs.indexOf(tab)
        if index >= 0:
            self.tabs.setTabText(index, title[:28] or 'Nova aba')
            self.tabs.setTabToolTip(index, title)

    def sync_toolbar(self):
        tab = self.current()
        if not tab or not hasattr(self, 'address'):
            return
        if not self.address.hasFocus():
            self.address.setText(tab.url())
        self.keep.setChecked(tab.protected)
        host = QUrl(tab.url()).host()
        self.shield.setText('Proteção: pausa' if host in self.blocker.allowed else 'Proteção: ligada')
        self.back_action.setEnabled(bool(tab.view and tab.view.history().canGoBack()))
        self.forward_action.setEnabled(bool(tab.view and tab.view.history().canGoForward()))

    def load_done(self, tab, ok):
        if tab == self.current():
            self.statusBar().showMessage(
                f'{self.blocked} requisições bloqueadas' if ok else 'Falha ao carregar — confira endereço e conexão.')
        self.sync_toolbar()

    def count_block(self):
        self.blocked += 1
        self.statusBar().showMessage(f'{self.blocked} requisições de anúncios/rastreadores bloqueadas')

    def with_view(self, method):
        tab = self.current()
        if tab and tab.view:
            getattr(tab.view, method)()

    def focus_address(self):
        self.address.setFocus()
        self.address.selectAll()

    def toggle_protection(self):
        host = QUrl(self.current().url()).host()
        if not host:
            return
        domains = set(self.blocker.allowed)
        if host in domains:
            domains.remove(host)
        else:
            domains.add(host)
        self.blocker.allowed = frozenset(domains)
        if not self.private:
            self.settings.setValue('allowed', sorted(domains))
        self.sync_toolbar()
        self.with_view('reload')

    def toggle_keep(self):
        tab = self.current()
        tab.protected = self.keep.isChecked()
        if tab.view and tab.protected:
            tab.view.page().setLifecycleState(QWebEnginePage.LifecycleState.Active)

    def toggle_ai(self):
        if self.ai_panel is None:
            self.ai_panel = AIPanel(self)
            self.dock.setWidget(self.ai_panel)
        self.dock.setVisible(not self.dock.isVisible())

    def new_window(self, request):
        if not request.isUserInitiated():
            return
        tab = self.add_tab()
        request.openIn(tab.ensure_view().page())

    def new_private(self):
        window = Window(private=True)
        self.child_windows.append(window)
        window.show()

    def permission(self, page, origin, feature):
        allow = QMessageBox.question(self, 'Permissão do site',
            f'{origin.toString()} solicita {feature.name}. Permitir?') == QMessageBox.StandardButton.Yes
        page.setFeaturePermission(origin, feature, QWebEnginePage.PermissionPolicy.PermissionGrantedByUser
                                  if allow else QWebEnginePage.PermissionPolicy.PermissionDeniedByUser)

    def download(self, item):
        path, _ = QFileDialog.getSaveFileName(self, 'Salvar download', item.downloadFileName())
        if not path:
            item.cancel()
            return
        destination = Path(path)
        item.setDownloadDirectory(str(destination.parent))
        item.setDownloadFileName(destination.name)
        item.stateChanged.connect(lambda _: self.statusBar().showMessage('Download: ' + item.state().name))
        item.accept()

    def bookmarks(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Favoritos')
        box = QVBoxLayout(dialog)
        entries = self.settings.value('bookmarks', []) or []
        for entry in entries:
            button = QPushButton(entry)
            button.clicked.connect(lambda checked=False, url=entry: (self.add_tab(url), dialog.accept()))
            box.addWidget(button)
        add = QPushButton('Adicionar página atual')
        add.setEnabled(bool(self.current().url()) and not self.private)
        def save():
            url = self.current().url()
            self.settings.setValue('bookmarks', list(dict.fromkeys(entries + [url]))[-100:])
            dialog.accept()
        add.clicked.connect(save)
        box.addWidget(add)
        clear = QPushButton('Limpar favoritos')
        clear.setEnabled(not self.private)
        clear.clicked.connect(lambda: (self.settings.setValue('bookmarks', []), dialog.accept()))
        box.addWidget(clear)
        dialog.exec()

    def closeEvent(self, event):
        if self.ai_panel and self.ai_panel.busy:
            QMessageBox.information(self, 'Consulta em andamento', 'Aguarde a consulta à IA terminar antes de fechar.')
            event.ignore()
            return
        import shiboken6
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if tab.view:
                shiboken6.delete(tab.view)
                tab.view = None
        self.timer.stop()
        event.accept()


def main():
    # Never disable Chromium sandbox / site isolation in production.
    app = QApplication(sys.argv)
    app.setApplicationName('Pluma Browser')
    app.setOrganizationName('Pluma')
    app.setStyleSheet(STYLE)
    window = Window(private='--private' in sys.argv)
    window.show()
    sys.exit(app.exec())
