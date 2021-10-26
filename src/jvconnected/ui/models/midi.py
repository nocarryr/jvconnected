from loguru import logger
import asyncio
from typing import Optional, ClassVar, Dict, Sequence

from PySide2 import QtCore, QtQml
from PySide2.QtCore import Qt, Property, Signal, Slot

from qasync import QEventLoop, asyncSlot, asyncClose

from jvconnected.utils import IOType
from jvconnected.interfaces.midi import MIDI_AVAILABLE
from jvconnected.ui.utils import GenericQObject
from jvconnected.ui.models.engine import EngineModel

class MidiPortModel(GenericQObject):
    """Qt Bridge to :class:`jvconnected.interfaces.midi.BasePort`

    Attributes:
        parent_model: The parent :class:`MidiPortsModel` container

    """
    _n_name = Signal()
    _n_index = Signal()
    _n_isActive = Signal()
    def __init__(self, *args, **kwargs):
        self._name = kwargs['name']
        self._index = kwargs['index']
        self._isActive = kwargs.get('isActive', False)
        self.parent_model = kwargs['parent_model']
        self.midi_io = self.parent_model.midi_io
        super().__init__(*args)

    def _g_name(self) -> str: return self._name
    def _s_name(self, value: str): self._generic_setter('_name', value)
    name = Property(str, _g_name, _s_name, notify=_n_name)
    """The port name"""

    def _g_index(self) -> int: return self._index
    def _s_index(self, value: int): self._generic_setter('_index', value)
    index = Property(int, _g_index, _s_index, notify=_n_index)
    """The port index"""

    def _g_isActive(self) -> bool: return self._isActive
    def _s_isActive(self, value: bool): self._generic_setter('_isActive', value)
    isActive = Property(bool, _g_isActive, _s_isActive, notify=_n_isActive)
    """Current state of the port"""

    @asyncSlot(bool)
    async def setIsActive(self, value: bool):
        """Set the port state
        """
        assert value is not self.isActive
        await self.parent_model.setPortActive(self.name, value)

    def __repr__(self):
        return f'<{self.__class__.__name__}: "{self}" (isActive={self.isActive})>'

    def __str__(self):
        return self.name

class MidiPortsModel(GenericQObject):
    """Base container for :class:`MidiPortModel` instances

    :Signals:
        .. event:: portAdded(port: MidiPortModel)

            Fired when a new port is added

        .. event:: portRemoved(port: MidiPortModel)

            Fired when an existing port is removed

        .. event:: portsUpdated()

            Fired when any change is made in the container
    """
    _n_engine = Signal()
    _n_count = Signal()
    portAdded = Signal(MidiPortModel)
    portRemoved = Signal(MidiPortModel)
    portsUpdated = Signal()
    io_type: ClassVar[IOType] = IOType.NONE
    def __init__(self, *args):
        self.loop = asyncio.get_event_loop()
        self.ports = {}
        self._engine = None
        self.midi_io = None
        super().__init__(*args)

    def _g_engine(self) -> Optional[EngineModel]:
        return self._engine
    def _s_engine(self, value: EngineModel):
        if value is None or value == self._engine:
            return
        assert self._engine is None
        self._engine = value
        if MIDI_AVAILABLE:
            self.set_midi_io(value.engine.midi_io)
    engine = Property(EngineModel, _g_engine, _s_engine, notify=_n_engine)
    """The :class:`~jvconnected.ui.models.engine.EngineModel` in use"""

    def _g_count(self) -> int: return len(self.ports)
    count = Property(int, _g_count, notify=_n_count)
    """Number of ports"""

    def set_midi_io(self, midi_io: 'jvconnected.interfaces.midi_io.MidiIO'):
        self.midi_io = midi_io
        self.update_ports()
        midi_io.bind(port_state=self.on_midi_io_port_state)

    def _get_all_port_names(self):
        raise NotImplementedError

    def _get_enabled_port_names(self):
        raise NotImplementedError

    def _get_enabled_ports_dict(self):
        raise NotImplementedError

    async def _set_port_active(self, name: str, state: bool):
        raise NotImplementedError

    @logger.catch
    def update_ports(self):
        midi_io = self.midi_io
        port_names_list = self._get_enabled_port_names()
        all_ports = self._get_all_port_names()
        changed = False
        count = len(self.ports)

        removed = set(self.ports.keys()) - set(all_ports)
        if len(removed):
            changed = True
        for name in removed:
            port = self.ports[name]
            del self.ports[name]
            self._n_count.emit()
            self.portRemoved.emit(port)

        for i, name in enumerate(all_ports):
            port = self.ports.get(name)
            active = name in port_names_list
            if port is not None:
                if port.index < i and port.name == all_ports[port.index]:
                    continue
                port_index = port.index
                assert port_index == i == port.index
                if port.isActive != active:
                    changed = True
                    port.isActive = active
            else:
                changed = True
                port = MidiPortModel(name=name, index=i, isActive=active, parent_model=self)
                self.ports[name] = port
                self._n_count.emit()
                self.portAdded.emit(port)

        if changed:
            self.portsUpdated.emit()

    @logger.catch
    def on_midi_io_port_state(self, io_type: IOType, name: str, state: bool, **kwargs):
        if io_type != self.io_type:
            return
        assert name in self.ports
        port = self.ports[name]
        if state is not port.isActive:
            port.isActive = state
            self.portsUpdated.emit()
        logger.debug(f'{self}.port_state: io_type={io_type}, name={name}, state={state}, port = {port!r}')

    @asyncSlot(str, bool)
    async def setPortActive(self, name: str, value: bool):
        """Enable or disable the port with the given name
        """
        await self._set_port_active(name, value)

    @QtCore.Slot(str, result=MidiPortModel)
    def getByName(self, name: str) -> MidiPortModel:
        """Lookup a :class:`port <MidiPortModel>` by :attr:`~MidiPortModel.name`
        """
        return self.ports[name]

    @QtCore.Slot(int, result=MidiPortModel)
    def getByIndex(self, ix: int) -> MidiPortModel:
        """Lookup a :class:`port <MidiPortModel>` by :attr:`~MidiPortModel.index`
        """
        d = {p.index for p in self.ports.values()}
        return d[ix]

class InportsModel(MidiPortsModel):
    """Container for input ports as :class:`MidiPortModel` instances
    """
    io_type: ClassVar[IOType] = IOType.INPUT

    def _get_all_port_names(self):
        return self.midi_io.get_available_inputs()

    def _get_enabled_port_names(self):
        return self.midi_io.inport_names

    def _get_enabled_ports_dict(self):
        return self.midi_io.inports

    async def _set_port_active(self, name: str, state: bool):
        if state:
            await self.midi_io.add_input(name)
        else:
            await self.midi_io.remove_input(name)

class OutportsModel(MidiPortsModel):
    """Container for input ports as :class:`MidiPortModel` instances
    """
    io_type: ClassVar[IOType] = IOType.OUTPUT

    def _get_all_port_names(self):
        return self.midi_io.get_available_outputs()

    def _get_enabled_port_names(self):
        return self.midi_io.outport_names

    def _get_enabled_ports_dict(self):
        return self.midi_io.outports

    async def _set_port_active(self, name: str, state: bool):
        if state:
            await self.midi_io.add_output(name)
        else:
            await self.midi_io.remove_output(name)

class DeviceMapModel(GenericQObject):
    """Representation of a single device/channel map within :class:`DeviceMapsModel`
    """
    _n_deviceId = Signal()
    _n_channel = Signal()
    _n_deviceIndex = Signal()
    _n_deviceName = Signal()
    _n_isMapped = Signal()
    _n_isActive = Signal()
    _n_isOnline = Signal()
    _n_edited = Signal()
    dataChanged = Signal(str, str)
    """Emitted on property changes

    :param str deviceId: The :attr:`deviceId` of the instance emitting the signal
    :param str attr: The property name that changed
    """

    midi_io: 'jvconnected.interfaces.midi.midi_io.MidiIO'
    """The active :class:`~jvconnected.interfaces.midi.midi_io.MidiIO` instance
    """

    conf_device: 'jvconnected.config.DeviceConfig'

    def __init__(self, *args, **kwargs):
        self.midi_io = kwargs['midi_io']
        self._deviceId = kwargs['deviceId']
        self.conf_device = kwargs['conf_device']
        self._deviceIndex = self.conf_device.device_index
        self._deviceName = self.conf_device.display_name
        channel = self.midi_io.device_channel_map.get(self._deviceId, -1)
        self._isMapped = channel is not None
        self._isOnline = self._deviceId in self.midi_io.mapped_devices
        self._channel = channel
        self._edited = False
        super().__init__(*args)
        self.midi_io.bind(
            device_channel_map=self.on_midi_io_device_channel_map,
            mapped_devices=self.on_midi_io_mapped_devices,
        )
        self.conf_device.bind(
            device_index=self.on_conf_device_index,
            display_name=self.on_conf_device_name,
        )

    def _g_deviceId(self) -> str: return self._deviceId
    def _s_deviceId(self, value: str): self._generic_setter('_deviceId', value)
    deviceId: str = Property(str, _g_deviceId, _s_deviceId, notify=_n_deviceId)
    """The :attr:`device_id <jvconnected.config.DeviceConfig.id>` associated
    with this instance
    """

    def _g_deviceName(self) -> str: return self._deviceName
    def _s_deviceName(self, value: str):
        changed = self._deviceName != value
        if changed:
            self._deviceName = value
            self._emit_change('deviceName')
    deviceName: str = Property(str, _g_deviceName, _s_deviceName, notify=_n_deviceName)
    """The :attr:`display_name <jvconnected.config.DeviceConfig.display_name>`
    of the device
    """

    def _g_isMapped(self) -> bool: return self._isMapped
    def _s_isMapped(self, value: bool):
        changed = self._isMapped != value
        if changed:
            self._isMapped = value
            self._emit_change('isMapped')
    isMapped: bool = Property(bool, _g_isMapped, _s_isMapped, notify=_n_isMapped)
    """True if the device is mapped to a Midi channel
    """

    def _g_isOnline(self) -> bool: return self._isOnline
    def _s_isOnline(self, value: bool):
        changed = value != self._isOnline
        if changed:
            self._isOnline = value
            self._emit_change('isOnline')
    isOnline: bool = Property(bool, _g_isOnline, _s_isOnline, notify=_n_isOnline)
    """True if the device is currently online
    """

    def _g_channel(self) -> int: return self._channel
    def _s_channel(self, value: int):
        changed = value != self._channel
        if changed:
            self._channel = value
            self._emit_change('channel')
        self.isMapped = value >= 0
        self.edited = value != self.get_current_channel()
    channel: int = Property(int, _g_channel, _s_channel, notify=_n_channel)
    """If :attr:`edited` is True, the midi channel to assign to the device.
    Otherwise the channel currently assigned

    Allowed values are from 0 to 15 and ``-1`` is used to indicate no assignment
    (where :attr:`isMapped` is False)
    """

    def _g_deviceIndex(self) -> int: return self._deviceIndex
    def _s_deviceIndex(self, value: int):
        changed = value != self._deviceIndex
        if changed:
            self._deviceIndex = value
            self._emit_change('deviceIndex')
    deviceIndex: int = Property(int, _g_deviceIndex, _s_deviceIndex, notify=_n_deviceIndex)
    """The :attr:`~jvconnected.config.DeviceConfig.device_index`
    """

    def _g_edited(self) -> bool: return self._edited
    def _s_edited(self, value: bool):
        changed = value != self._edited
        if changed:
            self._edited = value
            self._emit_change('edited')
    edited: bool = Property(bool, _g_edited, _s_edited, notify=_n_edited)
    """True if the :attr:`channel` has been edited by the user
    """

    @Slot()
    def reset(self):
        """Reset the :attr:`channel` to its original value
        """
        self.channel = self.get_current_channel()

    def _emit_change(self, attr: str):
        notify_sig = getattr(self, f'_n_{attr}')
        notify_sig.emit()
        self.dataChanged.emit(self.deviceId, attr)

    def get_current_channel(self) -> int:
        """Get the midi channel currently assigned within :attr:`midi_io`.
        ``-1`` is returned if there is not assigned channel
        """
        d = self.midi_io.device_channel_map
        return d.get(self._deviceId, -1)

    def on_midi_io_device_channel_map(self, instance, value, **kwargs):
        if self.edited:
            return
        self._update_channel()

    def _update_channel(self):
        channel = self.midi_io.device_channel_map.get(self._deviceId, -1)
        self.edited = channel != self._channel
        self.channel = channel

    def on_midi_io_mapped_devices(self, instance, value, **kwargs):
        self.isOnline = self._deviceId in value

    def on_conf_device_index(self, instance, value, **kwargs):
        if value is None:
            return
        self.deviceIndex = value

    def on_conf_device_name(self, instance, value, **kwargs):
        self.deviceName = value

    def __repr__(self):
        return f'<{self.__class__.__name__}: "{self}">'

    def __str__(self):
        return self.deviceId

class SortFilterProxyModel(QtCore.QSortFilterProxyModel):
    """Sortable proxy model for :class:`DeviceMapsModel`
    """
    @Slot(int, int)
    def setSorting(self, column: int, order: int):
        self.sort(column, order)

class DeviceMapsModel(QtCore.QAbstractTableModel):
    """A table model used to interface with :class:`~jvconnected.interfaces.midi.MidiIO`
    device mapping

    :class:`DeviceMapsModel` instances are created for each device within
    :attr:`jvconnected.config.Config.devices` and their :attr:`~DeviceMapsModel.channel`
    values are read from :attr:`MidiIO <MidiIO.device_channel_map>`.

    Changes to the channel assignments are stored temporarily until
    :meth:`applied <apply>` or :meth:`reset <reset>`
    """
    _n_engine = Signal()
    _n_proxyModel = Signal()
    _n_sortColumn = Signal()
    role_attrs: ClassVar[Sequence[str]] = [
        'deviceId', 'deviceIndex', 'deviceName',
        'channel', 'isOnline', 'isMapped', 'edited',
    ]
    """:class:`DeviceMapModel` property names used to populate the table columns
    """

    midi_io: 'jvconnected.interfaces.midi.midi_io.MidiIO'
    """The :class:`~jvconnected.interfaces.midi.midi_io.MidiIO` instance within the
    :attr:`engine`
    """

    role_names: Dict[Qt.ItemDataRole, bytes]
    """Qt.UserRoles mapped to each property defined in :attr:`role_attrs`

    This is convoluted, weird, cumbersome and many other adjectives, but it seems
    to be the only way to make QAbstractTableModel act like a table. No clue
    why "roles" are necessary to access columns since that's all a table
    is supposed to be ``¯\_(ツ)_/¯``
    """

    def __init__(self, *args):
        self.map_indices = []
        self.map_objs = {}
        self._sort_role = Qt.UserRole
        roles = [Qt.UserRole+i+1 for i in range(len(self.role_attrs))]
        self.role_names = {role:attr.encode() for role, attr in zip(roles, self.role_attrs)}
        self.role_names[self._sort_role] = b'__sort_role__'
        self._engine = None
        self.midi_io = None
        self._proxyModel = None
        self._sortColumn = 0
        super().__init__(*args)
        self.proxyModel = QtCore.QSortFilterProxyModel()
        self.proxyModel.setSourceModel(self)
        self.proxyModel.setSortRole(self._sort_role)

    def _g_engine(self) -> Optional[EngineModel]:
        return self._engine
    def _s_engine(self, value: EngineModel):
        if value is None or value == self._engine:
            return
        assert self._engine is None
        self._engine = value
        midi_io = value.engine.interfaces.get('midi')
        if midi_io is not None:
            self.set_midi_io(midi_io)
    engine = Property(EngineModel, _g_engine, _s_engine, notify=_n_engine)
    """The :class:`~jvconnected.ui.models.engine.EngineModel` in use"""

    def _g_proxyModel(self): return self._proxyModel
    def _s_proxyModel(self, value):
        if value is self._proxyModel:
            return
        self._proxyModel = value
        self._n_proxyModel.emit()
    proxyModel: SortFilterProxyModel = Property(
        QtCore.QAbstractItemModel,
        _g_proxyModel, _s_proxyModel, notify=_n_proxyModel,
    )
    """An attached :class:`SortFilterProxyModel` instance
    """

    def _g_sortColumn(self) -> int: return self._sortColumn
    def _s_sortColumn(self, value: int):
        if value == self._sortColumn:
            return
        self._sortColumn = value
        self._n_sortColumn.emit()
    sortColumn: int = Property(int, _g_sortColumn, _s_sortColumn, notify=_n_sortColumn)
    """The current sort column (index of the current :attr:`role_name <role_names>`)
    """

    @Slot(str, Qt.SortOrder)
    def setSorting(self, role_name: str, order: Qt.SortOrder):
        """Sort the :attr:`proxyModel` by the given :attr:`role_name <role_names>`
        """
        column = self.role_attrs.index(role_name)
        self.sortColumn = column
        self.proxyModel.sort(column, order)

    @Slot(str, result=int)
    def incrementChannel(self, device_id: str) -> int:
        """Increment the :attr:`~DeviceMapModel.channel` for the given device_id
        by at least one.

        Existing channel mappings are skipped and if the channel number would be
        out of range, no changes are made.
        """
        map_obj = self.map_objs[device_id]
        channel = map_obj.channel + 1
        if channel > 15:
            return map_obj.channel
        channel = self._get_next_channel(device_id, channel, decrement=False)
        if channel == -1:
            return map_obj.channel
        map_obj.channel = channel
        return channel

    @Slot(str, result=int)
    def decrementChannel(self, device_id: str) -> int:
        """Decrease the :attr:`~DeviceMapModel.channel` for the given device_id
        by at least one.

        Existing channel mappings are skipped and if the channel number would be
        out of range, no changes are made.

        This only affects the temporary value in the model.
        """
        map_obj = self.map_objs[device_id]
        channel = map_obj.channel - 1
        if channel <= 0:
            return map_obj.channel
        channel = self._get_next_channel(device_id, channel, decrement=True)
        if channel == -1:
            return map_obj.channel
        map_obj.channel = channel
        return channel

    @Slot(str)
    def unassignChannel(self, device_id: str):
        """Unassign the channel for the given device

        This only affects the temporary value in the model.
        """
        map_obj = self.map_objs[device_id]
        map_obj.channel = -1

    @Slot(str)
    def resetChannel(self, device_id: str):
        """Reset the channel for the given device

        This only affects the temporary value in the model.
        """
        map_obj = self.map_objs[device_id]
        map_obj.reset()

    def _validate_channel(self, device_id: str, channel: int) -> bool:
        if channel == -1:
            return True
        for map_obj in self.map_objs.values():
            if map_obj.deviceId == device_id:
                continue
            if map_obj.channel == -1:
                continue
            elif map_obj.channel == channel:
                return False
        return True

    def _get_next_channel(self, device_id: str, channel: int, decrement: bool = False) -> int:
        all_channels = set(range(16))
        in_use = set([map_obj.channel for map_obj in self.map_objs.values() if map_obj.deviceId != device_id])
        in_use.discard(-1)
        available = all_channels - in_use
        if channel in available:
            return channel
        if decrement:
            available = set([i for i in available if i < channel])
            if not len(available):
                return -1
            return max(available)
        else:
            available = set([i for i in available if i > channel])
            if not len(available):
                return -1
            return min(available)

    @property
    def config(self):
        return self.engine.engine.config

    def set_midi_io(self, midi_io: 'jvconnected.interfaces.midi_io.MidiIO'):
        self.midi_io = midi_io
        self.update_maps()
        self.engine.engine.bind(on_config_device_added=self.update_maps)

    @asyncSlot(str)
    async def unmapDevice(self, device_id: str):
        await self.midi_io.unmap_device(device_id, unassign_channel=True)

    @asyncSlot(str, int)
    async def mapDevice(self, device_id: str, midi_channel: int):
        await self.midi_io.map_device(device_id, midi_channel=midi_channel)

    @asyncSlot(str, int)
    async def remapDevice(self, device_id: str, midi_channel: int):
        await self.midi_io.remap_device_channel(device_id, midi_channel=midi_channel)
        assert self.midi_io.device_channel_map[device_id] == midi_channel
        assert self.midi_io.channel_device_map[midi_channel] == device_id

    @asyncSlot()
    async def apply(self):
        """Apply any changes made to the :attr:`DeviceMapModel.channel` mappings

        Remaps the necessary device/channel mappings in :attr:`midi_io`
        """
        maps = {
            devId:map_obj.channel
                for devId,map_obj in self.map_objs.items() if map_obj.edited
        }
        if not len(maps):
            return
        logger.debug(f'remapping: {maps}')
        for device_id, channel in maps.items():
            await self.midi_io.unmap_device(device_id, unassign_channel=True)
            map_obj = self.map_objs[device_id]
            map_obj._update_channel()
            assert not map_obj.isMapped
        for device_id, channel in maps.items():
            if channel == -1:
                continue
            map_obj = self.map_objs[device_id]
            await self.midi_io.remap_device_channel(device_id, channel)
            assert map_obj.channel == channel
            assert not map_obj.edited

    @Slot()
    def reset(self):
        """Reset all edited channels back to their original states
        """
        for map_obj in self.map_objs.values():
            map_obj.reset()

    def _add_map(self, device_id: str):
        if device_id in self.map_objs:
            return
        conf_device = self.config.devices[device_id]
        insert_ix = len(self.map_indices)
        map_obj = DeviceMapModel(
            midi_io=self.midi_io,
            deviceId=device_id,
            conf_device=conf_device,
            # index=insert_ix,
        )
        self.map_objs[device_id] = map_obj
        self.beginInsertRows(QtCore.QModelIndex(), insert_ix, insert_ix)
        map_obj.dataChanged.connect(self.onMapObjDataChanged)
        self.map_indices.append(device_id)
        self.endInsertRows()

    def _remove_map(self, device_id: str):
        map_obj = self.map_objs[device_id]
        ix = self.map_indices.index(device_id)
        self.beginRemoveRows(QtCore.QModelIndex(), ix, ix)
        del self.map_objs[device_id]
        del self.map_indices[ix]
        self.endRemoveRows()

    def roleNames(self):
        return self.role_names

    def columnCount(self, parent):
        if parent.isValid():
            return 0
        return len(self.role_names)

    def rowCount(self, parent):
        return len(self.map_indices)

    def flags(self, index):
        return Qt.ItemFlags.ItemIsEnabled

    def data(self, index, role):
        if not index.isValid():
            return None
        row = index.row()
        col = index.column()
        device_id = self.map_indices[row]
        if False:#col > 0:
            attr = self.role_attrs[col]
        elif role == self._sort_role:
            attr = self.role_attrs[self.sortColumn]
        else:
            attr = self.role_names[role].decode('UTF-8')

        map_obj = self.map_objs[device_id]
        return getattr(map_obj, attr)

    def onMapObjDataChanged(self, deviceId: str, attr: str):
        if deviceId not in self.map_indices:
            return
        map_obj = self.map_objs[deviceId]
        value = getattr(map_obj, attr)
        # logger.debug(f'dataChanged: {deviceId=}, {attr=}, {value=}')
        attr_ix = self.role_attrs.index(attr)
        row_ix = self.map_indices.index(deviceId)
        ix = self.createIndex(row_ix, attr_ix)
        self.dataChanged.emit(ix, ix)

    def update_maps(self, *args, **kwargs):
        old_keys = set(self.map_indices)
        new_keys = set(self.config.devices.keys())

        added = new_keys - old_keys
        removed = old_keys - new_keys
        for device_id in removed:
            self._remove_map(device_id)
        for device_id in added:
            self._add_map(device_id)


MODEL_CLASSES = (
    MidiPortModel, InportsModel, OutportsModel,
    DeviceMapModel, DeviceMapsModel, SortFilterProxyModel,
)

def register_qml_types():
    for cls in MODEL_CLASSES:
        QtQml.qmlRegisterType(cls, 'MidiModels', 1, 0, cls.__name__)
