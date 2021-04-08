from loguru import logger
import asyncio
from typing import Dict, Tuple, Set, Optional
import dataclasses
from dataclasses import dataclass, field
import enum

import jsonfactory

from tslumd import TallyColor, TallyType, TallyState


@dataclass
class TallyMap:
    """Map to a single :class:`tally type <tslumd.common.TallyType>` within a
    specific :class:`tslumd.tallyobj.Tally` by its index
    """
    tally_index: int = 0 #: The :attr:`~.tslumd.tallyobj.Tally.index`
    tally_type: TallyType = TallyType.no_tally #: The :class:`~tslumd.common.TallyType`
    def to_dict(self) -> Dict:
        attrs = ['tally_index', 'tally_type']
        return {attr:getattr(self, attr) for attr in attrs}

@dataclass
class DeviceMapping:
    """Map the preview and program tallies from UMD to a
    :class:`jvconnected.device.Device`

    This only defines the mapping, the functionality itself is carried out by
    :class:`MappedDevice`.
    """

    device_index: int
    """The :attr:`~jvconnected.device.Device.device_index` to associate with
    this mapping
    """

    program: TallyMap = field(default_factory=TallyMap)
    """Definition for program tally
    """

    preview: TallyMap = field(default_factory=TallyMap)
    """Definition for preview tally
    """

    def to_dict(self) -> Dict:
        attrs = ['device_index', 'program', 'preview']
        return {attr:getattr(self, attr) for attr in attrs}


class MappedDevice:
    """Link between :class:`~tslumd.Tally` objects and a
    :class:`jvconnected.device.Device`
    """
    umd_io: 'jvconnected.interfaces.tslumd.umd_io.UmdIo'
    """:class:`.UmdIo` instance"""

    map: DeviceMapping
    """Mapping definitions for the device"""

    device: Optional['jvconnected.device.Device']
    """The device instance"""

    program_tally: Optional[TallyMap]
    """The :class:`~tslumd.tallyobj.Tally` mapped to :attr:`jvconnected.device.TallyParams.program`
    """

    preview_tally: Optional[TallyMap]
    """The :class:`~tslumd.tallyobj.Tally` mapped to :attr:`jvconnected.device.TallyParams.preview`
    """

    tally_state: TallyState #: The current state
    have_tallies: bool
    def __init__(self,
                 umd_io: 'jvconnected.interfaces.tslumd.umd_io.UmdIo',
                 map: DeviceMapping):

        self.umd_io = umd_io
        self.map = map
        self.device = None
        self.program_tally = None
        self.preview_tally = None
        self.tally_state = TallyState.OFF
        self.have_tallies = False
        self.get_tallies()

    @logger.catch
    async def set_device(self, device: Optional['jvconnected.device.Device']):
        """Set the :attr:`device` and update its tally state
        """
        old = self.device
        if old is not None and old is not device:
            await old.tally.set_tally_light('Off')
        self.device = device
        if device is not None:
            await self.update_device_tally()

    def get_tallies(self) -> bool:
        """Attempt to find the :class:`~tslumd.tallyobj.Tally` objects in the :attr:`umd_io`

        Returns:
            bool: ``True`` if an update is needed
                (a tally object either changed or was found)
        """
        if self.have_tallies:
            return False
        loop = asyncio.get_event_loop()
        need_update = False
        have_tallies = True
        if self.map.program.tally_type == TallyType.no_tally:
            pgm = None
        else:
            pgm = self.umd_io.tallies.get(self.map.program.tally_index)
            if pgm is None:
                have_tallies = False
            if pgm is not self.program_tally:
                if self.program_tally is not None:
                    self.program_tally.unbind(self)
                self.program_tally = pgm
                if pgm is not None:
                    pgm.bind_async(loop, on_update=self.update_device_tally)
                need_update = True
        if self.map.preview.tally_type == TallyType.no_tally:
            pvw = None
        else:
            pvw = self.umd_io.tallies.get(self.map.preview.tally_index)
            if pvw is None:
                have_tallies = False
            if pvw is not self.preview_tally:
                if self.preview_tally is not None:
                    self.preview_tally.unbind(self)
                self.preview_tally = pvw
                if pvw is not None and pvw is not pgm:
                    pvw.bind_async(loop, on_update=self.update_device_tally)
                need_update = True
        self.have_tallies = have_tallies
        if have_tallies:
            logger.debug(f'{self.map}: program={pgm}, preview={pvw}')
        return need_update

    def update_tally_state(self, *args, **kwargs):
        """Update the :attr:`tally_state` using both :attr:`program_tally` and
        :attr:`preview_tally`. Since they are mutually exclusive in the device,
        priority is given to :attr:`program_tally`.

        Returns:
            bool: ``True`` if the state changed
        """
        if not self.have_tallies:
            self.get_tallies()
        if not self.have_tallies:
            return False
        pgm = self.program_tally
        pvw = self.preview_tally
        state = TallyState.OFF
        if self.map.program.tally_type != TallyType.no_tally and pgm is not None:
            value = getattr(pgm, self.map.program.tally_type.name)
            if value != TallyColor.OFF:
                state |= TallyState.PROGRAM
        if self.map.preview.tally_type != TallyType.no_tally and pvw is not None:
            value = getattr(pgm, self.map.preview.tally_type.name)
            if value != TallyColor.OFF:
                state |= TallyState.PREVIEW
        if state == self.tally_state:
            return False
        self.tally_state = state
        return True

    @logger.catch
    async def update_device_tally(self, *args, **kwargs):
        """Update the tally state (using :meth:`update_tally_state`) and
        send changes to the :attr:`device`
        """
        if self.device is None:
            return
        changed = self.update_tally_state()
        if not changed:
            return
        if TallyState.PROGRAM in self.tally_state:
            value = 'Program'
        elif TallyState.PREVIEW in self.tally_state:
            value = 'Preview'
        else:
            value = 'Off'
        await self.device.tally.set_tally_light(value)

    def __repr__(self):
        return f'<{self.__class__.__name__}: {self}>'

    def __str__(self):
        return f'device_index: {self.map.device_index}'


@jsonfactory.register
class JsonHandler(object):
    def cls_to_str(self, cls):
        if type(cls) is not type:
            cls = cls.__class__
        modname = '.'.join(cls.__module__.split('.')[:-1])
        return f'{modname}.{cls.__name__}'
    def str_to_cls(self, s):
        prefix = '.'.join(JsonHandler.__module__.split('.')[:-1])
        if s.endswith('TallyType'):
            return TallyType
        if not s.startswith(prefix):
            return None
        for cls in [TallyMap, DeviceMapping, TallyType]:
            if s.endswith(cls.__name__):
                return cls
    def encode(self, o):
        if isinstance(o, (TallyMap, DeviceMapping)):
            d = o.to_dict()
            d['__class__'] = self.cls_to_str(o)
            return d
        elif isinstance(o, TallyType):
            d = {
                '__class__':self.cls_to_str(o),
                'name':o.name,
                'value':o.value,
            }
            return d
    def decode(self, d):
        if '__class__' in d:
            cls = self.str_to_cls(d['__class__'])
            if cls is not None:
                if cls is DeviceMapping:
                    for key in ['program', 'preview']:
                        if not isinstance(d[key], TallyMap):
                            d[key] = self.decode(d[key])
                elif cls is TallyMap:
                    if not isinstance(d['tally_type'], TallyType):
                        d['tally_type'] = self.decode(d['tally_type'])
                elif cls is TallyType:
                    return getattr(TallyType, d['name'])
                del d['__class__']
                return cls(**d)
        return d
