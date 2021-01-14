from loguru import logger
import asyncio

from pydispatch import Dispatcher, Property, DictProperty, ListProperty

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

    Properties:
        model_name (str):
        serial_number (str):
        resolution (str):
        api_version (str):
        parameter_groups (dict): Container for :class:`ParameterGroup` instances
        connected (bool): Connection state
        device_index (int): The device index
        error (bool): Becomes ``True`` when a communication error occurs

    :Events:

        .. event:: on_client_error(self, exc)

            Fired when an error is caught by the http client. The first argument
            is the :class:`Device` instance and the second argument is the
            :class:`Exception` that was raised

    """
    model_name = Property()
    serial_number = Property()
    resolution = Property()
    api_version = Property()
    device_index = Property(0)
    connected = Property(False)
    error = Property(False)
    parameter_groups = DictProperty()
    _events_ = ['on_client_error']
    def __init__(self, hostaddr:str, auth_user:str, auth_pass:str, id_: str, hostport: int = 80):
        self.hostaddr = hostaddr
        self.hostport = hostport
        self.auth_user = auth_user
        self.auth_pass = auth_pass
        self.__id = id_
        self.client = Client(hostaddr, auth_user, auth_pass, hostport)
        self._poll_fut = None
        self._poll_enabled = False
        self._is_open = False
        for cls in PARAMETER_GROUP_CLS:
            self._add_param_group(cls)
        attrs = ['model_name', 'serial_number', 'resolution', 'api_version']
        self.bind(**{attr:self.on_attr for attr in attrs})
        self.request_queue = NamedQueue(maxsize=16)

    @property
    def id(self): return self.__id

    def _add_param_group(self, cls, **kwargs):
        pg = cls(self, **kwargs)
        assert pg.name not in self.parameter_groups
        self.parameter_groups[pg.name] = pg
        return pg

    def __getattr__(self, key):
        if hasattr(self, 'parameter_groups') and key in self.parameter_groups:
            return self.parameter_groups[key]
        raise AttributeError

    async def open(self):
        """Begin communication with the device
        """
        if self._is_open:
            return
        await self.client.open()
        await self._get_system_info()
        self._poll_enabled = True
        self._poll_fut = asyncio.ensure_future(self._poll_loop())
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

        while self._poll_enabled:
            item = await get_queue_item(timeout=.5)
            try:
                await do_poll(item)
            except ClientError as exc:
                asyncio.ensure_future(self._handle_client_error(exc))
                break

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

    Properties:
        name (str): The group name

    Attributes:
        _prop_attrs (list): A list of tuples to map instance attributes to the
            values returned by the api data from :meth:`Device._request_cam_status`
        _optional_api_keys (list): A list of any api values that may not be
            available. If the parameter is missing during :meth:`parse_status_response`,
            it will be allowed to fail if present in this list.
    """
    name = Property('')
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
        logger.info(f'{self}.{prop.name} = {value}')

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

class CameraParams(ParameterGroup):
    """Basic camera parameters

    Properties:
        status (str): Camera status. One of
            ``['NoCard', 'Stop', 'Standby', 'Rec', 'RecPause']``
        mode (str): Camera record / media mode. One of
            ``['Normal', 'Pre', 'Clip', 'Frame', 'Interval', 'Variable']``
        timecode (str): The current timecode value

    """
    _NAME = 'camera'
    status = Property()
    mode = Property()
    timecode = Property()
    _prop_attrs = [
        ('status', 'Camera.Status'),
        ('mode', 'Camera.Mode'),
        ('timecode', 'Camera.TC'),
    ]
    def on_prop(self, instance, value, **kwargs):
        prop = kwargs['property']
        if prop.name == 'timecode':
            return
        super().on_prop(instance, value, **kwargs)

class ExposureParams(ParameterGroup):
    """Exposure parameters

    Properties:
        mode (str): Exposure mode. One of
            ``['Auto', 'Manual', 'IrisPriority', 'ShutterPriority']``
        iris_mode (str): Iris mode. One of ``['Manual', 'Auto', 'AutoAELock']``
        iris_fstop (str): Character string for iris value
        iris_pos (int): Iris position (0-255)
        gain_mode (str): Gain mode. One of
            ``['ManualL', 'ManualM', 'ManualH', 'AGC', 'AlcAELock', 'LoLux', 'Variable']``
        gain_value (str): Gain value
        gain_pos (int): Gain value as an integer from -6 to 24
        shutter_mode (str): Shutter mode. One of
            ``['Off', 'Manual', 'Step', 'Variable', 'Eei']``
        shutter_value (str): Shutter value
        master_black (str): MasterBlack value
        master_black_pos (int): MasterBlack value as an integer from -50 to 50

    """
    _NAME = 'exposure'
    mode = Property()
    iris_mode = Property()
    iris_fstop = Property()
    iris_pos = Property()
    gain_mode = Property()
    gain_value = Property()
    gain_pos = Property(0)
    shutter_mode = Property()
    shutter_value = Property()
    master_black = Property()
    master_black_pos = Property(0)
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

class PaintParams(ParameterGroup):
    """Paint parameters

    Properties:
        white_balance_mode (str): Current white balance mode. One of
            ``['Preset', 'A', 'B', 'Faw', 'FawAELock',
            'Faw', 'Awb', 'OnePush', '3200K', '5600K', 'Manual']``
        color_temp (str): White balance value
        red_scale (int): Total range for WB red paint (0-64)
        red_pos (int): Current position of WB red paint (0-64)
        red_value (str): WB red paint value
        red_normalized (int): Red value from -31 to +31
        blue_scale (int): Total range for WB blue paint (0-64)
        blue_pos (int): Current position of WB blue paint (0-64)
        blue_value (str): WB blue paint value
        blue_normalized (int): Blue value from -31 to +31
        detail (str): Detail value as string
        detail_pos (int): Detail value as an integer from -10 to +10

    """
    _NAME = 'paint'

    white_balance_mode = Property()
    color_temp = Property()
    red_scale = Property(64)
    red_pos = Property()
    red_value = Property()
    red_normalized = Property(0)
    blue_scale = Property(64)
    blue_pos = Property()
    blue_value = Property()
    blue_normalized = Property(0)
    detail = Property()
    detail_pos = Property(0)

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

    Properties:
        program (bool): True if program tally is lit
        preview (bool): True if preview tally is lit
        tally_priority (str): The tally priority. One of ``['Camera', 'Web']``.
        tally_status (str): Tally light status. One of ``['Off', 'Program', 'Preview']``

    """
    _NAME = 'tally'
    program = Property(False)
    preview = Property(False)

    tally_priority = Property()
    tally_status = Property()
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

PARAMETER_GROUP_CLS = (CameraParams, ExposureParams, PaintParams, TallyParams)

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
