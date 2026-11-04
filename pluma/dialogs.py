"""Native management panels, created only when opened."""
import json
from html.parser import HTMLParser
from urllib.parse import urlsplit
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QComboBox, QSpinBox,
    QCheckBox, QDialogButtonBox, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QFileDialog, QMessageBox, QHeaderView,
)
from .storage import bookmark_records


class SettingsDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.setWindowTitle('Preferências')
        self.resize(480, 420)
        box = QVBoxLayout(self)
        form = QFormLayout()
        self.mode = QComboBox()
        self.mode.addItems(['Equilibrado', 'Econômico'])
        self.mode.setCurrentText(window.settings.value('mode', 'Equilibrado'))
        self.freeze, self.discard = QSpinBox(), QSpinBox()
        self.freeze.setRange(15, 3600)
        self.discard.setRange(60, 86400)
        self.freeze.setValue(int(window.settings.value('freeze', 60)))
        self.discard.setValue(int(window.settings.value('discard', 300)))
        self.restore = QCheckBox('Recuperar abas ao iniciar (sites carregados sob demanda)')
        self.restore.setChecked(window.settings.value('restore', True, type=bool))
        self.search = QComboBox()
        self.search.addItems(['DuckDuckGo', 'Google', 'Bing'])
        self.search.setCurrentText(window.settings.value('search', 'DuckDuckGo'))
        self.auto = QCheckBox('Atualizar listas de bloqueio a cada 7 dias')
        self.auto.setChecked(window.settings.value('filter_auto', False, type=bool))
        self.history = QCheckBox('Guardar histórico local (até 1.000 páginas)')
        self.history.setChecked(window.settings.value('history_enabled', False, type=bool))
        self.theme = QComboBox()
        self.theme.addItems(['Escuro', 'Claro'])
        self.theme.setCurrentText(window.settings.value('theme', 'Escuro'))
        form.addRow('Economia', self.mode)
        form.addRow('Suspender após (segundos)', self.freeze)
        form.addRow('Descartar após (segundos)', self.discard)
        form.addRow('Pesquisa', self.search)
        form.addRow('Tema', self.theme)
        box.addLayout(form)
        for checkbox in (self.restore, self.auto, self.history):
            box.addWidget(checkbox)
        note = QLabel('Listas são baixadas de easylist.to. Abas com áudio, fixadas ou marcadas como ativas são preservadas.')
        note.setWordWrap(True)
        box.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        box.addWidget(buttons)

    def values(self):
        return {'mode': self.mode.currentText(), 'freeze': self.freeze.value(),
                'discard': max(self.freeze.value() + 15, self.discard.value()),
                'restore': self.restore.isChecked(), 'search': self.search.currentText(),
                'filter_auto': self.auto.isChecked(), 'history_enabled': self.history.isChecked(),
                'theme': self.theme.currentText()}


class BookmarkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items, self.url, self.parts = [], None, []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'a':
            self.url = dict(attrs).get('href')
            self.parts = []

    def handle_data(self, data):
        if self.url:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == 'a' and self.url:
            self.items.append({'url': self.url, 'title': ''.join(self.parts), 'folder': 'Importados'})
            self.url = None


class BookmarksDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle('Favoritos')
        self.resize(760, 440)
        box = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Filtrar favoritos')
        self.search.textChanged.connect(self.filter)
        box.addWidget(self.search)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['Título', 'Endereço', 'Pasta'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.cellDoubleClicked.connect(self.open)
        box.addWidget(self.table)
        row = QHBoxLayout()
        for label, callback in [('Adicionar atual', self.add), ('Excluir', self.remove),
                                ('Importar', self.import_file), ('Exportar', self.export_file),
                                ('Salvar', self.save)]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            button.setEnabled(not window.private or label == 'Exportar')
            row.addWidget(button)
        box.addLayout(row)
        for item in window.bookmark_data:
            self.append(item)

    def append(self, item):
        row = self.table.rowCount()
        self.table.insertRow(row)
        for col, key in enumerate(('title', 'url', 'folder')):
            self.table.setItem(row, col, QTableWidgetItem(item[key]))

    def records(self):
        return bookmark_records([{key: self.table.item(row, col).text()
                                  for col, key in enumerate(('title', 'url', 'folder'))}
                                 for row in range(self.table.rowCount())])

    def filter(self, value):
        for row in range(self.table.rowCount()):
            self.table.setRowHidden(row, value.lower() not in ' '.join(
                self.table.item(row, col).text().lower() for col in range(3)))

    def open(self, row, col):
        url = self.table.item(row, 1).text()
        self.window.add_tab(url)
        self.accept()

    def add(self):
        tab = self.window.current()
        if tab.url():
            self.append({'url': tab.url(), 'title': self.window.tabs.tabText(self.window.tabs.currentIndex()),
                         'folder': ''})

    def remove(self):
        for row in sorted({item.row() for item in self.table.selectedItems()}, reverse=True):
            self.table.removeRow(row)

    def import_file(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Importar favoritos', '', 'Favoritos (*.json *.html *.htm)')
        if not path:
            return
        try:
            from pathlib import Path
            file = Path(path)
            if file.stat().st_size > 5_000_000:
                raise ValueError('Arquivo maior que 5 MB.')
            text = file.read_text(encoding='utf-8')
            if file.suffix.lower() == '.json':
                records = bookmark_records(json.loads(text))
            else:
                parser = BookmarkParser()
                parser.feed(text)
                records = bookmark_records(parser.items)
            existing = {r['url'] for r in self.records()}
            for item in records:
                if item['url'] not in existing and self.table.rowCount() < 2000:
                    self.append(item)
                    existing.add(item['url'])
        except Exception:
            QMessageBox.warning(self, 'Importação', 'Não foi possível ler os favoritos.')

    def export_file(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Exportar favoritos', 'favoritos.json', 'JSON (*.json)')
        if path:
            from .storage import atomic_json
            atomic_json(path, self.records())

    def save(self):
        if not self.window.private:
            self.window.save_bookmarks(self.records())
        self.accept()


class DownloadsDialog(QDialog):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Downloads')
        self.resize(680, 360)
        self.manager = manager
        self.box = QVBoxLayout(self)
        self.empty = QLabel('Nenhum download nesta janela.')
        self.box.addWidget(self.empty)
        self.rows = {}
        self.refresh()
        from PySide6.QtCore import QTimer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(500)

    def refresh(self):
        self.empty.setVisible(not self.manager)
        for item in self.manager[-100:]:
            ident = item.id()
            if ident not in self.rows:
                row = QHBoxLayout()
                label = QLabel()
                label.setWordWrap(True)
                row.addWidget(label, 1)
                pause, cancel = QPushButton('Pausar/retomar'), QPushButton('Cancelar')
                pause.clicked.connect(lambda _, d=item: d.resume() if d.isPaused() else d.pause())
                cancel.clicked.connect(item.cancel)
                row.addWidget(pause)
                row.addWidget(cancel)
                self.box.addLayout(row)
                self.rows[ident] = label, pause, cancel
            label, pause, cancel = self.rows[ident]
            total, received = item.totalBytes(), item.receivedBytes()
            progress = f'{received / 1048576:.1f} / {total / 1048576:.1f} MB' if total > 0 else f'{received / 1048576:.1f} MB'
            label.setText(f'{item.downloadFileName()}\n{progress} · {item.state().name}')
            pause.setEnabled(not item.isFinished())
            cancel.setEnabled(not item.isFinished())
