from __future__ import annotations
import typing as tp
from loguru import logger
import asyncio
from enum import Enum, auto

from pydispatch import Dispatcher, Property, DictProperty, ListProperty

from jvconnected.common import ConnectionState
from jvconnected.devicepreview import JpegSource
from jvconnected.client import Client, ClientError
from jvconnected.utils import NamedQueue

class Device(Dispatcher):
    """A Connected Cam device

    Arguments:
        hostaddr (str): The network host address
        auth_user (str): Api username
        auth_pass (str): Api password
        id_ (str): Unique string id
        hostport (int, optional): The network host port
    """
    model_name: str|None = Property()
    """Model name of the device"""

    serial_number: str|None = Property()
    """The device serial number"""

    resolution: str|None = Property()
    """Current output resolution in string format"""

    api_version: str|None = Property()
    """Api version supported by the device"""

    device_index: int = Property(0)
    """The device index"""

    connected: bool = Property(False)
    """``True`` communicating with the device"""

    connection_state: ConnectionState = Property(ConnectionState.UNKNOWN)
    """The device's :class:`~.common.ConnectionState`
    """

    error: bool = Property(False)
    """Becomes ``True`` when a communication error occurs"""

    parameter_groups: tp.Dict[str, 'ParameterGroup'] = DictProperty()
    """Container for :class:`ParameterGroup` instances"""

    def on_client_error(self, instance: 'Device', exc: Exception):
        """Fired when an error is caught by the http client.

        Arguments:
            instance: The device instance
            exc: The :class:`Exception` that was raised
        """

    _events_ = ['on_client_error']
    def __init__(self, hostaddr:str, auth_user:str, auth_pass:str, id_: str, hostport: int = 80):
        self.hostaddr = hostaddr
        self.hostport = hostport
        self.auth_user = auth_user
        self.auth_pass = auth_pass
        self._devicepreview = None
        self.__id = id_
        self.client = Client(hostaddr, auth_user, auth_pass, hostport)
        self._poll_fut = None
        self._poll_enabled = False
        self._first_poll_evt = asyncio.Event()
        self._first_poll_exc = None
        self._is_open = False
        for cls in PARAMETER_GROUP_CLS:
            self._add_param_group(cls)
        attrs = ['model_name', 'serial_number', 'resolution', 'api_version']
        self.bind(**{attr:self.on_attr for attr in attrs})
        self.request_queue = NamedQueue(maxsize=16)

    @property
    def id(self): return self.__id

    @property
    def devicepreview(self) -> JpegSource:
        """Instance of :class:`jvconnected.devicepreview.JpegSource` to
        acquire real-time jpeg images
        """
        pv = self._devicepreview
        if pv is None:
            pv = self._devicepreview = JpegSource(self)
        return pv

    def _add_param_group(self, cls, **kwargs):
        pg = cls(self, **kwargs)
        assert pg.name not in self.parameter_groups
        self.parameter_groups[pg.name] = pg
        return pg

    def __getattr__(self, key):
        if hasattr(self, 'parameter_groups') and key in self.parameter_groups:
            return self.parameter_groups[key]
        raise AttributeError(key)

    async def open(self):
        """Begin communication with the device
        """
        if self._is_open:
            return
        await self.client.open()
        await self._get_system_info()
        self._poll_enabled = True
        self._poll_fut = asyncio.ensure_future(self._poll_loop())
        await self._first_poll_evt.wait()
        if self._first_poll_exc is not None:
            await self._poll_fut
            raise self._first_poll_exc
        self._is_open = True
        self.connected = True

    async def close(self):
        """Stop communication and close all connections
        """
        if not self._is_open:
            return
        self._is_open = False
        self._poll_enabled = False
        logger.debug(f'{self} closing...')
        pv = self._devicepreview
        if pv is not None and pv.encoding:
            await pv.release()

        await self._poll_fut
        for pg in self.parameter_groups.values():
            await pg.close()
        await self.client.close()
        logger.debug(f'{self} closed')
        self.connected = False

    async def _get_system_info(self):
        """Request basic device info
        """
        resp = await self.client.request('GetSystemInfo')
        data = resp['Data']
        self.model_name = data['Model']
        self.api_version = data['ApiVersion']
        self.serial_number = data['Serial']

    @logger.catch
    async def _poll_loop(self):
        """Periodically request status updates
        """
        async def get_queue_item(timeout=.5):
            try:
                item = await asyncio.wait_for(self.request_queue.get(), timeout)
            except asyncio.TimeoutError:
                item = None
            return item

        async def do_poll(item):
            if item is not None:
                command, params = item.item
                logger.debug(f'tx: {command}, {params}')
                await self.client.request(command, params)
                await self._request_cam_status(short=True)
                self.request_queue.task_done()
            else:
                await self._request_cam_status(short=False)

        first_poll = True
        while self._poll_enabled:
            if first_poll:
                timeout = .1
            else:
                timeout = .5
            item = await get_queue_item(timeout=timeout)
            try:
                await do_poll(item)
            except ClientError as exc:
                if first_poll:
                    self._first_poll_exc = exc
                    self._first_poll_evt.set()
                else:
                    asyncio.ensure_future(self._handle_client_error(exc))
                break
            if first_poll:
                self._first_poll_evt.set()
            first_poll = False

    async def _request_cam_status(self, short=True):
        """Request all available camera parameters

        Called by :meth:`_poll_loop`. The response data is used to update the
        :class:`ParameterGroup` instances in :attr:`parameter_groups`.
        """
        resp = await self.client.request('GetCamStatus')
        data = resp['Data']
        # coros = []
        for pg in self.parameter_groups.values():
            # coros.append(pg.parse_status_response(data))
            try:
                pg.parse_status_response(data)
            except Exception as exc:
                import json
                jsdata = json.dumps(data, indent=2)
                logger.debug(f'data: {jsdata}')
                logger.error(exc)
                raise

        if not short:
            await self.parameter_groups['ntp']._update()
            await self.parameter_groups['preset_zoom']._update()

    @logger.catch
    async def _handle_client_error(self, exc: Exception):
        logger.warning(f'caught client error: {exc}')
        self.error = True
        self.emit('on_client_error', self, exc)

    async def send_web_button(self, kind: str, value: str):
        await self.queue_request('SetWebButtonEvent', {'Kind':kind, 'Button':value})

    async def queue_request(self, command: str, params=None):
        """Enqueue a command to be sent in the :meth:`_poll_loop`
        """
        item = self.request_queue.create_item(command, (command, params))
        await self.request_queue.put(item)

    def on_attr(self, instance, value, **kwargs):
        prop = kwargs['property']
        logger.info(f'{prop.name} = {value}')

    def __repr__(self):
        return f'<{self.__class__.__name__}: "{self}">'
    def __str__(self):
        return f'{self.model_name} ({self.hostaddr})'

class ParameterGroup(Dispatcher):
    """A logical group of device parameters

    Arguments:
        device (Device): The parent :class:`Device`

    Attributes:
        _prop_attrs (list): A list of tuples to map instance attributes to the
            values returned by the api data from :meth:`Device._request_cam_status`
        _optional_api_keys (list): A list of any api values that may not be
            available. If the parameter is missing during :meth:`parse_status_response`,
            it will be allowed to fail if present in this list.
    """
    name: str = Property('')
    """The group name"""

    _NAME = None
    _prop_attrs = []
    _optional_api_keys = []
    def __init__(self, device: Device, **kwargs):
        self.device = device
        if 'name' in kwargs:
            name = kwargs['name']
        elif self._NAME is not None:
            name = self._NAME
        else:
            name = self.__class__.__name__
        self.name = name
        self.bind(**{prop:self.on_prop for prop, _ in self._prop_attrs})

    def on_prop(self, instance, value, **kwargs):
        """Debug method
        """
        prop = kwargs['property']
        prop_value = getattr(self, prop.name)
        logger.info(f'{self}.{prop.name} = {prop_value}')

    def iter_api_key(self, api_key):
        if isinstance(api_key, str):
            for key in api_key.split('.'):
                if len(key):
                    yield key
        else:
            yield from api_key

    def drill_down_api_dict(self, api_key, data):
        """Walk down nested dict values and return the final value

        Arguments:
            api_key: Either a sequence or a string.  If the string is separated
                by periods (``.``) it will be split by :meth:`iter_api_key`
            data (dict): The response data from :meth:`parse_status_response`

        """
        result = data
        for key in self.iter_api_key(api_key):
            try:
                result = result[key]
            except KeyError:
                if api_key in self._optional_api_keys:
                    return None
        return result

    def parse_status_response(self, data):
        """Parse the response from :meth:`Device._request_cam_status`

        """
        for prop_attr, api_key in self._prop_attrs:
            value = self.drill_down_api_dict(api_key, data)
            self.set_prop_from_api(prop_attr, value)

    def set_prop_from_api(self, prop_attr: str, value):
        if isinstance(value, str):
            value = value.strip(' ')
        setattr(self, prop_attr, value)

    async def close(self):
        """Perform any cleanup actions before disconnecting
        """
        pass

    def __repr__(self):
        return f'<{self.__class__.__name__}: "{self}">'
    def __str__(self):
        return self.name

class MenuChoices(Enum):
    """Values used in :meth:`CameraParams.send_menu_button`
    """
    DISPLAY = auto()    #: DISPLAY
    STATUS = auto()     #: STATUS
    MENU = auto()       #: MENU
    CANCEL = auto()     #: CANCEL
    SET = auto()        #: SET
    UP = auto()         #: UP
    DOWN = auto()       #: DOWN
    LEFT = auto()       #: LEFT
    RIGHT = auto()      #: RIGHT

class CameraParams(ParameterGroup):
    """Basic camera parameters
    """
    _NAME = 'camera'
    status: str|None = Property()
    """Camera status. One of
    ``['NoCard', 'Stop', 'Standby', 'Rec', 'RecPause']``
    """

    menu_status: bool = Property(False)
    """``True`` if the camera menu is open"""

    mode: str|None = Property()
    """Camera record / media mode. One of
    ``['Normal', 'Pre', 'Clip', 'Frame', 'Interval', 'Variable']``
    """

    timecode: str|None = Property()
    """The current timecode value"""

    _prop_attrs = [
        ('status', 'Camera.Status'),
        ('mode', 'Camera.Mode'),
        ('timecode', 'Camera.TC'),
        ('menu_status', 'Camera.MenuStatus')
    ]

    async def send_menu_button(self, value: MenuChoices):
        """Send a menu button event

        Arguments:
            value: The menu button type as a member of :class:`MenuChoices`
        """
        param = value.name.title()
        await self.device.send_web_button('Menu', param)

    def set_prop_from_api(self, prop_attr, value):
        if prop_attr == 'menu_status':
            if isinstance(value, str):
                value = 'On' in value
        super().set_prop_from_api(prop_attr, value)

    def on_prop(self, instance, value, **kwargs):
        prop = kwargs['property']
        if prop.name == 'timecode':
            return
        super().on_prop(instance, value, **kwargs)

class NTPParams(ParameterGroup):
    """NTP parameters
    """
    _NAME = 'ntp'

    address: str = Property('')
    """The NTP server address (IP or URL)"""

    tc_sync: bool = Property(False)
    """True if using NTP for timecode"""

    syncronized: bool = Property(False)
    """Whether the device is syncronized to the :attr:`server <address>`"""

    sync_master: bool = Property(False)
    """True if the device is being used as a TC and sync (Genlock) master [#fsync_master]_
    """

    def __init__(self, device: Device, **kwargs):
        super().__init__(device, **kwargs)
        props = ['address', 'tc_sync', 'syncronized', 'sync_master']
        self.bind(**{k:self.on_prop for k in props})

    async def _update(self):
        c = self.device.client
        resp = await c.request('GetNTPStatus')
        data = resp['Data']
        self.address = data['Address']
        self.tc_sync = data.get('TcSync', '') == 'On'
        status = data['Status']
        self.syncronized = status == 'Syncronized'
        self.sync_master = status == 'Master'

    async def set_address(self, address: str):
        """Set the NTP server :attr:`address`
        """
        params = {'Address':address}
        await self.device.queue_request('SetNTPServer', params)


class BatteryState(Enum):
    """Values used for :attr:`BatteryParams.state`
    """
    UNKNOWN = auto()    #: UNKNOWN
    ERROR = auto()      #: ERROR
    NO_BATTERY = auto() #: NO_BATTERY
    ON_BATTERY = auto() #: ON_BATTERY
    CHARGING = auto()   #: CHARGING
    CHARGED = auto()    #: CHARGED

class BatteryParams(ParameterGroup):
    """Battery Info
    """
    _NAME = 'battery'
    info_str: str|None = Property()
    """Type of value given to :attr:`value_str`. One of
    ``['Time', 'Capacity', 'Voltage']``
    """
    level_str: str|None = Property()
    """Numeric value indicating various charging/discharging states"""

    value_str: str = Property('0')
    """One of remaining time (in minutes), capacity (percent)
    or voltage (x10) depending on the value of :attr:`info_str`
    """

    state: BatteryState = Property(BatteryState.UNKNOWN)
    """The current battery state"""

    level = Property(1.)
    minutes: int = Property(-1)
    """Minutes remaining until full (while charging) or battery
    runtime (while on-battery). If unavailable, this will be ``-1``
    """

    percent: int = Property(-1)
    """Capacity remaining. If unavailable, this will be ``-1``"""

    voltage: float = Property(-1)
    """Battery voltage. If unavailable, this will be ``-1``"""

    _prop_attrs = [
        ('info_str', 'Battery.Info'),
        ('level_str', 'Battery.Level'),
        ('value_str', 'Battery.Value'),
    ]

    _state_to_level_map = {
        BatteryState.NO_BATTERY: [0],
        BatteryState.ERROR: [2],
        BatteryState.ON_BATTERY: [3, 4, 5, 6, 7, 8, 9],
        BatteryState.CHARGING: [10, 11, 12, 14],
        BatteryState.CHARGED: [1, 13],

    }
    # Flatten the value lists from _state_to_level_map and use them as keys
    _level_to_state_map = {v:k for k,l in _state_to_level_map.items() for v in l}

    def __init__(self, device: Device, **kwargs):
        super().__init__(device, **kwargs)
        self.bind(**{k:self._fooprop for k in ['state', 'level', 'minutes', 'percent', 'voltage']})
    def _fooprop(self, instance, value, **kwargs):
        prop = kwargs['property']
        logger.success(f'{prop.name} = "{value!r}"')
    def on_prop(self, instance, value, **kwargs):
        prop = kwargs['property']
        if prop.name == 'info_str':
            if value == 'Time':
                self.minutes = int(self.value_str)
                self.percent = -1
                self.voltage = -1
            elif value == 'Capacity':
                self.minutes = -1
                self.percent = int(self.value_str)
                self.voltage = -1
            elif value == 'Voltage':
                self.minutes = -1
                self.percent = -1
                self.voltage = float(self.value_str) / 10
        elif prop.name == 'level_str':
            value = int(value)
            self.state = self._level_to_state_map.get(value, BatteryState.UNKNOWN)
            if value in range(5, 9):
                self.level = (value - 4) / 4
            elif value in range(10, 14):
                self.level = (value - 9) / 4
        elif prop.name == 'value_str':
            if self.info_str == 'Time':
                self.minutes = int(value)
            elif self.info_str == 'Capacity':
                self.percent = int(value)
            elif self.info_str == 'Voltage':
                self.voltage = float(value) / 10
        super().on_prop(instance, value, **kwargs)


class MasterBlackDirection(Enum):
    """Values used for :meth:`ExposureParams.seesaw_master_black`
    """
    Up = auto()     #: Up
    Down = auto()   #: Down
    Stop = auto()   #: Stop


class ExposureParams(ParameterGroup):
    """Exposure parameters
    """
    _NAME = 'exposure'
    mode: str|None = Property()
    """Exposure mode. One of
    ``['Auto', 'Manual', 'IrisPriority', 'ShutterPriority']``
    """

    iris_mode: str|None = Property()
    """Iris mode. One of ``['Manual', 'Auto', 'AutoAELock']``"""

    iris_fstop: str|None = Property()
    """Character string for iris value"""

    iris_pos: int|None = Property()
    """Iris position (0-255)"""

    gain_mode: str|None = Property()
    """Gain mode. One of
    ``['ManualL', 'ManualM', 'ManualH', 'AGC', 'AlcAELock', 'LoLux', 'Variable']``
    """

    gain_value: str|None = Property()
    """Gain value"""

    gain_pos: int = Property(0)
    """The :attr:`gain_value` as an integer from -6 to 24"""

    shutter_mode: str|None = Property()
    """Shutter mode. One of
    ``['Off', 'Manual', 'Step', 'Variable', 'Eei']``
    """

    shutter_value: str|None = Property()
    """Shutter value"""

    master_black: str|None = Property()
    """MasterBlack value"""

    master_black_pos: int = Property(0)
    """MasterBlack value as an integer from -50 to 50"""

    master_black_moving: bool = Property(False)
    """True if MasterBlack is being adjusted with the :meth:`seesaw_master_black`
    method
    """

    master_black_speed: int = Property(0)
    """Current MasterBlack movement speed from -8 (down) to +8 (up) where
    0 indicates no movement.
    """

    _prop_attrs = [
        ('mode', 'Exposure.Status'),
        ('iris_mode', 'Iris.Status'),
        ('iris_fstop', 'Iris.Value'),
        ('iris_pos', 'Iris.Position'),
        ('gain_mode', 'Gain.Status'),
        ('gain_value', 'Gain.Value'),
        ('shutter_mode', 'Shutter.Status'),
        ('shutter_value', 'Shutter.Value'),
        ('master_black', 'MasterBlack.Value'),
    ]
    _optional_api_keys = ['Exposure.Status']

    async def set_auto_iris(self, state: bool):
        """Set iris mode

        Arguments:
            state (bool): If True, enable auto iris mode, otherwise set to manual

        """
        value = {True:'Auto', False:'Manual'}.get(state)
        await self.device.send_web_button('Iris', value)

    async def set_auto_gain(self, state: bool):
        """Set AGC mode

        Arguments:
            state (bool): If True, enable auto gain mode, otherwise set to manual

        """
        value = {True:'Auto', False:'Manual'}.get(state)
        await self.device.send_web_button('Gain', value)

    async def set_iris_pos(self, value: int):
        """Set the iris position value

        Parameters:
            value (int): The iris value from 0 (closed) to 255 (open)

        """
        if value > 255:
            value = 255
        elif value < 0:
            value = 0
        params = {'Kind':'IrisBar', 'Position':value}
        await self.device.queue_request('SetWebSliderEvent', params)

    async def increase_iris(self):
        """Increase (open) iris
        """
        await self.adjust_iris(True)

    async def decrease_iris(self):
        """Decrease (close) iris
        """
        await self.adjust_iris(False)

    async def adjust_iris(self, direction: bool):
        """Increment (open) or decrement (close) iris

        Parameters:
            direction (bool): If True, increment, otherwise decrement

        """
        value = {True:'Open1', False:'Close1'}.get(direction)
        await self.device.send_web_button('Iris', value)

    async def increase_gain(self):
        """Increase gain
        """
        await self.adjust_gain(True)

    async def decrease_gain(self):
        """Decrease gain
        """
        await self.adjust_gain(False)

    async def adjust_gain(self, direction: bool):
        """Increment or decrement gain

        Parameters:
            direction (bool): If True, increment, otherwise decrement

        """
        # TODO: In manual mode (using the L,M,H switch), this adjusts the
        #       setting for whichever of the three preset gain positions is active
        # if self.gain_mode != 'Variable':
        #     await self.device.send_web_button('Gain', 'Variable')
        value = {True:'Up1', False:'Down1'}.get(direction)
        await self.device.send_web_button('Gain', value)

    async def increase_master_black(self):
        """Increase master black
        """
        await self.adjust_master_black(True)

    async def decrease_master_black(self):
        """Decrease master black
        """
        await self.adjust_master_black(False)

    async def adjust_master_black(self, direction: bool):
        """Increment or decrement master black

        Parameters:
            direction (bool): If True, increment, otherwise decrement

        """
        value = {True:'Up1', False:'Down1'}.get(direction)
        await self.device.send_web_button('MasterBlack', value)

    async def seesaw_master_black(self, direction: MasterBlackDirection|str|int, speed: int):
        """Start or stop MasterBlack movement

        Arguments:
            direction: Either a :class:`MasterBlackDirection` member,
                the name as str, or the integer value of one of the members
            speed (int): The movement speed from 0 to 8 (0 stops movement)
        """
        if isinstance(direction, str):
            direction = getattr(MasterBlackDirection, direction)
        elif isinstance(direction, int):
            direction = MasterBlackDirection(direction)
        params = {
            'Kind':'MasterBlackSeesaw',
            'Direction':direction.name,
            'Speed':speed,
        }
        await self.device.queue_request('SeesawSwitchOperation', params)
        if direction == MasterBlackDirection.Stop:
            speed = 0
        elif direction == MasterBlackDirection.Down:
            speed = -speed
        self.master_black_speed = speed
        self.master_black_moving = speed != 0

    def set_prop_from_api(self, prop_attr, value):
        if prop_attr == 'iris_fstop':
            value = value.strip(' ')
            if value != 'CLOSE':
                if value.startswith('AF'):
                    value = value.lstrip('AF')
                elif value.startswith('F'):
                    value = value.lstrip('F')
                value = float(value)
        super().set_prop_from_api(prop_attr, value)

    def on_prop(self, instance, value, **kwargs):
        prop = kwargs['property']
        if prop.name == 'gain_value':
            gain_pos = value.rstrip('dB').lstrip('A')
            self.gain_pos = int(gain_pos)
            logger.debug(f'{self}.gain_pos: {self.gain_pos}')
        elif prop.name == 'master_black':
            if len(value.strip(' ')):
                self.master_black_pos = int(value)
                logger.debug(f'{self}.master_black_pos: {self.master_black_pos}')
        super().on_prop(instance, value, **kwargs)


class FocusMode(Enum):
    """Values used for :attr:`LensParams.focus_mode`
    """
    Unknown = auto()
    AFFace = auto()
    AF = auto()         #: Auto focus
    MFOnePush = auto()
    MF = auto()         #: Manual focus
    MFFace = auto()

class ZoomDirection(Enum):
    """Values used for :meth:`LensParams.seesaw_zoom`
    """
    Wide = auto()   #: Wide
    Tele = auto()   #: Telephoto
    Stop = auto()   #: Stop

class FocusDirection(Enum):
    """Values used for :meth:`LensParams.seesaw_focus`
    """
    Near = auto()   #: Near
    Far = auto()    #: Far
    Stop = auto()   #: Stop

class LensParams(ParameterGroup):
    """Lens Parameters
    """
    _NAME = 'lens'

    focus_mode: FocusMode = Property(FocusMode.Unknown)
    """The current focus mode"""

    focus_value: str|None = Property()
    """Character string for focus value"""

    zoom_pos: int = Property(0)
    """Zoom position from 0 to 499"""

    zoom_value: str|None = Property()
    """Character string for zoom value"""

    focus_speed: int = Property(0)
    """Current focus speed from -8 (near) to +8 (far) where
    0 indicates no movement
    """

    zoom_speed: int = Property(0)
    """Current zoom speed from -8 (wide) to +8 (tele) where
    0 indicates no movement
    """

    focusing: bool = Property(False)
    """True while focus is moving"""

    zooming: bool = Property(False)
    """True while zoom is moving"""

    _prop_attrs = [
        ('focus_mode', 'Focus.Status'),
        ('focus_value', 'Focus.Value'),
        ('zoom_pos', 'Zoom.Position'),
        ('zoom_value', 'Zoom.DisplayValue')
    ]

    _focus_range_feet = (0.3, 328)

    async def set_focus_mode(self, mode):
        """Set focus mode

        Arguments:
            mode: A :class:`FocusMode` enum member, its string name or integer
                value
        """
        if isinstance(mode, str):
            mode = getattr(FocusMode, mode)
        elif isinstance(mode, int):
            mode = FocusMode(mode)
        else:
            assert isinstance(mode, FocusMode)
        if 'AF' in mode.name:
            value = 'Auto'
        elif 'MF' in mode.name:
            value = 'Manual'
        else:
            raise ValueError(f'Cannot set focus mode to "{mode}"')
        await self.device.send_web_button('Focus', value)

    async def set_zoom_position(self, value):
        """Set the zoom position

        Arguments:
            value (int): The zoom position from 0 to 499
        """
        params = {'Kind':'ZoomBar', 'Position':value}
        await self.device.queue_request('SetWebSliderEvent', params)

    async def focus_near(self, speed):
        """Begin focusing "near"

        Arguments:
            speed (int): Focus speed from 0 to 8 (0 stops movement)
        """
        await self.seesaw_focus(FocusDirection.Near, speed)

    async def focus_far(self, speed):
        """Begin focusing "far"

        Arguments:
            speed (int): Focus speed from 0 to 8 (0 stops movement)
        """
        await self.seesaw_focus(FocusDirection.Far, speed)

    async def focus_stop(self):
        """Stop focus movement
        """
        await self.seesaw_focus(FocusDirection.Stop, 0)

    async def focus_push_auto(self):
        """Focus PushAuto
        """
        await self.device.send_web_button('Focus', 'PushAuto')

    async def zoom_wide(self, speed):
        """Begin zooming "wide" (or "out")

        Arguments:
            speed (int): Zoom speed from 0 to 8 (0 stops movement)
        """
        await self.seesaw_zoom(ZoomDirection.Wide, speed)

    async def zoom_tele(self, speed):
        """Begin zooming "tele" (or "in")

        Arguments:
            speed (int): Zoom speed from 0 to 8 (0 stops movement)
        """
        await self.seesaw_zoom(ZoomDirection.Tele, speed)

    async def zoom_stop(self):
        """Stop zoom movement
        """
        await self.seesaw_zoom(ZoomDirection.Stop, 0)

    async def seesaw_focus(self, direction, speed):
        """Start or stop focus movement

        Arguments:
            direction: Either a :class:`FocusDirection` member, the name as str,
                or the integer value of one of the members
            speed (int): The focus speed from 0 to 8 (0 stops movement)
        """
        if isinstance(direction, str):
            direction = getattr(FocusDirection, direction)
        elif isinstance(direction, int):
            direction = FocusDirection(direction)
        params = {
            'Kind':'FocusSeesaw',
            'Direction':direction.name,
            'Speed':speed,
        }
        await self.device.queue_request('SeesawSwitchOperation', params)
        if direction == FocusDirection.Stop:
            speed = 0
        elif direction == FocusDirection.Near:
            speed = -speed
        self.focus_speed = speed
        self.focusing = speed != 0

    async def seesaw_zoom(self, direction, speed):
        """Start or stop zoom movement

        Arguments:
            direction: Either a :class:`ZoomDirection` member, the name as str,
                or the integer value of one of the members
            speed (int): The zoom speed from 0 to 8 (0 stops movement)
        """
        if isinstance(direction, str):
            direction = getattr(ZoomDirection, direction)
        elif isinstance(direction, int):
            direction = ZoomDirection(direction)
        params = {
            'Kind':'ZoomSeesaw',
            'Direction':direction.name,
            'Speed':speed,
        }
        await self.device.queue_request('SeesawSwitchOperation', params)
        if direction == ZoomDirection.Stop:
            speed = 0
        elif direction == ZoomDirection.Wide:
            speed = -speed
        self.zoom_speed = speed
        self.zooming = speed != 0

    def on_prop(self, instance, value, **kwargs):
        prop = kwargs['property']
        if prop.name == 'focus_mode':
            if not isinstance(value, FocusMode):
                if hasattr(FocusMode, value):
                    value = getattr(FocusMode, value)
                else:
                    value = FocusMode.Unknown
        super().on_prop(instance, value, **kwargs)

class ZoomPreset(Dispatcher):
    """Preset data for :class:`PresetZoomParams`
    """

    name: str = Property('')
    """The preset name (one of ``["A", "B", "C"]``)"""

    value: int = Property(-1)
    """The :attr:`~LensParams.zoom_pos` stored in the preset.
    (``-1`` indicates no data is stored)
    """

    is_active: bool = Property(False)
    """Flag indicating if the current :attr:`~LensParams.zoom_pos`
    matches the preset :attr:`value`
    """

    def __init__(self, name: str, value: int = -1):
        self.name = name
        self.value = value
        self.bind(**{prop:self._on_prop for prop in ['value', 'is_active']})

    def _on_prop(self, instance, value, **kwargs):
        prop = kwargs['property']
        logger.info(f'ZoomPreset {self.name}: {prop.name} = {value}')

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}: {self}>'

    def __str__(self) -> str:
        suffix = ' (active)' if self.is_active else ''
        return f'{self.name} {self.value}{suffix}'


class PresetZoomParams(ParameterGroup):
    """Preset zoom
    """
    _NAME = 'preset_zoom'

    presets: tp.Dict[str, ZoomPreset] = DictProperty()
    """Mapping of :class:`ZoomPreset` objects stored by their
    :attr:`~ZoomPreset.name`
    """

    def __init__(self, device: Device, **kwargs):
        for key in 'ABC':
            p = ZoomPreset(key)
            p.bind(value=self.on_preset_value)
            self.presets[key] = p
        super().__init__(device, **kwargs)
        self.device.lens.bind(zoom_pos=self.on_camera_zoom_changed)

    async def _update(self):
        c = self.device.client
        resp = await c.request('GetPresetZoomPosition')
        data = resp['Data']
        for key, val in data.items():
            preset = self.presets[key]
            preset.value = val

    async def set_preset(self, name: str, value: int|None = None):
        """Set zoom position for the given preset

        Arguments:
            name: The :attr:`~ZoomPreset.name` of preset to store
            value: The zoom position in the range of ``0 - 499``.
                If not given, the current :attr:`~LensParams.zoom_pos`
                is used.
        """
        if value is None:
            value = self.device.lens.zoom_pos
        params = {'ID': name, 'Position': value}
        await self.device.queue_request('SetPresetZoomPosition', params)

    async def recall_preset(self, name: str):
        """Recall the preset by the given :attr:`~ZoomPreset.name`
        """
        p = self.presets[name]
        if p.value < 0:
            return
        params = {'Position': p.value}
        await self.device.queue_request('SetZoomCtrl', params)

    async def clear_preset(self, name: str):
        """Delete the value for the given preset
        """
        await self.set_preset(name, -1)

    def on_preset_value(self, instance, value, **kwargs):
        pos = self.device.lens.zoom_pos
        instance.is_active = value == pos

    def on_camera_zoom_changed(self, instance, value, **kwargs):
        for p in self.presets.values():
            p.is_active = p.value == value


class PaintParams(ParameterGroup):
    """Paint parameters
    """
    _NAME = 'paint'

    white_balance_mode: str = Property()
    """Current white balance mode. One of
    ``['Preset', 'A', 'B', 'Faw', 'FawAELock',
    'Faw', 'Awb', 'OnePush', '3200K', '5600K', 'Manual']``
    """

    color_temp: str|None = Property()
    """White balance value"""

    red_scale: int = Property(64)
    """Total range for WB red paint (0-64)"""

    red_pos: int|None = Property()
    """Current position of :attr:`red_value` (WB red paint) in the range of 0-64
    """

    red_value: str|None = Property()
    """Character string for WB red paint value"""

    red_normalized: int = Property(0)
    """:attr:`red_pos` from -31 to +31"""

    blue_scale: int = Property(64)
    """Total range for WB blue paint (0-64)"""

    blue_pos: int|None = Property()
    """Current position of :attr:`blue_value` (WB blue paint) in the range of 0-64
    """

    blue_value: str|None = Property()
    """Character string for WB blue paint value"""

    blue_normalized: int = Property(0)
    """:attr:`blue_pos` from -31 to +31"""

    detail: str|None = Property()
    """Detail value as string"""

    detail_pos: int = Property(0)
    """:attr:`detail` as an integer from -10 to +10"""

    _prop_attrs = [
        ('white_balance_mode', 'Whb.Status'),
        ('color_temp', 'Whb.Value'),
        ('red_scale', 'Whb.WhPRScale'),
        ('red_pos', 'Whb.WhPRPosition'),
        ('red_value', 'Whb.WhPRValue'),
        ('blue_scale', 'Whb.WhPBScale'),
        ('blue_pos', 'Whb.WhPBPosition'),
        ('blue_value', 'Whb.WhPBValue'),
        ('detail', 'Detail.Value'),
    ]

    async def set_white_balance_mode(self, mode: str):
        """Set white balance mode

        Arguments:
            mode (str): The mode to set. Possible values are
                ``['Faw', 'Preset', 'A', 'B', 'Adjust', 'WhPaintRP', 'WhPaintRM',
                'WhPaintBP', 'WhPaintBM', 'Awb', '3200K', '5600K', 'Manual']``
        """
        await self.device.send_web_button('Whb', mode)

    async def set_red_pos(self, red: int):
        """Set red value

        Arguments:
            red (int): Red value in range -31 to +31

        """
        red += self.red_scale // 2
        await self.set_wb_pos_raw(red, self.blue_pos)

    async def set_blue_pos(self, blue: int):
        """Set blue value

        Arguments:
            blue (int): Blue value in range -31 to +31

        """
        blue += self.blue_scale // 2
        await self.set_wb_pos_raw(self.red_pos, blue)

    async def set_wb_pos(self, red: int, blue: int):
        """Set red/blue values

        Arguments:
            red (int): Red value in range -31 to +31
            blue (int): Blue value in range -31 to +31

        """
        red += self.red_scale // 2
        blue += self.blue_scale // 2
        await self.set_wb_pos_raw(red, blue)

    async def set_wb_pos_raw(self, red: int, blue: int):
        """Set raw values for red/blue

        Arguments:
            red (int): Red value in range 0 to 64
            blue (int): Blue value in range 0 to 64

        """
        if red > 64:
            red = 64
        elif red < 0:
            red = 0
        if blue > 64:
            blue = 64
        elif blue < 0:
            blue = 0
        params = {
            'Kind':'WhPaintRB',
            'XPosition':blue,
            'YPosition':red,
        }
        self.red_pos = red
        self.blue_pos = blue
        await self.device.queue_request('SetWebXYFieldEvent', params)

    async def increase_detail(self):
        """Increment detail value
        """
        await self.adjust_detail(True)

    async def decrease_detail(self):
        """Decrease detail value
        """
        await self.adjust_detail(False)

    async def adjust_detail(self, direction: bool):
        """Increment or decrement detail

        Parameters:
            direction (bool): If True, increment, otherwise decrement

        """
        value = {True:'Up', False:'Down'}.get(direction)
        await self.device.send_web_button('Detail', value)

    def on_prop(self, instance, value, **kwargs):
        prop = kwargs['property']
        if prop.name in ['red_value', 'blue_value']:
            value = int(value)
            value = f'{value:+3d}'
        super().on_prop(instance, value, **kwargs)
        if prop.name == 'detail':
            self.detail_pos = int(value)
        elif prop.name in ['red_pos', 'red_scale']:
            if self.red_pos is not None and self.red_scale is not None:
                self.red_normalized = self.red_pos - (self.red_scale // 2)
        elif prop.name in ['blue_pos', 'blue_scale']:
            if self.blue_pos is not None and self.blue_scale is not None:
                self.blue_normalized = self.blue_pos - (self.blue_scale // 2)


class TallyParams(ParameterGroup):
    """Tally light parameters
    """

    _NAME = 'tally'
    program: bool = Property(False)
    """True if program tally is lit"""

    preview: bool = Property(False)
    """True if preview tally is lit"""

    tally_priority: str|None = Property()
    """The tally priority. One of ``['Camera', 'Web']``."""

    tally_status: str|None = Property()
    """Tally light status. One of ``['Off', 'Program', 'Preview']``"""

    _prop_attrs = [
        ('tally_priority', 'TallyLamp.Priority'),
        ('tally_status', 'TallyLamp.StudioTally'),
    ]

    async def set_program(self, state: bool = True):
        """Enable or Disable Program tally

        Arguments:
            state (bool, optional): If False, turns off the tally light

        """
        if not state:
            value = 'Off'
        else:
            value = 'Program'
        await self.set_tally_light(value)

    async def set_preview(self, state: bool = True):
        """Enable or Disable Preview tally

        Arguments:
            state (bool, optional): If False, turns off the tally light

        """
        if not state:
            value = 'Off'
        else:
            value = 'Preview'
        await self.set_tally_light(value)

    async def set_tally_light(self, value: str):
        """Set tally light state

        Arguments:
            value (str): One of 'Program', 'Preview' or 'Off'

        """
        await self.device.queue_request('SetStudioTally', {'Indication':value})
        self.tally_status = value

    async def close(self):
        await self.set_tally_light('Off')

    def on_prop(self, instance, value, **kwargs):
        prop = kwargs['property']
        if prop.name == 'tally_status':
            self.program = value == 'Program'
            self.preview = value == 'Preview'
        super().on_prop(instance, value, **kwargs)

PARAMETER_GROUP_CLS = (
    CameraParams, NTPParams, BatteryParams, ExposureParams,
    LensParams, PresetZoomParams, PaintParams, TallyParams,
)

@logger.catch
def main(hostaddr, auth_user, auth_pass, id_=None):
    """Build a device and open it
    """
    loop = asyncio.get_event_loop()
    dev = Device(hostaddr, auth_user, auth_pass, id_)
    loop.run_until_complete(dev.open())
    try:
        loop.run_forever()
    finally:
        loop.run_until_complete(dev.close())
    return dev
