from loguru import logger
import asyncio
from typing import Iterator, Optional, Literal, Sequence
from numbers import Number
from dataclasses import dataclass

from pydispatch import Dispatcher, Property, DictProperty, ListProperty

from jvconnected.interfaces import base

DEFAULT_HOSTPORT = 1234

TALLY_TYPE = Literal['PGM', 'PVW']

@dataclass
class TallyParameter:
    index: int
    value: bool
    tally_type: TALLY_TYPE

    @classmethod
    def from_string(cls, msg: str):
        """Parse the api string and construct an instance

        The input string should be formatted as::

            "TALLY.xxx:n=v"

        where ``"xxx"`` is one of ``"PGM"`` or ``"PVW"``, ``"n"`` is the index,
        and ``"v"`` is the value (``"0"`` or ``"1"``)
        """
        tally_type = msg.split('TALLY.')[1].split(':')[0]
        ix, value = msg.split(':')[1].split('=')
        ix = int(ix)
        value = int(value) == 1
        return cls(tally_type=tally_type, index=ix, value=value)
    def to_api_string(self) -> str:
        v = {True:1, False:0}.get(self.value)
        return f'<TALLY.{self.tally_type}:{self.index}={v}>'



def iter_messages(rx_str: str) -> Iterator[Sequence[str]]:
    remaining = rx_str
    while '<' in remaining and '>' in remaining:
        start_ix = remaining.index('<')
        end_ix = remaining.find('>', start_ix)
        if end_ix == -1:
            break
        msg = remaining[start_ix:end_ix+1]
        try:
            remaining = remaining[end_ix+1:]
        except IndexError:
            remaining = ''
        yield msg, remaining
    yield '', remaining


class NetlinxClient(base.Interface):
    """Interface for tally control from Netlinx (AMX) systems

    Properties:
        hostaddr (str): The IP address of the master
        hostport (int): The host listen port of the master
        connected (bool): The current connection status
        config: Instance of :class:`jvconnected.config.Config`. This is gathered
            from the :attr:`engine` after :meth:`set_engine` has been called.

    Attributes:
        reader: :class:`asyncio.StreamReader` used to receive from the master
        writer: :class:`asyncio.StreamWriter` used to send data to the master

    """
    connected = Property(False)
    hostaddr = Property()
    hostport = Property(DEFAULT_HOSTPORT)
    config = Property()
    def __init__(self):
        self._reading_config = False
        self.loop = asyncio.get_event_loop()
        self.reader = None
        self.writer = None
        self._engine = None
        self._reconnect_task = None
        self._read_loop_task = None
        self.reconnect_evt = asyncio.Event()
        self.rx_buffer = ''
        self.bind(hostaddr=self.update_config, hostport=self.update_config)
        self.bind_async(self.loop, config=self.read_config)

    async def set_engine(self, engine: 'jvconnected.engine.Engine'):
        if engine is self.engine:
            return
        self.config = engine.config
        await super().set_engine(engine)

    async def set_hostaddr(self, hostaddr: str):
        """Set the :attr:`hostaddr` to the given value and connect to it
        """
        if hostaddr == self.hostaddr:
            return
        self.hostaddr = hostaddr
        if self.running:
            self.reconnect_evt.set()

    async def set_hostport(self, hostport: int):
        """Set the :attr:`hostport` to the given value and connect to it
        """
        if hostport == self.hostport:
            return
        self.hostport = hostport
        if self.running:
            self.reconnect_evt.set()

    @logger.catch
    async def open(self):
        if self.running:
            return
        logger.debug('NetlinxClient.open()')
        self.running = True
        self._reconnect_task = asyncio.ensure_future(self.connect_to_server())
        logger.success(f'NetlinxClient running')

    @logger.catch
    async def connect_to_server(self, retry_timeout: Number = 5):
        """Continuously connect/reconnect to the master while :attr:`running`

        Arguments:
            retry_timeout (Number, optional): Number of seconds to wait between
                connection attempts. Default is ``5``
        """

        async def wait_for_event(evt, _timeout=None):
            if _timeout is None:
                return await evt.wait()
            else:
                try:
                    await asyncio.wait_for(evt.wait(), _timeout)
                    r = True
                except asyncio.TimeoutError:
                    r = False
                return r

        self.reconnect_evt.clear()
        while self.running:
            await self.connect_client()
            if not self.connected:
                t = retry_timeout
            else:
                t = None
            await wait_for_event(self.reconnect_evt, t)
            self.reconnect_evt.clear()

    async def connect_client(self, timeout: Number = 1) -> bool:
        """Connect to the master using :any:`asyncio.open_connection`

        If necessary, :meth:`disconnect_client` will be called before new
        connections are attempted.

        Arguments:
            timeout (Number): Time in seconds to wait for the connection
                before considering the host unavailable

        """
        if None not in [self.reader, self.writer]:
            await self.disconnect_client()
        logger.debug('connecting')
        task = asyncio.open_connection(self.hostaddr, self.hostport)
        r, w = None, None
        try:
            r, w = await asyncio.wait_for(task, timeout)
            connected = True
        except (asyncio.TimeoutError, ConnectionError):
            connected = False
            logger.warning('could not connect')
        if connected:
            self.reader, self.writer = r, w
            self.connected = True
            self._read_loop_task = asyncio.ensure_future(self.read_loop(r))
            await self.request_tally()
        logger.info(f'NetlinxClient.connected: {connected}')
        self.connected = connected
        return connected

    async def disconnect_client(self):
        """Close the :attr:`reader` and :attr:`writer` streams and cancel
        the :meth:`read_loop`
        """
        logger.debug('disconnecting')
        r, w = self.reader, self.writer
        self.reader = None
        self.writer = None
        if w is not None:
            logger.debug('closing writer')
            w.close()
            await w.wait_closed()
            logger.debug('writer closed')
        logger.debug('disconnected')
        self.connected = False

        read_task = self._read_loop_task
        self._read_loop_task = None
        if read_task is not None:
            logger.debug('waiting for read task')
            read_task.cancel()
            try:
                await read_task
            except asyncio.CancelledError:
                pass
            logger.debug('read task finished')
        self.rx_buffer = ''

    async def close(self):
        if not self.running:
            return
        logger.debug('NetlinxClient.close()')
        self.running = False
        self.reconnect_evt.set()
        if self._reconnect_task is not None:
            await self._reconnect_task
            self._reconnect_task = None
        await self.disconnect_client()
        logger.success('NetlinxClient stopped')

    def get_device_by_index(self, ix: int) -> Optional['jvconnected.device.Device']:
        """Find the :class:`~jvconnected.device.Device` with
        :attr:`~jvconnected.device.Device.device_index` matching the given value
        """
        if self.engine is None:
            return None
        for device in self.engine.devices.values():
            if device.device_index == ix:
                return device

    async def handle_tally_message(self, rx_str: str) -> TallyParameter:
        """Process a single tally message
        """
        tally_p = TallyParameter.from_string(rx_str)
        logger.debug(f'Parsed TallyParameter: {tally_p}')
        device = self.get_device_by_index(tally_p.index)
        if device is not None:
            if tally_p.tally_type == 'PGM':
                await device.tally.set_program(tally_p.value)
            else:
                await device.tally.set_preview(tally_p.value)
        return tally_p

    @logger.catch
    async def handle_incoming(self, rx_str: str):
        """Handle data received by :meth:`read_loop`
        """
        logger.debug(f'NetlinxClient.rx: {rx_str}')
        to_parse = f'{self.rx_buffer}{rx_str}'
        remaining = None
        results = []
        for msg, _remaining in iter_messages(to_parse):
            if not len(msg):
                remaining = _remaining
                continue
            msg = msg.lstrip('<').rstrip('>')
            if 'PONG' in msg:
                results.append('PONG')
            elif msg.startswith('TALLY.'):
                r = await self.handle_tally_message(msg)
                results.append(r)
        if '<' not in remaining:
            remaining = ''
        self.rx_buffer = remaining
        return results

    @logger.catch
    async def read_loop(self, reader: asyncio.StreamReader):
        """Wait for and process incoming data from the reader while :attr:`running`
        """
        while self.running and self.connected:
            try:
                msg_bytes = await reader.readuntil(b'\n')
            except asyncio.IncompleteReadError:
                logger.debug('IncompleteReadError: setting reconnect_evt')
                self.connected = False
                self.reconnect_evt.set()
                break
            if not len(msg_bytes.strip(b'\n')):
                continue
            await self.handle_incoming(msg_bytes.decode('UTF-8'))
            await asyncio.sleep(0)

    async def send(self, msg: str):
        """Send to the master through the :attr:`writer` stream
        """
        w = self.writer
        if not self.connected or w is None:
            return
        self.writer.write(msg.encode())
        await self.writer.drain()

    async def request_tally(self):
        """Request all preview and program tally values from the master
        """
        coros = [
            self.send(f'<TALLY.{ttype}?>') for ttype in ['PGM', 'PVW']
        ]
        await asyncio.gather(*coros)

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
        d = config['interfaces'].get('netlinx')
        if d is None:
            d = config['interfaces']['netlinx'] = {}
        d.update({'hostaddr':self.hostaddr, 'hostport':self.hostport})

    async def read_config(self, *args, **kwargs):
        config = self.config
        if config is None:
            return
        d = config.get('interfaces', {}).get('netlinx', {})
        self._reading_config = True
        hostaddr = d.get('hostaddr')
        if hostaddr is not None:
            self.hostaddr = hostaddr
        hostport = d.get('hostport')
        if hostport is not None:
            self.hostport = hostport
        self._reading_config = False
