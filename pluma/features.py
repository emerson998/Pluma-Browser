"""Browser features: native panels, debounced stores and opt-in network jobs."""
import json
import time
import threading
from pathlib import Path
from urllib.parse import urlsplit
from PySide6.QtCore import Qt, QTimer, QUrl, QStandardPaths
from PySide6.QtGui import QAction, QKeySequence, QDesktopServices
from PySide6.QtWidgets import (QMenu, QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QMessageBox, QFileDialog, QInputDialog, QPlainTextEdit, QDialogButtonBox)
from PySide6.QtWebEngineCore import QWebEnginePage
from .core import host_matches
from .storage import read_json, atomic_json, session_entries, bookmark_records
from .jobs import Job
from .dialogs import SettingsDialog, BookmarksDialog, DownloadsDialog

_ENGINE = None
_ENGINE_LOCK = threading.Lock()


def filter_engine():
    global _ENGINE
    if _ENGINE is None:
        with _ENGINE_LOCK:
            if _ENGINE is None:
                from .blocking import FilterEngine
                root = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
                _ENGINE = FilterEngine(root / 'filters')
    return _ENGINE


class Features:
    def init_state(self):
        self.root = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
        self.close_pending = False
        self.history_dirty = False
        self.jobs, self.downloads, self.closed_tabs = [], [], []
        self.bookmark_data = bookmark_records(read_json(self.root / 'bookmarks.json',
                                            self.settings.value('bookmarks', []) or []))
        self.history_data = [] if self.private else read_json(self.root / 'history.json', [])
        if not isinstance(self.history_data, list):
            self.history_data = []
        self.session_timer = QTimer(self)
        self.session_timer.setSingleShot(True)
        self.session_timer.setInterval(800)
        self.session_timer.timeout.connect(self.save_session)
        self.filter_job = None
        self.find_query = ''
        self.stats_timer = QTimer(self)
        self.stats_timer.setInterval(1000)
        self.stats_timer.timeout.connect(self.refresh_stats)
        self.stats_timer.start()

    def init_controls(self, toolbar):
        menu = QMenu(self)
        commands = [
            ('Preferências', self.preferences, None),
            ('Encontrar na página', self.find, 'Ctrl+F'),
            ('Próxima ocorrência', lambda: self.find(next_only=True), 'Ctrl+G'),
            ('Reabrir aba fechada', self.reopen, 'Ctrl+Shift+T'),
            ('Fixar/desafixar aba', self.pin, None),
            ('Silenciar aba', self.mute, 'Ctrl+M'),
            ('Aumentar zoom', lambda: self.zoom(.1), 'Ctrl++'),
            ('Diminuir zoom', lambda: self.zoom(-.1), 'Ctrl+-'),
            ('Zoom 100%', lambda: self.zoom(reset=True), 'Ctrl+0'),
            ('Salvar PDF', self.pdf, None),
            ('Imprimir', self.print_page, 'Ctrl+P'),
            ('Downloads', self.show_downloads, 'Ctrl+Shift+J'),
            ('Histórico', self.show_history, 'Ctrl+H'),
            ('Privacidade deste site', self.privacy, None),
            ('Atualizar listas de bloqueio', self.update_filters, None),
            ('Gerenciar exceções do bloqueador', self.exceptions, None),
            ('Desempenho', self.performance, None),
            ('Verificar atualizações', self.check_updates, None),
            ('Sobre', self.about, None),
        ]
        for title, callback, shortcut in commands:
            action = QAction(title, self)
            action.triggered.connect(callback)
            if shortcut:
                action.setShortcut(QKeySequence(shortcut))
                self.addAction(action)
            menu.addAction(action)
        from PySide6.QtWidgets import QToolButton
        button = QToolButton()
        button.setText('☰')
        button.setAccessibleName('Menu do navegador')
        button.setMenu(menu)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        toolbar.addWidget(button)
        self.tabs.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.tabBar().customContextMenuRequested.connect(self.tab_menu)
        self.tabs.tabBar().tabMoved.connect(lambda *_: self.queue_session())
        if not self.private and self.settings.value('restore', True, type=bool):
            saved = session_entries(read_json(self.root / 'session.json', []))
            if saved:
                self.tabs.blockSignals(True)
                initial = self.tabs.widget(0)
                self.tabs.removeTab(0)
                initial.deleteLater()
                for entry in saved:
                    tab = self.add_tab(entry['url'], lazy=True)
                    tab.protected, tab.pinned = entry['protected'], entry['pinned']
                    self.tab_title(tab, entry['title'])
                self.tabs.setCurrentIndex(0)
                self.tabs.blockSignals(False)
                self.activate(0)
        self.apply_theme()
        if not self.private and self.settings.value('filter_auto', False, type=bool):
            metadata = read_json(self.root / 'filters/metadata.json', {})
            if time.time() - metadata.get('updated', 0) > 7 * 86400:
                QTimer.singleShot(3000, self.update_filters)

    def queue_session(self):
        if not self.private and not self.close_pending:
            self.session_timer.start()

    def save_session(self):
        if self.private:
            return
        values = []
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            values.append({'url': tab.url(), 'title': self.tabs.tabText(i),
                           'protected': tab.protected, 'pinned': tab.pinned})
        try:
            atomic_json(self.root / 'session.json', session_entries(values))
            if self.history_dirty:
                atomic_json(self.root / 'history.json', self.history_data)
                self.history_dirty = False
        except OSError:
            self.statusBar().showMessage('Não foi possível salvar a sessão.')

    def entry(self, tab):
        return {'url': tab.url(), 'title': self.tabs.tabText(self.tabs.indexOf(tab)),
                'pinned': tab.pinned, 'protected': tab.protected}

    def reopen(self):
        if self.closed_tabs:
            entry = self.closed_tabs.pop()
            tab = self.add_tab(entry['url'])
            tab.pinned, tab.protected = entry['pinned'], entry['protected']

    def pin(self):
        tab = self.current()
        tab.pinned = not tab.pinned
        self.tab_title(tab, tab.view.title() if tab.view else self.tabs.tabText(self.tabs.currentIndex()).lstrip('• '))
        if tab.pinned:
            self.tabs.tabBar().moveTab(self.tabs.currentIndex(), 0)
        self.queue_session()

    def mute(self):
        tab = self.current()
        if tab.view:
            tab.view.page().setAudioMuted(not tab.view.page().isAudioMuted())

    def tab_menu(self, position):
        index = self.tabs.tabBar().tabAt(position)
        if index < 0:
            return
        self.tabs.setCurrentIndex(index)
        menu = QMenu(self)
        menu.addAction('Fixar/desafixar', self.pin)
        menu.addAction('Silenciar/ativar áudio', self.mute)
        menu.addAction('Duplicar', lambda: self.add_tab(self.current().url()))
        menu.addAction('Fechar', lambda: self.close_tab(self.tabs.currentIndex()))
        menu.exec(self.tabs.tabBar().mapToGlobal(position))

    def zoom(self, delta=0, reset=False):
        tab = self.current()
        if tab.view:
            tab.view.setZoomFactor(1 if reset else min(3, max(.25, tab.view.zoomFactor() + delta)))

    def find(self, next_only=False):
        tab = self.current()
        if not tab.view:
            return
        if not next_only:
            query, ok = QInputDialog.getText(self, 'Buscar na página', 'Texto:', text=self.find_query)
            if not ok:
                tab.view.page().findText('')
                return
            self.find_query = query
        tab.view.page().findText(self.find_query, QWebEnginePage.FindFlag(0),
            lambda result: self.statusBar().showMessage(f'{result.activeMatch()} de {result.numberOfMatches()} ocorrências'))

    def pdf(self):
        tab = self.current()
        if not tab.view:
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Salvar PDF', 'pagina.pdf', 'PDF (*.pdf)')
        if path:
            tab.view.page().printToPdf(path)
            self.statusBar().showMessage('Gerando PDF…')

    def print_page(self):
        tab = self.current()
        if not tab.view:
            return
        from PySide6.QtPrintSupport import QPrinter, QPrintDialog
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.printer = printer  # Keep alive until Chromium completes.
            tab.view.print(printer)

    def preferences(self):
        if self.private:
            QMessageBox.information(self, 'Preferências', 'Altere preferências em uma janela normal.')
            return
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            for key, value in dialog.values().items():
                self.settings.setValue(key, value)
            self.apply_theme()
            if self.settings.value('filter_auto', False, type=bool):
                self.update_filters()

    def apply_theme(self):
        from .app import STYLE
        light = STYLE.replace('#111416', '#f5f7f6').replace('#e7ecea', '#182b23').replace(
            '#1d2325', '#ffffff').replace('#242d2d', '#e1eae5').replace('#99aaa4', '#40574b').replace(
            '#26332f', '#d4e7dc').replace('#a8e8cb', '#164b34').replace('#b9efd7', '#246548').replace(
            '#a5b7af', '#496052').replace('#1b2321', '#e1eae5')
        self.setStyleSheet(light if self.settings.value('theme', 'Escuro') == 'Claro' else STYLE)

    def save_bookmarks(self, records):
        if not self.private:
            self.bookmark_data = bookmark_records(records)
            atomic_json(self.root / 'bookmarks.json', self.bookmark_data)

    def bookmarks(self):
        BookmarksDialog(self).exec()

    def show_downloads(self):
        DownloadsDialog(self.downloads, self).exec()

    def record_history(self, tab):
        if self.private or not self.settings.value('history_enabled', False, type=bool) or not tab.url().startswith(('http:', 'https:')):
            return
        self.history_data = [x for x in self.history_data if isinstance(x, dict) and x.get('url') != tab.url()]
        self.history_data.insert(0, {'url': tab.url(), 'title': tab.view.title(), 'time': time.time()})
        self.history_data = self.history_data[:1000]
        self.history_dirty = True
        self.queue_session()

    def show_history(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Histórico local')
        dialog.resize(650, 400)
        box = QVBoxLayout(dialog)
        if self.private:
            box.addWidget(QLabel('Histórico indisponível na janela privada.'))
        else:
            from PySide6.QtWidgets import QListWidget
            listing = QListWidget()
            for entry in self.history_data:
                listing.addItem(entry.get('title', '') + ' · ' + entry.get('url', ''))
            listing.itemDoubleClicked.connect(lambda item: self.add_tab(self.history_data[listing.row(item)]['url']))
            box.addWidget(listing)
            clear = QPushButton('Apagar histórico')
            clear.clicked.connect(lambda: (self.history_data.clear(),
                atomic_json(self.root / 'history.json', []), listing.clear()))
            box.addWidget(clear)
        dialog.exec()

    def privacy(self):
        tab = self.current()
        if not tab.view:
            return
        origin = QUrl(tab.url())
        host = origin.host()
        origin.setPath('/')
        origin.setQuery('')
        origin.setFragment('')
        dialog = QDialog(self)
        dialog.setWindowTitle('Privacidade · ' + host)
        box = QVBoxLayout(dialog)
        label = QLabel(origin.toString() + '\nHTTPS ativo' if origin.scheme() == 'https' else origin.toString() + '\nConexão HTTP')
        box.addWidget(label)
        permissions = self.profile.listPermissionsForOrigin(origin)
        for permission in permissions:
            row = QPushButton(permission.permissionType().name + ': ' + permission.state().name + ' — Revogar')
            row.clicked.connect(lambda _, p=permission, b=row: (p.reset(), b.setText('Permissão revogada')))
            box.addWidget(row)
        clear = QPushButton('Apagar cookies e armazenamento desta página')
        def clear_site():
            store = self.profile.cookieStore()
            def remove(cookie):
                domain = cookie.domain().lstrip('.')
                if host == domain or host.endswith('.' + domain):
                    store.deleteCookie(cookie)
            store.cookieAdded.connect(remove)
            store.loadAllCookies()
            def disconnect():
                import shiboken6
                if shiboken6.isValid(store):
                    store.cookieAdded.disconnect(remove)
            QTimer.singleShot(2500, disconnect)
            tab.view.page().runJavaScript("""(async()=>{
                localStorage.clear(); sessionStorage.clear();
                if(window.caches) for(const k of await caches.keys()) await caches.delete(k);
                if(indexedDB.databases) for(const d of await indexedDB.databases()) indexedDB.deleteDatabase(d.name);
                return true;
            })()""")
            clear.setText('Solicitada limpeza. Recarregue a página.')
        clear.clicked.connect(clear_site)
        box.addWidget(clear)
        all_cookies = QPushButton('Apagar cookies e cache de todos os sites deste perfil')
        all_cookies.clicked.connect(lambda: (self.profile.cookieStore().deleteAllCookies(),
                                             self.profile.clearHttpCache(),
                                             all_cookies.setText('Limpeza solicitada')))
        box.addWidget(all_cookies)
        note = QLabel('Páginas abertas podem recriar dados. Feche abas do site antes de encerrar a sessão.')
        note.setWordWrap(True)
        box.addWidget(note)
        dialog.exec()

    def exceptions(self):
        text, ok = QInputDialog.getMultiLineText(self, 'Exceções de bloqueio',
            'Um domínio por linha. Inclui seus subdomínios:', '\n'.join(sorted(self.blocker.allowed)))
        if ok:
            hosts = set()
            for value in text.splitlines():
                value = value.strip().lower().rstrip('.')
                if value and '/' not in value and ' ' not in value and ':' not in value:
                    hosts.add(value)
            self.blocker.allowed = frozenset(hosts)
            if not self.private:
                self.settings.setValue('allowed', sorted(hosts))
            self.sync_toolbar()

    def run_job(self, task, callback):
        job = Job(task, self)
        self.jobs.append(job)
        job.result.connect(callback)
        job.error.connect(lambda text: self.statusBar().showMessage(text))
        def done():
            self.jobs.remove(job)
            job.deleteLater()
            if self.close_pending and not self.jobs:
                self.close()
        job.finished.connect(done)
        job.start()
        return job

    def update_filters(self):
        if self.filter_job and self.filter_job.isRunning():
            return
        self.statusBar().showMessage('Atualizando filtros em segundo plano…')
        self.filter_job = self.run_job(
            lambda job: filter_engine().update(cancelled=job.isInterruptionRequested),
            lambda message: self.statusBar().showMessage(message))
        self.filter_job.finished.connect(lambda: setattr(self, 'filter_job', None))

    def check_updates(self):
        from .updates import check_release
        def result(release):
            if release['new']:
                if QMessageBox.question(self, 'Atualização', release['message'] + '\nAbrir release oficial para baixar?') == QMessageBox.StandardButton.Yes:
                    QDesktopServices.openUrl(QUrl(release['url']))
            else:
                QMessageBox.information(self, 'Atualizações', release['message'])
        self.run_job(lambda job: check_release(), result)

    def performance(self):
        import psutil
        dialog = QDialog(self)
        dialog.setWindowTitle('Desempenho')
        layout = QVBoxLayout(dialog)
        label = QLabel()
        layout.addWidget(label)
        processes = {}
        def refresh():
            from PySide6.QtWebEngineCore import qWebEngineChromiumVersion
            states = {'Active': 0, 'Frozen': 0, 'Discarded': 0, 'Sem renderer': 0}
            for i in range(self.tabs.count()):
                tab = self.tabs.widget(i)
                state = tab.view.page().lifecycleState().name if tab.view else 'Sem renderer'
                states[state] += 1
            try:
                root = psutil.Process()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                label.setText('Métricas de processos indisponíveis neste ambiente.\n' +
                              '\n'.join(f'{key}: {value}' for key, value in states.items()))
                return
            rss = uss = cpu = 0
            current = [root] + root.children(recursive=True)
            for process in current:
                try:
                    if process.pid not in processes:
                        processes[process.pid] = process
                        process.cpu_percent()
                    rss += process.memory_info().rss
                    uss += getattr(process.memory_full_info(), 'uss', 0)
                    cpu += processes[process.pid].cpu_percent()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            processes_keys = {p.pid for p in current}
            for pid in list(processes):
                if pid not in processes_keys:
                    del processes[pid]
            label.setText('\n'.join(f'{key}: {value}' for key, value in states.items()) +
                f'\n\nRAM RSS: {rss / 1048576:.1f} MiB\nMemória exclusiva USS: {uss / 1048576:.1f} MiB'
                f'\nCPU: {cpu:.1f}% · Processos: {len(current)}' +
                '\nModo: ' + self.settings.value('mode', 'Equilibrado') +
                '\nCache: até 64 MiB (não é limite de RAM)\nChromium: ' + qWebEngineChromiumVersion() +
                '\n\nValores abrangem o processo e seus filhos, incluindo outras janelas.'
                '\nRSS pode contar páginas compartilhadas mais de uma vez.')
        timer = QTimer(dialog)
        timer.setInterval(1000)
        timer.timeout.connect(refresh)
        refresh()
        timer.start()
        dialog.exec()
        timer.stop()

    def about(self):
        from . import __version__
        from PySide6.QtWebEngineCore import qWebEngineChromiumVersion, qWebEngineChromiumSecurityPatchVersion
        QMessageBox.information(self, 'Pluma',
            'Pluma ' + __version__ + '\nChromium ' + qWebEngineChromiumVersion() +
            '\nCorreções Chromium até ' + qWebEngineChromiumSecurityPatchVersion() +
            '\nMIT · Qt e componentes mantêm suas licenças.\nAtualizações: menu → Verificar atualizações.')

    def refresh_stats(self):
        if self.blocked != self.blocker.blocked_count:
            self.blocked = self.blocker.blocked_count
            self.statusBar().showMessage(f'{self.blocked} requisições bloqueadas nesta janela')

    def apply_cosmetics(self, tab):
        if not tab.view:
            return
        page, url = tab.view.page(), tab.url()
        def received(data):
            import shiboken6
            if not shiboken6.isValid(tab) or not tab.view or tab.url() != url or not isinstance(data, dict):
                return
            selectors = filter_engine().cosmetic(url, data.get('classes', []), data.get('ids', []), self.blocker.allowed)
            if selectors:
                css = ','.join(selectors) + '{display:none!important}'
                page.runJavaScript("(()=>{let s=document.getElementById('pluma-filter-style');"
                    "if(!s){s=document.createElement('style');s.id='pluma-filter-style';document.documentElement.append(s);}"
                    "s.textContent=" + json.dumps(css) + ";})()")
        # One bounded scan after load; no perpetual MutationObserver or polling.
        page.runJavaScript("""(()=>{let cs=new Set(),ids=new Set();
            for(const n of [...document.querySelectorAll('[class],[id]')].slice(0,10000)){
                for(const c of n.classList) if(cs.size<3000)cs.add(c);
                if(n.id&&ids.size<3000)ids.add(n.id);
            } return {classes:[...cs],ids:[...ids]};})()""", received)
