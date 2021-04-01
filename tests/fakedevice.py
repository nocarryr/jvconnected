from loguru import logger
from typing import Sequence
import asyncio
from pathlib import Path
from contextvars import ContextVar
import socket
import datetime
import ipaddress
import argparse

import pkg_resources
ZC_VERSION = pkg_resources.get_distribution('zeroconf').parsed_version
if ZC_VERSION < pkg_resources.parse_version('0.28.6'):
    SERV_NAME_KWARGS = {'allow_underscores':True}
else:
    SERV_NAME_KWARGS = {'strict':False}

from aiohttp import web
from pydispatch import Dispatcher, Property, DictProperty, ListProperty
import zeroconf
import ifaddr
# from zeroconf import ServiceInfo

from jvconnected import device
from jvconnected.discovery import PROCAM_FQDN


PREVIEW_IMAGE_DIR = Path(__file__).resolve().parent / 'test_images'

def get_image_filenames(img_dir: Path = PREVIEW_IMAGE_DIR) -> Sequence[Path]:
    d = {}
    for p in img_dir.glob('*.jpg'):
        num = int(p.stem)
        d[num] = p
    if not len(d):
        logger.warning('No test images exist')
    return [d[num] for num in sorted(d.keys())]

class NotUniqueError(Exception):
    pass
class NameNotUnique(NotUniqueError):
    pass
class PortNotUnique(NotUniqueError):
    pass


def get_non_loopback_ip() -> ipaddress.IPv4Interface:
    """Find the first non-loopback network address on the system. If none is
    found, fall back to the loopback ip.
    """
    loopback_ip = None
    for nic in ifaddr.get_adapters():
        for ip in nic.ips:
            if not ip.is_IPv4:
                continue
            net = ipaddress.ip_interface(f'{ip.ip}/{ip.network_prefix}')
            if net.is_loopback:
                loopback_ip = net
                continue
            return net
    return loopback_ip


class ImageServer:
    def __init__(self):
        self.loop = asyncio.get_event_loop()
        self.fps = 1
        self.frame_dur = 1 / self.fps
        self.image_filenames = get_image_filenames()
        self.current_index = 0
        self.max_index = len(self.image_filenames) - 1
        self.last_frame_time = None
        self.encoding = False
        self.lock = asyncio.Lock()
        self.current_img_data = None

    async def set_encoding(self, value: bool):
        if value == self.encoding:
            return
        logger.debug(f'encoding: {value}')
        async with self.lock:
            self.encoding = value
            self.current_img_data = None
            self.last_frame_time = None
            self.current_index = 0

    async def get_file_response(self, request):
        if not self.encoding:
            return web.Response(status=404, reason='Not Found', text='Not found')
        async with self.lock:
            file_changed = self.check_increment()
            img_data = self.current_img_data
        if file_changed or img_data is None:
            await self.load_file()
        return web.Response(body=img_data, content_type='image/jpeg')

    async def load_file(self):
        filepath = self.image_filenames[self.current_index]
        data = filepath.read_bytes()
        async with self.lock:
            self.current_img_data = data

    def check_increment(self):
        now = self.loop.time()
        last_t = self.last_frame_time
        if last_t is None:
            self.last_frame_time = now
            return False
        elapsed = now - last_t
        if elapsed < self.frame_dur:
            return False
        ix = self.current_index + 1
        if ix > self.max_index:
            ix = 0
        self.current_index = ix
        self.last_frame_time = now
        return True

class FakeDevice(Dispatcher):
    model_name = Property('GY-HC500')
    serial_number = Property('12340000')
    hostaddr = Property('127.0.0.1')
    hostport = Property(9090)
    dns_name_prefix = Property('hc500')
    api_version = Property('01.234.567')
    resolution = Property('1920x1080')
    country = Property('US')
    parameter_groups = DictProperty()
    zc_service_info = Property()
    def __init__(self, **kwargs):
        self.image_server = ImageServer()
        keys = ['model_name', 'serial_number', 'hostaddr', 'hostport', 'dns_name_prefix']
        kwargs.setdefault('hostaddr', str(get_non_loopback_ip().ip))
        for key in keys:
            if key in kwargs:
                setattr(self, key, kwargs[key])
        for cls in PARAMETER_GROUP_CLS:
            self._add_param_group(cls)
        self._command_map = {
            'GetSystemInfo':self.handle_system_info_req,
            'GetCamStatus':self.handle_status_request,
            'SetWebButtonEvent':self.handle_web_button_event,
            'SetWebSliderEvent':self.handle_web_slider_event,
            'SetWebXYFieldEvent':self.handle_web_xy_event,
            'SetStudioTally':self.handle_tally_request,
            'JpegEncode':self.handle_jpg_encode_request,
        }
        self.zc_service_info = self._build_zc_service_info()
        attrs = ['dns_name_prefix', 'serial_number', 'hostaddr', 'hostport']
        self.bind(**{attr:self._check_zc_service_info for attr in attrs})

    @property
    def dns_name(self):
        return f'{self.dns_name_prefix}-{self.serial_number}'

    def _add_param_group(self, cls, **kwargs):
        pg = cls(self, **kwargs)
        assert pg.name not in self.parameter_groups
        self.parameter_groups[pg.name] = pg
        return pg

    async def handle_command_req(self, request):
        payload = await request.json()
        command = payload['Request']['Command']
        resp_data = {
            'Response':{
                'Requested':command
            }
        }
        m = self._command_map.get(command)
        if m is None:
            resp_data['Response']['Result'] = 'Error'
        else:
            data = await m(request, payload)
            if isinstance(data, dict):
                resp_data['Response']['Data'] = data
            resp_data['Response']['Result'] = 'Success'
        return web.json_response(resp_data)

    async def handle_jpg_req(self, request):
        return await self.image_server.get_file_response(request)

    async def handle_system_info_req(self, request, payload):
        data = {
            'Model':self.model_name,
            'Destination':self.country,
            'ApiVersion':self.api_version,
            'Serial':self.serial_number,
            'Resolution':self.resolution,
        }
        return data

    async def handle_status_request(self, request, payload):
        data = {}
        for pg in self.parameter_groups.values():
            pg.update_status_dict(data)
        return data

    async def handle_web_button_event(self, request, payload):
        coros = []
        for pg in self.parameter_groups.values():
            coros.append(pg.handle_web_button_event(request, payload))
        await asyncio.gather(*coros)

    async def handle_web_slider_event(self, request, payload):
        coros = []
        for pg in self.parameter_groups.values():
            coros.append(pg.handle_web_slider_event(request, payload))
        await asyncio.gather(*coros)

    async def handle_web_xy_event(self, request, payload):
        coros = []
        for pg in self.parameter_groups.values():
            coros.append(pg.handle_web_xy_event(request, payload))
        await asyncio.gather(*coros)

    async def handle_tally_request(self, request, payload):
        await self.parameter_groups['tally'].handle_tally_request(request, payload)

    async def handle_jpg_encode_request(self, request, payload):
        params = payload['Request']['Params']
        encode = params['Operate'] == 'Start'
        await self.image_server.set_encoding(encode)

    def _build_zc_service_info(self) -> 'ServiceInfo':
        return ServiceInfo(
            PROCAM_FQDN,
            f'{self.dns_name}.{PROCAM_FQDN}',
            addresses=[socket.inet_aton(self.hostaddr)],
            port=self.hostport,
            properties={b'model':bytes(self.model_name, 'UTF-8')},
        )

    def _check_zc_service_info(self, *args, **kwargs):
        info = self._build_zc_service_info()
        self.zc_service_info = info


class FakeParamBase(Dispatcher):
    def __init__(self, device: FakeDevice, **kwargs):
        self.device = device
        if 'name' in kwargs:
            name = kwargs['name']
        elif self._NAME is not None:
            name = self._NAME
        else:
            name = self.__class__.__name__
        self.name = name
        self.bind(**{prop:self.on_prop for prop, _ in self._prop_attrs})

    def iter_api_key(self, api_key):
        if isinstance(api_key, str):
            for key in api_key.split('.'):
                if len(key):
                    yield key
        else:
            yield from api_key

    def drill_down_api_dict(self, api_key, data):
        nextdata = data
        prevdata = None
        for key in self.iter_api_key(api_key):
            if key not in nextdata:
                nextdata[key] = {}
            prevdata = nextdata
            nextdata = nextdata[key]
        return key, prevdata

    def update_status_dict(self, data: dict):
        for my_key, api_key in self._prop_attrs:
            dest_key, dest_dict = self.drill_down_api_dict(api_key, data)
            value = getattr(self, my_key)
            # data[self._NAME][data_key] = value
            dest_dict[dest_key] = value

    async def handle_web_button_event(self, request, payload):
        pass

    async def handle_web_slider_event(self, request, payload):
        pass

    async def handle_web_xy_event(self, request, payload):
        pass

    def on_prop(self, instance, value, **kwargs):
        pass

class CameraParams(FakeParamBase):
    _NAME = device.CameraParams._NAME
    _prop_attrs = device.CameraParams._prop_attrs
    status = Property()
    menu_status = Property('Off')
    mode = Property()
    timecode = Property('00:00:00;00')

    def _get_now_tc(self):
        dt = datetime.datetime.now()
        microsecond = dt.microsecond / 1e6
        fr = int(microsecond * (30000/1001))
        tc_str = dt.strftime('%H:%M:%S')
        return f'{tc_str};{fr:02d}'

    def update_status_dict(self, data: dict):
        self.timecode = self._get_now_tc()
        super().update_status_dict(data)

    async def handle_web_button_event(self, request, payload):
        params = payload['Request']['Params']
        kind = params['Kind']
        btn = params['Button']
        if kind == 'Menu':
            if btn == 'Menu':
                if self.menu_status == 'Off':
                    self.menu_status = 'On'
                else:
                    self.menu_status = 'Off'
            elif btn == 'Cancel':
                self.menu_status = 'Off'

class BatteryParams(FakeParamBase):
    _NAME = device.BatteryParams._NAME
    _prop_attrs = device.BatteryParams._prop_attrs
    info_str = Property('Time')
    level_str = Property(1)
    value_str = Property(0)

def build_fstops():
    f = 0
    i = 0
    fstops = []
    while f < 32:
        f = 2 ** (i/3*.5)
        # f = round(f, 1)
        if f >= 2:
            fstops.append(f)
        i += 1
    fstops = [f'F{f:3.1f}' for f in fstops]
    # fstops = [f'F{stop:3.1f}' for stop in [2, 2.8, 4, 5.6, 8, 11, 16, 22]]
    fstops.append('CLOSE')
    print(fstops)
    print(len(fstops))
    step = 256 // len(fstops)
    i = 0
    pos_fstop_arr = []
    fstop_iter = iter(reversed(fstops))
    # fstop_iter = iter(fstops)
    f = next(fstop_iter)
    for pos in range(256):
        pos_fstop_arr.append(f)
        i += 1
        if i >= step:
            i = 0
            try:
                f = next(fstop_iter)
            except StopIteration:
                f = fstops[0]
    return pos_fstop_arr

class ExposureParams(FakeParamBase):
    _NAME = device.ExposureParams._NAME
    _prop_attrs = device.ExposureParams._prop_attrs

    mode = Property()
    iris_mode = Property('Manual')
    iris_fstop = Property('F4.0')
    iris_pos = Property(64)
    gain_mode = Property('ManualL')
    gain_value = Property('0dB')
    gain_pos = Property(0)
    shutter_mode = Property('Off')
    shutter_value = Property(' [OFF]  ')
    master_black = Property('-3')
    master_black_pos = Property(-3)

    _gain_range = [-6, 30]
    _master_black_range = [-12, 12]

    def __init__(self, device: FakeDevice, **kwargs):
        self._iris_lock = asyncio.Lock()
        self._iris_task = None
        self.pos_fstop_arr = build_fstops()

        super().__init__(device, **kwargs)
        self.bind(**{k:self.on_prop for k in ['gain_pos', 'master_black_pos']})

    async def handle_iris_bump(self, btn: str):
        if 'Open' in btn:
            amt = int(btn.lstrip('Open'))
            if self.iris_pos == 255:
                return
        else:
            amt = int(btn.lstrip('Close')) * -1
            if self.iris_pos == 0:
                return
        amt *= 2
        next_value = self.iris_pos + amt
        await self.queue_iris_change(next_value)

    async def queue_iris_change(self, value: int):
        async with self._iris_lock:
            t = self._iris_task
            if t is not None:
                t.cancel()
            self._iris_task = asyncio.ensure_future(self._set_iris_value(value))

    async def _set_iris_value(self, value: int):
        if value < 0:
            value = 0
        elif value > 255:
            value = 255
        await asyncio.sleep(.5)
        async with self._iris_lock:
            self.iris_pos = value
            self._iris_task = None

    async def handle_gain_bump(self, btn: str):
        if 'Up' in btn:
            amt = int(btn.lstrip('Up'))
        else:
            amt = int(btn.lstrip('Down')) * -1
        vmin, vmax = self._gain_range
        v = self.gain_pos + (amt*3)
        if v > vmax:
            v = vmax
        elif v < vmin:
            v = vmin
        self.gain_pos = v

    async def handle_mb_bump(self, btn: str):
        if 'Up' in btn:
            amt = int(btn.lstrip('Up'))
        else:
            amt = int(btn.lstrip('Down')) * -1
        vmin, vmax = self._master_black_range
        v = self.master_black_pos + amt
        if v > vmax:
            v = vmax
        elif v < vmin:
            v = vmin
        self.master_black_pos = v

    async def handle_web_button_event(self, request, payload):
        params = payload['Request']['Params']
        kind = params['Kind']
        btn = params['Button']
        if kind == 'Iris':
            await self.handle_iris_bump(btn)
        elif kind == 'Gain':
            await self.handle_gain_bump(btn)
        elif kind == 'MasterBlack':
            await self.handle_mb_bump(btn)

    async def handle_web_slider_event(self, request, payload):
        params = payload['Request']['Params']
        kind = params['Kind']
        pos = params['Position']
        if kind == 'IrisBar':
            await self.queue_iris_change(pos)

    def on_prop(self, instance, value, **kwargs):
        prop = kwargs['property']
        if prop.name == 'iris_pos':
            self.iris_fstop = self.pos_fstop_arr[value]
        elif prop.name == 'gain_pos':
            self.gain_value = f'{value}dB'
        elif prop.name == 'master_black_pos':
            self.master_black = str(value)

class PaintParams(FakeParamBase):
    _NAME = device.PaintParams._NAME
    _prop_attrs = device.PaintParams._prop_attrs

    white_balance_mode = Property('B')
    color_temp = Property('B< 5600K>')
    red_scale = Property(64)
    red_pos = Property(32)
    red_value = Property('0')
    blue_scale = Property(64)
    blue_pos = Property(32)
    blue_value = Property('0')
    detail = Property('0')
    detail_pos = Property(0)

    _detail_range = [-10, 10]

    def __init__(self, device: FakeDevice, **kwargs):
        super().__init__(device, **kwargs)
        self.bind(detail_pos=self.on_prop)

    async def handle_wb_xy_pos(self, xpos: int, ypos: int):
        if xpos > self.blue_scale:
            xpos = self.blue_scale
        elif xpos < 0:
            xpos = 0
        if ypos > self.red_scale:
            ypos = self.red_scale
        elif ypos < 0:
            ypos = 0
        self.blue_pos = xpos
        self.red_pos = ypos

    async def handle_detail_bump(self, btn: str):
        if 'Up' in btn:
            amt = 1
        else:
            amt = -1
        vmin, vmax = self._detail_range
        v = self.detail_pos + amt
        if v > vmax:
            v = vmax
        elif v < vmin:
            v = vmin
        self.detail_pos = v

    async def handle_web_button_event(self, request, payload):
        params = payload['Request']['Params']
        kind = params['Kind']
        btn = params['Button']
        if kind == 'Whb':
            pass
        elif kind == 'Detail':
            await self.handle_detail_bump(btn)

    async def handle_web_xy_event(self, request, payload):
        params = payload['Request']['Params']
        kind = params['Kind']
        xpos = params['XPosition']
        ypos = params['YPosition']
        if kind == 'WhPaintRB':
            await self.handle_wb_xy_pos(xpos, ypos)

    def on_prop(self, instance, value, **kwargs):
        prop = kwargs['property']
        if prop.name == 'blue_pos':
            self.blue_value = str(value)
        elif prop.name == 'red_pos':
            self.red_value = str(value)
        elif prop.name == 'detail_pos':
            self.detail = str(value)

class TallyParams(FakeParamBase):
    _NAME = device.TallyParams._NAME
    _prop_attrs = device.TallyParams._prop_attrs

    tally_priority = Property('Camera')
    tally_status = Property('Off')

    async def handle_tally_request(self, request, payload):
        value = payload['Request']['Params']['Indication']
        self.tally_status = value


PARAMETER_GROUP_CLS = (CameraParams, BatteryParams, ExposureParams, PaintParams, TallyParams)




# BEGIN <Zeroconf monkeypatch>

class ServiceInfo(zeroconf.ServiceInfo):
    def __eq__(self, other):
        if not isinstance(other, zeroconf.ServiceInfo):
            return False
        attrs = ['name', 'port']#, 'addresses', 'properties']
        for attr in attrs:
            if getattr(self, attr) != getattr(other, attr):
                return False
        return True
    def __ne__(self, other):
        return not self == other

# Override Zeroconf.check_service() to use `allow_underscores=True` in
# zeroconf.service_type_name()
class Zeroconf(zeroconf.Zeroconf):
    def check_service(
        self, info: zeroconf.ServiceInfo, allow_name_change: bool, cooperating_responders: bool = False
    ) -> None:
        """Checks the network for a unique service name, modifying the
        ServiceInfo passed in if it is not unique."""

        # This is kind of funky because of the subtype based tests
        # need to make subtypes a first class citizen
        service_name = zeroconf.service_type_name(info.name, **SERV_NAME_KWARGS)
        if not info.type.endswith(service_name):
            raise zeroconf.BadTypeInNameException

        instance_name = info.name[: -len(service_name) - 1]
        next_instance_number = 2

        now = zeroconf.current_time_millis()
        next_time = now
        i = 0
        while i < 3:
            if not cooperating_responders:
                # check for a name conflict
                while self.cache.current_entry_with_name_and_alias(info.type, info.name):
                    if not allow_name_change:
                        raise zeroconf.NonUniqueNameException

                    # change the name and look for a conflict
                    info.name = '%s-%s.%s' % (instance_name, next_instance_number, info.type)
                    next_instance_number += 1
                    zeroconf.service_type_name(info.name, **SERV_NAME_KWARGS)
                    next_time = now
                    i = 0

            if now < next_time:
                self.wait(next_time - now)
                now = zeroconf.current_time_millis()
                continue

            out = zeroconf.DNSOutgoing(zeroconf._FLAGS_QR_QUERY | zeroconf._FLAGS_AA)
            self.debug = out
            out.add_question(zeroconf.DNSQuestion(info.type, zeroconf._TYPE_PTR, zeroconf._CLASS_IN))
            out.add_authorative_answer(zeroconf.DNSPointer(info.type, zeroconf._TYPE_PTR, zeroconf._CLASS_IN, info.other_ttl, info.name))
            self.send(out)
            i += 1
            next_time += zeroconf._CHECK_TIME

# END </Zeroconf monkeypatch>

class DeviceService(Dispatcher):
    published = Property(False)
    def __init__(self, device: FakeDevice, info: ServiceInfo):
        self.device = device
        self.__info = info
    @property
    def info(self):
        return self.__info
    @property
    def id(self):
        return (self.info.name, self.info.port)



class ZeroconfPublisher(Dispatcher):
    running = Property(False)
    _service_type = '_jvc_procam_web._tcp.local.'
    def __init__(self):
        self.loop = asyncio.get_event_loop()
        self.device_infos = {}
        self.infos_by_port = {}
        self.devices = {}
        self.services = {}
        self._stop_evt = asyncio.Event()
        self.service_lock = asyncio.Lock()

    async def open(self):
        if self.running:
            return
        zc = self.zeroconf = Zeroconf()
        for service in self.services.values():
            if service.published:
                logger.info(f'Register zc service: {service.info!r}')
                zc.register_service(service.info)
        self.running = True

    async def close(self):
        if not self.running:
            return
        zc = self.zeroconf
        for service in self.services.values():
            service.published = False
        zc.close()
        self.running = False

    def _check_service_info(self, info: ServiceInfo):
        if info.name in self.device_infos:
            raise NameNotUnique(f'Name "{info.name}" not unique. {self.device_infos}')
        if info.port in self.infos_by_port:
            raise PortNotUnique(f'Port "{info.port}" already in use. {self.infos_by_port}')

    async def add_device(self, device: FakeDevice, published: bool = False):
        info = device.zc_service_info
        self._check_service_info(info)

        self.device_infos[info.name] = info
        self.infos_by_port[info.port] = info

        service = DeviceService(device, info)
        self.services[service.id] = service
        device.bind(zc_service_info=self.on_device_service_info_changed)
        service.bind(published=self.on_service_published_changed)
        service.published = published
        return service

    def on_service_published_changed(self, instance, value, **kwargs):
        if not self.running:
            return
        if value:
            logger.info(f'Register zc service: {instance.info!r}')
            self.zeroconf.register_service(instance.info)
        else:
            logger.info(f'Unregister zc service: {instance.info!r}')
            self.zeroconf.unregister_service(instance.info)

    def on_device_service_info_changed(self, instance, value, **kwargs):
        logger.warning(f'device info changed: {instance}, {value}, {kwargs}')


# aiohttp server stuff

APP_LEVEL = ContextVar('APP_LEVEL', default=-1)

def init_func(argv=None, **kwargs):
    num_devices = kwargs.get('num_devices', 1)
    leave_published = kwargs.get('leave_published', False)
    port_offset = kwargs.get('port_offset', 0)
    no_publish = kwargs.get('no_publish', False)

    app = web.Application()
    routes = web.RouteTableDef()
    app['servers'] = {}
    app['zeroconf'] = ZeroconfPublisher()

    async def on_startup(app):
        APP_LEVEL.set(APP_LEVEL.get() + 1)
        lvl = APP_LEVEL.get()
        logger.debug(f'APP_LEVEL: {lvl}')
        if lvl > 0:
            return
        zc = app['zeroconf']
        await zc.open()
        coros = []
        for _ in range(num_devices):
            coros.append(build_device(app, port_offset=port_offset, no_publish=no_publish))
        await asyncio.gather(*coros)
        logger.success('Servers ready')

    async def on_shutdown(app):
        APP_LEVEL.set(APP_LEVEL.get() - 1)
        lvl = APP_LEVEL.get()
        logger.debug(f'APP_LEVEL: {lvl}')
        zc = app['zeroconf']
        await zc.close()

    app.on_startup.append(on_startup)
    if not leave_published:
        app.on_shutdown.append(on_shutdown)

    @routes.post('/cgi-bin/api.cgi')
    async def handle_command_req(request):
        hostaddr, port = request.host.split(':')
        s_id = (hostaddr, int(port))
        servers = request.app['servers']
        d = request.app['servers'].get(s_id)
        if d is not None:
            device = d['device']
            return await device.handle_command_req(request)
        return web.Response(status=404, reason='Not Found', text='Not found')

    @routes.get('/api.php')
    async def handle_auth_req(request):
        resp = web.Response(text='Ok')
        resp.set_cookie('SessionID', '1234')
        return resp

    @routes.get('/cgi-bin/get_jpg.cgi')
    async def handle_jpg_req(request):
        hostaddr, port = request.host.split(':')
        s_id = (hostaddr, int(port))
        servers = request.app['servers']
        d = request.app['servers'].get(s_id)
        if d is not None:
            device = d['device']
            return await device.handle_jpg_req(request)
        return web.Response(status=404, reason='Not Found', text='Not found')

    app.add_routes(routes)

    return app

async def build_device(app, **kwargs):
    port_offset = kwargs.pop('port_offset', 0)
    no_publish = kwargs.pop('no_publish', False)
    device = FakeDevice(**kwargs)
    device.hostport += port_offset
    zc = app['zeroconf']
    i = 0
    unique = False
    async with zc.service_lock:
        while not unique:
            try:
                zc._check_service_info(device.zc_service_info)
                unique = True
            except PortNotUnique:
                if i >= 50:
                    raise
                device.hostport += 1
            except NameNotUnique:
                if i >= 50:
                    raise
                device.serial_number = str(int(device.serial_number) + 1)
            i += 1
        s_id = (device.hostaddr, device.hostport)
        logger.info(f'Starting server for {s_id}')

        assert s_id not in app['servers']
        service = await zc.add_device(device)

    runner = web.AppRunner(app)
    logger.debug(f'setup runner for {s_id}')
    await runner.setup()
    site = web.TCPSite(runner, device.hostaddr, device.hostport)
    app['servers'][s_id] = {'device':device, 'runner':runner, 'site':site}
    logger.debug(f'start site for {s_id}')
    await site.start()
    if no_publish is False:
        logger.debug(f'publishing service for {s_id}')
        service.published = True
    return device, runner, site

def main():
    p = argparse.ArgumentParser()
    p.add_argument('-n', '--num-devices', dest='num_devices', type=int, default=1)
    p.add_argument('--leave-published', dest='leave_published', action='store_true')
    p.add_argument('--no-publish', dest='no_publish', action='store_true')
    p.add_argument('--port-offset', dest='port_offset', type=int, default=0)
    args = p.parse_args()

    loop = asyncio.get_event_loop()

    app = init_func(**vars(args))
    web.run_app(app)

if __name__ == '__main__':
    main()
