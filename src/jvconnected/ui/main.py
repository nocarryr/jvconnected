from loguru import logger
import os
import sys
import asyncio
from pathlib import Path
import argparse
import importlib

from PySide2 import QtCore, QtQml, QtGui
from PySide2.QtCore import Qt
from PySide2.QtWidgets import QApplication
from PySide2.QtQuick import QQuickView

from qasync import QEventLoop, asyncSlot, asyncClose

from jvconnected.ui import models
from jvconnected.ui import resource_manager
from jvconnected.ui.tools.qrc_utils import QRCDocument
from . import palette
from . import get_resource_filename

resource_manager.load()

def register_qml_types():
    palette.register_qml_types()
    models.register_qml_types()

QML_PATH = get_resource_filename('qml')
QML_QRC = get_resource_filename('qml.qrc')


def check_qrc_hash():
    if not QML_PATH.exists():
        return
    if not QML_QRC.exists():
        return
    qrc_doc = QRCDocument.from_file(QML_QRC)
    hmatch = qrc_doc.hashes_match()
    logger.debug(f'QRC hashes match={hmatch}')
    if not hmatch:
        try:
            from jvconnected.ui.tools import build_qrc
        except ImportError as exc:
            logger.exception(exc)
            return
        logger.info('Rebuilding qml qrc...')
        build_qrc.pack_qml(build_rcc=True)
        logger.success('qml qrc rebuilt')
        logger.info('reloading resource modules')
        resource_manager.load_module('rc_qml')
        logger.success('resource modules reloaded')

def run(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    p = argparse.ArgumentParser()
    p.add_argument('-l', '--local-qml', dest='local_qml', action='store_true',
        help='Use local qml files (development mode)',
    )
    p.add_argument('--palette', dest='palette', choices=['system', 'dark'], default='dark')
    args, remaining = p.parse_known_args(argv)

    if not resource_manager.ready:
        resource_manager.build_missing()
        assert resource_manager.ready is True

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    app = QApplication(remaining)
    QtGui.QIcon.setThemeName('fa-icons')
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
        check_qrc_hash()
        qml_import = 'qrc:/qml'
        qml_main = 'qrc:/qml/main.qml'
    register_qml_types()
    engine.addImportPath(qml_import)
    palette_manager = palette.PaletteManager(
        qmlEngine=engine,
        defaultPaletteName=args.palette,
    )
    context = engine.rootContext()
    context.setContextProperty('paletteManager', palette_manager)

    engine.load(qml_main)
    win = engine.rootObjects()[0]
    win.show()
    with loop:
        sys.exit(loop.run_forever())

if __name__ == '__main__':
    run()
