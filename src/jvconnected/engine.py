from __future__ import annotations
import typing as tp
from loguru import logger
import asyncio
from typing import Optional

from pydispatch import Dispatcher, Property, DictProperty, ListProperty

from jvconnected.common import ConnectionState, RemovalReason, ReconnectStatus
from jvconnected.config import Config, DeviceConfig
from jvconnected.device import Device
from jvconnected.discovery import Discovery
from jvconnected.client import ClientError, ClientAuthError, ClientNetworkError

from jvconnected import interfaces
from jvconnected.interfaces import midi


class Engine(Dispatcher):
    """Top level component to handle config, discovery and device control
    """

    devices: tp.Dict[str, Device] = DictProperty()
    """Mapping of :class:`~.device.Device` instances using their
    :attr:`~.device.Device.id` as keys
    """

    discovered_devices = DictProperty()
    running = Property(False)
    auto_add_devices = Property(True)
    """If ``True``, devices will be added automatically
    when discovered on the network. Otherwise, they must be added manually
    using :meth:`add_device_from_conf`
    """

    midi_io = Property()
    interfaces: tp.Dict[str, 'jvconnected.interfaces.base.Interface'] = DictProperty()
    """Container for :class:`~.interfaces.base.Interface` instances
    """

    _events_ = [
        'on_config_device_added', 'on_device_discovered',
        'on_device_added', 'on_device_connected', 'on_device_removed',
    ]
    config: Config
    """The :class:`~.config.Config` instance"""

    discovery: Discovery
    """The :class:`~.discovery.Discovery` instance"""

    connection_status: tp.Dict[str, ReconnectStatus]
    """Mapping of :class:`~.common.ReconnectStatus` instances using the associated
    :attr:`device_id <.config.DeviceConfig.id>` as keys
    """

    def on_config_device_added(self, conf_device: DeviceConfig):
        """Fired when an instance of :class:`~.config.DeviceConfig` is added
        """

    def on_device_discovered(self, conf_device: DeviceConfig):
        """Fired when a device is detected on the network. An instance of
        :class:`~.config.DeviceConfig` is found (or created)
        and passed as the argument
        """

    def on_device_added(self, device: Device):
        """Fired when an instance of :class:`~.device.Device` is
        added to :attr:`devices`
        """

    def on_device_connected(self, device: Device):
        """Fired when an instance of :class:`~.device.Device` has been added
        and successfully connected
        """

    def on_device_removed(self, device: Device, reason: RemovalReason):
        """Fired when an instance of :class:`~.device.Device` is removed

        Arguments:
            device: The device that was removed
            reason: Reason for removal
        """

    _device_reconnect_timeout = 5
    _device_reconnect_max_attempts = 100
    def __init__(self, **kwargs):
        self.auto_add_devices = kwargs.get('auto_add_devices', True)
        self.loop = asyncio.get_event_loop()
        self.config = Config()
        self.discovery = Discovery()
        self.device_reconnect_queue = asyncio.Queue()
        self._device_reconnect_main_task = None
        self._run_pending = False
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
        self._run_pending = True
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
            on_service_updated=self.on_discovery_service_updated,
            on_service_removed=self.on_discovery_service_removed,
        )
        self.running = True
        self._run_pending = False
        await self.add_always_connected_devices()
        await self.discovery.open()
        logger.success('Engine open')

    async def add_always_connected_devices(self):
        """Create and open any devices with
        :attr:`~jvconnected.config.DeviceConfig.always_connect` set to True
        """
        coros = []
        for device_conf in self.config.devices.values():
            if not device_conf.always_connect:
                continue
            assert device_conf.id not in self.discovered_devices
            info = device_conf.build_service_info()
            coros.append(self.on_discovery_service_added(info.name, info=info))
        if len(coros):
            await asyncio.sleep(.01)
            await asyncio.gather(*coros)
            await asyncio.sleep(.01)

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

        for conf_device in self.discovered_devices.values():
            conf_device.online = False

        await asyncio.sleep(0)

        async def close_device(device):
            conf_device = self.config.devices[device.id]
            status = self.connection_status[device.id]
            try:
                await device.close()
            finally:
                await self.set_status_state(status, ConnectionState.DISCONNECT)
                del self.devices[device.id]
                self.emit('on_device_removed', device, RemovalReason.SHUTDOWN)
        coros = []
        for device in self.devices.values():
            coros.append(close_device(device))
        await asyncio.gather(*coros)
        self.connection_status.clear()
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

        logger.debug(f'add_device_from_conf: {device_conf}')
        device = Device(
            device_conf.hostaddr,
            device_conf.auth_user,
            device_conf.auth_pass,
            device_conf.id,
            device_conf.hostport,
        )
        await self.set_status_state(status, ConnectionState.ATTEMPTING)
        device.device_index = device_conf.device_index
        self.devices[device_conf.id] = device
        self.emit('on_device_added', device)
        async with status:
            try:
                await device.open()
            except ClientError as exc:
                await asyncio.sleep(0)
                await self.on_device_client_error(device, exc, skip_status_lock=True)
                return
            await self.set_status_state(status, ConnectionState.CONNECTED)
            status.reason = RemovalReason.UNKNOWN
            status.num_attempts = 0
        self.emit('on_device_connected', device)
        device.bind_async(self.loop, on_client_error=self.on_device_client_error)

    @logger.catch
    async def on_device_client_error(self, device, exc, **kwargs):
        skip_status_lock = kwargs.get('skip_status_lock', False)
        disconnect_state = kwargs.get('state', ConnectionState.FAILED)
        if not self.running:
            return
        if isinstance(exc, ClientNetworkError):
            reason = RemovalReason.TIMEOUT
        elif isinstance(exc, ClientAuthError):
            reason = RemovalReason.AUTH
            logger.warning(f'Authentication failed for device_id: {device.id}')
        else:
            reason = kwargs.get('reason', RemovalReason.UNKNOWN)
        device_conf = self.discovered_devices[device.id]
        status = self.connection_status[device.id]
        async def handle_state():
            try:
                await device.close()
            finally:
                await self.set_status_state(status, disconnect_state)
                if device.id in self.devices:
                    del self.devices[device.id]
                if reason == RemovalReason.TIMEOUT and status.reason != RemovalReason.OFFLINE:
                    await self.device_reconnect_queue.put((device.id, reason))
        if skip_status_lock:
            await handle_state()
        else:
            async with status:
                await handle_state()

        self.emit('on_device_removed', device, reason)

    async def disconnect_device(self, device_id: str):
        """Disconnect the device matching the given id (if connected)
        """
        logger.debug(f'disconnect_device({device_id})')
        status = self.connection_status.get(device_id)
        if status is not None:
            if status.state not in [ConnectionState.CONNECTED, ConnectionState.FAILED]:
                logger.debug('cancelling task')
                task = status.task
                if task is not None:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                status.task = None
                status.num_attempts = 0
        device = self.devices.get(device_id)
        if device is not None:
            logger.debug(f'disconnecting')
            await self.on_device_client_error(
                device, None, reason=RemovalReason.USER,
                state=ConnectionState.USER_DISCONNECT,
            )
        assert device_id not in self.devices
        logger.info(f'Disconnected device "{device_id}"')

    @logger.catch
    async def reconnect_device(self, device_conf: DeviceConfig, wait_for_status: bool = False):
        """Attempt to reestablish a device connection

        This method is primarily useful when a new device is discovered and
        authentication information is needed for it. Once the information is
        set on the *device_conf*, this method may be used to retry the connection.

        Arguments:
            device_conf: The :class:`~.config.DeviceConfig` to reconnect
            wait_for_status: If ``True``, attempt to wait for the connection state
                (using :meth:`ReconnectStatus.wait_for_connect_or_failure() <.common.ReconnectStatus.wait_for_connect_or_failure>`).
                Default is False
        """
        logger.debug(f'reconnect_device({device_conf})')
        device_id = device_conf.id
        await self.disconnect_device(device_id)
        await self.add_device_from_conf(device_conf)
        status = self.connection_status.get(device_id)
        if wait_for_status:
            try:
                await status.wait_for_connect_or_failure(timeout=5)
            except asyncio.TimeoutError:
                logger.warning(f'Timeout reached when reconnecting to "{device_conf!r}"')
        return status.state

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
                device_conf.update_from_service_info(info)
            else:
                device_conf = self.config.add_discovered_device(info)
                self.discovered_devices[device_id] = device_conf
        elif device_conf is None:
            device_conf = self.add_discovered_device(info)

        if device_id not in self.config.devices:
            dev = self.config.add_device(device_conf)

        device_conf.online = True
        self.emit('on_device_discovered', device_conf)
        if self.auto_add_devices:
            if device_conf.id not in self.devices:
                await self.add_device_from_conf(device_conf)

    async def on_discovery_service_updated(self, name, **kwargs):
        logger.debug(f'on_discovery_service_updated: "{name}", {kwargs}')
        info = kwargs['info']
        old = kwargs['old']
        device_id = DeviceConfig.get_id_for_service_info(old)
        status = self.connection_status.get(device_id)
        if status.task is not None and not status.task.done():
            await status.task
        await self.on_discovery_service_removed(name, info=old)
        await self.on_discovery_service_added(name, info=info)

    async def on_discovery_service_removed(self, name, **kwargs):
        logger.debug(f'on_discovery_service_removed: {name}, {kwargs}')
        info = kwargs['info']
        device_id = DeviceConfig.get_id_for_service_info(info)
        device_conf = self.discovered_devices.get(device_id)
        if device_conf is not None:
            device_conf.online = False
            if device_conf.always_connect:
                return
        status = self.connection_status[device_id]
        async with status:
            await self.set_status_state(ConnectionState.FAILED)
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

    async def set_status_state(self, status: ReconnectStatus, state: ConnectionState):
        device_conf = self.discovered_devices.get(status.device_id)
        device = self.devices.get(status.device_id)
        if device_conf is not None:
            device_conf.connection_state = state
        if device is not None:
            device.connection_state = state
        await status.set_state(state)

    @logger.catch
    async def _reconnect_devices(self):
        q = self.device_reconnect_queue

        async def do_reconnect(status: ReconnectStatus):
            await self.set_status_state(status, ConnectionState.SLEEPING)
            await asyncio.sleep(self._device_reconnect_timeout)
            async with status:
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

        while self.running or self._run_pending:
            item = await q.get()
            if item is None or not self.running:
                q.task_done()
                break
            device_id, reason = item
            status = self.connection_status[device_id]
            valid = True
            async with status:
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
                    await self.set_status_state(status, ConnectionState.SCHEDULING)
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
