import sys
import time
from PyQt6.QtCore import QThreadPool
from PyQt6.QtWidgets import QApplication, QLabel
from ui_worker import Worker 

def long_running_task(seconds):
    time.sleep(seconds)
    return f"Task completed after {seconds} seconds"

app = QApplication(sys.argv)
label = QLabel("Running long task...")
label.resize(300, 100)
label.show()

def on_finished(result):
    label.setText(str(result))

def on_failed(error_message):
    label.setText(f"Error: {error_message}")

worker = Worker(long_running_task, 5)
worker.signals.finished.connect(on_finished)
worker.signals.failed.connect(on_failed)
QThreadPool.globalInstance().start(worker)

sys.exit(app.exec())