from loguru import logger
import asyncio
import enum
from dataclasses import dataclass, field
from typing import Optional

from pydispatch import Dispatcher, Property, DictProperty, ListProperty

from jvconnected.config import Config, DeviceConfig
from jvconnected.device import Device
from jvconnected.discovery import Discovery
from jvconnected.client import ClientError, ClientAuthError, ClientNetworkError

from jvconnected import interfaces
from jvconnected.interfaces import midi

class RemovalReason(enum.Enum):
    """Possible values used in :event:`Engine.on_device_removed`
    """

    UNKNOWN = enum.auto()
    """Unknown reason"""

    OFFLINE = enum.auto()
    """The device is no longer on the network"""

    TIMEOUT = enum.auto()
    """Communication was lost due to a timeout. Reconnection will be attempted"""

    AUTH = enum.auto()
    """Authentication with the device failed, likely due to invalid credentials"""

    SHUTDOWN = enum.auto()
    """The engine is shutting down"""


class ConnectionState(enum.Enum):
    """State used in :class:`ReconnectStatus`
    """
    UNKNOWN = enum.auto()
    """Unknown state"""

    SCHEDULING = enum.auto()
    """A task is being scheduled to reconnect, but it has not begun execution"""

    SLEEPING = enum.auto()
    """The :attr:`ReconnectStatus.task` is waiting before attempting to reconnect"""

    ATTEMPTING = enum.auto()
    """The connection is being established"""

    CONNECTED = enum.auto()
    """Connection attempt success"""

    FAILED = enum.auto()
    """Connection has been lost"""

@dataclass
class ReconnectStatus:
    """Holds state used in device reconnect methods
    """
    device_id: str
    """The associated device id"""

    state: ConnectionState = ConnectionState.UNKNOWN
    """Current :class:`ConnectionState`"""

    reason: RemovalReason = RemovalReason.UNKNOWN
    """The :class:`RemovalReason` for disconnect"""

    task: Optional[asyncio.Task] = None
    """The current :class:`asyncio.Task` scheduled to reconnect"""

    num_attempts: int = 0
    """Number of reconnect attempts"""


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
        connection_status (dict): Mapping of :class:`ReconnectStatus` instances

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

        .. event:: on_device_removed(device: jvconnected.device.Device, reason: RemovalReason)

            Fired when an instance of :class:`~jvconnected.device.Device` is
            removed

            :param device: The device that was removed
            :type device: jvconnected.device.Device
            :param reason: Reason for removal
            :type reason: RemovalReason

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
    _device_reconnect_timeout = 5
    _device_reconnect_max_attempts = 100
    def __init__(self, **kwargs):
        self.auto_add_devices = kwargs.get('auto_add_devices', True)
        self.loop = asyncio.get_event_loop()
        self.config = Config()
        self.discovery = Discovery()
        self.device_reconnect_queue = asyncio.Queue()
        self._device_reconnect_main_task = None
        self.connection_status = {}
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
        t = asyncio.create_task(self._reconnect_devices())
        self._device_reconnect_main_task = t
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

        t = self._device_reconnect_main_task
        self._device_reconnect_main_task = None
        await self.device_reconnect_queue.put(None)
        await t
        for status in self.connection_status.values():
            t = status.task
            if t is None or t.done():
                continue
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
        self.connection_status.clear()

        async def close_device(device):
            try:
                await device.close()
            finally:
                del self.devices[device.id]
                self.emit('on_device_removed', device, RemovalReason.SHUTDOWN)
        coros = []
        for device in self.devices.values():
            coros.append(close_device(device))
        await asyncio.gather(*coros)
        logger.success('Engine closed')

    async def add_device_from_conf(self, device_conf: 'jvconnected.config.DeviceConfig'):
        """Add a client :class:`~jvconnected.device.Device` instance from the given
        :class:`~jvconnected.config.DeviceConfig` and attempt to connect.

        If auth information is incorrect or does not exist, display the error
        and remove the newly added device.

        """
        status = self.connection_status.get(device_conf.id)
        if status is None:
            status = ReconnectStatus(device_id=device_conf.id)
            self.connection_status[device_conf.id] = status
        if status.state == ConnectionState.ATTEMPTING:
            task = status.task
            if task is not None and not task.done():
                await task
                if status.state == ConnectionState.CONNECTED:
                    return

        status.state = ConnectionState.ATTEMPTING
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
        except ClientError as exc:
            status.state = ConnectionState.FAILED
            del self.devices[device_conf.id]
            await device.close()
            await self.on_device_client_error(device, exc)
            return
        status.state = ConnectionState.CONNECTED
        status.reason = RemovalReason.UNKNOWN
        status.num_attempts = 0
        device_conf.active = True
        device.bind_async(self.loop, on_client_error=self.on_device_client_error)
        self.emit('on_device_added', device)

    @logger.catch
    async def on_device_client_error(self, device, exc, **kwargs):
        if not self.running:
            return
        if isinstance(exc, ClientNetworkError):
            reason = RemovalReason.TIMEOUT
        elif isinstance(exc, ClientAuthError):
            reason = RemovalReason.AUTH
            logger.warning(f'Authentication failed for device_id: {device.id}')
        else:
            reason = RemovalReason.UNKNOWN
        # logger.debug(f'device client error: device={device}, reason={reason}, exc={exc}')
        device_conf = self.discovered_devices[device.id]
        device_conf.active = False
        try:
            await device.close()
        finally:
            status = self.connection_status[device.id]
            status.state = ConnectionState.FAILED
            if device.id in self.devices:
                del self.devices[device.id]
            if reason == RemovalReason.TIMEOUT:
                await self.device_reconnect_queue.put((device.id, reason))
            self.emit('on_device_removed', device, reason)

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
        status = self.connection_status.get(device_id)
        if status is not None:
            status.reason = RemovalReason.OFFLINE
        device = self.devices.get(device_id)
        if device is not None:
            try:
                await device.close()
            finally:
                del self.devices[device_id]
                self.emit('on_device_removed', device, RemovalReason.OFFLINE)

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

    @logger.catch
    async def _reconnect_devices(self):
        q = self.device_reconnect_queue

        async def do_reconnect(status: ReconnectStatus):
            status.state = ConnectionState.SLEEPING
            await asyncio.sleep(self._device_reconnect_timeout)
            if status.state != ConnectionState.SLEEPING:
                return
            if not self.running:
                return
            disco_conf = self.discovered_devices.get(status.device_id)
            if disco_conf is None:
                return
            if not disco_conf.online:
                return
            logger.debug(f'reconnect to {disco_conf}')
            status.num_attempts += 1
            await self.add_device_from_conf(disco_conf)

        while self.running:
            item = await q.get()
            if item is None or not self.running:
                q.task_done()
                break
            device_id, reason = item
            status = self.connection_status[device_id]
            valid = True
            if status.state != ConnectionState.FAILED:
                valid = False
            elif status.num_attempts >= self._device_reconnect_max_attempts:
                logger.debug(f'max attempts reached for "{device_id}"')
                valid = False
            elif status.task is not None and not status.task.done():
                logger.error(f'Active reconnect task exists for {status}')
                valid = False
            elif reason == RemovalReason.TIMEOUT and status.reason == RemovalReason.OFFLINE:
                valid = False

            if valid:
                status.reason = reason
                status.state = ConnectionState.SCHEDULING
                logger.debug(f'scheduling reconnect for {device_id}, num_attempts={status.num_attempts}')
                status.task = asyncio.create_task(do_reconnect(status))
            q.task_done()

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
