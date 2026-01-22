from loguru import logger
from PySide6 import QtCore, QtQml
from PySide6.QtCore import Qt, Property, Signal, Slot
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication

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

    darkPalette.setColor(QPalette.ColorRole.Window, window)
    darkPalette.setColor(QPalette.ColorRole.WindowText, text)
    darkPalette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, disabledText)
    darkPalette.setColor(QPalette.ColorRole.Base, base)
    darkPalette.setColor(QPalette.ColorRole.AlternateBase, QColor(46, 47, 48))
    darkPalette.setColor(QPalette.ColorRole.ToolTipBase, base)
    darkPalette.setColor(QPalette.ColorRole.ToolTipText, text)
    darkPalette.setColor(QPalette.ColorRole.Text, text)
    darkPalette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabledText)
    darkPalette.setColor(QPalette.ColorRole.Button, button)
    darkPalette.setColor(QPalette.ColorRole.ButtonText, text)
    darkPalette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabledText)

    darkPalette.setColor(QPalette.ColorRole.Mid, button.lighter(120))
    darkPalette.setColor(QPalette.ColorRole.Highlight, highlight)
    darkPalette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Highlight, QColor(80, 80, 80))
    darkPalette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
    darkPalette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.HighlightedText, QColor(127, 127, 127))
    darkPalette.setColor(QPalette.ColorRole.Shadow, Qt.GlobalColor.black)
    darkPalette.setColor(QPalette.ColorRole.Link, highlight.lighter(160))
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
