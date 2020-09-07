from loguru import logger
import asyncio
import threading

from PySide2 import QtCore, QtQml
from PySide2.QtCore import Property, Signal

from asyncqt import QEventLoop, asyncSlot, asyncClose

from jvconnected.engine import Engine
from jvconnected.ui.utils import GenericQObject, connect_close_event
from jvconnected.ui.models.device import DeviceModel, DeviceConfigModel

class EngineModel(GenericQObject):
    _n_running = Signal()
    _n_deviceViewIndices = Signal()
    deviceAdded = Signal(DeviceModel)
    deviceRemoved = Signal(str)
    deviceRemoved = Signal(str)
    configDeviceAdded = Signal(DeviceConfigModel)
    def __init__(self, *args):
        self.loop = asyncio.get_event_loop()
        self.engine = Engine(auto_add_devices=False)
        self.engine.bind_async(self.loop,
            running=self.on_engine_running,
            on_config_device_added=self.on_config_device_added,
            on_device_discovered=self.on_device_discovered,
            on_device_added=self._engine_device_added,
            on_device_removed=self._engine_device_removed,
        )
        self._running = False
        self._device_configs = {}
        self._devices = {}
        self._deviceViewIndices = []
        super().__init__(*args)
        connect_close_event(self.appClose)

    @asyncSlot()
    async def open(self):
        for conf_device in self.engine.config.devices.values():
            await self.on_config_device_added(conf_device)
        await self.engine.open()

    @asyncSlot()
    async def close(self):
        await self.engine.close()

    @asyncSlot()
    async def appClose(self):
        await self.close()

    @QtCore.Slot(str, result=DeviceConfigModel)
    def getDeviceConfig(self, device_id):
        return self._device_configs[device_id]

    @QtCore.Slot(result='QVariantList')
    def getAllDeviceConfigIds(self):
        return list(self._device_configs.keys())

    @QtCore.Slot(str, result=DeviceModel)
    def getDevice(self, device_id):
        return self._devices[device_id]

    def _g_running(self): return self._running
    def _s_running(self, value): self._generic_setter('_running', value)
    running = Property(bool, _g_running, _s_running, notify=_n_running)

    def _g_deviceViewIndices(self): return self._deviceViewIndices
    def _s_deviceViewIndices(self, value): self._generic_setter('_deviceViewIndices', value)
    deviceViewIndices = Property('QVariantList', _g_deviceViewIndices, _s_deviceViewIndices, notify=_n_deviceViewIndices)

    def on_engine_running(self, instance, value, **kwargs):
        self.running = value

    async def _build_device_from_conf(self, device_id):
        conf_device = self.engine.discovered_devices[device_id]
        device = await self.engine.add_device_from_conf(conf_device)
        return device

    async def _add_device_from_conf(self, device_id):
        conf_device = self.engine.config.devices[device_id]
        conf_device_model = self._device_configs[device_id]
        device = self.engine.devices.get(device_id)
        if device is None:
            if conf_device.device_index is None:
                conf_device.device_index = -1
            device = await self._build_device_from_conf(device_id)
        logger.debug(f'_build_device_from_conf: {device}')

    async def on_config_device_added(self, conf_device):
        if conf_device.id in self._device_configs:
            return
        logger.debug(f'adding conf_device: {conf_device}')
        conf_device.bind(device_index=self._calc_device_view_indices)
        model = DeviceConfigModel()
        model.device = conf_device
        self._device_configs[conf_device.id] = model
        self.configDeviceAdded.emit(model)

    @logger.catch
    async def on_device_discovered(self, conf_device, **kwargs):
        logger.info(f'engine.on_device_discovered: {conf_device}')
        await self.on_config_device_added(conf_device)
        await self._add_device_from_conf(conf_device.id)

    async def _engine_device_added(self, device, **kwargs):
        logger.info(f'engine.on_device_added: {device}')
        conf_device_model = self._device_configs[device.id]
        if device.id in self._devices:
            model = self._devices[device.id]
            if model.device is device:
                return
            assert model.deviceId == device.id
            logger.info(f'setting model.device to "{device}"')
            model.device = device
        else:
            model = DeviceModel()
            model.device = device
            model.confDevice = conf_device_model
            self._devices[model.deviceId] = model
            self._calc_device_view_indices()
            # conf_device.bind(device_index=self._calc_device_view_indices)
            self.deviceAdded.emit(model)
            model.removeDeviceIndex.connect(self.on_device_remove_index)


    async def _engine_device_removed(self, device, **kwargs):
        logger.info(f'engine.on_device_removed: {device}')

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
