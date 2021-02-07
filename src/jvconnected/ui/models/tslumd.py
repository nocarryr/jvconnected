from loguru import logger
import asyncio
import enum
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
    tally_qcolors = {
        TallyColor.OFF: QtGui.QColor(Qt.transparent),
        TallyColor.RED: QtGui.QColor(Qt.red),
        TallyColor.GREEN: QtGui.QColor(Qt.green),
        TallyColor.AMBER: QtGui.QColor(Qt.yellow),
    }
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
            val = self.tally_qcolors[val]
        return val

MODEL_CLASSES = (UmdModel, TallyListModel)

def register_qml_types():
    for cls in MODEL_CLASSES:
        QtQml.qmlRegisterType(cls, 'UmdModels', 1, 0, cls.__name__)
