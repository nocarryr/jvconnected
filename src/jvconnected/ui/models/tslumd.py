from loguru import logger
import asyncio
import enum
import dataclasses
from typing import Optional, List
from bisect import bisect_left

from PySide2 import QtCore, QtQml, QtGui
from PySide2.QtCore import Property, Signal
from PySide2.QtCore import Qt

from qasync import QEventLoop, asyncSlot, asyncClose

from jvconnected.ui.utils import GenericQObject
from jvconnected.ui.models.engine import EngineModel

from jvconnected.interfaces.tslumd.messages import TallyColor
from jvconnected.interfaces.tslumd.umd_io import Tally, UmdIo
from jvconnected.interfaces.tslumd.mapper import (
    DeviceMapping, TallyMap, TallyType,
)

class UmdModel(GenericQObject):
    _n_engine = Signal()
    _n_running = Signal()
    _n_hostaddr = Signal()
    _n_hostport = Signal()
    _n_editedProperties = Signal()
    _editable_properties = ('hostaddr', 'hostport')
    umd_io: UmdIo #: Instance of :class:`jvconnected.interfaces.umd_io.UmdIo`
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
    engine = Property(EngineModel, _g_engine, _s_engine, notify=_n_engine)
    """The :class:`~jvconnected.ui.models.engine.EngineModel` in use"""

    def _g_running(self) -> bool: return self._running
    def _s_running(self, value: bool): self._generic_setter('_running', value)
    running = Property(bool, _g_running, _s_running, notify=_n_running)
    """Alias for :class:`jvconnected.interfaces.tslumd.umd_io.UmdIo.running`"""

    def _g_hostaddr(self) -> str: return self._hostaddr
    def _s_hostaddr(self, value: str): self._generic_setter('_hostaddr', value)
    hostaddr = Property(str, _g_hostaddr, _s_hostaddr, notify=_n_hostaddr)
    """Alias for :class:`jvconnected.interfaces.tslumd.umd_io.UmdIo.hostaddr`"""

    def _g_hostport(self) -> int: return self._hostport
    def _s_hostport(self, value: int): self._generic_setter('_hostport', value)
    hostport = Property(int, _g_hostport, _s_hostport, notify=_n_hostport)
    """Alias for :class:`jvconnected.interfaces.tslumd.umd_io.UmdIo.hostport`"""

    def _g_editedProperties(self) -> List[str]: return self._editedProperties
    def _s_editedProperties(self, value: List[str]):
        self._generic_setter('_editedProperties', value)
    editedProperties = Property('QVariantList', _g_editedProperties, _s_editedProperties, notify=_n_editedProperties)
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
    IndexRole = Qt.UserRole + 1
    RhTallyRole = Qt.UserRole + 2
    TxtTallyRole = Qt.UserRole + 3
    LhTallyRole = Qt.UserRole + 4
    TextRole = int(Qt.DisplayRole)
    def get_tally_prop(self):
        prop = self.name.split('Role')[0]
        if 'Tally' in prop:
            s = prop.split('Tally')[0].lower()
            return f'{s}_tally'
        return prop.lower()
    def get_qt_prop(self):
        if self.name == 'IndexRole':
            return 'tallyIndex'
        prop = self.name.split('Role')[0]
        if 'Tally' in prop:
            s = prop.split('Tally')[0].lower()
            return f'{s}Tally'
        return prop.lower()

class TallyListModel(QtCore.QAbstractTableModel):
    _n_engine = Signal()
    _prop_attrs = ('index', 'rh_tally', 'txt_tally', 'lh_tally', 'text')
    def __init__(self, *args, **kwargs):
        self._engine = None
        self.umd_io = None
        self._row_count = 0
        self._tally_indices = []
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
    engine = Property(EngineModel, _g_engine, _s_engine, notify=_n_engine)
    """The :class:`~jvconnected.ui.models.engine.EngineModel` in use"""

    @property
    def tallies(self):
        if self.umd_io is None:
            return None
        return self.umd_io.tallies

    def _init_interface(self):
        for tally in self.umd_io.tallies.values():
            self.add_tally(tally)
        self.umd_io.bind(on_tally_added=self.add_tally)

    def add_tally(self, tally: Tally):
        insert_ix = bisect_left(self._tally_indices, tally.index)
        self.beginInsertRows(QtCore.QModelIndex(), insert_ix, insert_ix)
        self._tally_indices.insert(insert_ix, tally.index)
        self.endInsertRows()
        tally.bind(on_update=self.update_tally)

    def update_tally(self, tally: Tally, props_changed):
        row_ix = self._tally_indices.index(tally.index)
        props = {i:prop for i,prop in enumerate(self._prop_attrs) if prop in props_changed}
        tl = self.index(row_ix, min(props.keys()))
        br = self.index(row_ix, max(props.keys()))
        self.dataChanged.emit(tl, br)

    def roleNames(self):
        return {m:m.get_qt_prop().encode() for m in TallyRoles.__members__.values()}

    def columnCount(self, parent):
        return len(self._prop_attrs)

    def rowCount(self, parent):
        return len(self._tally_indices)

    def flags(self, index):
        return Qt.ItemFlags.ItemIsEnabled

    @QtCore.Slot(int, result=int)
    def getIndexForRow(self, row: int) -> int:
        return self._tally_indices[row]

    @QtCore.Slot(int, result=str)
    def getTallyTypeForColumn(self, column: int) -> str:
        return self._prop_attrs[column]

    def data(self, index, role):
        if not index.isValid():
            return None
        ix = self._tally_indices[index.row()]
        tallies = self.tallies
        if tallies is None:
            tally = None
        else:
            tally = tallies[ix]

        if tally is None:
            return None
        role = TallyRoles(role)
        val = getattr(tally, role.get_tally_prop())
        if isinstance(val, TallyColor):
            val = val.name
        return val


class TallyMapBase(GenericQObject):
    _n_tallyIndex = Signal()
    _n_tallyType = Signal()
    def __init__(self, *args):
        self._tallyIndex = -1
        self._tallyType = ''
        super().__init__(*args)

    def _g_tallyIndex(self) -> int: return self._tallyIndex
    def _s_tallyIndex(self, value: int): self._generic_setter('_tallyIndex', value)
    tallyIndex = Property(int, _g_tallyIndex, _s_tallyIndex, notify=_n_tallyIndex)

    def _g_tallyType(self) -> str: return self._tallyType
    def _s_tallyType(self, value: str): self._generic_setter('_tallyType', value)
    tallyType = Property(str, _g_tallyType, _s_tallyType, notify=_n_tallyType)


class TallyMapModel(TallyMapBase):
    _n_deviceIndex = Signal()
    _n_destTallyType = Signal()
    def __init__(self, *args):
        self._deviceIndex = -1
        self._destTallyType = ''
        super().__init__(*args)

    def _g_deviceIndex(self) -> int: return self._deviceIndex
    def _s_deviceIndex(self, value: int): self._generic_setter('_deviceIndex', value)
    deviceIndex = Property(int, _g_deviceIndex, _s_deviceIndex, notify=_n_deviceIndex)

    def _g_destTallyType(self) -> str: return self._destTallyType
    def _s_destTallyType(self, value: str): self._generic_setter('_destTallyType', value)
    destTallyType = Property(str, _g_destTallyType, _s_destTallyType, notify=_n_destTallyType)

    @QtCore.Slot(result=bool)
    def checkValid(self) -> bool:
        if -1 in [self.tallyIndex, self.deviceIndex]:
            return False
        if self.tallyType not in TallyType.__members__:
            return False
        if self.destTallyType.lower() not in ['preview', 'program']:
            return False
        return True

    @asyncSlot(UmdModel)
    async def applyMap(self, umd_model: UmdModel):
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

    def create_device_map(self):
        kw = dict(device_index=self.deviceIndex)
        tmap = TallyMap(
            tally_index=self.tallyIndex,
            tally_type=getattr(TallyType, self.tallyType),
        )
        kw[self.destTallyType.lower()] = tmap
        return DeviceMapping(**kw)

    def merge_with_device_map(self, existing_map: DeviceMapping) -> DeviceMapping:
        my_map = self.create_device_map()
        attr = self.destTallyType.lower()
        kw = {attr:getattr(my_map, attr)}
        return dataclasses.replace(existing_map, **kw)


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
                if tmap.tally_index != self.tallyIndex:
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


MODEL_CLASSES = (UmdModel, TallyListModel, TallyMapModel, TallyUnmapModel)

def register_qml_types():
    for cls in MODEL_CLASSES:
        QtQml.qmlRegisterType(cls, 'UmdModels', 1, 0, cls.__name__)
