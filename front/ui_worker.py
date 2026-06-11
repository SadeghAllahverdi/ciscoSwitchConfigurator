import traceback
from typing import Callable

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot


class WorkerSignals(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)


class Worker(QRunnable):

    def __init__(self, func: Callable, *args, **kwargs):
        super().__init__()
        self.fn = func
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.finished.emit(result)
        except Exception:
            self.signals.failed.emit(traceback.format_exc())
