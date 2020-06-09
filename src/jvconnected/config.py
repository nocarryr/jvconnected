from loguru import logger
import os
import sys
import asyncio
from pathlib import Path
import typing as tp

from pydispatch import Dispatcher
from pydispatch.properties import Property, DictProperty, ListProperty
import jsonfactory


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

class Config(Dispatcher):
    """Configuration storage

    This object provides a dict-like interface and stores the configuration data
    automatically when it changes. The stored config data is read on initialization.

    Arguments:
        filename (:class:`pathlib.Path`, optional): The configuration filename. If not provided,
            the :attr:`DEFAULT_FILENAME` is used

    Attributes:
        DEFAULT_FILENAME (:class:`pathlib.Path`): Platform-dependent default filename
            (``<config_dir>/jvconnected/config.json``). Where ``<config_dir>``
            is chosen in :func:`get_config_dir`

    """
    data = DictProperty()
    DEFAULT_FILENAME: 'pathlib.Path' = get_config_dir('jvconnected') / 'config.json'
    def __init__(self, filename: tp.Optional['pathlib.Path'] = None):
        if filename is None:
            filename = self.DEFAULT_FILENAME
        logger.info(f'Config using filename: {filename}')
        self.filename = filename
        self._setitem_lock = DumbLock()
        self.read()
        self.bind(data=self.on_data_changed)

    @property
    def devices(self):
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

        """
        if device.id in self.devices:
            with self._setitem_lock:
                self.devices[device.id].update_from_other(device)
            self.write()
        else:
            self.devices[device.id] = device
            device.bind(on_change=self.on_device_prop_change)
        return self.devices[device.id]

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
        p = self.filename.parent
        if not p.exists():
            p.mkdir(mode=0o700, parents=True)
        self.filename.write_text(jsonfactory.dumps(self.data, indent=2))

    def on_data_changed(self, instance, value, **kwargs):
        if self._setitem_lock.locked():
            return
        self.write()

    def on_device_prop_change(self, instance, prop_name, value, **kwargs):
        self.write()

class DeviceConfig(Dispatcher):
    """Configuration data for a device

    Properties:
        name (str): The device name, taken from :meth:`zeroconf.ServiceInfo.get_name`
        dns_name (str): The fully qualified name for the service host, taken from
            :class:`ServiceInfo.server <zeroconf.ServiceInfo>`
        fqdn (str): The fully qualified service name, taken from
            :class:`ServiceInfo.name <zeroconf.ServiceInfo>`
        hostaddr (str): The IPv4 address (in string form)
        hostport (int): The service port
        auth_user (str): Username to use with authentication
        auth_pass (str): Password to use with authentication

    :Events:
        .. event:: on_change(instance, prop_name, value)

            Fired when any property value changes

    """
    name = Property('')
    dns_name = Property('')
    fqdn = Property('')
    hostaddr = Property('')
    hostport = Property(80)
    auth_user = Property(None)
    auth_pass = Property(None)

    _all_prop_names = (
        'name', 'dns_name', 'fqdn',
        'hostaddr', 'hostport', 'auth_user', 'auth_pass',
    )
    _immutable_prop_names = (
        'model_name', 'serial_number',
    )

    _events_ = ['on_change']
    def __init__(self, model_name: str, serial_number: str, **kwargs):
        self.__model_name = model_name
        self.__serial_number = serial_number
        for attr in self._all_prop_names:
            if attr not in kwargs:
                continue
            val = kwargs[attr]
            setattr(self, attr, val)

        self.bind(**{attr:self.on_prop_change for attr in self._all_prop_names})

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

    def update_from_service_info(self, info: 'zeroconf.ServiceInfo'):
        """Update instance attributes from a :class:`zeroconf.ServiceInfo`
        """
        props = self.get_props_from_service_info(info)
        for key, val in props.items():
            if key in self._immutable_prop_names:
                assert getattr(self, key) == val
                continue
            setattr(self, key, val)

    def update_from_other(self, other: 'DeviceConfig'):
        """Update from another instance of :class:`DeviceConfig`
        """
        for attr in self._all_prop_names:
            val = getattr(other, attr)
            if val is None:
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
