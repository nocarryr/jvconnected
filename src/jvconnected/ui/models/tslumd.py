from loguru import logger
import asyncio
from typing import Optional
from bisect import bisect_left

from PySide2 import QtCore, QtQml, QtGui
from PySide2.QtCore import Property, Signal
from PySide2.QtCore import Qt

from qasync import QEventLoop, asyncSlot, asyncClose

from jvconnected.ui.utils import GenericQObject
from jvconnected.ui.models.engine import EngineModel

from jvconnected.interfaces.tslumd.messages import TallyColor
from jvconnected.interfaces.tslumd.umd_io import Tally

# class UmdModel(GenericQObject):
#     _n_engine = Signal()
#     def __init__(self, *args):
#         self._engine = None
#         self.umd_io = None
#         super().__init__(*args)
#
#     def _g_engine(self) -> Optional[EngineModel]:
#         return self._engine
#     def _s_engine(self, value: EngineModel):
#         if value is None or value == self._engine:
#             return
#         assert self._engine is None
#         self._engine = value
#         self.umd_io = value.engine.interfaces['tslumd']
#         self._init_interface()
#     engine = Property(EngineModel, _g_engine, _s_engine, notify=_n_engine)
#     """The :class:`~jvconnected.ui.models.engine.EngineModel` in use"""
#
#     def _init_interface(self):
#         for tally in self.umd_io.tallies.values():
#             self.add_tally(tally)
#         self.umd_io.bind(on_tally_added=self.add_tally)
#
#     def add_tally(self, tally: Tally):
#         tally.bind(on_update=self.update_tally)
#
#     def update_tally(self, tally: Tally, props_changed):
#         pass

class TallyListModel(QtCore.QAbstractTableModel):
    IndexRole = Qt.UserRole + 1
    RhTallyRole = Qt.UserRole + 2
    TxtTallyRole = Qt.UserRole + 3
    LhTallyRole = Qt.UserRole + 4
    _n_engine = Signal()
    _prop_attrs = ('index', 'rh_tally', 'txt_tally', 'lh_tally', 'text')
    tally_qcolors = {
        TallyColor.OFF: QtGui.QColor(Qt.transparent),
        TallyColor.RED: QtGui.QColor(Qt.red),
        TallyColor.GREEN: QtGui.QColor(Qt.green),
        TallyColor.AMBER: QtGui.QColor(Qt.yellow),
    }
    headers = ('tallyIndex', 'rhTally', 'txtTally', 'lhTally', 'display')
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
        return {
            TallyListModel.IndexRole: b'tallyIndex',
            TallyListModel.RhTallyRole: b'rhTally',
            TallyListModel.TxtTallyRole: b'txtTally',
            TallyListModel.LhTallyRole: b'lhTally',
            Qt.DisplayRole: b'text',
        }

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
        if role == TallyListModel.IndexRole:
            return tally.index
        elif role == TallyListModel.RhTallyRole:
            return self.tally_qcolors[tally.rh_tally]
        elif role == TallyListModel.TxtTallyRole:
            return self.tally_qcolors[tally.txt_tally]
        elif role == TallyListModel.LhTallyRole:
            return self.tally_qcolors[tally.lh_tally]
        elif role == Qt.DisplayRole:
            return tally.text

MODEL_CLASSES = (TallyListModel,)

def register_qml_types():
    for cls in MODEL_CLASSES:
        QtQml.qmlRegisterType(cls, 'UmdModels', 1, 0, cls.__name__)
