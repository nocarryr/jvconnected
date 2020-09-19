from loguru import logger
import os
import sys
import asyncio
from pathlib import Path
import argparse

from PySide2 import QtCore, QtQml
from PySide2.QtWidgets import QApplication
from PySide2.QtQuick import QQuickView

from asyncqt import QEventLoop, asyncSlot, asyncClose

from jvconnected.ui import models
from jvconnected.ui import rc_images, rc_qml
from . import get_resource_filename

def register_qml_types():
    models.register_qml_types()

QML_PATH = get_resource_filename('qml')

def run(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    p = argparse.ArgumentParser()
    p.add_argument('-l', '--local-qml', dest='local_qml', action='store_true',
        help='Use local qml files (development mode)',
    )
    args, remaining = p.parse_known_args(argv)

    app = QApplication(remaining)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    app.setOrganizationName('jvconnected')
    app.setApplicationName('jvconnected')
    engine = QtQml.QQmlApplicationEngine()
    if args.local_qml:
        logger.debug('Using local qml files')
        qml_import = str(QML_PATH)
        qml_main = str(QML_PATH / 'main.qml')
    else:
        qml_import = 'qrc:/qml'
        qml_main = 'qrc:/qml/main.qml'
    register_qml_types()
    engine.addImportPath(qml_import)
    engine.load(qml_main)
    win = engine.rootObjects()[0]
    win.show()
    with loop:
        sys.exit(loop.run_forever())

if __name__ == '__main__':
    run()
