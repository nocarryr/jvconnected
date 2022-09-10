from loguru import logger
import asyncio
import threading
from typing import List

from PySide2 import QtCore, QtQml
from PySide2.QtCore import Property, Signal

from qasync import QEventLoop, asyncSlot, asyncClose

from jvconnected.common import ConnectionState
from jvconnected.engine import Engine
from jvconnected.ui.utils import (
    GenericQObject, connect_async_close_event, AnnotatedQtSignal as AnnoSignal,
)
from jvconnected.ui.models.device import DeviceModel, DeviceConfigModel

class EngineModel(GenericQObject):
    """Qt Bridge to :class:`jvconnected.engine.Engine`

    This object creates an instance of :class:`jvconnected.engine.Engine`
    and handles all necessary interaction with it
    """
    _n_running = Signal()
    _n_deviceViewIndices = Signal()
    deviceAdded: AnnoSignal(device=DeviceModel) = Signal(DeviceModel)
    """Fired when an active device is added to the engine
    """

    deviceRemoved: AnnoSignal(device_id=str) = Signal(str)
    """Fired when a device is removed
    """

    configDeviceAdded: AnnoSignal(conf_device=DeviceConfigModel) = Signal(DeviceConfigModel)
    """Fired when a device is detected or loaded from config
    """

    engine: Engine
    """The engine instance"""

    def __init__(self, *args):
        self.loop = asyncio.get_event_loop()
        self.engine = Engine(auto_add_devices=True)
        self.engine.bind_async(self.loop,
            running=self.on_engine_running,
            on_config_device_added=self.on_config_device_added,
            on_device_discovered=self.on_device_discovered,
            on_device_added=self._engine_device_added,
            on_device_connected=self._engine_device_connected,
            on_device_removed=self._engine_device_removed,
        )
        self._running = False
        self._device_configs = {}
        self._devices = {}
        self._deviceViewIndices = []
        super().__init__(*args)
        connect_async_close_event(self.appClose)

    @asyncSlot()
    async def open(self):
        """Open the :attr:`engine`
        See :meth:`jvconnected.engine.Engine.open`
        """
        for conf_device in self.engine.config.devices.values():
            await self.on_config_device_added(conf_device)
        await self.engine.open()

    @asyncSlot()
    async def close(self):
        """Close the :attr:`engine`
        See :meth:`jvconnected.engine.Engine.close`
        """
        await self.engine.close()

    async def appClose(self):
        await self.close()

    @QtCore.Slot(str, result=DeviceConfigModel)
    def getDeviceConfig(self, device_id: str) -> DeviceConfigModel:
        """Get a :class:`jvconnected.ui.models.device.DeviceConfigModel` by its
        :attr:`~jvconnected.ui.models.device.DeviceConfig.deviceId`
        """
        return self._device_configs[device_id]

    @QtCore.Slot(result='QVariantList')
    def getAllDeviceConfigIds(self) -> List[str]:
        """Get a list of all device ids in the :class:`jvconnected.config.Config`
        """
        return list(self._device_configs.keys())

    @QtCore.Slot(str, result=DeviceModel)
    def getDevice(self, device_id: str) -> DeviceModel:
        """Get a :class:`jvconnected.ui.models.device.DeviceModel` by its
        :attr:`~jvconnected.ui.models.device.DeviceModel.deviceId`
        """
        return self._devices[device_id]

    def _g_running(self) -> bool: return self._running
    def _s_running(self, value: bool): self._generic_setter('_running', value)
    running: bool = Property(bool, _g_running, _s_running, notify=_n_running)
    """Run state"""

    def _g_deviceViewIndices(self): return self._deviceViewIndices
    def _s_deviceViewIndices(self, value): self._generic_setter('_deviceViewIndices', value)
    deviceViewIndices: List[int] = Property('QVariantList',
        _g_deviceViewIndices, _s_deviceViewIndices, notify=_n_deviceViewIndices,
    )

    def on_engine_running(self, instance, value, **kwargs):
        self.running = value

    @logger.catch
    async def on_config_device_added(self, conf_device):
        if conf_device.id in self._device_configs:
            model = self._device_configs[conf_device.id]
            if model.device is not conf_device:
                if model.device is not None:
                    model.device.unbind(self)
                model.device = conf_device
                conf_device.bind(device_index=self._calc_device_view_indices)
            return
        logger.debug(f'adding conf_device: {conf_device}')
        conf_device.bind(device_index=self._calc_device_view_indices)
        model = DeviceConfigModel(device=conf_device)
        self._device_configs[conf_device.id] = model
        model.reconnectSignal.connect(self.on_device_conf_reconnect_sig)
        self.configDeviceAdded.emit(model)

    @logger.catch
    async def on_device_discovered(self, conf_device, **kwargs):
        logger.info(f'engine.on_device_discovered: {conf_device}')
        await self.on_config_device_added(conf_device)

    @logger.catch
    async def _engine_device_added(self, device, **kwargs):
        conf_device_model = self._device_configs[device.id]
        if device.connection_state == ConnectionState.CONNECTED:
            return
        if conf_device_model.alwaysConnect:
            await self._engine_device_connected(device, **kwargs)


    @logger.catch
    async def _engine_device_connected(self, device, **kwargs):
        conf_device_model = self._device_configs[device.id]
        logger.info(f'engine.on_device_connected: {device=}, {conf_device_model=}')
        engine_conf_device = self.engine.config.devices[device.id]
        assert conf_device_model.device is engine_conf_device
        if device.id in self._devices:
            model = self._devices[device.id]
            assert model.confDevice is conf_device_model
            if model.device is device:
                return
            assert model.deviceId == device.id
            logger.info(f'setting model.device to "{device}"')
            model.device = device
        else:
            logger.info(f'creating new DeviceModel for "{device.id}"')
            model = DeviceModel(confDevice=conf_device_model)
            model.device = device
            model.reconnectSignal.connect(self.on_device_reconnect_sig)
            self._devices[model.deviceId] = model
            self._calc_device_view_indices()
            self.deviceAdded.emit(model)
            model.removeDeviceIndex.connect(self.on_device_remove_index)
        logger.debug(f'{engine_conf_device.connection_state=}, {engine_conf_device.device_index=}, {device.device_index=}')

    @logger.catch
    async def _engine_device_removed(self, device, reason, **kwargs):
        conf_device_model = self._device_configs.get(device.id)
        logger.info(f'engine.on_device_removed: {device}, {reason}, {conf_device_model=}')
        model = self._devices.get(device.id)
        if model is not None:
            model.device = None

    @asyncSlot(DeviceConfigModel)
    async def on_device_conf_reconnect_sig(self, conf_device_model: DeviceConfigModel):
        """Reconnect the given device

        Calls the :meth:`~jvconnected.engine.Engine.reconnect_device` method on
        the :attr:`engine`.
        """
        conf_device = conf_device_model.device
        if conf_device.device_index is None:
            conf_device.device_index = -1
            logger.debug(f'set conf_device index: {conf_device.device_index=}')

        state = await self.engine.reconnect_device(conf_device, wait_for_state=True)
        logger.debug(f'reconnect state={state!r}')
        config_conf_device = self.engine.config.devices[conf_device.id]
        assert config_conf_device is conf_device


    @asyncSlot(DeviceModel)
    async def on_device_reconnect_sig(self, device_model: DeviceModel):
        await self.on_device_conf_reconnect_sig(device_model.confDevice)

    def _calc_device_view_indices(self, *args, **kwargs):
        devices = self.engine.config.devices
        d = {dev.device_index:dev.id for dev in devices.values() if dev.id in self._devices and dev.device_index is not None}
        # d = {dev.deviceIndex:dev.deviceId for dev in self._devices.values()}
        l = [d[key] for key in sorted(d.keys())]
        self.deviceViewIndices = l

    # @asyncSlot(str)
    def on_device_remove_index(self, device_id):
        model = self._devices[device_id]
        device = model.device
        conf_device_model = self._device_configs[device_id]
        conf_device = conf_device_model.device
        # await device.stop()
        # model.device = None
        conf_device.device_index = None

def register_qml_types():
    QtQml.qmlRegisterType(EngineModel, 'DeviceModels', 1, 0, 'EngineModel')
