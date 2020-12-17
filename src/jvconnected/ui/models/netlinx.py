from loguru import logger
import asyncio
from typing import Optional

from PySide2 import QtCore, QtQml
from PySide2.QtCore import Property, Signal

from qasync import QEventLoop, asyncSlot, asyncClose

from jvconnected.ui.utils import GenericQObject
from jvconnected.ui.models.engine import EngineModel

class NetlinxModel(GenericQObject):
    """Qt Bridge to :class:`jvconnected.interfaces.netlinx.client.NetlinxClient`

    Attributes:
        netlinx: The :class:`~jvconnected.interfaces.netlinx.client.NetlinxClient`
            instance gathered from :attr:`engine`
    """
    _n_engine = Signal()
    _n_hostaddr = Signal()
    _n_hostport = Signal()
    _n_connected = Signal()
    def __init__(self, *args):
        self.loop = asyncio.get_event_loop()
        self._engine = None
        self.netlinx = None
        self._hostaddr = None
        self._hostport = 0
        self._connected = False
        super().__init__(*args)

    def _g_engine(self) -> Optional[EngineModel]:
        return self._engine
    def _s_engine(self, value: EngineModel):
        if value == self._engine:
            return
        assert self._engine is None
        self._engine = value
        self.netlinx = value.engine.interfaces['netlinx']
        self.hostaddr = self.netlinx.hostaddr
        self.hostport = self.netlinx.hostport
        self.connected = self.netlinx.connected
        self.netlinx.bind(
            hostaddr=self.on_netlinx_hostaddr,
            hostport=self.on_netlinx_hostport,
            connected=self.on_netlinx_connected,
        )
        self._n_engine.emit()
    engine = Property(EngineModel, _g_engine, _s_engine, notify=_n_engine)
    """The :class:`~jvconnected.ui.models.engine.EngineModel` in use"""

    def _g_hostaddr(self): return self._hostaddr
    def _s_hostaddr(self, value: str): self._generic_setter('_hostaddr', value)
    hostaddr = Property(str, _g_hostaddr, _s_hostaddr, notify=_n_hostaddr)
    """The :attr:`~jvconnected.interfaces.netlinx.client.NetlinxClient.hostaddr`
    value of the :attr:`netlinx`
    """

    def _g_hostport(self): return self._hostport
    def _s_hostport(self, value: int): self._generic_setter('_hostport', value)
    hostport = Property(int, _g_hostport, _s_hostport, notify=_n_hostport)
    """The :attr:`~jvconnected.interfaces.netlinx.client.NetlinxClient.hostport`
    value of the :attr:`netlinx`
    """

    def _g_connected(self): return self._connected
    def _s_connected(self, value: bool): self._generic_setter('_connected', value)
    connected = Property(bool, _g_connected, _s_connected, notify=_n_connected)
    """The :attr:`~jvconnected.interfaces.netlinx.client.NetlinxClient.connected`
    value of the :attr:`netlinx`
    """

    def on_netlinx_hostaddr(self, instance, value, **kwargs):
        self.hostaddr = value

    def on_netlinx_hostport(self, instance, value, **kwargs):
        self.hostport = value

    def on_netlinx_connected(self, instance, value, **kwargs):
        self.connected = value

    @asyncSlot(str)
    async def setHostaddr(self, value: str):
        """Call :meth:`jvconnected.interfaces.netlinx.client.NetlinxClient.set_hostaddr`
        on the :attr:`netlinx`
        """
        await self.netlinx.set_hostaddr(value)

    @asyncSlot(int)
    async def setHostport(self, value: int):
        """Call :meth:`jvconnected.interfaces.netlinx.client.NetlinxClient.set_hostport`
        on the :attr:`netlinx`
        """
        await self.netlinx.set_hostport(value)


def register_qml_types():
    QtQml.qmlRegisterType(NetlinxModel, 'NetlinxModels', 1, 0, 'NetlinxModel')
