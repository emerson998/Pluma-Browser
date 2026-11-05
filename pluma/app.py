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
from .core import navigation_url, host_matches, lifecycle_action
from .features import Features, filter_engine

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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.allowed = frozenset()
        self.blocked_count = 0

    def interceptRequest(self, info):
        kind = info.resourceType().name.removeprefix('ResourceType').lower()
        kind = {'mainframe': 'document', 'subframe': 'subdocument',
                'xhr': 'xmlhttprequest', 'favicon': 'image'}.get(kind, kind)
        if filter_engine().blocked(info.requestUrl().toString(), info.firstPartyUrl().toString(),
                                   kind, self.allowed):
            info.block(True)
            self.blocked_count += 1


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
        self.pinned = False
        self.pending_url = ''
        self.view = None
        self.floating_window = None
        self.video_request = 0
        self.video_pending = False
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
        self.floating_placeholder = QWidget(self)
        floating_box = QVBoxLayout(self.floating_placeholder)
        floating_box.addStretch()
        floating_text = QLabel('Este vídeo está em uma janela flutuante.')
        floating_text.setWordWrap(True)
        floating_box.addWidget(floating_text)
        restore_video = QPushButton('Trazer vídeo de volta para esta aba')
        restore_video.clicked.connect(lambda: self.floating_window.return_to_tab() if self.floating_window else None)
        floating_box.addWidget(restore_video)
        floating_box.addStretch()
        self.layout.addWidget(self.floating_placeholder)
        self.floating_placeholder.hide()
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
        page.pdfPrintingFinished.connect(lambda path, ok: self.window.statusBar().showMessage('PDF salvo: ' + path if ok else 'Falha ao gerar PDF'))
        page.printRequested.connect(self.window.print_page)
        self.view.loadFinished.connect(lambda ok: self.window.load_done(self, ok))
        page.newWindowRequested.connect(self.window.new_window)
        page.fullScreenRequested.connect(lambda request: self.floating_window.fullscreen(request) if self.floating_window else self.window.fullscreen(request))
        page.permissionRequested.connect(self.window.permission_request)
        page.renderProcessTerminated.connect(lambda *_: self.window.statusBar().showMessage('A página parou. Recarregue para continuar.'))
        return self.view

    def navigate(self, text):
        try:
            url = navigation_url(text)
        except ValueError as exc:
            QMessageBox.warning(self, 'Endereço inválido', str(exc))
            return
        search = self.window.settings.value('search', 'DuckDuckGo')
        if url.startswith('https://duckduckgo.com/?q='):
            url = url.replace('https://duckduckgo.com/?q=', {
                'Google': 'https://www.google.com/search?q=', 'Bing': 'https://www.bing.com/search?q='
            }.get(search, 'https://duckduckgo.com/?q='), 1)
        if self.floating_window:
            self.floating_window.close()
        self.pending_url = ''
        self.ensure_view().setUrl(QUrl(url))
        self.window.queue_session()

    def url(self):
        return self.view.url().toString() if self.view else self.pending_url


class Window(Features, QMainWindow):
    def __init__(self, private=False):
        super().__init__()
        self.setWindowTitle('Pluma Browser' + (' — Privado' if private else ''))
        self.resize(1220, 800)
        self.private = private
        self.blocked = 0
        self.ai_panel = None
        self.child_windows = []
        self.settings = QSettings('Pluma', 'Browser')
        self.init_state()
        # Separate unnamed profile is off-the-record.
        self.profile = QWebEngineProfile(self) if private else QWebEngineProfile('Pluma', self)
        if not private:
            root = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
            self.profile.setPersistentStoragePath(str(root / 'profile'))
            self.profile.setCachePath(str(root / 'cache'))
        self.profile.setPersistentPermissionsPolicy(
            QWebEngineProfile.PersistentPermissionsPolicy.StoreInMemory if private
            else QWebEngineProfile.PersistentPermissionsPolicy.StoreOnDisk)
        self.profile.setHttpCacheMaximumSize(64 * 1024 * 1024)
        web_settings = self.profile.settings()
        web_settings.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
        for attribute in (
            QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows,
            QWebEngineSettings.WebAttribute.PluginsEnabled,
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls,
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,
        ):
            web_settings.setAttribute(attribute, False)
        web_settings.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, True)
        self.blocker = Blocker(self.profile)
        allowed = self.settings.value('allowed', []) if not private else []
        self.blocker.allowed = frozenset(allowed or [])
        self.youtube_enabled = self.settings.value('youtube_protection', True, type=bool)
        self.refresh_youtube_protection()
        self.profile.setUrlRequestInterceptor(self.blocker)
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
        self.address.returnPressed.connect(self.navigate_address)
        self.address.setAccessibleName('Endereço ou pesquisa')
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
            ('Escape', lambda: self.showNormal()),
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
        self.init_controls(toolbar)
        self.statusBar().showMessage('Pronto • bloqueio nativo ligado')

    def current(self):
        return self.tabs.currentWidget()

    def add_tab(self, url=None, lazy=False):
        tab = BrowserTab(self)
        self.tabs.addTab(tab, 'Nova aba')
        self.tabs.setCurrentWidget(tab)
        if url and lazy:
            tab.pending_url = url
            self.tabs.setTabText(self.tabs.indexOf(tab), QUrl(url).host())
        elif url:
            tab.navigate(url)
        self.queue_session()
        return tab

    def close_tab(self, index):
        tab = self.tabs.widget(index)
        if tab is None:
            return
        if tab.pinned and QMessageBox.question(self, 'Aba fixada', 'Fechar esta aba fixada?') != QMessageBox.StandardButton.Yes:
            return
        tab.video_request += 1
        if tab.floating_window:
            tab.floating_window.close()
        if tab.url():
            self.closed_tabs.append(self.entry(tab))
            self.closed_tabs = self.closed_tabs[-20:]
        self.tabs.removeTab(index)
        tab.deleteLater()
        self.queue_session()
        if not self.tabs.count():
            self.add_tab()

    def activate(self, index):
        current = self.current()
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if tab == current:
                tab.last_active = time.monotonic()
                if tab.pending_url:
                    tab.navigate(tab.pending_url)
                elif tab.view:
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
            if tab.floating_window:
                page.setLifecycleState(QWebEnginePage.LifecycleState.Active)
                continue
            if page.lifecycleState() == page.LifecycleState.Discarded and not tab.protected:
                continue
            recommended = page.recommendedState().name.lower()
            economical = self.settings.value('mode', 'Equilibrado') == 'Econômico'
            freeze = int(self.settings.value('freeze', 60))
            discard = max(freeze + 15, int(self.settings.value('discard', 300)))
            if economical:
                freeze, discard = min(freeze, 30), min(discard, 120)
            state = lifecycle_action(time.monotonic() - tab.last_active, recommended,
                                     page.recentlyAudible(), tab.protected or tab.pinned,
                                     freeze, discard)
            target = {'active': page.LifecycleState.Active, 'frozen': page.LifecycleState.Frozen,
                      'discarded': page.LifecycleState.Discarded}[state]
            if page.lifecycleState() != target:
                page.setLifecycleState(target)

    def tab_title(self, tab, title):
        index = self.tabs.indexOf(tab)
        if index >= 0:
            self.tabs.setTabText(index, ('• ' if tab.pinned else '') + (title[:28] or 'Nova aba'))
            self.tabs.setTabToolTip(index, title)
            if tab.floating_window:
                tab.floating_window.setWindowTitle(title[:100] + ' — Pluma vídeo')

    def sync_toolbar(self):
        tab = self.current()
        if not tab or not hasattr(self, 'address'):
            return
        if not self.address.isModified():
            self.address.setText(tab.url())
            self.address.setModified(False)
        self.keep.setChecked(tab.protected)
        host = QUrl(tab.url()).host()
        self.shield.setText('Proteção: pausa' if host_matches(host, self.blocker.allowed) else 'Proteção: ligada')
        self.back_action.setEnabled(bool(tab.view and tab.view.history().canGoBack()))
        self.forward_action.setEnabled(bool(tab.view and tab.view.history().canGoForward()))

    def load_done(self, tab, ok):
        if ok:
            if tab.floating_window:
                tab.floating_window.close()
            self.record_history(tab)
            self.apply_cosmetics(tab)
            self.queue_session()
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
        if host_matches(host, domains):
            domains = {domain for domain in domains if not host_matches(host, {domain})}
        else:
            domains.add(host)
        self.blocker.allowed = frozenset(domains)
        if not self.private:
            self.settings.setValue('allowed', sorted(domains))
        self.refresh_youtube_protection()
        self.sync_toolbar()
        self.with_view('reload')

    def toggle_keep(self):
        tab = self.current()
        tab.protected = self.keep.isChecked()
        if tab.view and tab.protected:
            tab.view.page().setLifecycleState(QWebEnginePage.LifecycleState.Active)

    def toggle_ai(self):
        if self.ai_panel is None:
            from .ai_panel import AIPanel
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
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        window.destroyed.connect(lambda: self.child_windows.remove(window) if window in self.child_windows else None)
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
        self.downloads = [download for download in self.downloads if not download.isFinished()][-99:]
        self.downloads.append(item)
        item.accept()

    def navigate_address(self):
        text = self.address.text()
        self.address.setModified(False)
        self.address.clearFocus()
        self.current().navigate(text)

    def fullscreen(self, request):
        request.accept()
        if request.toggleOn():
            self.showFullScreen()
        else:
            self.showNormal()

    def permission_request(self, permission):
        allow = QMessageBox.question(self, 'Permissão do site',
            permission.origin().toString() + ' solicita ' + permission.permissionType().name +
            '. Permitir?') == QMessageBox.StandardButton.Yes
        permission.grant() if allow else permission.deny()

    def closeEvent(self, event):
        self.save_session()
        busy = bool(self.ai_panel and self.ai_panel.busy) or bool(self.jobs)
        if busy:
            self.close_pending = True
            if self.ai_panel:
                self.ai_panel.cancel()
            for job in self.jobs:
                job.requestInterruption()
            self.statusBar().showMessage('Encerrando operações…')
            event.ignore()
            return
        # Tear down private profiles immediately, rather than retaining closed windows.
        import shiboken6
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            tab.video_request += 1
            if tab.floating_window:
                tab.floating_window.close()
            if tab.view:
                if not self.private:
                    tab.pending_url = tab.url()
                shiboken6.delete(tab.view)
                tab.view = None
        self.timer.stop()
        self.stats_timer.stop()
        self.session_timer.stop()
        if self.ai_panel:
            self.ai_panel.flush_timer.stop()
            self.ai_panel.key.clear()
            self.ai_panel.history.clear()
        if self.private:
            shiboken6.delete(self.profile)
        event.accept()


def main():
    # Never disable Chromium sandbox / site isolation in production.
    app = QApplication(sys.argv)
    app.setApplicationName('Pluma Browser')
    app.setOrganizationName('Pluma')
    app.setStyleSheet(STYLE)
    if '--self-test' in sys.argv:
        from .selftest import run
        sys.exit(run(app, sys.argv[sys.argv.index('--self-test') + 1]))
    from .instance import connect_instance, bind
    urls = [value for value in sys.argv[1:] if value.startswith(('https://', 'http://'))]
    server, forwarded = connect_instance(urls, '--private' in sys.argv)
    if forwarded:
        return
    window = Window(private='--private' in sys.argv)
    bind(server, window)
    for value in sys.argv[1:]:
        if value.startswith(('https://', 'http://')):
            window.add_tab(value)
    window.show()
    sys.exit(app.exec())
