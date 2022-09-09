from __future__ import annotations
import typing as tp
from loguru import logger
import os
import sys
import asyncio
from pathlib import Path
import typing as tp
from contextlib import contextmanager

from pydispatch import Dispatcher, Property, DictProperty, ListProperty
import jsonfactory

from zeroconf import ServiceInfo

from jvconnected.common import ConnectionState
from jvconnected.utils import IndexedDict

def get_config_dir(app_name: str) -> 'pathlib.Path':
    """Get the platform's preferred configuration directory

    * For Windows, the :literal:`%LOCALAPPDATA%` environment variable is used.
      Typically ``c:\\Users\\<username>\\AppData\\Local``
    * For MacOS, ``~/Library/Preferences``
    * All others will be ``~/.config``
    """
    if sys.platform == 'win32':
        p = Path(os.environ['LOCALAPPDATA'])
    elif sys.platform == 'darwin':
        p = Path.home() / 'Library' / 'Preferences'
    else:
        p = Path.home() / '.config'
    return p / app_name

class DumbLock(object):
    def __init__(self):
        self._locked = 0
    def acquire(self):
        self._locked += 1
    def release(self):
        if not self.locked():
            raise Exception('Lock not acquired')
        self._locked -= 1
    def locked(self):
        return self._locked > 0
    def __enter__(self):
        self.acquire()
        return self
    def __exit__(self, *args):
        self.release()
    async def __aenter__(self):
        self.acquire()
        return self
    async def __aexit__(self, *args):
        self.release()

class ContextLock(DumbLock):
    def __init__(self):
        self.context = None
        super().__init__()
    @contextmanager
    def set(self, value):
        self.acquire()
        self.context = value
        yield
        self.release()
    def release(self):
        super().release()
        if not self.locked():
            self.context = None


class Config(Dispatcher):
    """Configuration storage

    This object provides a dict-like interface and stores the configuration data
    automatically when it changes. The stored config data is read on initialization.

    Arguments:
        filename (:class:`pathlib.Path`, optional): The configuration filename. If not provided,
            the :attr:`DEFAULT_FILENAME` is used
    """
    data: tp.Dict[str, tp.Any] = DictProperty()
    DEFAULT_FILENAME: Path = get_config_dir('jvconnected') / 'config.json'
    """Platform-dependent default filename
    (``<config_dir>/jvconnected/config.json``).
    Where ``<config_dir>`` is chosen in :func:`get_config_dir`
    """

    indexed_devices: IndexedDict
    """An instance of :class:`jvconnected.utils.IndexedDict` to handle
    device indexing
    """
    _events_ = ['on_device_added']

    def on_device_added(self, device: 'DeviceConfig'):
        """Triggered when a device is added to the config
        """

    def __init__(self, filename: tp.Optional['pathlib.Path'] = None):
        if filename is None:
            filename = self.DEFAULT_FILENAME
        logger.info(f'Config using filename: {filename}')
        self._read_complete = False
        self._device_reindexing = ContextLock()
        self.indexed_devices = IndexedDict()
        self.indexed_devices.bind(
            on_item_index_changed=self.on_device_dict_index_changed,
        )
        self.filename = filename
        self._setitem_lock = DumbLock()
        self.read()
        self._read_complete = True
        self.bind(data=self.on_data_changed)

    @property
    def devices(self) -> tp.Dict[str, 'DeviceConfig']:
        """Mapping of :class:`DeviceConfig` using their :attr:`~DeviceConfig.id`
        as keys
        """
        if 'devices' not in self:
            self['devices'] = {}
        return self['devices']

    def __setitem__(self, key, item):
        with self._setitem_lock:
            self.data[key] = item
            self.write()

    def __getitem__(self, key):
        return self.data[key]

    def __contains__(self, key):
        return key in self.data

    def keys(self): return self.data.keys()
    def values(self): return self.data.values()
    def items(self): return self.data.items()

    def get(self, key, default=None):
        return self.data.get(key, default)

    def update(self, other: tp.Dict):
        """Update from another :class:`dict`
        """
        other = other.copy()
        with self._setitem_lock:
            oth_devices = other.get('devices', {})
            if 'devices' in other:
                del other['devices']
            self.data.update(other)
            for device in oth_devices.values():
                self.add_device(device)
        self.write()

    def add_device(self, device: 'DeviceConfig') -> 'DeviceConfig':
        """Add a :class:`DeviceConfig` instance

        If a device config already exists, it will be updated with the info
        provided using :meth:`DeviceConfig.update_from_other`

        If its :attr:`~DeviceConfig.device_index` is set, it will be added
        to :attr:`indexed_devices`.

        """
        key = device.id
        if key in self.devices:
            with self._setitem_lock:
                ix = self.devices[key].device_index
                self.devices[key].update_from_other(device)
                if not self._read_complete:
                    if ix is not None and ix != -1:
                        assert self.devices[key].device_index == ix
            self.write()
        else:
            assert not self._device_reindexing.locked()
            ix = device.device_index
            if ix is not None:
                with self._setitem_lock:
                    with self._device_reindexing.set(device):
                        new_index = self.indexed_devices.add(key, device, ix)
                        if not self._read_complete and ix != -1:
                            assert ix == new_index
                        device.device_index = new_index
            self.devices[key] = device
            device.stored_in_config = True
            device.bind(
                device_index=self.on_device_index,
                on_change=self.on_device_prop_change,
            )
            # self.indexed_devices.compact_indices()
            self.write()
            self.emit('on_device_added', device)
        return self.devices[key]

    def add_discovered_device(self, info: 'zeroconf.ServiceInfo') -> 'DeviceConfig':
        """Add a :class:`DeviceConfig` from zeroconf data
        """
        device = DeviceConfig.from_service_info(info)
        return self.add_device(device)

    def read(self):
        if not self.filename.exists():
            return
        with self._setitem_lock:
            data = jsonfactory.loads(self.filename.read_text())
            self.update(data)

    def write(self):
        if not self._read_complete:
            return
        p = self.filename.parent
        if not p.exists():
            p.mkdir(mode=0o700, parents=True)
        self.filename.write_text(jsonfactory.dumps(self.data, indent=2))

    def on_data_changed(self, instance, value, **kwargs):
        if self._setitem_lock.locked():
            return
        self.write()

    def on_device_dict_index_changed(self, **kwargs):
        key = kwargs['key']
        device = kwargs['item']
        old_index = kwargs['old_index']
        new_index = kwargs['new_index']
        if self._device_reindexing.locked():
            device.device_index = new_index
        else:
            with self._device_reindexing.set(device):
                with self._setitem_lock:
                    device.device_index = new_index
                self.write()

    def on_device_index(self, instance, value, **kwargs):
        if self._device_reindexing.locked():
            return
        if self._setitem_lock.locked():
            return
        key = instance.id
        old = kwargs['old']
        if value is None:
            assert isinstance(old, int)
            if key in self.indexed_devices:
                self.indexed_devices.remove(key)
        else:
            with self._device_reindexing.set(instance):
                with self._setitem_lock:
                    key = instance.id
                    if old is None:
                        new_index = self.indexed_devices.add(key, instance, value)
                        if value != -1:
                            assert value == new_index
                        else:
                            assert new_index >= 0
                        instance.device_index = new_index
                    else:
                        self.indexed_devices.change_item_index(key, value)
                    # self.indexed_devices.compact_indices()
                self.write()

    def on_device_prop_change(self, instance, prop_name, value, **kwargs):
        if prop_name == 'device_index':
            return
        self.write()

class DeviceConfig(Dispatcher):
    """Configuration data for a device
    """
    name: str = Property('')
    """The device name, taken from :meth:`zeroconf.ServiceInfo.get_name`"""

    dns_name: str = Property('')
    """The fully qualified name for the service host, taken from
    :class:`ServiceInfo.server <zeroconf.ServiceInfo>`
    """

    fqdn: str = Property('')
    """The fully qualified service name, taken from
    :class:`ServiceInfo.name <zeroconf.ServiceInfo>`
    """

    hostaddr: str = Property('')
    """The IPv4 address (in string form)"""

    hostport: int = Property(80)
    """The service port"""

    display_name: str = Property('')
    """A user-defined name for the device, defaults to :attr:`name`"""

    auth_user: str|None = Property(None)
    """Username to use with authentication"""

    auth_pass: str|None = Property(None)
    """Password to use with authentication"""

    device_index: int|None = Property(None)
    """Index for the device for organization purposes.

    If ``None`` (default), no index is assigned. Otherwise, the index
    will be assigned according to :meth:`jvconnected.utils.IndexedDict.add`
    """

    always_connect: bool = Property(False)
    """If ``True``, the :class:`~jvconnected.engine.Engine`
    will attempt to connect to this device without it being discovered
    on the network
    """

    stored_in_config: bool = Property(False)
    """``True`` if the device is stored in :class:`Config`"""

    online: bool = Property(False)
    """``True`` if the device is currently active on the network"""

    active: bool = Property(False)
    """``True`` if a :class:`jvconnected.device.Device` is currently
    communicating with the device
    """

    connection_state: ConnectionState = Property(ConnectionState.UNKNOWN)
    """The device's :class:`~.common.ConnectionState`
    """

    def on_change(instance: 'DeviceConfig', prop_name: str, value: tp.Any):
        """Fired when any property value changes

        Arguments:
            instance: The instance whose property changed
            prop_name: The Property name
            value: New value for the Property
        """

    _zeroconf_prop_names = (
        'name', 'dns_name', 'fqdn', 'hostaddr', 'hostport',
    )
    _immutable_prop_names = (
        'model_name', 'serial_number',
    )
    _user_def_prop_names = (
        'display_name', 'always_connect', 'device_index',
        'auth_user', 'auth_pass',
    )
    _all_prop_names = _zeroconf_prop_names + _user_def_prop_names

    _events_ = ['on_change']
    def __init__(self, model_name: str, serial_number: str, **kwargs):
        self.__model_name = model_name
        self.__serial_number = serial_number
        for attr in self._all_prop_names:
            if attr not in kwargs:
                continue
            val = kwargs[attr]
            setattr(self, attr, val)
        if not self.display_name:
            self.display_name = self.name

        self.bind(**{attr:self.on_prop_change for attr in self._all_prop_names})
        self.bind(connection_state=self.on_connection_state)

    def on_connection_state(self, instance, value, **kwargs):
        self.active = value == ConnectionState.CONNECTED

    @property
    def model_name(self) -> str:
        """The model name of the device, taken from
        :class:`ServiceInfo.properties <zeroconf.ServiceInfo>`
        """
        return self.__model_name

    @property
    def serial_number(self) -> str:
        """The serial number of the device, taken from the
        service name ``hc500-XXXXXXXX`` where ``XXXXXXXX`` is the serial number
        """
        return self.__serial_number

    @property
    def id(self) -> str:
        """A unique id for the device using the :attr:`model_name`
        and :attr:`serial_number` attributes
        """
        return f'{self.model_name}-{self.serial_number}'

    @classmethod
    def get_id_for_service_info(cls, info: 'zeroconf.ServiceInfo') -> str:
        """Get the :attr:`id` attribute for the given :class:`zeroconf.ServiceInfo`
        """
        props = cls.get_props_from_service_info(info)
        return f'{props["model_name"]}-{props["serial_number"]}'

    @classmethod
    def get_props_from_service_info(cls, info: 'zeroconf.ServiceInfo') -> tp.Dict:
        """Build a dictionary of instance attributes from a :class:`zeroconf.ServiceInfo`
        """
        props = dict(
            name=info.get_name(),
            model_name=info.properties[b'model'].decode('UTF-8'),
            serial_number=info.get_name().split('-')[1],
            dns_name=info.server,
            fqdn=info.name,
            hostaddr=info.parsed_addresses()[0],
            hostport=info.port,
        )
        return props

    @classmethod
    def from_service_info(cls, info: 'zeroconf.ServiceInfo') -> 'DeviceConfig':
        """Construct an instance from a :class:`zeroconf.ServiceInfo`
        """
        kw = cls.get_props_from_service_info(info)
        return cls(**kw)

    def build_service_info(self) -> ServiceInfo:
        """Create a :class:`zeroconf.ServiceInfo` from the values in this instance
        """
        info = ServiceInfo(
            name=self.fqdn,
            type_='.'.join(self.fqdn.split('.')[1:]),
            server=self.dns_name,
            properties={b'model':bytes(self.model_name, 'UTF-8')},
            port=self.hostport,
            parsed_addresses=[self.hostaddr],
        )
        return info

    def update_from_service_info(self, info: 'zeroconf.ServiceInfo'):
        """Update instance attributes from a :class:`zeroconf.ServiceInfo`
        """
        props = self.get_props_from_service_info(info)
        for key, val in props.items():
            if key in self._immutable_prop_names:
                assert getattr(self, key) == val
                continue
            elif key in self._user_def_prop_names:
                continue
            setattr(self, key, val)

    def update_from_other(self, other: 'DeviceConfig'):
        """Update from another instance of :class:`DeviceConfig`
        """
        for attr in self._all_prop_names:
            val = getattr(other, attr)
            if attr == 'device_index' and val == -1:
                continue
            elif attr == 'display_name':
                if val == other.name:
                    continue
            elif attr == 'always_connect':
                val = self.always_connect or other.always_connect
            elif val is None:
                continue
            setattr(self, attr, val)

    def on_prop_change(self, instance, value, **kwargs):
        prop = kwargs['property']
        self.emit('on_change', instance, prop.name, value)

    def _serialize(self):
        d = {k:getattr(self, k) for k in self._all_prop_names}
        d.update({k:getattr(self, k) for k in self._immutable_prop_names})
        return d

    def __repr__(self):
        return f'<{self.__class__.__name__}: "{self}">'
    def __str__(self):
        return f'{self.model_name} - {self.serial_number}'

@jsonfactory.register
class JsonHandler(object):
    def cls_to_str(self, cls):
        if type(cls) is not type:
            cls = cls.__class__
        return '.'.join([cls.__module__, cls.__name__])
    def str_to_cls(self, s):
        for cls in [DeviceConfig]:
            if self.cls_to_str(cls) == s:
                return cls
    def encode(self, o):
        if isinstance(o, DeviceConfig):
            d = o._serialize()
            d['__class__'] = self.cls_to_str(o)
            return d
    def decode(self, d):
        if '__class__' in d:
            cls = self.str_to_cls(d['__class__'])
            if cls is not None:
                return cls(**d)
        return d
