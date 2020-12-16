from loguru import logger
import asyncio

from pydispatch import Dispatcher, Property, DictProperty, ListProperty

from jvconnected.config import Config, DeviceConfig
from jvconnected.device import Device
from jvconnected.discovery import Discovery
from jvconnected.client import ClientAuthError

from jvconnected import interfaces
from jvconnected.interfaces import midi

class Engine(Dispatcher):
    """Top level component to handle config, discovery and device control

    Properties:
        interfaces (dict): Container for :class:`jvconnected.interfaces.base.Interface`
            instances
        devices (dict): Container for :class:`~jvconnected.device.Device` instances
        auto_add_devices (bool): If ``True``, devices will be added automatically
            when discovered on the network. Otherwise, they must be added manually
            using :meth:`add_device_from_conf`

    Attributes:
        config: The :class:`~jvconnected.config.Config` instance
        discovery: The :class:`~jvconnected.discovery.Discovery` instance

    :Events:
        .. event:: on_config_device_added(conf_device)

            Fired when an instance of :class:`~jvconnected.config.DeviceConfig`
            is added

        .. event:: on_device_discovered(conf_device)

            Fired when a device is detected on the network. An instance of
            :class:`~jvconnected.config.DeviceConfig` is found (or created)
            and passed as the argument

        .. event:: on_device_added(device)

            Fired when an instance of :class:`~jvconnected.device.Device` is
            added to :attr:`devices`

        .. event:: on_device_removed(device)

            Fired when an instance of :class:`~jvconnected.device.Device` is
            removed

    """
    devices = DictProperty()
    discovered_devices = DictProperty()
    running = Property(False)
    auto_add_devices = Property(True)
    midi_io = Property()
    interfaces = DictProperty()

    _events_ = [
        'on_config_device_added', 'on_device_discovered',
        'on_device_added', 'on_device_removed',
    ]
    def __init__(self, **kwargs):
        self.auto_add_devices = kwargs.get('auto_add_devices', True)
        self.loop = asyncio.get_event_loop()
        self.config = Config()
        self.discovery = Discovery()
        for name, cls in interfaces.registry:
            obj = cls()
            self.interfaces[name] = obj
            if name == 'midi':
                self.midi_io = obj
        interfaces.registry.bind_async(
            self.loop,
            interface_added=self.on_interface_registered,
        )

    async def on_interface_registered(self, name, cls, **kwargs):
        if name not in self.interfaces:
            obj = cls()
            self.interfaces[name] = obj
            await obj.set_engine(self)

    def run_forever(self):
        """Convenience method to open and run until interrupted
        """
        self.loop.run_until_complete(self.open())
        try:
            self.loop.run_forever()
        except KeyboardInterrupt:
            self.loop.run_until_complete(self.close())
        finally:
            self.loop.run_until_complete(self.close())

    async def open(self):
        """Open all communication methods
        """
        if self.running:
            return
        for obj in self.interfaces.values():
            await obj.set_engine(self)
        self.config.bind_async(
            self.loop,
            on_device_added=self._on_config_device_added,
        )
        self.discovery.bind_async(
            self.loop,
            on_service_added=self.on_discovery_service_added,
            on_service_removed=self.on_discovery_service_removed,
        )
        await self.discovery.open()
        self.running = True
        logger.success('Engine open')

    async def close(self):
        """Close the discovery engine and any running device clients
        """
        if not self.running:
            return
        self.running = False
        self.discovery.unbind(self)
        await self.discovery.close()
        coros = []
        for device in self.devices.values():
            coros.append(device.close())
        await asyncio.gather(*coros)
        logger.success('Engine closed')

    async def add_device_from_conf(self, device_conf: 'jvconnected.config.DeviceConfig'):
        """Add a client :class:`~jvconnected.device.Device` instance from the given
        :class:`~jvconnected.config.DeviceConfig` and attempt to connect.

        If auth information is incorrect or does not exist, display the error
        and remove the newly added device.

        """
        logger.debug(f'add_device_from_conf: {device_conf}')
        device = Device(
            device_conf.hostaddr,
            device_conf.auth_user,
            device_conf.auth_pass,
            device_conf.id,
            device_conf.hostport,
        )
        device.device_index = device_conf.device_index
        self.devices[device_conf.id] = device
        try:
            await device.open()
        except ClientAuthError as exc:
            del self.devices[device_conf.id]
            logger.exception(exc)
            await device.close()
            return
        device_conf.active = True
        device.bind_async(self.loop, on_client_error=self.on_device_client_error)
        self.emit('on_device_added', device)

    async def on_device_client_error(self, device, exc, **kwargs):
        try:
            await device.close()
        finally:
            del self.devices[device.id]
            self.emit('on_device_removed', device)

    @logger.catch
    async def on_discovery_service_added(self, name, **kwargs):
        logger.debug(f'on_discovery_service_added: {name}, {kwargs}')
        info = kwargs['info']
        device_id = DeviceConfig.get_id_for_service_info(info)
        device_conf = self.discovered_devices.get(device_id)

        if device_id in self.config.devices:
            if device_conf is not None:
                dev = self.config.add_device(device_conf)
                assert dev is device_conf
            else:
                device_conf = self.config.add_discovered_device(info)
                self.discovered_devices[device_id] = device_conf
        elif device_conf is None:
            device_conf = self.add_discovered_device(info)

        device_conf.online = True
        if self.auto_add_devices:
            if device_conf.id not in self.devices:
                await self.add_device_from_conf(device_conf)
        self.emit('on_device_discovered', device_conf)

    async def on_discovery_service_removed(self, name, **kwargs):
        logger.debug(f'on_discovery_service_removed: {name}, {kwargs}')
        info = kwargs['info']
        device_id = DeviceConfig.get_id_for_service_info(info)
        device_conf = self.discovered_devices.get(device_id)
        if device_conf is not None:
            device_conf.active = False
            device_conf.online = False

        device = self.devices.get(device_id)
        if device is not None:
            try:
                await device.close()
            finally:
                del self.devices[device_id]
                self.emit('on_device_removed', device)

    def add_discovered_device(self, info: 'zeroconf.ServiceInfo') -> DeviceConfig:
        """Create a :class:`~jvconnected.config.DeviceConfig` and add it to
        :attr:`discovered_devices`
        """
        device_id = DeviceConfig.get_id_for_service_info(info)
        if device_id in self.discovered_devices:
            device_conf = self.discovered_devices[device_id]
        else:
            device_conf = DeviceConfig.from_service_info(info)
            self.discovered_devices[device_conf.id] = device_conf
        return device_conf


    async def _on_config_device_added(self, conf_device, **kwargs):
        conf_device.bind(device_index=self._on_config_device_index_changed)
        self.emit('on_config_device_added', conf_device)

    def _on_config_device_index_changed(self, instance, value, **kwargs):
        device_id = instance.id
        device = self.devices.get(device_id)
        if device is None:
            return
        device.device_index = value

if __name__ == '__main__':
    Engine().run_forever()
