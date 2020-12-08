from loguru import logger
import asyncio
from typing import Optional

from PySide2 import QtCore, QtQml
from PySide2.QtCore import Property, Signal

from asyncqt import QEventLoop, asyncSlot, asyncClose

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
        self._isActive = self._name in self.parent_model._get_enabled_port_names()
        prop_name = self.parent_model.port_names_prop
        self.midi_io.bind(**{prop_name:self.on_enabled_port_names})
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
        await self.parent_model.setPortActive(self.name, value)

    def on_enabled_port_names(self, instance, value, **kwargs):
        self.isActive = self.name in value

    def __repr__(self):
        return f'<{self.__class__.__name__}: "{self}">'

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
    port_names_prop = None
    _n_engine = Signal()
    _n_count = Signal()
    portAdded = Signal(MidiPortModel)
    portRemoved = Signal(MidiPortModel)
    portsUpdated = Signal()
    def __init__(self, *args):
        self.loop = asyncio.get_event_loop()
        self.ports = {}
        self._engine = None
        self.midi_io = None
        super().__init__(*args)

    def _g_engine(self) -> Optional[EngineModel]:
        return self._engine
    def _s_engine(self, value: EngineModel):
        if value == self._engine:
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
        prop_name = self.port_names_prop
        midi_io.bind(**{prop_name:self.on_midi_io_port_names})

    def _get_all_port_names(self):
        raise NotImplementedError

    def _get_enabled_port_names(self):
        raise NotImplementedError

    def _get_enabled_ports_dict(self):
        raise NotImplementedError

    async def _set_port_active(self, name: str, state: bool):
        raise NotImplementedError

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
                # if port.index != i:
                #     changed = True
                # if port.isActive != active:
                #     changed = True
                # port.index = i
                # port.isActive = active
                pass
            else:
                changed = True
                port = MidiPortModel(name=name, index=i, isActive=active, parent_model=self)
                self.ports[name] = port
                self._n_count.emit()
                self.portAdded.emit(port)

        if changed:
            self.portsUpdated.emit()

    def on_midi_io_port_names(self, instance, value, **kwargs):
        self.update_ports()

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
    port_names_prop = 'inport_names'
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
    port_names_prop = 'outport_names'
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

MODEL_CLASSES = (MidiPortModel, InportsModel, OutportsModel)

def register_qml_types():
    for cls in MODEL_CLASSES:
        QtQml.qmlRegisterType(cls, 'MidiModels', 1, 0, cls.__name__)
