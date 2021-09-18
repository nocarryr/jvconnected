from loguru import logger
import asyncio
from pathlib import Path
import enum
from typing import Union, Optional

from PySide2 import QtCore, QtQml, QtQuick
from PySide2.QtCore import Property, Signal
from PySide2.QtGui import QPixmap, QColor

from qasync import QEventLoop, asyncSlot, asyncClose

from jvconnected.ui.models.device import DeviceModel
from jvconnected.ui.utils import GenericQObject
from jvconnected.ui.models.waveform import (
    get_waveform_qimage,
    rasterize_wfm_arr,
    img_arr_to_qimg,
    paint_graticules,
)

class PreviewMode(enum.Enum):
    """PreviewMode Enum
    """
    OFF = enum.auto()           #: OFF
    VIDEO = enum.auto()         #: Video
    WAVEFORM = enum.auto()      #: Waveform


class CameraPreview(QtQuick.QQuickPaintedItem):
    """A video or waveform monitor as a QQuickPaintedItem
    """
    _n_device = Signal()
    _n_videoMode = Signal()
    def __init__(self, *args):
        self._device = None
        self._videoMode = PreviewMode.OFF
        self.pixmap = None
        self.capture_task = None
        self._task_lock = asyncio.Lock()
        super().__init__(*args)
        self.setFillColor(QColor('black'))
        self.setRenderTarget(QtQuick.QQuickPaintedItem.RenderTarget.FramebufferObject)
        self.setOpaquePainting(True)

    def _g_device(self): return self._device
    def _s_device(self, value):
        if value == self._device:
            return
        self._device = value
        value._n_connected.connect(self.checkModeOnDeviceConnect)
        self._n_device.emit()
    device = Property(DeviceModel, _g_device, _s_device, notify=_n_device)
    """The :class:`~jvconnected.ui.models.DeviceModel` instance"""

    @asyncSlot()
    async def checkModeOnDeviceConnect(self):
        if self.device is None:
            if self._videoMode != PreviewMode.OFF:
                await self.setVideoMode('OFF')
            return

        if self.device.connected:
            if self._videoMode != PreviewMode.OFF and self.capture_task is None:
                mode = await self._setVideoMode(self._videoMode)
        elif self._videoMode != PreviewMode.OFF:
            await self.setVideoMode('OFF')

    def _g_videoMode(self): return self._videoMode.name
    def _s_videoMode(self, value: Union[str, PreviewMode]):
        if isinstance(value, str):
            value = getattr(PreviewMode, value.upper())
        if value == self._videoMode:
            return
        self._videoMode = value
        self._n_videoMode.emit()
    videoMode = Property(str, _g_videoMode, _s_videoMode, notify=_n_videoMode)
    """The current display mode as a member of :class:`PreviewMode`
    """

    @asyncSlot(str)
    async def setVideoMode(self, mode: str):
        """Set :attr:`videoMode` and handle necessary task control
        """
        mode = getattr(PreviewMode, mode.upper())
        if mode == self._videoMode:
            return
        last_mode = self._videoMode
        self.videoMode = mode
        set_mode = await self._setVideoMode(mode, last_mode)
        if set_mode != mode:
            logger.warning(f'unable to set mode to {mode}.  Result is {set_mode}')

    @logger.catch
    async def _setVideoMode(
        self, mode: PreviewMode, last_mode: Optional[PreviewMode] = None
    ) -> PreviewMode:

        if mode == last_mode:
            return mode
        elif mode in [PreviewMode.VIDEO, PreviewMode.WAVEFORM]:
            if self.device is None or self.device.device is None or not self.device.connected:
                return await self._setVideoMode(PreviewMode.OFF)
            was_off = last_mode not in [PreviewMode.VIDEO, PreviewMode.WAVEFORM]
            if was_off or self.capture_task is None:
                async with self._task_lock:
                    assert self.capture_task is None
                    self.capture_task = asyncio.create_task(self.capture_loop())
        elif mode == PreviewMode.OFF:
            async with self._task_lock:
                t = self.capture_task
                self.capture_task = None
                if t is not None:
                    await t
                self.pixmap = None
            await self.triggerUpdate()
        else:
            raise ValueError(f'Invalid mode: {mode}')
        return mode

    @logger.catch
    async def capture_loop(self):
        """Open the :attr:`~jvconnected.device.Device.devicepreview` and continuously
        request image frames while :attr:`videoMode` is :attr:`~PreviewMode.VIDEO`
        or :attr:`~PreviewMode.WAVEFORM`.

        Each frame is then placed into a ``QPixmap`` and an update is requested
        via ``QPainter``
        """
        device = self.device.device
        async with device.devicepreview as src:
            async for img_bytes in src:
                if self._videoMode == PreviewMode.OFF:
                    break
                if img_bytes is None:
                    continue
                px = QPixmap()
                px.loadFromData(img_bytes)
                await self.setPixmap(px)

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

        mode = self._videoMode
        if mode == PreviewMode.OFF:
            return

        if px is not None:
            if px.width() == 0 or px.height() == 0:
                return
            elif mode == PreviewMode.WAVEFORM:
                px = px.scaled(rect.width(), rect.height())

                wfm_arr = get_waveform_qimage(px.toImage())
                img_arr = rasterize_wfm_arr(wfm_arr)
                qimg = img_arr_to_qimg(img_arr, rect)
                # qimg = draw_wfm_pillow(rect, wfm_arr)
                painter.drawImage(rect, qimg)

                ire_vals, graticules = paint_graticules(painter, rect)
            elif mode == PreviewMode.VIDEO:
                painter.drawPixmap(rect, px)

def register_qml_types():
    QtQml.qmlRegisterType(CameraPreview, 'DeviceModels', 1, 0, 'CameraPreview')
