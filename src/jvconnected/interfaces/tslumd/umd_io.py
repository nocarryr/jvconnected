from loguru import logger
import asyncio
from typing import Dict, Tuple, Set

from pydispatch import Dispatcher, Property, DictProperty, ListProperty

from jvconnected.interfaces import Interface
from jvconnected.interfaces.tslumd.messages import Message, Display, TallyColor

class Tally(Dispatcher):
    """A single tally object

    Properties:
        rh_tally (TallyColor): State of the "right-hand" tally indicator
        txt_tally (TallyColor): State of the "text" tally indicator
        lh_tally (TallyColor): State of the "left-hand" tally indicator
        brightness (int): Tally indicator brightness from 0 to 3
        text (str): Text to display

    :Events:
        .. event:: on_update(instance: Tally, props_changed: Sequence[str])

            Fired when any property changes

    """
    rh_tally = Property(TallyColor.OFF)
    txt_tally = Property(TallyColor.OFF)
    lh_tally = Property(TallyColor.OFF)
    brightness = Property(3)
    text = Property('')
    _events_ = ['on_update']
    _prop_attrs = ('rh_tally', 'txt_tally', 'lh_tally', 'brightness', 'text')
    def __init__(self, index_, **kwargs):
        self.__index = index_
        self._updating_props = False
        self.update(**kwargs)
        self.bind(**{prop:self._on_prop_changed for prop in self._prop_attrs})

    @property
    def index(self) -> int:
        """Index of the tally object from ``0`` to ``65534``
        """
        return self.__index

    @classmethod
    def from_display(cls, display: Display) -> 'Tally':
        """Create an instance from the given :class:`~.messages.Display` object
        """
        kw = {attr:getattr(display, attr) for attr in cls._prop_attrs}
        return cls(display.index, **kw)

    def update(self, **kwargs) -> Set[str]:
        """Update any known properties from the given keyword-arguments

        Returns:
            set: The property names, if any, that changed
        """
        log_updated = kwargs.pop('LOG_UPDATED', False)
        props_changed = set()
        self._updating_props = True
        for attr in self._prop_attrs:
            if attr not in kwargs:
                continue
            val = kwargs[attr]
            if getattr(self, attr) == val:
                continue
            props_changed.add(attr)
            setattr(self, attr, kwargs[attr])
            if log_updated:
                logger.debug(f'{self!r}.{attr} = {val}')
        self._updating_props = False
        if len(props_changed):
            self.emit('on_update', self, props_changed)
        return props_changed

    def update_from_display(self, display: Display) -> Set[str]:
        """Update this instance from the values of the given
        :class:`~.messages.Display` object

        Returns:
            set: The property names, if any, that changed
        """
        kw = {attr:getattr(display, attr) for attr in self._prop_attrs}
        kw['LOG_UPDATED'] = True
        return self.update(**kw)

    def to_dict(self) -> Dict:
        """Serialize to a :class:`dict`
        """
        d = {attr:getattr(self, attr) for attr in self._prop_attrs}
        d['index'] = self.index
        return d

    def to_display(self) -> Display:
        """Create a :class:`~.messages.Display` from this instance
        """
        kw = self.to_dict()
        return Display(**kw)

    def _on_prop_changed(self, instance, value, **kwargs):
        if self._updating_props:
            return
        prop = kwargs['property']
        self.emit('on_update', self, [prop.name])

    def __eq__(self, other):
        if not isinstance(other, (Tally, Display)):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __ne__(self, other):
        if not isinstance(other, (Tally, Display)):
            return NotImplemented
        return self.to_dict() != other.to_dict()

    def __repr__(self):
        return f'<{self.__class__.__name__}: "{self}">'

    def __str__(self):
        return str(self.index)


class UmdProtocol(asyncio.DatagramProtocol):
    def __init__(self, umd_io: 'UmdIo'):
        self.umd_io = umd_io
    def connection_made(self, transport):
        logger.debug(f'transport={transport}')
        self.transport = transport
    def datagram_received(self, data, addr):
        # logger.debug(f'rx: {data}')
        self.umd_io.parse_incoming(data, addr)

class UmdIo(Interface):
    """Main UMD interface

    Properties:
        hostaddr (str): The local host address to bind the server to. Defaults
            to ``0.0.0.0``
        hostport (int): The port to listen on. Defaults to ``60000``
        tallies (Dict[int, Tally]): Mapping of :class:`Tally` objects using the
            :attr:`~Tally.index` as keys
        config: Instance of :class:`jvconnected.config.Config`. This is gathered
            from the :attr:`engine` after :meth:`set_engine` has been called.

    :Events:
        .. on_tally_added(tally: Tally)

            Fired when a :class:`Tally` instance is added to :attr:`tallies`

        .. on_tally_updated(tally: Tally)

            Fired when any :class:`Tally` instance has been updated
    """
    hostaddr = Property('0.0.0.0')
    hostport = Property(60000)
    config = Property()
    tallies = DictProperty()
    _events_ = ['on_tally_added', 'on_tally_updated']

    def __init__(self):
        self._reading_config = False
        self._config_read = asyncio.Event()
        self._connect_lock = asyncio.Lock()
        super().__init__()
        self.bind_async(self.loop, config=self.read_config)
        self.bind(**{prop:self.update_config for prop in ['hostaddr', 'hostport']})

    async def set_engine(self, engine: 'jvconnected.engine.Engine'):
        if engine is self.engine:
            return
        if engine.config is not self.config:
            self._config_read.clear()
        self.config = engine.config
        await self._config_read.wait()
        await super().set_engine(engine)

    async def open(self):
        async with self._connect_lock:
            if self.running:
                return
            logger.debug('UmdIo.open()')
            self.running = True
            self.transport, self.protocol = await self.loop.create_datagram_endpoint(
                lambda: UmdProtocol(self),
                local_addr=(self.hostaddr, self.hostport),
                reuse_port=True,
            )
            logger.success('UmdIo running')

    async def close(self):
        async with self._connect_lock:
            if not self.running:
                return
            logger.debug('UmdIo.close()')
            self.running = False
            self.transport.close()
            logger.success('UmdIo closed')

    async def set_bind_address(self, hostaddr: str, hostport: int):
        """Set the :attr:`hostaddr` and :attr:`hostport` and restart the server
        """
        if hostaddr == self.hostaddr and hostport == self.hostport:
            return
        running = self.running
        if running:
            await self.close()
        self.hostaddr = hostaddr
        self.hostport = hostport
        if running:
            await self.open()

    async def set_hostaddr(self, hostaddr: str):
        """Set the :attr:`hostaddr` and restart the server
        """
        await self.set_bind_address(hostaddr, self.hostport)

    async def set_hostport(self, hostport: int):
        """Set the :attr:`hostport` and restart the server
        """
        await self.set_bind_address(self.hostaddr, hostport)

    def parse_incoming(self, data: bytes, addr: Tuple[str, int]):
        """Parse data received by the server
        """
        while True:
            message, remaining = Message.parse(data)
            for display in message.displays:
                self.update_display(display)
            if not len(remaining):
                break

    def update_display(self, rx_display: Display):
        """Update or create a :class:`Tally` from data received by the server
        """
        if rx_display.index not in self.tallies:
            tally = Tally.from_display(rx_display)
            self.tallies[rx_display.index] = tally
            logger.debug(f'New Tally: {tally!r}')
            self.emit('on_tally_added', self.tallies[rx_display.index])
            return
        tally = self.tallies[rx_display.index]
        changed = tally.update_from_display(rx_display)
        if changed:
            self.emit('on_tally_updated', tally)

    def update_config(self, *args, **kwargs):
        """Update the :attr:`config` with current state
        """
        if self._reading_config:
            return
        config = self.config
        if config is None:
            return
        if 'interfaces' not in config:
            config['interfaces'] = {}
        if 'tslumd' not in config['interfaces']:
            config['interfaces']['tslumd'] = {}
        d = config['interfaces']['tslumd']
        d['hostaddr'] = self.hostaddr
        d['hostport'] = self.hostport

    async def read_config(self, *args, **kwargs):
        config = self.config
        if config is None:
            return
        d = config.get('interfaces', {}).get('tslumd', {})
        self._reading_config = True
        hostaddr = d.get('hostaddr', self.hostaddr)
        hostport = d.get('hostport', self.hostport)
        await self.set_bind_address(hostaddr, hostport)
        self._reading_config = False
        self._config_read.set()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    umd = UmdIo()

    loop.run_until_complete(umd.open())
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        loop.run_until_complete(umd.close())
    finally:
        loop.close()
