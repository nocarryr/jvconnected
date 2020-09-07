import os
import sys
import asyncio
from pathlib import Path

from PySide2 import QtCore, QtQml
from PySide2.QtWidgets import QApplication
from PySide2.QtQuick import QQuickView

from asyncqt import QEventLoop, asyncSlot, asyncClose

from jvconnected.ui import models
from jvconnected.ui import rc_images

def register_qml_types():
    models.register_qml_types()

BASE_PATH = Path(__file__).resolve().parent
QML_PATH = BASE_PATH / 'qml'

def run(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    app = QApplication(argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    app.setOrganizationName('jvconnected')
    app.setApplicationName('jvconnected')
    engine = QtQml.QQmlApplicationEngine()
    engine.setBaseUrl(str(QML_PATH))
    engine.addImportPath(str(QML_PATH))
    register_qml_types()
    qml_main = QML_PATH / 'main.qml'
    engine.load(str(qml_main))
    win = engine.rootObjects()[0]
    win.show()
    with loop:
        sys.exit(loop.run_forever())

if __name__ == '__main__':
    run()
