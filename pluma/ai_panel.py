"""Lazy native assistant with explicit context preview and bounded conversation."""
import time
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QLineEdit, QPushButton, QCheckBox, QPlainTextEdit, QMessageBox, QDialog, QDialogButtonBox)
from .ai import PRESETS, ask
from .core import validate_endpoint
from .jobs import Job


class AIPanel(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window, self.worker, self.busy = window, None, False
        self.history = []
        self.pending_tokens = []
        self.answer = ''
        box = QVBoxLayout(self)
        intro = QLabel('Sua IA, sua chave. Conteúdo só é enviado ao clicar em Enviar.')
        intro.setWordWrap(True)
        box.addWidget(intro)
        form = QFormLayout()
        self.provider = QComboBox()
        self.provider.addItems(PRESETS)
        self.endpoint, self.model, self.key = QLineEdit(), QLineEdit(), QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText('Chave — somente nesta sessão')
        for label, field in [('Provedor', self.provider), ('Endpoint', self.endpoint),
                             ('Modelo', self.model), ('Chave', self.key)]:
            form.addRow(label, field)
        box.addLayout(form)
        self.remember = QCheckBox('Salvar chave no cofre do sistema')
        box.addWidget(self.remember)
        row = QHBoxLayout()
        for text, callback in [('Carregar chave', self.load_key), ('Apagar chave', self.forget_key)]:
            button = QPushButton(text)
            button.clicked.connect(callback)
            row.addWidget(button)
        box.addLayout(row)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumBlockCount(1500)
        box.addWidget(self.output, 1)
        actions = QHBoxLayout()
        for title, prompt in [('Resumir', 'Resuma os pontos principais deste texto.'),
                              ('Explicar seleção', 'Explique este trecho de forma simples.'),
                              ('Traduzir seleção', 'Traduza este trecho para português brasileiro.')]:
            button = QPushButton(title)
            button.clicked.connect(lambda _, t=title, p=prompt: self.quick(t, p))
            actions.addWidget(button)
        box.addLayout(actions)
        self.prompt = QPlainTextEdit()
        self.prompt.setPlaceholderText('Sua pergunta…')
        self.prompt.setMaximumHeight(90)
        box.addWidget(self.prompt)
        self.context = QCheckBox('Incluir texto da página (prévia antes de enviar)')
        self.with_history = QCheckBox('Usar contexto da conversa (limitado)')
        self.with_history.setChecked(True)
        box.addWidget(self.context)
        box.addWidget(self.with_history)
        row = QHBoxLayout()
        self.send, self.stop = QPushButton('Enviar'), QPushButton('Parar')
        self.send.clicked.connect(self.submit)
        self.stop.clicked.connect(self.cancel)
        self.stop.setEnabled(False)
        row.addWidget(self.send)
        row.addWidget(self.stop)
        box.addLayout(row)
        clear = QPushButton('Limpar conversa')
        clear.clicked.connect(self.clear)
        box.addWidget(clear)
        self.provider.currentTextChanged.connect(self.preset)
        self.endpoint.textChanged.connect(lambda: (self.key.clear(), self.remember.setChecked(False)))
        saved_provider = window.settings.value('ai_provider', list(PRESETS)[0])
        self.provider.setCurrentText(saved_provider)
        self.preset(self.provider.currentText())
        self.endpoint.setText(window.settings.value('ai_endpoint', self.endpoint.text()))
        self.model.setText(window.settings.value('ai_model', self.model.text()))
        self.flush_timer = QTimer(self)
        self.flush_timer.setInterval(60)
        self.flush_timer.timeout.connect(self.flush)

    def preset(self, provider):
        endpoint, model = PRESETS[provider]
        self.endpoint.setText(endpoint)
        self.model.setText(model)
        self.key.clear()
        self.history.clear()

    def load_key(self):
        try:
            import keyring
            self.key.setText(keyring.get_password('Pluma Browser', validate_endpoint(self.endpoint.text())) or '')
        except Exception:
            QMessageBox.warning(self, 'Cofre', 'Cofre indisponível. Use uma chave somente em memória.')

    def forget_key(self):
        self.key.clear()
        self.remember.setChecked(False)
        try:
            import keyring
            account = validate_endpoint(self.endpoint.text())
            if keyring.get_password('Pluma Browser', account):
                keyring.delete_password('Pluma Browser', account)
        except Exception:
            QMessageBox.warning(self, 'Cofre', 'Não foi possível apagar a chave do cofre.')

    def quick(self, title, prompt):
        if self.busy:
            return
        tab = self.window.current()
        if not tab or not tab.view:
            return
        self.prompt.setPlainText(prompt)
        if title == 'Resumir':
            tab.view.page().toPlainText(lambda text: self.preview_and_start(text[:24000]))
        else:
            text = tab.view.page().selectedText()
            if not text:
                QMessageBox.information(self, title, 'Selecione um trecho na página primeiro.')
                return
            self.preview_and_start(text[:24000])

    def submit(self):
        if self.busy or not self.prompt.toPlainText().strip():
            return
        tab = self.window.current()
        if self.context.isChecked() and tab and tab.view:
            tab.view.page().toPlainText(lambda text: self.preview_and_start(text[:24000]))
        else:
            self.start('')

    def preview_and_start(self, text):
        if self.busy:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle('Confirmar conteúdo enviado à IA')
        dialog.resize(650, 450)
        layout = QVBoxLayout(dialog)
        label = QLabel('Destino: ' + self.endpoint.text() + '\nRevise ou edite o texto; ele pode conter dados pessoais.')
        label.setWordWrap(True)
        layout.addWidget(label)
        preview = QPlainTextEdit(text)
        layout.addWidget(preview)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.start(preview.toPlainText()[:24000])

    def start(self, context):
        if self.busy:
            return
        try:
            endpoint = validate_endpoint(self.endpoint.text())
            prompt = self.prompt.toPlainText().strip()
            if not prompt or len(prompt) > 12000 or not self.model.text().strip():
                raise ValueError('Informe modelo e pergunta de até 12.000 caracteres.')
        except ValueError as exc:
            QMessageBox.warning(self, 'IA', str(exc))
            return
        if not self.window.private:
            for name, value in [('provider', self.provider.currentText()), ('endpoint', endpoint),
                                ('model', self.model.text().strip())]:
                self.window.settings.setValue('ai_' + name, value)
        if self.remember.isChecked():
            try:
                import keyring
                keyring.set_password('Pluma Browser', endpoint, self.key.text())
            except Exception:
                QMessageBox.warning(self, 'Cofre', 'Chave permanece somente em memória.')
        args = dict(provider=self.provider.currentText(), endpoint=endpoint, model=self.model.text().strip(),
                    key=self.key.text(), prompt=prompt, context=context,
                    history=list(self.history) if self.with_history.isChecked() else [])
        self.output.appendPlainText('\nVocê: ' + prompt + '\nIA: ')
        self.answer = ''
        self.pending_prompt = prompt
        self.busy = True
        self.flush_timer.start()
        self.send.setEnabled(False)
        self.stop.setEnabled(True)
        self.provider.setEnabled(False)
        self.endpoint.setEnabled(False)

        def run(job):
            buffered, last = [], time.monotonic()
            def token(value):
                nonlocal last
                buffered.append(value)
                if time.monotonic() - last >= .06:
                    job.chunk.emit(''.join(buffered))
                    buffered.clear()
                    last = time.monotonic()
            result = ask(**args, on_chunk=token, cancelled=job.isInterruptionRequested)
            if buffered:
                job.chunk.emit(''.join(buffered))
            args.clear()
            return result
        self.worker = Job(run, self)
        self.worker.chunk.connect(self.receive)
        self.worker.result.connect(self.complete)
        self.worker.error.connect(lambda text: self.output.appendPlainText('\n' + text))
        self.worker.finished.connect(self.done)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def receive(self, value):
        self.answer += value
        self.pending_tokens.append(value)

    def flush(self):
        if self.pending_tokens:
            cursor = self.output.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            cursor.insertText(''.join(self.pending_tokens))
            self.output.setTextCursor(cursor)
            self.pending_tokens.clear()

    def complete(self, result):
        self.history.extend([{'role': 'user', 'content': self.pending_prompt},
                             {'role': 'assistant', 'content': result}])
        self.history = self.history[-12:]
        while sum(len(x['content']) for x in self.history) > 48000:
            self.history.pop(0)

    def cancel(self):
        if self.worker:
            self.worker.requestInterruption()
            self.stop.setEnabled(False)
            self.stop.setText('Parando…')

    def done(self):
        self.flush()
        self.flush_timer.stop()
        self.busy = False
        self.worker = None
        self.send.setEnabled(True)
        self.stop.setEnabled(False)
        self.stop.setText('Parar')
        self.provider.setEnabled(True)
        self.endpoint.setEnabled(True)
        if self.window.close_pending:
            self.window.close()

    def clear(self):
        if not self.busy:
            self.history.clear()
            self.output.clear()
