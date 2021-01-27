from loguru import logger
from PySide2 import QtCore, QtQml
from PySide2.QtCore import Qt, Property, Signal, Slot
from PySide2.QtGui import QPalette, QColor
from PySide2.QtWidgets import QApplication

from jvconnected.ui.utils import GenericQObject

def build_dark_palette():
    darkPalette = QPalette()
    window = QColor(50, 52, 55)
    text = QColor(200, 200, 200)
    disabledText = text.darker(170)
    base = window.darker(150)
    button = window.lighter(115)
    highlight = QColor(42, 130, 218)
    dark = window.darker(170)

    darkPalette.setColor(QPalette.Window, window)
    darkPalette.setColor(QPalette.WindowText, text)
    darkPalette.setColor(QPalette.Disabled, QPalette.WindowText, disabledText)
    darkPalette.setColor(QPalette.Base, base)
    darkPalette.setColor(QPalette.AlternateBase, QColor(46, 47, 48))
    darkPalette.setColor(QPalette.ToolTipBase, base)
    darkPalette.setColor(QPalette.ToolTipText, text)
    darkPalette.setColor(QPalette.Text, text)
    darkPalette.setColor(QPalette.Disabled, QPalette.Text, disabledText)
    darkPalette.setColor(QPalette.Button, button)
    darkPalette.setColor(QPalette.ButtonText, text)
    darkPalette.setColor(QPalette.Disabled, QPalette.ButtonText, disabledText)

    darkPalette.setColor(QPalette.Mid, button.lighter(120))
    darkPalette.setColor(QPalette.Highlight, highlight)
    darkPalette.setColor(QPalette.Disabled, QPalette.Highlight, QColor(80, 80, 80))
    darkPalette.setColor(QPalette.HighlightedText, Qt.white)
    darkPalette.setColor(QPalette.Disabled, QPalette.HighlightedText, QColor(127, 127, 127))
    darkPalette.setColor(QPalette.Shadow, Qt.black)
    darkPalette.setColor(QPalette.Link, highlight.lighter(130))
    return darkPalette

class PaletteManager(GenericQObject):
    paletteChanged = Signal(QPalette)
    _n_qmlEngine = Signal()
    _n_palettes = Signal()
    _n_defaultPaletteName = Signal()
    def __init__(self, *args, **kwargs):
        self._palettes = {}
        self._qmlEngine = kwargs['qmlEngine']
        self._defaultPaletteName = kwargs.get('defaultPaletteName', 'dark')
        app = self.app
        self._palettes['system'] = QPalette(app.palette())
        self._palettes['dark'] = build_dark_palette()
        super().__init__(*args)
        app.paletteChanged.connect(self.on_app_paletteChanged)
        self.setPaletteByName(self.defaultPaletteName)

    @property
    def app(self) -> QApplication:
        return QApplication.instance()

    @property
    def app_palette(self) -> QPalette:
        return self.app.palette()

    def _g_currentPalette(self) -> QPalette:
        return self.app.palette()
    def _s_currentPalette(self, palette: QPalette):
        app_palette = self.app_palette
        if app_palette == palette:
            return
        app_palette.swap(QPalette())
        self.app.setPalette(QPalette(palette))

    currentPalette = Property(QPalette, _g_currentPalette, _s_currentPalette, notify=paletteChanged)

    @Slot(QPalette)
    def on_app_paletteChanged(self, palette: QPalette):
        # if self.qmlEngine.rootObjects():
        #     logger.info('reload qml')
        #     self.qmlEngine.reload()
        self.paletteChanged.emit(palette)

    def _g_qmlEngine(self): return self._qmlEngine
    def _s_qmlEngine(self, value): self._generic_setter('_qmlEngine', value)
    qmlEngine = Property(QtQml.QQmlApplicationEngine, _g_qmlEngine, _s_qmlEngine, notify=_n_qmlEngine)

    def _g_palettes(self): return self._palettes
    def _s_palettes(self, value): self._generic_setter('_palettes', value)
    palettes = Property('QVariantMap', _g_palettes, _s_palettes, notify=_n_palettes)

    def _g_defaultPaletteName(self): return self._defaultPaletteName
    def _s_defaultPaletteName(self, value): self._generic_setter('_defaultPaletteName', value)
    defaultPaletteName = Property(str, _g_defaultPaletteName, _s_defaultPaletteName, notify=_n_defaultPaletteName)

    def _g_defaultPalette(self): return self.palettes[self.defaultPaletteName]
    defaultPalette = Property(QPalette, _g_defaultPalette, notify=_n_defaultPaletteName)

    @Slot('QVariantList')
    def getPaletteNames(self):
        return list(self.palettes.keys())

    @Slot(str, result=QPalette)
    def getPalette(self, name):
        return self.palettes[name]

    @Slot(str)
    def setPaletteByName(self, name: str):
        palette = self.palettes[name]
        self.currentPalette = palette

    @Slot(str, QPalette)
    def addPalette(self, name, palette):
        if name in self.palettes:
            raise ValueError(f'palette named "{name}" exists')
        self.palettes[name] = palette
        self._n_palettes.emit()

def register_qml_types():
    QtQml.qmlRegisterType(PaletteManager, 'Palette', 1, 0, 'PaletteManager')
