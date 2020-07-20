from loguru import logger
import asyncio

from pydispatch import Dispatcher
from pydispatch.properties import Property, DictProperty, ListProperty

from jvconnected.config import Config
from jvconnected.device import Device
from jvconnected.discovery import Discovery
from jvconnected.client import ClientAuthError

class Engine(Dispatcher):
    """Top level component to handle config, discovery and device control

    Properties:
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
    running = Property(False)
    auto_add_devices = Property(True)

    _events_ = [
        'on_config_device_added', 'on_device_discovered',
        'on_device_added', 'on_device_removed',
    ]
    def __init__(self, **kwargs):
        self.auto_add_devices = kwargs.get('auto_add_devices', True)
        self.loop = asyncio.get_event_loop()
        self.config = Config()
        self.discovery = Discovery()

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
        self.config.bind_async(
            self.loop,
            on_device_added=self._on_config_device_added,
        )
        self.discovery.bind_async(
            self.loop,
            on_service_added=self.on_discovery_service_added,
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
        self.devices[device_conf.id] = device
        try:
            await device.open()
        except ClientAuthError as exc:
            del self.devices[device_conf.id]
            logger.exception(exc)
            await device.close()
            return
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
        device_conf = self.config.add_discovered_device(info)
        logger.debug(f'device_conf: {device_conf}')
        self.emit('on_device_discovered', device_conf)
        if self.auto_add_devices:
            if device_conf.id not in self.devices:
                await self.add_device_from_conf(device_conf)

    async def _on_config_device_added(self, conf_device, **kwargs):
        self.emit('on_config_device_added', conf_device)

if __name__ == '__main__':
    Engine().run_forever()
