"""Cooperative background jobs. The GUI never waits on remote HTTP."""
from PySide6.QtCore import QThread, Signal


class Job(QThread):
    result = Signal(object)
    error = Signal(str)
    chunk = Signal(str)

    def __init__(self, task, parent=None):
        super().__init__(parent)
        self.task = task

    def run(self):
        try:
            value = self.task(self)
            if not self.isInterruptionRequested():
                self.result.emit(value)
        except Exception as exc:
            if not self.isInterruptionRequested():
                self.error.emit(str(exc) if isinstance(exc, ValueError) else 'Falha na operação. Confira a conexão.')
        finally:
            self.task = None
