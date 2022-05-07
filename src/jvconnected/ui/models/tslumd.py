from loguru import logger
import asyncio
import enum
import dataclasses
from typing import Optional, List, Dict, Tuple, Set, Any
from bisect import bisect_left

from PySide2 import QtCore, QtQml, QtGui
from PySide2.QtCore import Property, Signal
from PySide2.QtCore import Qt

from qasync import QEventLoop, asyncSlot, asyncClose
from tslumd import Tally, TallyType, TallyColor, TallyKey

from jvconnected.ui.utils import GenericQObject
from jvconnected.ui.models.engine import EngineModel

from jvconnected.interfaces.tslumd import UmdIo
from jvconnected.interfaces.tslumd.mapper import DeviceMapping, TallyMap

class UmdModel(GenericQObject):
    """Qt bridge to :class:`jvconnected.interfaces.tslumd.umd_io.UmdIo`
    """
    _n_engine = Signal()
    _n_running = Signal()
    _n_hostaddr = Signal()
    _n_hostport = Signal()
    _n_editedProperties = Signal()
    _editable_properties = ('hostaddr', 'hostport')
    umd_io: UmdIo
    """:class:`~jvconnected.interfaces.tslumd.umd_io.UmdIo` instance"""

    def __init__(self, *args):
        self._engine = None
        self._running = False
        self._hostaddr = ''
        self._hostport = 0
        self._editedProperties = []
        self.umd_io = None
        self._updating_from_interface = False
        super().__init__(*args)

    def _g_engine(self) -> Optional[EngineModel]:
        return self._engine
    def _s_engine(self, value: EngineModel):
        if value is None or value == self._engine:
            return
        assert self._engine is None
        self._engine = value
        self.umd_io = value.engine.interfaces['tslumd']
        self.running = self.umd_io.running
        self.hostaddr = self.umd_io.hostaddr
        self.hostport = self.umd_io.hostport
        self.umd_io.bind(
            running=self.on_interface_running,
            hostaddr=self.on_interface_hostaddr,
            hostport=self.on_interface_hostport,
        )
    engine: EngineModel = Property(
        EngineModel, _g_engine, _s_engine, notify=_n_engine,
    )
    """The :class:`~jvconnected.ui.models.engine.EngineModel` in use"""

    def _g_running(self) -> bool: return self._running
    def _s_running(self, value: bool): self._generic_setter('_running', value)
    running: bool = Property(bool, _g_running, _s_running, notify=_n_running)
    """Alias for :class:`jvconnected.interfaces.tslumd.umd_io.UmdIo.running`"""

    def _g_hostaddr(self) -> str: return self._hostaddr
    def _s_hostaddr(self, value: str): self._generic_setter('_hostaddr', value)
    hostaddr: str = Property(str, _g_hostaddr, _s_hostaddr, notify=_n_hostaddr)
    """Alias for :class:`jvconnected.interfaces.tslumd.umd_io.UmdIo.hostaddr`"""

    def _g_hostport(self) -> int: return self._hostport
    def _s_hostport(self, value: int): self._generic_setter('_hostport', value)
    hostport: int = Property(int, _g_hostport, _s_hostport, notify=_n_hostport)
    """Alias for :class:`jvconnected.interfaces.tslumd.umd_io.UmdIo.hostport`"""

    def _g_editedProperties(self) -> List[str]: return self._editedProperties
    def _s_editedProperties(self, value: List[str]):
        self._generic_setter('_editedProperties', value)
    editedProperties: List[str] = Property('QVariantList',
        _g_editedProperties, _s_editedProperties, notify=_n_editedProperties,
    )
    """A list of attributes that have changed and are waiting to be set on the
    :attr:`umd_io`
    """

    @asyncSlot()
    async def sendValuesToInterface(self):
        """Update the :attr:`umd_io` values for any attributes currently in
        :attr:`editedProperties`.

        After all values are set, the :attr:`editedProperties` list is emptied.
        """
        self._updating_from_interface = True
        d = {attr:getattr(self, attr) for attr in self.editedProperties}
        if 'hostaddr' in d and 'hostport' in d:
            await self.umd_io.set_bind_address(d['hostaddr'], d['hostport'])
        elif 'hostaddr' in d:
            await self.umd_io.set_hostaddr(d['hostaddr'])
        elif 'hostport' in d:
            await self.umd_io.set_hostport(d['hostport'])
        self.editedProperties = []
        self._updating_from_interface = False

    @asyncSlot()
    async def getValuesFromInterface(self):
        """Get the current values from the :attr:`umd_io`

        Changes made to anything in :attr:`editedProperties` are overwritten
        and the list is cleared.
        """
        self._updating_from_interface = True
        for attr in self._editable_properties:
            val = getattr(self.umd_io, attr)
            setattr(self, attr, val)
        self.editedProperties = []
        self._updating_from_interface = False

    def _generic_setter(self, attr, value):
        super()._generic_setter(attr, value)
        attr = attr.lstrip('_')
        if attr == 'editedProperties':
            return
        props = set(self.editedProperties)
        if attr in self._editable_properties:
            if self._updating_from_interface or self.umd_io is None:
                return
            if attr in props:
                return
            if getattr(self.umd_io, attr) == value:
                props.discard(attr)
            else:
                props.add(attr)
        self.editedProperties = list(sorted(props))

    def on_interface_running(self, instance, value, **kwargs):
        self.running = value

    def on_interface_hostaddr(self, instance, value, **kwargs):
        if 'hostaddr' not in self.editedProperties:
            self.hostaddr = value

    def on_interface_hostport(self, instance, value, **kwargs):
        if 'hostport' not in self.editedProperties:
            self.hostport = value


class TallyRoles(enum.IntEnum):
    """Role definitions to specify column mapping in :class:`TallyListModel` to
    a ``QtQuick.TableView``
    """
    screenIndexRole = Qt.UserRole + 1   #: Screen index
    tallyIndexRole = Qt.UserRole + 2    #: Tally index
    RhTallyRole = Qt.UserRole + 3       #: rhTally
    TxtTallyRole = Qt.UserRole + 4      #: txtTally
    LhTallyRole = Qt.UserRole + 5       #: lhTally
    TextRole = int(Qt.DisplayRole)      #: text
    def get_tally_prop(self) -> str:
        """Get the attribute name of this role mapped to
        :class:`jvconnected.interfaces.tslumd.umd_io.Tally`
        """
        prop = self.name.split('Role')[0]
        if prop == 'screenIndex':
            return 'screen.index'
        elif prop == 'tallyIndex':
            return 'index'
        elif 'Tally' in prop:
            s = prop.split('Tally')[0].lower()
            return f'{s}_tally'
        return prop.lower()

    def get_tally_prop_value(self, tally: Tally) -> Any:
        """Get the value associated with this role from the given
        :class:`tslumd.tallyobj.Tally`
        """
        prop = self.get_tally_prop()
        if '.' in prop:
            obj = tally
            for attr in prop.split('.'):
                obj = getattr(obj, attr)
            return obj
        return getattr(tally, prop)

    def get_qt_prop(self) -> str:
        """Get the camel-case name of this role used in Qml
        """
        prop = self.name.split('Role')[0]
        if 'Index' in prop:
            return prop
        if 'Tally' in prop:
            s = prop.split('Tally')[0].lower()
            return f'{s}Tally'
        return prop.lower()

class TallyListModel(QtCore.QAbstractTableModel):
    """Table Model for :class:`jvconnected.interfaces.tslumd.umd_io.Tally` objects
    """
    _n_engine = Signal()
    _roles = tuple((role for role in TallyRoles))

    tally_key_indices: List[TallyKey]
    """Used to keep the table row in sync with the item key within :attr:`tallies`
    """

    umd_io: UmdIo
    """:class:`~jvconnected.interfaces.tslumd.umd_io.UmdIo` instance"""

    def __init__(self, *args, **kwargs):
        self._engine = None
        self.umd_io = None
        self._row_count = 0
        self.tally_key_indices = []
        super().__init__(*args)

    def _g_engine(self) -> Optional[EngineModel]:
        return self._engine
    def _s_engine(self, value: EngineModel):
        if value is None or value == self._engine:
            return
        assert self._engine is None
        self._engine = value
        self.umd_io = value.engine.interfaces['tslumd']
        self._init_interface()
    engine: EngineModel = Property(EngineModel, _g_engine, _s_engine, notify=_n_engine)
    """The :class:`~jvconnected.ui.models.engine.EngineModel` in use"""

    @property
    def tallies(self) -> Optional[Dict[TallyKey, Tally]]:
        """Shortcut for :attr:`~jvconnected.interfaces.tslumd.umd_io.UmdIo.tallies`
        on :attr:`umd_io`
        """
        if self.umd_io is None:
            return None
        return self.umd_io.tallies

    def _init_interface(self):
        for tally in self.umd_io.tallies.values():
            self.add_tally(tally)
        self.umd_io.bind(on_tally_added=self.add_tally)

    def add_tally(self, tally: Tally):
        insert_ix = bisect_left(self.tally_key_indices, tally.id)
        self.beginInsertRows(QtCore.QModelIndex(), insert_ix, insert_ix)
        self.tally_key_indices.insert(insert_ix, tally.id)
        self.endInsertRows()
        tally.bind(on_update=self.update_tally)

    def get_props_from_tally(self, tally: Tally, props_changed: Optional[Set[str]] = None) -> Dict[str, Any]:
        props = {}
        for i, role in enumerate(TallyRoles):
            prop = role.get_tally_prop()
            if props_changed is not None and prop in props_changed:
                continue
            val = role.get_tally_prop_value(tally)
            props[i] = val
        return props

    def update_tally(self, tally: Tally, props_changed: Set[str]):
        row_ix = self.tally_key_indices.index(tally.id)
        props = self.get_props_from_tally(tally, props_changed)
        tl = self.index(row_ix, min(props.keys()))
        br = self.index(row_ix, max(props.keys()))
        self.dataChanged.emit(tl, br)

    def roleNames(self):
        return {m:m.get_qt_prop().encode() for m in TallyRoles.__members__.values()}

    def columnCount(self, parent):
        return len(self._roles)

    def rowCount(self, parent):
        return len(self.tally_key_indices)

    def flags(self, index):
        return Qt.ItemFlags.ItemIsEnabled

    @QtCore.Slot(int, result='QVariantList')
    def getTallyKeyForRow(self, row: int) -> TallyKey:
        """Get the key within :attr:`tallies` for the given row
        """
        return self.tally_key_indices[row]

    @QtCore.Slot(int, result=str)
    def getTallyTypeForColumn(self, column: int) -> str:
        role = self._roles[column]
        return role.get_tally_prop()

    def data(self, index, role):
        if not index.isValid():
            return None
        key = self.tally_key_indices[index.row()]
        tallies = self.tallies
        if tallies is None:
            tally = None
        else:
            tally = tallies[key]

        if tally is None:
            return None
        role = TallyRoles(role)
        val = role.get_tally_prop_value(tally)
        if isinstance(val, TallyColor):
            val = val.name
            if val.lower() == 'amber':
                val = 'yellow'
        return val


class TallyMapListModel(QtCore.QAbstractTableModel):
    """Table Model for :class:`jvconnected.interfaces.tslumd.mapper.DeviceMapping`
    objects
    """
    _prop_attrs = (
        'device_index',
        'program.screen_index',
        'program.tally_index',
        'program.tally_type',
        'preview.screen_index',
        'preview.tally_index',
        'preview.tally_type',
    )

    _n_engine = Signal()
    umd_io: UmdIo
    """:class:`~jvconnected.interfaces.tslumd.umd_io.UmdIo` instance"""

    map_indices: List[int]
    """Used to keep the table row in sync with the item key within :attr:`maps`
    """

    def __init__(self, *args, **kwargs):
        self._engine = None
        self.umd_io = None
        self._row_count = 0
        self.map_indices = []
        self._role_names = {Qt.UserRole+i+6:attr.encode() for i, attr in enumerate(self._prop_attrs)}
        super().__init__(*args)

    def _g_engine(self) -> Optional[EngineModel]:
        return self._engine
    def _s_engine(self, value: EngineModel):
        if value is None or value == self._engine:
            return
        assert self._engine is None
        self._engine = value
        self.umd_io = value.engine.interfaces['tslumd']
        self._init_interface()
    engine: EngineModel = Property(EngineModel, _g_engine, _s_engine, notify=_n_engine)
    """The :class:`~jvconnected.ui.models.engine.EngineModel` in use"""

    @property
    def maps(self) -> Optional[Dict[int, DeviceMapping]]:
        """Shortcut for :attr:`~jvconnected.interfaces.tslumd.umd_io.UmdIo.device_maps`
        of the :attr:`umd_io`
        """
        if self.umd_io is None:
            return None
        return self.umd_io.device_maps

    @QtCore.Slot(int, result=int)
    def getIndexForRow(self, row: int) -> int:
        """Get the key within :attr:`maps` for the given row
        """
        return self.map_indices[row]

    def iter_maps(self):
        maps = self.maps
        if maps is None:
            yield from []
        else:
            for key in sorted(maps.keys()):
                yield key, maps[key]

    def _init_interface(self):
        for ix, dev_map in self.iter_maps():
            self.add_map(dev_map)
        self.umd_io.bind(device_maps=self.on_umd_io_device_maps)

    def add_map(self, dev_map: DeviceMapping):
        insert_ix = bisect_left(self.map_indices, dev_map.device_index)
        self.beginInsertRows(QtCore.QModelIndex(), insert_ix, insert_ix)
        self.map_indices.insert(insert_ix, dev_map.device_index)
        self.endInsertRows()

    def remove_map(self, device_index: int):
        ix = self.map_indices.index(device_index)
        self.beginRemoveRows(QtCore.QModelIndex(), ix, ix)
        del self.map_indices[ix]
        self.endRemoveRows()

    def on_umd_io_device_maps(self, instance, device_maps, **kwargs):
        new_keys = set(device_maps.keys())
        old_keys = set(self.map_indices)
        added = new_keys - old_keys
        removed = old_keys - new_keys
        for device_index in removed:
            self.remove_map(device_index)
        for device_index in added:
            self.add_map(device_maps[device_index])

    def roleNames(self):
        return self._role_names

    def columnCount(self, parent):
        return len(self._prop_attrs)

    def columnCount(self, parent):
        return len(self._prop_attrs)

    def rowCount(self, parent):
        return len(self.map_indices)

    def flags(self, index):
        return Qt.ItemFlags.ItemIsEnabled

    def data(self, index, role):
        if not index.isValid():
            return None
        ix = self.map_indices[index.row()]
        dev_map = self.maps[ix]
        attr = self._role_names[role].decode('UTF-8')
        if '.' in attr:
            tmap = getattr(dev_map, attr.split('.')[0])
            value = getattr(tmap, attr.split('.')[1])
            if isinstance(value, TallyType):
                value = value.name
            return str(value)
        else:
            return str(getattr(dev_map, attr))

    @asyncSlot(int)
    async def unMapByRow(self, row: int):
        """Remove a :class:`~jvconnected.interfaces.tslumd.mapper.DeviceMapping`
        from the :attr:`umd_io`.
        See :meth:`jvconnected.interfaces.tslumd.umd_io.UmdIo.remove_device_mapping`

        Arguments:
            row (int): The table row index
        """
        ix = self.map_indices[row]
        await self.umd_io.remove_device_mapping(ix)

class TallyMapBase(GenericQObject):
    _n_tallyKey = Signal()
    _n_screenIndex = Signal()
    _n_tallyIndex = Signal()
    _n_tallyType = Signal()
    def __init__(self, *args):
        self._screenIndex = -1
        self._tallyIndex = -1
        self._tallyType = ''
        super().__init__(*args)

    def _g_tallyKey(self) -> TallyKey:
        return [self.screenIndex, self.tallyIndex]
    def _s_tallyKey(self, value: TallyKey):
        scr, tly = value
        if scr != self.screenIndex:
            self.screenIndex = scr
        if tly != self.tallyIndex:
            self.tallyIndex = tly
    tallyKey: Tuple[int, int] = Property('QVariantList',
        _g_tallyKey, _s_tallyKey, notify=_n_tallyKey,
    )
    """Tuple of :attr:`screenIndex`, :attr:`tallyIndex` matching
    :attr:`jvconnected.interfaces.tslumd.mapper.TallyMap.tally_key`
    """

    def _g_screenIndex(self) -> int: return self._screenIndex
    def _s_screenIndex(self, value: int):
        changed = value == self._screenIndex
        self._generic_setter('_screenIndex', value)
        if changed:
            self._n_tallyKey.emit()
    screenIndex: int = Property(int, _g_screenIndex, _s_screenIndex, notify=_n_screenIndex)
    """Alias for :attr:`jvconnected.interfaces.tslumd.mapper.TallyMap.screen_index`"""

    def _g_tallyIndex(self) -> int: return self._tallyIndex
    def _s_tallyIndex(self, value: int):
        changed = value == self._tallyIndex
        self._generic_setter('_tallyIndex', value)
        if changed:
            self._n_tallyKey.emit()
    tallyIndex: int = Property(int, _g_tallyIndex, _s_tallyIndex, notify=_n_tallyIndex)
    """Alias for :attr:`jvconnected.interfaces.tslumd.mapper.TallyMap.tally_index`"""

    def _g_tallyType(self) -> str: return self._tallyType
    def _s_tallyType(self, value: str): self._generic_setter('_tallyType', value)
    tallyType: str = Property(str, _g_tallyType, _s_tallyType, notify=_n_tallyType)
    """Alias for :attr:`jvconnected.interfaces.tslumd.mapper.TallyMap.tally_type`
    """


class TallyMapModel(TallyMapBase):
    _n_deviceIndex = Signal()
    _n_destTallyType = Signal()
    def __init__(self, *args):
        self._deviceIndex = -1
        self._destTallyType = ''
        super().__init__(*args)

    def _g_deviceIndex(self) -> int: return self._deviceIndex
    def _s_deviceIndex(self, value: int): self._generic_setter('_deviceIndex', value)
    deviceIndex: int = Property(int, _g_deviceIndex, _s_deviceIndex, notify=_n_deviceIndex)
    """Alias for :attr:`jvconnected.interfaces.tslumd.mapper.DeviceMapping.device_index`"""

    def _g_destTallyType(self) -> str: return self._destTallyType
    def _s_destTallyType(self, value: str): self._generic_setter('_destTallyType', value)
    destTallyType: str = Property(str, _g_destTallyType, _s_destTallyType, notify=_n_destTallyType)
    """The destination tally type to map to the device (``'Preview'`` or ``'Program'``)"""

    @QtCore.Slot(result=bool)
    def checkValid(self) -> bool:
        """Check validity of current parameters
        """
        if -1 in self.tallyKey:
            return False
        if max(self.tallyKey) >= 0xfffe:
            return False
        if self.tallyType not in TallyType.__members__:
            return False
        if getattr(TallyType, self.tallyType) == TallyType.no_tally:
            return False
        if self.destTallyType.lower() not in ['preview', 'program']:
            return False
        return True

    @asyncSlot(UmdModel)
    async def applyMap(self, umd_model: UmdModel):
        """Add a :class:`~jvconnected.interfaces.tslumd.mapper.DeviceMapping`
        to the :attr:`UmdModel.umd_io` using
        :meth:`jvconnected.interfaces.tslumd.umd_io.UmdIo.add_device_mapping`
        """
        await self._apply_map(umd_model)

    @logger.catch
    async def _apply_map(self, umd_model: UmdModel):
        assert self.checkValid()
        umd_io = umd_model.umd_io
        dev_map = umd_io.device_maps.get(self.deviceIndex)
        if dev_map is None:
            dev_map = self.create_device_map()
        else:
            dev_map = self.merge_with_device_map(dev_map)
        await umd_io.add_device_mapping(dev_map)

    def create_device_map(self) -> DeviceMapping:
        """Create a :class:`~jvconnected.interfaces.tslumd.mapper.DeviceMapping`
        with the current values of this instance
        """
        kw = dict(device_index=self.deviceIndex)
        tmap = TallyMap(
            screen_index=self.screenIndex,
            tally_index=self.tallyIndex,
            tally_type=getattr(TallyType, self.tallyType),
        )
        kw[self.destTallyType.lower()] = tmap
        return DeviceMapping(**kw)

    def merge_with_device_map(self, existing_map: DeviceMapping) -> DeviceMapping:
        """Merge an existing :class:`~jvconnected.interfaces.tslumd.mapper.DeviceMapping`
        with one created by :meth:`create_device_map`
        """
        my_map = self.create_device_map()
        attr = self.destTallyType.lower()
        kw = {attr:getattr(my_map, attr)}
        return dataclasses.replace(existing_map, **kw)

class TallyCreateMapModel(GenericQObject):
    _n_deviceIndex = Signal()
    _n_program = Signal()
    _n_preview = Signal()
    def __init__(self, *args):
        self._deviceIndex = -1
        self._program = None
        self._preview = None
        super().__init__(*args)
        self.program = TallyMapModel(self)
        self.program.destTallyType = 'Program'
        self.preview = TallyMapModel(self)
        self.preview.destTallyType = 'Preview'

    def _g_deviceIndex(self) -> int: return self._deviceIndex
    def _s_deviceIndex(self, value: int):
        self._generic_setter('_deviceIndex', value)
        self.program.deviceIndex = value
        self.preview.deviceIndex = value
    deviceIndex: int = Property(int, _g_deviceIndex, _s_deviceIndex, notify=_n_deviceIndex)
    """The device index"""

    def _g_program(self) -> TallyMapModel: return self._program
    def _s_program(self, value: TallyMapModel): self._generic_setter('_program', value)
    program: TallyMapModel = Property(TallyMapModel,
        _g_program, _s_program, notify=_n_program,
    )
    """Instance of :class:`TallyMapModel` to be used for program tally"""

    def _g_preview(self) -> TallyMapModel: return self._preview
    def _s_preview(self, value: TallyMapModel): self._generic_setter('_preview', value)
    preview: TallyMapModel = Property(TallyMapModel,
        _g_preview, _s_preview, notify=_n_preview,
    )
    """Instance of :class:`TallyMapModel` to be used for preview tally"""

    @QtCore.Slot(result=bool)
    def checkValid(self) -> bool:
        """Check validity of current parameters

        Calls :meth:`~TallyMapModel.checkValid` on both :attr:`program` and
        :attr:`preview` objects
        """
        assert self.program.destTallyType == 'Program'
        assert self.preview.destTallyType == 'Preview'
        if self.deviceIndex == -1:
            return False
        if not self.program.checkValid():
            return False
        if not self.preview.checkValid():
            return False
        return True

    @asyncSlot(UmdModel)
    async def applyMap(self, umd_model: UmdModel):
        """Add a :class:`~jvconnected.interfaces.tslumd.mapper.DeviceMapping`
        to the :attr:`UmdModel.umd_io` using
        :meth:`jvconnected.interfaces.tslumd.umd_io.UmdIo.add_device_mapping`.

        The values from the :attr:`program` and :attr:`preview` objects are
        merged
        """
        await self._apply_map(umd_model)

    @logger.catch
    async def _apply_map(self, umd_model: UmdModel):
        assert self.checkValid()
        umd_io = umd_model.umd_io
        dev_map = self.program.create_device_map()
        dev_map = self.preview.merge_with_device_map(dev_map)
        await umd_io.add_device_mapping(dev_map)


class TallyUnmapModel(TallyMapBase):
    @QtCore.Slot(UmdModel, result='QVariantList')
    def getMappedDeviceIndices(self, umd_model: UmdModel) -> List[int]:
        d = self.get_mapped(umd_model)
        return list(sorted(d.keys()))

    def get_mapped(self, umd_model: UmdModel):
        d = {}
        for device_index, device_map in umd_model.umd_io.device_maps.items():
            for attr in ['program', 'preview']:
                tmap = getattr(device_map, attr)
                if tmap.tally_key != self.tallyKey:
                    continue
                if tmap.tally_type == TallyType.no_tally:
                    continue
                if device_index not in d:
                    d[device_index] = {'map':device_map, 'matching':set()}
                d[device_index]['matching'].add(attr)
        return d

    @asyncSlot(UmdModel, 'QVariantList')
    async def unmapByIndices(self, umd_model: UmdModel, indices: List[int]):
        data = self.get_mapped(umd_model)
        umd_io = umd_model.umd_io
        for ix in indices:
            if ix not in data:
                continue
            d = data[ix]
            device_map = d['map']
            if 'program' in d['matching'] and 'preview' in d['matching']:
                await umd_io.remove_device_mapping(ix)
                continue
            elif 'program' in d['matching']:
                attr = 'program'
            elif 'preview' in d['matching']:
                attr = 'preview'
            else:
                raise Exception()
            tmap = TallyMap(tally_type=TallyType.no_tally)
            new_device_map = dataclasses.replace(device_map, **{attr:tmap})
            logger.debug(f'{new_device_map}')
            await umd_io.add_device_mapping(new_device_map)


MODEL_CLASSES = (
    UmdModel, TallyListModel, TallyMapListModel, TallyMapModel,
    TallyCreateMapModel, TallyUnmapModel,
)

def register_qml_types():
    for cls in MODEL_CLASSES:
        QtQml.qmlRegisterType(cls, 'UmdModels', 1, 0, cls.__name__)
