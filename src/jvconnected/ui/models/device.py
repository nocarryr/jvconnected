from __future__ import annotations
from loguru import logger
import asyncio
import typing as tp
from typing import List, TYPE_CHECKING
if TYPE_CHECKING:
    from jvconnected.config import DeviceConfig
    from jvconnected.device import Device, ParameterGroup
from jvconnected.common import ConnectionState
from jvconnected.device import (
    MenuChoices, BatteryState, FocusDirection, ZoomDirection,
)

from PySide2 import QtCore, QtQml
from PySide2.QtCore import Property, Signal

from qasync import QEventLoop, asyncSlot, asyncClose

from jvconnected.ui.utils import GenericQObject, AnnotatedQtSignal as AnnoSignal

class DeviceBase(GenericQObject):
    """Base class to interface devices with Qt
    """
    _n_device = Signal()
    _n_deviceId = Signal()
    _n_deviceIndex = Signal()
    _n_modelName = Signal()
    _n_serialNumber = Signal()
    _n_displayName = Signal()
    _n_hostaddr = Signal()
    _n_hostport = Signal()
    _n_authUser = Signal()
    _n_authPass = Signal()
    _n_connectionState = Signal()
    reconnectSignal: AnnoSignal(device='DeviceBase') = Signal(QtCore.QObject)
    """Signals the owning :class:`~.engine.EngineModel` to initiate a reconnect
    for the device

    See :meth:`.engine.EngineModel.on_device_conf_reconnect_sig`
    """
    def __init__(self, *args):
        self.loop = asyncio.get_event_loop()
        self._device = None
        self._deviceId = None
        self._deviceIndex = -1
        self._modelName = None
        self._serialNumber = None
        self._displayName = ''
        self._hostaddr = None
        self._hostport = 80
        self._authUser = None
        self._authPass = None
        self._connectionState = ConnectionState.UNKNOWN
        super().__init__(*args)

    def _g_device(self): return self._device
    def _s_device(self, value):
        if value is not None and value is self._device:
            return
        self._do_set_device(value)
    def _do_set_device(self, device):
        raise NotImplementedError
    device = Property(object, _g_device, _s_device, notify=_n_device)
    """The device instance"""

    def _on_device_set(self, device):
        self.deviceId = device.id
        self.modelName = device.model_name
        self.serialNumber = device.serial_number
        self.hostaddr = device.hostaddr
        self.hostport = device.hostport
        self.authUser = device.auth_user
        self.authPass = device.auth_pass

    def _g_deviceId(self) -> str: return self._deviceId
    def _s_deviceId(self, value: str): self._generic_setter('_deviceId', value)
    deviceId: str = Property(str, _g_deviceId, _s_deviceId, notify=_n_deviceId)
    """The device id"""

    def _g_deviceIndex(self): return self._deviceIndex
    def _s_deviceIndex(self, value): self._generic_setter('_deviceIndex', value)
    deviceIndex: int = Property(int, _g_deviceIndex, _s_deviceIndex, notify=_n_deviceIndex)
    """The device index"""

    def _g_modelName(self): return self._modelName
    def _s_modelName(self, value): self._generic_setter('_modelName', value)
    modelName = Property(str, _g_modelName, _s_modelName, notify=_n_modelName)

    def _g_serialNumber(self): return self._serialNumber
    def _s_serialNumber(self, value): self._generic_setter('_serialNumber', value)
    serialNumber = Property(str, _g_serialNumber, _s_serialNumber, notify=_n_serialNumber)

    def _g_displayName(self): return self._displayName
    def _s_displayName(self, value): self._generic_setter('_displayName', value)
    displayName = Property(str, _g_displayName, _s_displayName, notify=_n_displayName)

    def _g_hostaddr(self): return self._hostaddr
    def _s_hostaddr(self, value): self._generic_setter('_hostaddr', value)
    hostaddr = Property(str, _g_hostaddr, _s_hostaddr, notify=_n_hostaddr)

    def _g_hostport(self): return self._hostport
    def _s_hostport(self, value): self._generic_setter('_hostport', value)
    hostport = Property(int, _g_hostport, _s_hostport, notify=_n_hostport)

    def _g_authUser(self): return self._authUser
    def _s_authUser(self, value): self._generic_setter('_authUser', value)
    authUser = Property(str, _g_authUser, _s_authUser, notify=_n_authUser)

    def _g_authPass(self): return self._authPass
    def _s_authPass(self, value): self._generic_setter('_authPass', value)
    authPass = Property(str, _g_authPass, _s_authPass, notify=_n_authPass)

    def _g_connectionState(self) -> str: return self._connectionState.name.lower()
    def _s_connectionState(self, value: ConnectionState|str):
        if not isinstance(value, ConnectionState):
            value = getattr(ConnectionState, value.upper())
        if value == self._connectionState:
            return
        self._connectionState = value
        self._n_connectionState.emit()
    connectionState: str = Property(str, _g_connectionState, _s_connectionState, notify=_n_connectionState)
    """The device's :class:`~jvconnected.common.ConnectionState`
    as a lowercase string
    """

    @QtCore.Slot()
    def reconnect(self):
        """Send the :attr:`reconnectSignal`
        """
        self.reconnectSignal.emit(self)

    def __repr__(self):
        return f'<{self.__class__}: "{self}">'
    def __str__(self):
        if self.device is not None:
            return str(self.device)
        elif self.deviceId is not None:
            return self.deviceId
        return 'None'

class DeviceConfigModel(DeviceBase):
    """Qt Bridge for :class:`jvconnected.config.DeviceConfig`
    """
    _n_deviceOnline = Signal()
    _n_deviceActive = Signal()
    _n_storedInConfig = Signal()
    _n_alwaysConnect = Signal()
    _n_editedProperties = Signal()
    propertiesUpdated = Signal('QVariantList')
    _prop_attr_map = {
        'always_connect':'alwaysConnect',
        'stored_in_config':'storedInConfig', 'device_index':'deviceIndex',
        'display_name':'displayName', 'auth_user':'authUser', 'auth_pass':'authPass',
        'hostaddr':'hostaddr', 'hostport':'hostport',
    }
    _editable_properties = [
        'display_name', 'device_index', 'auth_user', 'auth_pass',
        'hostaddr', 'hostport', 'always_connect',
    ]
    def __init__(self, *args, **kwargs):
        prop_map, editable = self._prop_attr_map, self._editable_properties
        self._editable_props_camel_case = [prop_map[prop] for prop in editable]
        self._deviceOnline = False
        self._deviceActive = False
        self._storedInConfig = False
        self._alwaysConnect = False
        super().__init__(*args)
        self.device = kwargs['device']

    def _g_deviceOnline(self) -> bool: return self._deviceOnline
    def _s_deviceOnline(self, value: bool): self._generic_setter('_deviceOnline', value)
    deviceOnline: bool = Property(bool,
        _g_deviceOnline, _s_deviceOnline, notify=_n_deviceOnline,
    )
    """Alias for :attr:`jvconnected.config.DeviceConfig.online`"""

    def _g_deviceActive(self) -> bool: return self._deviceActive
    def _s_deviceActive(self, value: bool): self._generic_setter('_deviceActive', value)
    deviceActive: bool = Property(bool,
        _g_deviceActive, _s_deviceActive, notify=_n_deviceActive,
    )
    """Alias for :attr:`jvconnected.config.DeviceConfig.active`"""

    def _g_storedInConfig(self): return self._storedInConfig
    def _s_storedInConfig(self, value): self._generic_setter('_storedInConfig', value)
    storedInConfig: bool = Property(bool,
        _g_storedInConfig, _s_storedInConfig, notify=_n_storedInConfig,
    )
    """Alias for :attr:`jvconnected.config.DeviceConfig.stored_in_config`"""

    def _g_alwaysConnect(self): return self._alwaysConnect
    def _s_alwaysConnect(self, value): self._generic_setter('_alwaysConnect', value)
    alwaysConnect: bool = Property(bool,
        _g_alwaysConnect, _s_alwaysConnect, notify=_n_alwaysConnect,
    )
    """Alias for :attr:`jvconnected.config.DeviceConfig.always_connect`"""

    def _do_set_device(self, device):
        if device is not None:
            assert self._device is None
            self._device = device
            self._on_device_set(device)
            self._n_device.emit()
        else:
            self._generic_setter('_device', device)

    @asyncSlot(int)
    async def setDeviceIndex(self, value: int):
        """Set the :attr:`~jvconnected.config.DeviceConfig.device_index`
        on the :attr:`device`
        """
        if value == -1:
            value = None
        self.device.device_index = value

    @QtCore.Slot('QVariantMap')
    def setFormValues(self, data: dict):
        for dev_attr, my_attr in self._prop_attr_map.items():
            if dev_attr not in self._editable_properties:
                continue
            if my_attr not in data:
                continue
            value = data[my_attr]
            dev_val = getattr(self.device, dev_attr)
            if my_attr == 'deviceIndex':
                if value == -1:
                    value = None
            if value == dev_val:
                continue
            logger.debug(f'DeviceConfigModel setting {dev_attr}={value}')
            setattr(self.device, dev_attr, value)

    @QtCore.Slot(result='QVariantMap')
    def getEditableProperties(self):
        d = {}
        for dev_attr, my_attr in self._prop_attr_map.items():
            value = getattr(self, my_attr)
            if value is None:
                value = ''
            d[my_attr] = value
        return d

    @QtCore.Slot(str, result='QVariant')
    def getEditableProperty(self, name: str):
        return getattr(self, name)

    def _on_device_set(self, device):
        props_updated = []
        for dev_attr, self_attr in self._prop_attr_map.items():
            val = getattr(device, dev_attr)
            if self_attr == 'deviceIndex':
                if val is None:
                    val = -1
            changed = getattr(self, self_attr) == val
            setattr(self, self_attr, val)
            if changed:
                if dev_attr in self._prop_attr_map:
                    props_updated.append(self_attr)
        if len(props_updated):
            self.propertiesUpdated.emit(props_updated)
        keys = self._prop_attr_map.keys()
        device.bind(**{key:self.on_device_prop_change for key in keys})
        super()._on_device_set(device)
        self.deviceOnline, self.deviceActive = device.online, device.active
        self.connectionState = device.connection_state
        device.bind(
            online=self.on_device_online,
            active=self.on_device_active,
            connection_state=self.on_device_connection_state,
        )

    def on_device_online(self, instance, value, **kwargs):
        if instance is not self.device:
            return
        self.deviceOnline = value

    def on_device_active(self, instance, value, **kwargs):
        if instance is not self.device:
            return
        self.deviceActive = value

    def on_device_connection_state(self, instance, value, **kwargs):
        if instance is not self.device:
            return
        self.connectionState = value

    def on_device_prop_change(self, instance, value, **kwargs):
        if instance is not self.device:
            return
        prop = kwargs['property']
        attr = self._prop_attr_map.get(prop.name)

        if attr is not None:
            if attr == 'deviceIndex':
                if value is None:
                    value = -1
            setattr(self, attr, value)
            if prop.name in self._prop_attr_map:
                self.propertiesUpdated.emit([attr])


class DeviceModel(DeviceBase):
    """Qt Bridge for :class:`jvconnected.device.Device`

    """
    _n_connected = Signal()
    _n_confDevice = Signal()
    removeDeviceIndex: AnnoSignal(device_id=str) = Signal(str)
    """When triggered, the :class:`~jvconnected.ui.models.engine.EngineModel`
    resets the device_index of the :class:`jvconnected.config.DeviceConfig`
    for this :attr:`device`. This will force an auto-calculation of the
    index
    """

    def __init__(self, *args, **kwargs):
        self._connected = False
        self._confDevice = None
        super().__init__(*args)
        self.confDevice = kwargs['confDevice']

    def _g_confDevice(self) -> DeviceConfigModel: return self._confDevice
    def _s_confDevice(self, value: DeviceConfigModel):
        if self._confDevice == value:
            return
        self._generic_setter('_confDevice', value)
        if value is not None:
            self.deviceIndex = value.deviceIndex
            value._n_deviceIndex.connect(self._on_conf_index_changed)
            self.displayName = value.displayName
            value._n_displayName.connect(self._on_conf_display_name_changed)
    confDevice: DeviceConfigModel = Property(DeviceConfigModel,
        _g_confDevice, _s_confDevice, notify=_n_confDevice,
    )
    """Instance of :class:`DeviceConfigModel` matching this device"""

    def _do_set_device(self, device):
        old = self._device
        if old is not None:
            old.unbind(self)
        if device is not None:
            if old is not None:
                assert not old.connected
                assert device.id == self.deviceId
            self._device = device
            self._on_device_set(device)
            self._n_device.emit()
        else:
            self._generic_setter('_device', device)
            self.connected = False

    def _g_connected(self) -> bool: return self._connected
    def _s_connected(self, value: bool): self._generic_setter('_connected', value)
    connected: bool = Property(bool, _g_connected, _s_connected, notify=_n_connected)
    """Alias for :attr:`jvconnected.device.Device.connected`"""

    @asyncSlot()
    async def open(self):
        """Calls :meth:`~jvconnected.device.Device.open` on the :attr:`device`
        """
        device = self.device
        if device is None:
            self.connected = False
            return
        await device.open()

    @asyncSlot()
    async def close(self):
        """Calls :meth:`~jvconnected.device.Device.close` on the :attr:`device`
        """
        device = self.device
        if device is None:
            return
        await device.close()

    @asyncClose
    async def onAppClose(self):
        await self.close()

    @asyncSlot(int)
    async def setDeviceIndex(self, value: int):
        """Calls :meth:`~DeviceConfigModel.setDeviceIndex` on :attr:`confDevice`
        """
        await self.confDevice.setDeviceIndex(value)

    def _on_device_set(self, device):
        super()._on_device_set(device)
        self.connected = device._is_open
        self.connectionState = device.connection_state
        device.bind(connection_state=self.on_device_connection_state)
        device.bind_async(self.loop,
            model_name=self._on_device_model_name,
            serial_number=self._on_device_serial_number,
            connected=self._on_device_connected,
        )

    def on_device_connection_state(self, instance, value, **kwargs):
        if instance is not self.device:
            return
        self.connectionState = value

    def _on_conf_index_changed(self):
        self.deviceIndex = self.confDevice.deviceIndex

    def _on_conf_display_name_changed(self):
        self.displayName = self.confDevice.displayName

    async def _on_device_model_name(self, instance, value, **kwargs):
        self.modelName = value

    async def _on_device_serial_number(self, instance, value, **kwargs):
        self.serialNumber = value

    async def _on_device_connected(self, instance, value, **kwargs):
        if instance is not self.device:
            return
        self.connected = value

class ParamBase(GenericQObject):
    """Qt Bridge for :class:`jvconnected.device.ParameterGroup`
    """
    _n_device = Signal()
    _n_paramGroup = Signal()
    _param_group_key = None
    _prop_attr_map = None
    def __init__(self, *args):
        self.loop = asyncio.get_event_loop()
        assert self._param_group_key is not None
        self._device = None
        self._paramGroup = None
        super().__init__(*args)

    def _g_device(self) -> DeviceModel: return self._device
    def _s_device(self, value: DeviceModel):
        if value is not None and value is self._device:
            return
        self._generic_setter('_device', value)
        self._on_device_set(value)
        if value is not None:
            value._n_device.connect(self.on_device_changed)
    device: DeviceModel = Property(DeviceModel,
        _g_device, _s_device, notify=_n_device,
    )
    """The parent :class:`DeviceModel`"""

    def _g_paramGroup(self) -> 'ParameterGroup': return self._paramGroup
    def _s_paramGroup(self, value: 'ParameterGroup'):
        if value is not None and value is self._paramGroup:
            return
        old = self._paramGroup
        if old is not None:
            old.unbind(self)
        self._generic_setter('_paramGroup', value)
    paramGroup: ParameterGroup = Property(object,
        _g_paramGroup, _s_paramGroup, notify=_n_paramGroup,
    )
    """The :class:`jvconnected.device.ParameterGroup` for this object. Retreived
    from the :attr:`device`
    """

    def _on_device_set(self, device):
        if device is None or device.device is None:
            self.paramGroup = None
            return
        p = self.paramGroup = device.device.parameter_groups[self._param_group_key]
        self._on_param_group_set(p)

    def on_device_changed(self):
        self._on_device_set(self.device)

    def _on_param_group_set(self, param_group):
        if not self._prop_attr_map:
            return
        for pg_attr, my_attr in self._prop_attr_map.items():
            val = getattr(param_group, pg_attr)
            setattr(self, my_attr, val)
            param_group.bind_async(self.loop, **{pg_attr:self._on_prop_set})

    def _on_prop_set(self, instance, value, **kwargs):
        if instance is not self.paramGroup:
            return
        prop = kwargs['property']
        pg_attr = prop.name
        my_attr = self._prop_attr_map[pg_attr]
        setattr(self, my_attr, value)

    async def _run_on_device_loop(self, coro):
        return await coro
        # fut = asyncio.run_coroutine_threadsafe(coro, loop=self.device.loop)
        # return await asyncio.wrap_future(fut)

class CameraParamsModel(ParamBase):
    _n_status = Signal()
    _n_menuStatus = Signal()
    _n_mode = Signal()
    _n_timecode = Signal()
    _param_group_key = 'camera'
    _prop_attr_map = {
        'status':'status', 'menu_status':'menuStatus', 'mode':'mode', 'timecode':'timecode',
    }
    def __init__(self, *args):
        self._status = None
        self._menuStatus = False
        self._mode = None
        self._timecode = None
        super().__init__(*args)

    def _g_status(self) -> str: return self._status
    def _s_status(self, value: str): self._generic_setter('_status', value)
    status: str = Property(str, _g_status, _s_status, notify=_n_status)
    """Alias for :attr:`jvconnected.device.CameraParams.status`"""

    def _g_menuStatus(self) -> bool: return self._menuStatus
    def _s_menuStatus(self, value: bool): self._generic_setter('_menuStatus', value)
    menuStatus: bool = Property(bool, _g_menuStatus, _s_menuStatus, notify=_n_menuStatus)
    """Alias for :attr:`jvconnected.device.CameraParams.menu_status`"""

    def _g_mode(self) -> str: return self._mode
    def _s_mode(self, value: str): self._generic_setter('_mode', value)
    mode: str = Property(str, _g_mode, _s_mode, notify=_n_mode)
    """Alias for :attr:`jvconnected.device.CameraParams.status`"""

    def _g_timecode(self) -> str: return self._timecode
    def _s_timecode(self, value: str): self._generic_setter('_timecode', value)
    timecode: str = Property(str, _g_timecode, _s_timecode, notify=_n_timecode)
    """Alias for :attr:`jvconnected.device.CameraParams.status`"""

    @asyncSlot(str)
    async def sendMenuButton(self, value: str):
        """Send a menu button event

        Arguments:
            value (str): The menu button type as a string. Must be the name of
                a member of :class:`~jvconnected.device.MenuChoices`

        See :meth:`jvconnected.device.CameraParams.send_menu_button`
        """
        enum_value = getattr(MenuChoices, value.upper())
        await self.paramGroup.send_menu_button(enum_value)

class NTPParamsModel(ParamBase):
    """Qt bridge for :class:`jvconnected.device.NTPParams`
    """
    _param_group_key = 'ntp'
    _prop_attr_map = {
        'address':'address', 'tc_sync':'tcSync',
        'syncronized':'syncronized', 'sync_master':'syncMaster',
    }
    _n_address = Signal()
    _n_tcSync = Signal()
    _n_syncronized = Signal()
    _n_syncMaster = Signal()

    def __init__(self, *args):
        self._address = ''
        self._tcSync = False
        self._syncronized = False
        self._syncMaster = False
        super().__init__(*args)

    def _g_address(self) -> str: return self._address
    def _s_address(self, value: str): self._generic_setter('_address', value)
    address: str = Property(str, _g_address, _s_address, notify=_n_address)
    """Alias for :class:`jvconnected.device.NTPParams.address`"""

    def _g_tcSync(self) -> bool: return self._tcSync
    def _s_tcSync(self, value: bool): self._generic_setter('_tcSync', value)
    tcSync: bool = Property(bool, _g_tcSync, _s_tcSync, notify=_n_tcSync)
    """Alias for :class:`jvconnected.device.NTPParams.tc_sync`"""

    def _g_syncronized(self) -> bool: return self._syncronized
    def _s_syncronized(self, value: bool): self._generic_setter('_syncronized', value)
    syncronized: bool = Property(bool, _g_syncronized, _s_syncronized, notify=_n_syncronized)
    """Alias for :class:`jvconnected.device.NTPParams.syncronized`"""

    def _g_syncMaster(self) -> bool: return self._syncMaster
    def _s_syncMaster(self, value: bool): self._generic_setter('_syncMaster', value)
    syncMaster: bool = Property(bool, _g_syncMaster, _s_syncMaster, notify=_n_syncMaster)
    """Alias for :class:`jvconnected.device.NTPParams.sync_master`"""

    @asyncSlot(str)
    async def setAddress(self, address: str):
        """Set the NTP server using :meth:`jvconnected.device.NTPParams.set_address`
        """
        await self.paramGroup.set_address(address)

class BatteryParamsModel(ParamBase):
    _param_group_key = 'battery'
    _prop_attr_map = {'state':'batteryState', 'level':'level'}
    _n_batteryState = Signal()
    _n_level = Signal()
    _n_textStatus = Signal()

    def __init__(self, *args):
        self._batteryState = BatteryState.UNKNOWN.name
        self._textStatus = ''
        self._level = 0.
        super().__init__(*args)

    def _g_batteryState(self) -> str: return self._batteryState
    def _s_batteryState(self, value: BatteryState):
        if value is not None:
            value = value.name
        self._generic_setter('_batteryState', value)
    batteryState: str = Property(str,
        _g_batteryState, _s_batteryState, notify=_n_batteryState,
    )
    """Alias for :attr:`jvconnected.device.BatteryParams.state`"""

    def _g_level(self) -> float: return self._level
    def _s_level(self, value: float): self._generic_setter('_level', value)
    level: float = Property(float, _g_level, _s_level, notify=_n_level)
    """Alias for :attr:`jvconnected.device.BatteryParams.level`"""

    def _g_textStatus(self) -> str: return self._textStatus
    def _s_textStatus(self, value: BatteryState): self._generic_setter('_textStatus', value)
    textStatus: str = Property(str, _g_textStatus, _s_textStatus, notify=_n_textStatus)
    """Battery information from one of :attr:`~jvconnected.device.BatteryParams.minutes`,
    :attr:`~jvconnected.device.BatteryParams.percent` or
    :attr:`~jvconnected.device.BatteryParams.voltage` depending on availability
    """

    def _on_param_group_set(self, param_group):
        super()._on_param_group_set(param_group)
        props = ['minutes', 'percent', 'voltage']
        param_group.bind(**{prop:self._update_text_status for prop in props})

    def _update_text_status(self, instance, value, **kwargs):
        if instance is not self.paramGroup:
            return
        if value == -1:
            return
        prop = kwargs['property']
        if prop.name == 'minutes':
            txt = f'{value}min'
        elif prop.name == 'percent':
            txt = f'{value}%'
        elif prop.name == 'voltage':
            txt = f'{value:.1f}V'
        else:
            txt = ''
        self.textStatus = txt

class IrisModel(ParamBase):
    _param_group_key = 'exposure'
    _prop_attr_map = {
        'iris_mode':'mode',
        'iris_fstop':'fstop',
        'iris_pos':'pos',
    }
    _n_mode = Signal()
    _n_fstop = Signal()
    _n_pos = Signal()
    _n_requestedPos = Signal()
    def __init__(self, *args):
        self._mode = None
        self._fstop = None
        self._pos = None
        self._requestedPos = -1
        self._request_pending = asyncio.Lock()
        super().__init__(*args)

    def _g_mode(self) -> str: return self._mode
    def _s_mode(self, value: str): self._generic_setter('_mode', value)
    mode: str = Property(str, _g_mode, _s_mode, notify=_n_mode)
    """Alias for :attr:`jvconnected.device.ExposureParams.iris_mode`"""

    def _g_fstop(self) -> str: return str(self._fstop)
    def _s_fstop(self, value: str): self._generic_setter('_fstop', value)
    fstop: str = Property(str, _g_fstop, _s_fstop, notify=_n_fstop)
    """Alias for :attr:`jvconnected.device.ExposureParams.iris_fstop`"""

    def _g_pos(self) -> int: return self._pos
    def _s_pos(self, value: int): self._generic_setter('_pos', value)
    pos: int = Property(int, _g_pos, _s_pos, notify=_n_pos)
    """Alias for :attr:`jvconnected.device.ExposureParams.iris_pos`"""

    def _g_requestedPos(self): return self._requestedPos
    def _s_requestedPos(self, value):
        value = int(value)
        if value == self._requestedPos:
            return
        # logger.debug(f'requestedPos = {value}')
        self._requestedPos = value
        self._n_requestedPos.emit()
    requestedPos = Property(int, _g_requestedPos, _s_requestedPos, notify=_n_requestedPos)

    @asyncSlot(bool)
    async def setAutoIris(self, value: bool):
        """Set auto iris mode

        See :meth:`jvconnected.device.ExposureParams.set_auto_iris`
        """
        await self.paramGroup.set_auto_iris(value)

    @asyncSlot(int)
    async def setPos(self, value: int):
        """Set the iris position

        See :meth:`jvconnected.device.ExposureParams.set_iris_pos`
        """
        # logger.debug(f'setPos({value})')
        if self.requestedPos != -1:
            self.requestedPos = value
            return
        self.requestedPos = value

        async with self._request_pending:
            logger.debug('LOCKED')
            req_value = self.requestedPos
            await self.paramGroup.set_iris_pos(req_value)
            # await self._run_on_device_loop(self.paramGroup.set_iris_pos(req_value))
            logger.debug(f'set_iris_pos({req_value})')
            while req_value != self.requestedPos:
                req_value = self.requestedPos
                await self.paramGroup.set_iris_pos(req_value)
                # await self._run_on_device_loop(self.paramGroup.set_iris_pos(req_value))
                logger.debug(f'set_iris_pos({req_value})')
            self.requestedPos = -1
        logger.debug('UNLOCKED')


    @asyncSlot()
    async def increase(self):
        """Calls :meth:`jvconnected.device.ExposureParams.increase_iris`
        """
        if self._request_pending.locked():
            return
        async with self._request_pending:
            await self.paramGroup.increase_iris()
            # await self._run_on_device_loop(self.paramGroup.increase_iris())

    @asyncSlot()
    async def decrease(self):
        """Calls :meth:`jvconnected.device.ExposureParams.increase_iris`
        """
        if self._request_pending.locked():
            return
        async with self._request_pending:
            await self.paramGroup.decrease_iris()
            # await self._run_on_device_loop(self.paramGroup.decrease_iris())

class SingleParam(ParamBase):
    """A direct mapping to a single parameter within a
    :class:`~jvconnected.device.ParameterGroup`
    """
    _param_group_attr = None
    _n_value = Signal()
    def __init__(self, *args):
        assert self._param_group_attr is not None
        self._prop_attr_map = {self._param_group_attr:'value'}
        self._value = None
        super().__init__(*args)

    def _g_value(self) -> str: return str(self._value)
    def _s_value(self, value: str): self._generic_setter('_value', value)
    value: str = Property(str, _g_value, _s_value, notify=_n_value)
    """The parameter value"""

class SingleAdjustableParam(SingleParam):
    """A single parameter with increment/decrement methods
    """
    def __init__(self, *args):
        self._request_pending = asyncio.Lock()
        super().__init__(*args)

    @asyncSlot()
    async def increase(self):
        """Increment the parameter value
        """
        if self._request_pending.locked():
            return
        async with self._request_pending:
            await self._increase()
            # await self._run_on_device_loop(self._increase())

    @asyncSlot()
    async def decrease(self):
        """Decrement the parameter value
        """
        if self._request_pending.locked():
            return
        async with self._request_pending:
            await self._decrease()
            # await self._run_on_device_loop(self._decrease())

    async def _increase(self):
        raise NotImplementedError

    async def _decrease(self):
        raise NotImplementedError

class GainModeModel(SingleParam):
    _param_group_key = 'exposure'
    _param_group_attr = 'gain_mode'

class GainValueModel(SingleAdjustableParam):
    _param_group_key = 'exposure'
    _param_group_attr = 'gain_value'

    async def _increase(self):
        await self.paramGroup.increase_gain()

    async def _decrease(self):
        await self.paramGroup.decrease_gain()

class MasterBlackModel(SingleAdjustableParam):
    _param_group_key = 'exposure'
    _param_group_attr = 'master_black'

    async def _increase(self):
        await self.paramGroup.increase_master_black()

    async def _decrease(self):
        await self.paramGroup.decrease_master_black()

class FocusModeModel(SingleParam):
    _param_group_key = 'lens'
    _param_group_attr = 'focus_mode'

    @asyncSlot(str)
    async def setMode(self, mode: str):
        await self.paramGroup.set_focus_mode(mode)

class SeesawParam(SingleParam):
    """Base parameter for "seesaw" movement
    """
    _n_currentSpeed = Signal()
    _n_moving = Signal()
    def __init__(self, *args):
        self._request_pending = asyncio.Lock()
        self._currentSpeed = 0
        self._moving = False
        super().__init__(*args)

    def _g_currentSpeed(self) -> int: return self._currentSpeed
    def _s_currentSpeed(self, value: int):
        self._generic_setter('_currentSpeed', value)
        moving = value != 0
        if moving != self._moving:
            self.moving = moving
    currentSpeed: int = Property(int,
        _g_currentSpeed, _s_currentSpeed, notify=_n_currentSpeed,
    )
    """Current speed of movement from -8 to 8
    """

    def _g_moving(self) -> bool: return self._moving
    def _s_moving(self, value: bool):
        logger.debug(f'{self.moving=}, {value=}')
        self._generic_setter('_moving', value)
        if not value:
            if self._currentSpeed != 0:
                self.currentSpeed = 0
    moving: bool = Property(bool, _g_moving, _s_moving, notify=_n_moving)
    """True if the parameter is moving
    """

class MasterBlackPosModel(SeesawParam):
    """MasterBlack seesaw operation
    """

    _param_group_key = 'exposure'
    _param_group_attr = 'master_black'

    @asyncSlot(int)
    async def up(self, speed: int):
        """Move MasterBlack up at the specified speed (0 to 8)
        """
        await self.move('Up', speed)

    @asyncSlot(int)
    async def down(self, speed: int):
        """Move MasterBlack down at the specified speed (0 to 8)
        """
        await self.move('Down', speed)

    @asyncSlot()
    async def stop(self):
        """Stop moving
        """
        await self.move('Stop', 0)

    @logger.catch
    async def move(self, direction: MasterBlackDirection, speed: int):
        async with self._request_pending:
            await self.paramGroup.seesaw_master_black(direction, speed)

    def _on_param_group_set(self, param_group):
        super()._on_param_group_set(param_group)
        param_group.bind(master_black_speed=self._on_master_black_speed)

    def _on_master_black_speed(self, instance, value, **kwargs):
        if instance is not self.paramGroup:
            return
        self.currentSpeed = value


class FocusPosModel(SeesawParam):
    """Focus position and movement
    """
    _param_group_key = 'lens'
    _param_group_attr = 'focus_value'

    @asyncSlot()
    async def pushAuto(self):
        await self.paramGroup.focus_push_auto()

    @asyncSlot(int)
    async def near(self, speed: int):
        """Focus "near" at the specified speed (0 to 8)
        """
        await self.move(FocusDirection.Near, speed)

    @asyncSlot(int)
    async def far(self, speed: int):
        """Focus "far" at the specified speed (0 to 8)
        """
        await self.move(FocusDirection.Far, speed)

    @asyncSlot()
    async def stop(self):
        """Stop moving
        """
        await self.move(FocusDirection.Stop, 0)

    async def move(self, direction: FocusDirection, speed: int):
        async with self._request_pending:
            await self.paramGroup.seesaw_focus(direction, speed)

    def _on_param_group_set(self, param_group):
        super()._on_param_group_set(param_group)
        param_group.bind(focus_speed=self._on_focus_speed)

    def _on_focus_speed(self, instance, value, **kwargs):
        if instance is not self.paramGroup:
            return
        self.currentSpeed = value


class ZoomPresetModel(GenericQObject):
    """Qt bridge for :class:`jvconnected.device.ZoomPreset`
    """
    _n_name = Signal()
    _n_value = Signal()
    _n_isActive = Signal()
    def __init__(self, *args, **kwargs):
        self._name = kwargs.get('name', '')
        self._value = kwargs.get('value', -1)
        self._isActive = kwargs.get('isActive', False)
        super().__init__(*args)

    def _bind_to_preset(self, preset: 'jvconnected.device.ZoomPreset'):
        assert self.name == preset.name
        self.value = preset.value
        self.isActive = preset.is_active
        preset.bind(value=self._on_preset_value, is_active=self._on_preset_active)

    def _g_name(self) -> str: return self._name
    def _s_name(self, value: str): self._generic_setter('_name', value)
    name: str = Property(str, _g_name, _s_name, notify=_n_name)
    """The preset name (or id)"""

    def _g_value(self) -> int: return self._value
    def _s_value(self, value: int): self._generic_setter('_value', value)
    value: int = Property(int, _g_value, _s_value, notify=_n_value)
    """Stored zoom position of the preset"""

    def _g_isActive(self) -> bool: return self._isActive
    def _s_isActive(self, value: bool): self._generic_setter('_isActive', value)
    isActive: bool = Property(bool, _g_isActive, _s_isActive, notify=_n_isActive)
    """Flag indicating if the current zoom :attr:`~ZoomPosModel.pos`
    matches the stored :attr:`value`
    """

    def _on_preset_value(self, instance, value, **kwargs):
        self.value = value

    def _on_preset_active(self, instance, value, **kwargs):
        self.isActive = value


class ZoomPosModel(SeesawParam):
    """Zoom position and movement
    """
    _param_group_key = 'lens'
    _param_group_attr = 'zoom_value'
    _n_pos = Signal()
    _n_presets = Signal()

    def __init__(self, *args):
        self._pos = 0
        self._presets = []
        self._preset_map = {}
        super().__init__(*args)
        self.presets = [ZoomPresetModel(name=name) for name in 'ABC']
        self._preset_map = {p.name: p for p in self.presets}


    def _g_pos(self) -> int: return self._pos
    def _s_pos(self, value: int):
        self._generic_setter('_pos', value)
    pos: int = Property(int, _g_pos, _s_pos, notify=_n_pos)
    """Current zoom position from 0 to 499
    """

    def _g_presets(self) -> tp.List[ZoomPresetModel]: return self._presets
    def _s_presets(self, presets: tp.List[ZoomPresetModel]): self._generic_setter('_presets', presets)
    presets: tp.List[ZoomPresetModel] = Property('QVariantList', _g_presets, _s_presets, notify=_n_presets)
    """A list of :class:`ZoomPresetModel` instances"""

    @asyncSlot(int)
    async def tele(self, speed: int):
        """Zoom in (tele) at the specified speed (0 to 8)
        """
        await self.move(ZoomDirection.Tele, speed)

    @asyncSlot(int)
    async def wide(self, speed: int):
        """Zoom out (wide) at the specified speed (0 to 8)
        """
        await self.move(ZoomDirection.Wide, speed)

    @asyncSlot()
    async def stop(self):
        """Stop moving
        """
        await self.move(ZoomDirection.Stop, 0)

    async def move(self, direction: ZoomDirection, speed: int):
        async with self._request_pending:
            await self.paramGroup.seesaw_zoom(direction, speed)

    @asyncSlot(int)
    async def setPos(self, pos: int):
        """Set zoom position from 0 to 499
        """
        async with self._request_pending:
            if self.moving:
                await self.paramGroup.zoom_stop()
            await self.paramGroup.set_zoom_position(pos)

    @asyncSlot(str)
    async def setPreset(self, name: str):
        """Store the current zoom :attr:`pos` to a preset

        (See :meth:`jvconnected.device.PresetZoomParams.set_preset`)

        Arguments:
            name: The preset name (one of ``["A", "B", "C"]``)
        """
        pos = self.pos
        device = self.paramGroup.device
        pg = device.preset_zoom
        await pg.set_preset(name, pos)

    @asyncSlot(str)
    async def recallPreset(self, name: str):
        """Recall the zoom preset matching the given :attr:`~ZoomPresetModel.name`

        (See :meth:`jvconnected.device.PresetZoomParams.recall_preset`)
        """
        device = self.paramGroup.device
        pg = device.preset_zoom
        await pg.recall_preset(name)

    @asyncSlot(str)
    async def clearPreset(self, name: str):
        """Clear the stored value of the preset by the given
        :attr:`~ZoomPresetModel.name`

        (See :meth:`jvconnected.device.PresetZoomParams.clear_preset`)
        """
        device = self.paramGroup.device
        pg = device.preset_zoom
        await pg.clear_preset(name)

    def _on_param_group_set(self, param_group):
        super()._on_param_group_set(param_group)
        self.pos = param_group.zoom_pos
        param_group.bind(
            zoom_speed=self._on_zoom_speed,
            zoom_pos=self._on_zoom_pos,
        )
        preset_group = param_group.device.preset_zoom
        for preset in self.presets:
            preset._bind_to_preset(preset_group.presets[preset.name])

    def _on_zoom_speed(self, instance, value, **kwargs):
        if instance is not self.paramGroup:
            return
        self.currentSpeed = value

    def _on_zoom_pos(self, instance, value, **kwargs):
        if instance is not self.paramGroup:
            return
        self.pos = value


class WbModeModel(SingleParam):
    _param_group_key = 'paint'
    _param_group_attr = 'white_balance_mode'

    @asyncSlot(str)
    async def setMode(self, mode: str):
        await self.paramGroup.set_white_balance_mode(mode)

class WbColorTempModel(SingleParam):
    _param_group_key = 'paint'
    _param_group_attr = 'color_temp'

class WbPaintModelBase(ParamBase):
    _param_group_key = 'paint'
    _color_name = None
    _n_scale = Signal()
    _n_pos = Signal()
    _n_rawPos = Signal()
    _n_value = Signal()
    def __init__(self, *args):
        assert self._color_name is not None
        self._prop_attr_map = {
            f'{self._color_name}_scale':'scale',
            f'{self._color_name}_normalized':'pos',
            f'{self._color_name}_pos':'rawPos',
            f'{self._color_name}_value':'value',
        }
        self._scale = 0
        self._pos = 0
        self._rawPos = 32
        self._value = ''
        self._request_pending = asyncio.Lock()
        super().__init__(*args)

    def _g_scale(self) -> int: return self._scale
    def _s_scale(self, value: int): self._generic_setter('_scale', value)
    scale: int = Property(int, _g_scale, _s_scale, notify=_n_scale)
    """Total range of values for the parameter"""

    def _g_pos(self) -> int: return self._pos
    def _s_pos(self, value: int): self._generic_setter('_pos', value)
    pos: int = Property(int, _g_pos, _s_pos, notify=_n_pos)
    """The normalized position value (zero-centered)"""

    def _g_rawPos(self) -> int: return self._rawPos
    def _s_rawPos(self, value: int): self._generic_setter('_rawPos', value)
    rawPos: int = Property(int, _g_rawPos, _s_rawPos, notify=_n_rawPos)
    """Un-normalized position value"""

    def _g_value(self) -> str: return self._value
    def _s_value(self, value: str): self._generic_setter('_value', value)
    value: str = Property(str, _g_value, _s_value, notify=_n_value)
    """String representation of the value"""

    @asyncSlot(int)
    async def setPos(self, value: int):
        """Set the position value

        See :meth:`setRedPos` and :meth:`setBluePos`
        """
        # if self._request_pending.locked():
        #     return
        # async with self._request_pending:
        #     # logger.debug(f'setPos: {self._color_name}({value})')
        if self._color_name == 'red':
            # await self.paramGroup.set_red_pos(value)
            await self.setRedPos(value)
        else:
            # await self.paramGroup.set_blue_pos(value)
            await self.setBluePos(value)

    @asyncSlot(int)
    async def setRedPos(self, value: int):
        """Set the red white balance position

        See :meth:`jvconnected.device.PaintParams.set_red_pos`
        """
        if self._request_pending.locked():
            return
        async with self._request_pending:
            # logger.debug(f'setRedPos({value})')
            if self._color_name == 'red':
                self._set_temp_values(value)
            await self.paramGroup.set_red_pos(value)
            # await self._run_on_device_loop(self.paramGroup.set_red_pos(value))

    @asyncSlot(int)
    async def setBluePos(self, value):
        """Set the red white balance position

        See :meth:`jvconnected.device.PaintParams.set_blue_pos`
        """
        if self._request_pending.locked():
            return
        async with self._request_pending:
            # logger.debug(f'setBluePos({value})')
            if self._color_name == 'blue':
                self._set_temp_values(value)
            await self.paramGroup.set_blue_pos(value)
            # await self._run_on_device_loop(self.paramGroup.set_blue_pos(value))

    @asyncSlot(int, int)
    async def setRBPos(self, red: int, blue: int):
        """Set both red and blue position values

        See :meth:`jvconnected.device.PaintParams.set_wb_pos`
        """
        if self._request_pending.locked():
            return
        async with self._request_pending:
            if self._color_name == 'red':
                tmp = red
            else:
                tmp = blue
            self._set_temp_values(tmp - self.scale // 2)
            await self.paramGroup.set_wb_pos(red, blue)
            # await self._run_on_device_loop(self.paramGroup.set_wb_pos(red, blue))

    @asyncSlot(int, int)
    async def setRBPosRaw(self, red: int, blue: int):
        """Set both red and blue position values un-normalized

        See :meth:`jvconnected.device.PaintParams.set_wb_pos_raw`
        """
        if self._request_pending.locked():
            return
        async with self._request_pending:
            if self._color_name == 'red':
                tmp = red
            else:
                tmp = blue
            self._set_temp_values(tmp - self.scale // 2)
            await self.paramGroup.set_wb_pos_raw(red, blue)
            # await self._run_on_device_loop(self.paramGroup.set_wb_pos_raw(red, blue))

    def _set_temp_values(self, pos: int):
        self.pos = pos
        self.value = f'{pos:+3d}'
        self.rawPos = pos + self.scale // 2

    def _on_prop_set(self, instance, value, **kwargs):
        prop = kwargs['property']
        logger.debug(f'{self.__class__.__name__}.{prop.name} = {value} ({type(value)})')
        super()._on_prop_set(instance, value, **kwargs)

class WbRedPaintModel(WbPaintModelBase):
    """Red paint parameter
    """
    _color_name = 'red'

class WbBluePaintModel(WbPaintModelBase):
    """Blue paint parameter
    """
    _color_name = 'blue'

class DetailModel(SingleAdjustableParam):
    _param_group_key = 'paint'
    _param_group_attr = 'detail'

    async def _increase(self):
        await self.paramGroup.increase_detail()

    async def _decrease(self):
        await self.paramGroup.decrease_detail()

class TallyModel(ParamBase):
    _param_group_key = 'tally'
    _prop_attr_map = {
        'program':'program',
        'preview':'preview',
    }
    _n_program = Signal()
    _n_preview = Signal()
    def __init__(self, *args):
        self._program = False
        self._preview = False
        super().__init__(*args)

    def _g_program(self) -> bool: return self._program
    def _s_program(self, value: bool): self._generic_setter('_program', value)
    program: bool = Property(bool, _g_program, _s_program, notify=_n_program)
    """Alias for :attr:`jvconnected.device.TallyParams.program`"""

    def _g_preview(self) -> bool: return self._preview
    def _s_preview(self, value: bool): self._generic_setter('_preview', value)
    preview: bool = Property(bool, _g_preview, _s_preview, notify=_n_preview)
    """Alias for :attr:`jvconnected.device.TallyParams.preview`"""

    @asyncSlot(bool)
    async def setProgram(self, state: bool):
        """Set the program tally state

        See :meth:`jvconnected.device.TallyParams.set_program`
        """
        await self.paramGroup.set_program(state)
        # await self._run_on_device_loop(self.paramGroup.set_program(state))

    @asyncSlot(bool)
    async def setPreview(self, state):
        """Set the program tally state

        See :meth:`jvconnected.device.TallyParams.set_preview`
        """
        await self.paramGroup.set_preview(state)
        # await self._run_on_device_loop(self.paramGroup.set_preview(state))


MODEL_CLASSES = (
    DeviceConfigModel, DeviceModel, NTPParamsModel, CameraParamsModel, IrisModel, BatteryParamsModel,
    GainModeModel, GainValueModel, MasterBlackModel, DetailModel, TallyModel,
    MasterBlackPosModel, FocusModeModel, FocusPosModel, ZoomPosModel,
    WbModeModel, WbColorTempModel, WbPaintModelBase, WbRedPaintModel, WbBluePaintModel,
)

def register_qml_types():
    for cls in MODEL_CLASSES:
        QtQml.qmlRegisterType(cls, 'DeviceModels', 1, 0, cls.__name__)
