from loguru import logger
logger.disable('tslumd.tallyobj')
import asyncio
from typing import Dict, Tuple, Set, Optional

from pydispatch import Dispatcher, Property, DictProperty, ListProperty
from tslumd import Message, Display, Tally, TallyColor, UmdReceiver

from jvconnected.interfaces import Interface
from jvconnected.interfaces.tslumd.mapper import DeviceMapping, MappedDevice

class UmdIo(Interface):
    """Main UMD interface
    """

    hostaddr: str = Property('0.0.0.0')
    """Alias for :attr:`tslumd.receiver.UmdReceiver.hostaddr`"""

    hostport: int = Property(65000)
    """Alias for :attr:`tslumd.receiver.UmdReceiver.hostport`"""

    device_maps: Dict[int, DeviceMapping] = DictProperty()
    """A ``dict`` of :class:`~.mapper.DeviceMapping` definitions stored with
    their :attr:`~.mapper.DeviceMapping.device_index` as keys
    """

    mapped_devices: Dict[int, MappedDevice] = DictProperty()
    """A ``dict`` of :class:`~.mapper.MappedDevice` stored with the
    ``device_index`` of their :attr:`~.mapper.MappedDevice.map` as keys
    """

    def on_tally_added(self, tally: Tally):
        """Fired when a :class:`tslumd.tallyobj.Tally` instance is
        added to :attr:`tallies`
        """

    def on_tally_updated(self, tally: Tally):
        """Fired when any :class:`tslumd.tallyobj.Tally` instance has
        been updated
        """

    _events_ = ['on_tally_added', 'on_tally_updated']
    interface_name = 'tslumd'
    def __init__(self):
        self._reading_config = False
        self._config_read = asyncio.Event()
        self._connect_lock = asyncio.Lock()
        super().__init__()
        self.receiver = UmdReceiver()
        self.hostaddr = self.receiver.hostaddr
        self.hostport = self.receiver.hostport
        self.receiver.bind_async(self.loop,
            on_tally_added=self._on_receiver_tally_added,
            on_tally_updated=self._on_receiver_tally_updated,
        )
        self.bind_async(self.loop,
            config=self.read_config,
        )
        self.bind(**{prop:self.update_config for prop in ['hostaddr', 'hostport']})

    @property
    def tallies(self) -> Dict[int, Tally]:
        """Alias for :attr:`tslumd.receiver.UmdReceiver.tallies`
        """
        return self.receiver.tallies

    async def set_engine(self, engine: 'jvconnected.engine.Engine'):
        if engine is self.engine:
            return
        if engine.config is not self.config:
            self._config_read.clear()
        await super().set_engine(engine)
        engine.bind_async(
            self.loop,
            on_device_added=self.on_engine_device_added,
            on_device_removed=self.on_engine_device_removed,
        )

    async def open(self):
        async with self._connect_lock:
            if self.running:
                return
            logger.debug('UmdIo.open()')
            if self.config is not None:
                await self._config_read.wait()
            self.running = True
            await self.receiver.open()
            logger.success('UmdIo running')

    async def close(self):
        async with self._connect_lock:
            if not self.running:
                return
            logger.debug('UmdIo.close()')
            self.running = False
            await self.receiver.close()
            logger.success('UmdIo closed')

    async def set_bind_address(self, hostaddr: str, hostport: int):
        """Set the :attr:`hostaddr` and :attr:`hostport` and restart the server
        """
        await self.receiver.set_bind_address(hostaddr, hostport)
        self.hostaddr = self.receiver.hostaddr
        self.hostport = self.receiver.hostport


    async def set_hostaddr(self, hostaddr: str):
        """Set the :attr:`hostaddr` and restart the server
        """
        await self.set_bind_address(hostaddr, self.hostport)

    async def set_hostport(self, hostport: int):
        """Set the :attr:`hostport` and restart the server
        """
        await self.set_bind_address(self.hostaddr, hostport)

    async def _on_receiver_tally_added(self, tally, **kwargs):
        for mapped_device in self.mapped_devices.values():
            if mapped_device.have_tallies:
                continue
            r = mapped_device.get_tallies()
            if r:
                await mapped_device.update_device_tally()
        self.emit('on_tally_added', tally, **kwargs)

    async def _on_receiver_tally_updated(self, tally: Tally, props_changed: Set[str], **kwargs):
        self.emit('on_tally_updated', tally, props_changed, **kwargs)

    def get_device_by_index(self, ix: int) -> Optional['jvconnected.device.Device']:
        device = None
        if self.engine is not None:
            device_conf = self.engine.config.indexed_devices.get_by_index(ix)
            if device_conf is not None:
                device = self.engine.devices.get(device_conf.id)
        return device

    @logger.catch
    async def add_device_mapping(self, device_map: 'DeviceMapping'):
        """Add a :class:`~.mapper.DeviceMapping` definition to :attr:`device_maps`
        and update the :attr:`config`.

        An instance of :class:`~.mapper.MappedDevice` is also created and
        associated with its :class:`~jvconnected.device.Device`
        if found in the :attr:`engine`.
        """
        ix = device_map.device_index
        self.device_maps[ix] = device_map
        mapped_device = self.mapped_devices.get(ix)
        if mapped_device is not None:
            await mapped_device.set_device(None)
            del self.mapped_devices[ix]
        device = self.get_device_by_index(ix)
        mapped_device = MappedDevice(map=device_map, umd_io=self)
        self.mapped_devices[ix] = mapped_device
        await mapped_device.set_device(device)
        self.update_config()

    async def remove_device_mapping(self, device_index: int):
        """Remove a :class:`~.mapper.DeviceMapping` and its associated
        :class:`~.mapper.MappedDevice` by the given device index
        """
        if device_index not in self.device_maps:
            return
        del self.device_maps[device_index]
        mapped_device = self.mapped_devices.get(device_index)
        if mapped_device is not None:
            await mapped_device.set_device(None)
            del self.mapped_devices[device_index]
        self.update_config()

    async def on_engine_device_added(self, device, **kwargs):
        mapped_device = self.mapped_devices.get(device.device_index)
        if mapped_device is not None:
            await mapped_device.set_device(device)

    async def on_engine_device_removed(self, device, reason, **kwargs):
        mapped_device = self.mapped_devices.get(device.device_index)
        if mapped_device is not None:
            await mapped_device.set_device(None)

    def update_config(self, *args, **kwargs):
        """Update the :attr:`config` with current state
        """
        if self._reading_config:
            return
        if self.config is None:
            return
        if not self._config_read.is_set():
            return
        d = self.get_config_section()
        if d is None:
            return
        d['hostaddr'] = self.hostaddr
        d['hostport'] = self.hostport
        m = self.device_maps
        d['device_maps'] = [m[k] for k in sorted(m.keys())]

    @logger.catch
    async def read_config(self, *args, **kwargs):
        d = self.get_config_section()
        if d is None:
            return
        self._reading_config = True
        hostaddr = d.get('hostaddr', self.hostaddr)
        hostport = d.get('hostport', self.hostport)
        coros = []
        for dev_map in d.get('device_maps', []):
            coros.append(self.add_device_mapping(dev_map))
        await asyncio.gather(*coros)
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
