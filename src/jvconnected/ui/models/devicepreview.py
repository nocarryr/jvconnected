from loguru import logger
import asyncio
from pathlib import Path

from PySide2 import QtCore, QtQml, QtQuick
from PySide2.QtCore import Property, Signal
from PySide2.QtGui import QPixmap

from qasync import QEventLoop, asyncSlot, asyncClose

from jvconnected.ui.models.device import DeviceModel
from jvconnected.ui.utils import GenericQObject

class CameraPreview(QtQuick.QQuickPaintedItem):
    _n_device = Signal()
    _n_videoEnabled = Signal()
    def __init__(self, *args):
        self._device = None
        self._videoEnabled = False
        self.pixmap = None
        self.capture_task = None
        super().__init__(*args)

    def _g_device(self): return self._device
    def _s_device(self, value):
        if value == self._device:
            return
        self._device = value
        value._n_connected.connect(self._on_device_connected)
        self._n_device.emit()
    device = Property(DeviceModel, _g_device, _s_device, notify=_n_device)
    """The :class:`~jvconnected.ui.models.DeviceModel` instance"""

    @asyncSlot()
    async def _on_device_connected(self):
        if not self.device.connected:
            await self.setVideoEnabled(False)

    def _g_videoEnabled(self): return self._videoEnabled
    def _s_videoEnabled(self, value):
        if value == self._videoEnabled:
            return
        self._videoEnabled = value
        self._n_videoEnabled.emit()
    videoEnabled = Property(bool, _g_videoEnabled, _s_videoEnabled, notify=_n_videoEnabled)
    """Whether the image capture is currently active"""

    @asyncSlot(bool)
    async def setVideoEnabled(self, enabled: bool):
        """Begin or end encoding and retreiving image frames from the device
        """
        if enabled == self.videoEnabled:
            return
        self.videoEnabled = enabled
        if enabled:
            if self.device is None or self.device.device is None or not self.device.connected:
                self.videoEnabled = False
                return
            self.capture_task = asyncio.create_task(self.capture_loop())
        else:
            t = self.capture_task
            self.capture_task = None
            await t
            self.pixmap = None
            await self.triggerUpdate()

    @logger.catch
    async def capture_loop(self):
        """Open the :attr:`~jvconnected.device.Device.devicepreview` and continuously
        request image frames while :attr:`videoEnabled` is ``True``.

        Each frame is then placed into a ``QPixmap`` and an update is requested
        via ``QPainter``
        """
        device = self.device.device
        async with device.devicepreview as src:
            async for img_bytes in src:
                if not self.videoEnabled:
                    break
                if img_bytes is None:
                    continue
                px = QPixmap()
                px.loadFromData(img_bytes)
                await self.setPixmap(px)
        self.videoEnabled = False

    @asyncSlot(QPixmap)
    async def setPixmap(self, px):
        self.pixmap = px
        await self.triggerUpdate()

    @asyncSlot()
    async def triggerUpdate(self):
        rect = QtCore.QRect(0, 0, self.width(), self.height())
        self.update(rect)

    def paint(self, painter):
        px = self.pixmap
        rect = QtCore.QRect(0, 0, self.width(), self.height())
        if px is None:
            painter.eraseRect(rect)
        else:
            painter.drawPixmap(rect, px)

def register_qml_types():
    QtQml.qmlRegisterType(CameraPreview, 'DeviceModels', 1, 0, 'CameraPreview')
