# https://mountainutilities.eu/system/files/download/BC-MIDI-Implementation-1.2.9.pdf

from loguru import logger
from typing import List, Sequence, ByteString, ClassVar, Tuple, Dict, Optional
import dataclasses
from dataclasses import dataclass, field

import mido

from . import aioport

MidiString = Sequence[ByteString]


def byte_split(i: int) -> Tuple[int, int]:
    lsb = i & 0x7f
    msb = i >> 7
    return tuple([msb, lsb])

def byte_unsplit(msb: int, lsb: int) -> int:
    return (msb << 7) | lsb


def bool_to_bcl(value: bool) -> str:
    return {True:'on', False:'off'}[value]

ERROR_CODES = {
    0: ('noerr', 'No error'),
    1: ('unknowntoken', 'Invalid identifier after ‘$’ or ‘.’.'),
    2: ('datawithouttoken', '‘$’ or ‘.’ expected'),
    3: ('argumentmissing', 'MIDI output argument expected'),
    4: ('wrongdevice', 'Invalid model'),
    5: ('wrongrevision', 'Unsupported revision'),
    6: ('missingrevision', 'No block defined'),
    7: ('internal', ''),
    8: ('modemissing', 'No section defined'),
    9: ('baditemindex', 'Element number out of range'),
    10: ('notanumber', 'Invalid numerical argument'),
    11: ('valoutofrange', 'Argument value out of range'),
    12: ('invalidargument', 'Invalid text argument'),
    13: ('invalidcommand', 'Setting not allowed in current section'),
    14: ('wrongnumberofargs', 'Invalid number of arguments (too few or too many)'),
    15: ('toomuchdata', 'Too much MIDI output data (for tx statement)'),
    16: ('alreadydefined', ''),
    17: ('presetmissing', ''),
    18: ('presettoocomplex', 'Preset too complex'),
    19: ('wrongpreset', ''),
    20: ('presettoonew', ''),
    21: ('presetcheck', ''),
    22: ('sequence', 'Invalid message index (compare error 6)'),
    23: ('wrongcontext', ''),
}

class ResponseError(Exception):
    """Raised on errors indicated by :class:`BCLReply` messages

    The :attr:`error_code` is used to provide a description of the error,
    if possible
    """

    error_code: int
    """The :attr:`error number <BCLReply.error_code>` from the device
    """

    def __init__(self, error_code: int):
        self.error_code = error_code

    def __str__(self):
        if self.error_code not in ERROR_CODES:
            return str(self.error_code)
        msg_code, msg_desc = ERROR_CODES[self.error_code]
        return f'Error {self.error_code}: "{msg_desc}" ({msg_code})'

@dataclass
class BCLSyxBase:
    """Wrapper for a single BCL command as a Sysex message
    """

    manufacturer: MidiString = (0x00, 0x20, 0x32)
    """The Sysex manufacturer id

    This should always be ``(0x00, 0x20, 0x32)`` (Behringer)
    """

    device_id: MidiString = (0x7f,)
    """The device id from 0x00 to 0x15, or 0x7f for "any"
    """

    model: MidiString = (0x14,) # for BCF2000, `0x15` is BCR2000
    """0x14 for BCF2000, 0x15 for BCR2000, or 0x7f for "any"
    """

    command: MidiString = (0x20,)
    """The command type. This is 0x20 for BCL messages
    """

    message_index: int = 0
    """Index of the BCL command within a :class:`BCLBlock`
    """

    msg_attrs: ClassVar[Sequence[str]] = (
        'manufacturer', 'device_id', 'model', 'command',
        'index_msb', 'index_lsb',
    )

    @classmethod
    def from_sysex_message(cls, msg: mido.Message) -> 'BCLSysex':
        """Create an instance from the given :class:`~mido.Message`
        """
        kw = cls._parse_kwargs_from_sysex(msg)
        return cls(**kw)

    @classmethod
    def _parse_kwargs_from_sysex(cls, msg: mido.Message) -> Dict:
        data = msg.data
        kw = dict(
            manufacturer=data[:3],
            device_id=data[3:4],
            model=data[4:5],
            command=data[5:6],
            message_index=byte_unsplit(data[6], data[7]),
        )
        return kw

    @property
    def index_msb(self) -> MidiString:
        """Bits 7-13 of :attr:`message_index`
        """
        return byte_split(self.message_index)[0:1]

    @property
    def index_lsb(self) -> MidiString:
        """Bits 0-6 of :attr:`message_index`
        """
        return byte_split(self.message_index)[1:2]

    def build_sysex_data(self) -> MidiString:
        """Build the Sysex message as a sequence of int
        """
        msg = []
        for attr in self.msg_attrs:
            val = self._field_to_syx_list(attr)
            msg.extend(val)
        return msg

    def _field_to_syx_list(self, attr: str) -> List[ByteString]:
        return list(getattr(self, attr))

    def build_sysex_message(self) -> mido.Message:
        """Build a Sysex message wrapped in a :class:`mido.Message`
        """
        data = self.build_sysex_data()
        return mido.Message('sysex', data=data)

@dataclass
class BCLSysex(BCLSyxBase):
    """A BCL Text command
    """

    bcl_text: str = ''
    """The BCL line
    """

    msg_attrs: ClassVar[Sequence[str]] = (
        'manufacturer', 'device_id', 'model', 'command',
        'index_msb', 'index_lsb', 'bcl_text',
    )

    @classmethod
    def _parse_kwargs_from_sysex(cls, msg: mido.Message) -> Dict:
        kw = super()._parse_kwargs_from_sysex(msg)
        data = msg.data
        kw['bcl_text'] = bytearray(data[8:]).decode('UTF-8')
        return kw

    def _field_to_syx_list(self, attr: str) -> List[ByteString]:
        if attr == 'bcl_text':
            val = list(bytearray(self.bcl_text, 'UTF-8'))
        else:
            val = list(getattr(self, attr))
        return val

@dataclass
class BCLReply(BCLSyxBase):
    """A message sent from a BC device in response to a BCL command
    """

    error_code: MidiString = (0,)
    """If non-zero, indicates an error occured
    """

    msg_attrs: ClassVar[Sequence[str]] = (
        'manufacturer', 'device_id', 'model', 'command',
        'index_msb', 'index_lsb', 'error_code',
    )

    @classmethod
    def _parse_kwargs_from_sysex(cls, msg: mido.Message) -> Dict:
        kw = super()._parse_kwargs_from_sysex(msg)
        data = msg.data
        kw['error_code'] = data[8]
        return kw

    def raise_on_error(self):
        """Check for errors and raise a :class:`ResponseError` if necessary
        """
        if self.error_code != 0:
            raise ResponseError(self.error_code)
            # raise Exception(f'Received error code "{self.error_code}" from device')


@dataclass
class BCLBlock:
    """A sequence of BCL commands either received from or sent to a BC device
    """

    revision: str = 'F1'
    """The device type and revision number for the device

    This is typically "F1" for the BCF2000 and "R1" for the BCR2000
    """

    text_lines: Sequence[str] = field(default_factory=list)
    """The BCL command lines within the block (not including the block start
    or end commands)
    """

    @classmethod
    def from_midi_messages(cls, messages: Sequence[mido.Message]) -> Tuple['BCLBlock', Sequence[mido.Message]]:
        """Create a :class:`BCLBlock` from the given :class:`Messages <mido.Message>`

        Returns
        -------
        blk : BCLBlock
            The parsed instance
        unhandled : List[mido.Message]
            The messages remaining after parsing

        """
        # items = []
        kw = {'text_lines':[]}

        unhandled = []
        messages = list(messages)

        bcl_ix = 0
        msg_ix = 0
        start_item = None
        end_item = None
        for msg_ix, msg in enumerate(messages):
            if msg.type != 'sysex':
                unhandled.append(msg)
                continue
            item = BCLSysex.from_sysex_message(msg)
            if start_item is None:
                if item.bcl_text.startswith('$rev'):
                    start_item = item
                    msg_ix = item.message_index
                    kw['revision'] = item.bcl_text.split('$rev')[1].strip(' ')
                else:
                    unhandled.append(msg)
                continue
            elif end_item is not None:
                msg_ix += 1
                if item.message_index != msg_ix:
                    raise Exception('wrong message index')
                if item.bcl_text.startswith('$end'):
                    end_item = item
                else:
                    kw['text_lines'].append(item.bcl_text)
            else:
                unhandled.append(msg)

            # # assert item.message_index == i
            # # items.append(item)
            # if item.bcl_text.startswith('$rev'):
            #     kw['revision'] = item.bcl_text.split('$rev')[1].strip(' ')
            # elif item.bcl_text.startswith('$end'):
            #     break
            # kw['text_lines'].append(item.bcl_text)
        blk = cls(**kw)
        return tuple([blk, unhandled])

    def build_sysex_items(self) -> Sequence[BCLSysex]:
        """Construct the :class:`BCLSysex` items needed to send the block
        """
        all_lines = [f'$rev {self.revision}']
        all_lines.extend(list(self.text_lines))
        all_lines.append('$end')
        items = []
        for i, line in enumerate(all_lines):
            # items.append(BCLSysex(message_index=i, bcl_text=line))
            item = BCLSysex(message_index=i, bcl_text=line)
            parsed = BCLSysex.from_sysex_message(item.build_sysex_message())
            assert item == parsed
            assert item.message_index == parsed.message_index
            assert item.index_msb == parsed.index_msb
            assert item.index_lsb == parsed.index_lsb
            items.append(item)
        return items

    def build_sysex_messages(self) -> Sequence[mido.Message]:
        """Build the block as a sequence of Sysex :class:`Messages <mido.Message>`
        """
        items = self.build_sysex_items()
        return [item.build_sysex_message() for item in items]

    @logger.catch
    async def send(self, inport: aioport.InputPort, outport: aioport.OutputPort):
        """Send the block and wait for the device reply using the given Midi ports

        Arguments:
            inport (aioport.InputPort): An open midi input port to receive
                BCL replies from
            outport (aioport.OutputPort): An open midi output port to send
                BCL messages to

        """
        async def get_response():
            while True:
                msg = await inport.receive(1)
                if msg is None:
                    raise asyncio.TimeoutError
                if msg.type != 'sysex':
                    inport.task_done()
                    continue
                resp = BCLReply.from_sysex_message(msg)
                inport.task_done()
                return resp
        items = self.build_sysex_items()
        for item in items:
            logger.debug(f'tx {item.message_index}: "{item.bcl_text}"')
            await outport.send(item.build_sysex_message())
            resp = await get_response()
            # logger.info(f'rx {resp.message_index}: {resp}')
            resp.raise_on_error()
            assert resp.message_index == item.message_index

    async def send_to_port_name(self, name: str):
        """Send the block and wait for the device reply using the given port name

        Opens an :class:`.aioport.IOPort` matching the given name.
        The input/output ports are then used as described in the :meth:`send` method
        """
        ioport = aioport.IOPort(name)
        await ioport.open()
        try:
            await self.send(ioport.inport, ioport.outport)
        finally:
            await ioport.close()


@dataclass
class ControlBase:
    """Base class for control definitions
    """

    message_type: str = 'control_change'
    """Midi message type for the control

    .. rubric:: Choices

    ::

        ['note', 'aftertouch', 'control_change', 'program_change', 'pitch_bend']

    """

    channel: int = 0
    """Midi channel (zero-indexed)"""

    number: int = 0
    """Note or controller number (zero-indexed)"""

    mode: str = ''

    value_min: int = 0
    """Minimum controller value"""

    value_max: int = 127
    """Maximum controller value"""

    value_default: Optional[int] = None
    """Default controller value"""

    show_value: bool = True
    """Whether the value should be displayed in the
    4-digit LED display when adjusted
    """

    bcl_command: ClassVar[str] = ''

    include_mode_in_block: ClassVar[bool] = True

    message_types: ClassVar[Dict[str, str]] = {
        'note':'NOTE', 'aftertouch':'AT', 'control_change':'CC',
        'program_change':'PC', 'pitch_bend':'PB'
    }

    def __post_init__(self):
        if self.is_14_bit and self.value_max == 127:
            self.value_max = 16383

    @property
    def is_14_bit(self) -> bool:
        """True if the control uses 14-bit values
        """
        return self._get_is_14_bit()

    def _get_is_14_bit(self) -> bool:
        return self.mode.endswith('/14')

    def get_easyparams(self) -> str:
        ch = self.channel + 1
        # if self.message_type != 'note':
        #     ch += 1
        num = self.number
        return f'{ch} {num} {self.value_min} {self.value_max}'

    def build_bcl_lines(self) -> Sequence[str]:
        """Build the BCL commands for the controller as a sequence of str
        """
        msg_type = self.message_types[self.message_type]
        show_value = bool_to_bcl(self.show_value)
        easyparams = self.get_easyparams()
        lines = [
            f'{self.bcl_command} {self.index}',
            f'  .easypar {msg_type} {easyparams}',
            f'  .showvalue {show_value}',
        ]
        if self.value_default is not None:
            lines.append(f'  .default {self.value_default}')
        if self.include_mode_in_block and len(self.mode):
            lines.append(f'  .mode {self.mode}')
        return lines


@dataclass
class EncoderConf(ControlBase):
    """A Push Encoder configuration
    """

    index: int = 1
    """Encoder number starting with ``1``"""

    mode: str = '1dot'
    """LED Display mode

    .. rubric:: Choices

    ::

        [
            'off', '1dot', '1dot/off', '12dot', '12dot/off', 'bar', 'bar/off',
            'spread', 'pan', 'qual', 'cut', 'damp',
        ]

    """

    encoder_mode: str = 'absolute'
    """Control mode for the encoder

    .. rubric:: Choices

    ::

        [
            'absolute', 'relative-1', 'relative-2', 'relative-3', 'inc/dec',
            'absolute/14', 'relative-1/14', 'relative-2/14', 'relative-3/14',
        ]

    """

    resolution: Sequence[int] = (96, 96, 96, 96)
    """Steps per revolution at four different rotation speeds
    """

    bcl_command: ClassVar[str] = '$encoder'

    def _get_is_14_bit(self) -> bool:
        return self.encoder_mode.endswith('/14')

    def get_easyparams(self) -> str:
        s = super().get_easyparams()
        return f'{s} {self.encoder_mode}'

    def build_bcl_lines(self) -> Sequence[str]:
        lines = super().build_bcl_lines()
        resolution = ' '.join([str(i) for i in self.resolution])
        lines.append(f'  .resolution {resolution}')
        return lines


@dataclass
class FaderConf(ControlBase):
    """A fader configuration
    """

    index: int = 1
    """Fader number starting with ``1``"""

    mode: str = 'absolute'

    motor: bool = True
    """Enable/disable the fader motor"""

    override: str = 'move'
    """Behavior when :attr:`motor` is ``False``

    .. rubric:: Choices

    ::

        ['move', 'pickup']

    ``'move'``
        Immediately send output messages when the fader is moved

    ``'pickup'``
        Wait for the fader to reach last known value before sending output messages

    """

    keyoverride: str = 'off'
    """Set a button to temporarily disable the fader motor when held

    .. rubric:: Choices

    ::

        ['off', 1 .. 64]

    """

    bcl_command: ClassVar[str] = '$fader'
    include_mode_in_block: ClassVar[bool] = False

    def get_easyparams(self) -> str:
        s = super().get_easyparams()
        return f'{s} {self.mode}'

    def build_bcl_lines(self) -> Sequence[str]:
        lines = super().build_bcl_lines()
        motor = bool_to_bcl(self.motor)
        lines.extend([
            f'  .motor {motor}',
            f'  .override {self.override}',
            f'  .keyoverride {self.keyoverride}',
        ])
        return lines


@dataclass
class ButtonConf(ControlBase):
    """A Button configuration
    """

    # for toggleon/toggleoff:
    #   .easypar CC Channel Controller Value1 Value2 Mode
    # for incr/decr:
    #   .easypar CC Channel Controller Value1 Value2 Mode Increment
    index: int = 1
    """Button number starting with ``1``"""

    button_mode: str = 'toggleon'
    """
    .. rubric:: Choices

    ::

        ['toggleoff', 'toggleon', 'increment']

    """

    increment: int = 1
    """Amount to increment/decrement if :attr:`button_mode` is ``'increment'``"""

    bcl_command: ClassVar[str] = '$button'

    def get_easyparams(self) -> str:
        params = super().get_easyparams().split(' ')[:2]
        # params = [self.channel + 1, self.number]
        if self.message_type == 'note':
            params.extend([self.value_max, self.button_mode])
        else:
            params.extend([self.value_min, self.value_max, self.button_mode])

        if self.mode == 'increment':
            params.append(self.increment)
        return ' '.join([str(p) for p in params])

class Preset:
    """Representation of a BCF preset containing :attr:`encoders`, :attr:`faders`
    and :attr:`buttons`
    """

    name: str = ''
    """Name of the preset"""

    snapshot: bool = False
    """If ``True``, send predefined values when a preset is selected"""

    request: bool = False
    """If ``True``, send any ``LearnOutput`` data when a preset is selected"""

    egroups: int = 4
    """Number of encoder groups to enable"""

    fkeys: bool = True
    """Enable/disable the STORE, LEARN, EDIT and EXIT function keys"""

    lock: bool = False
    """Enable/disable the ``<`` and ``>`` preset buttons"""

    encoders: Dict[int, EncoderConf]
    """Mapping of :class:`EncoderConf` definitions using their index as keys
    """

    faders: Dict[int, FaderConf]
    """Mapping of :class:`FaderConf` definitions using their index as keys
    """

    buttons: Dict[int, ButtonConf]
    """Mapping of :class:`ButtonConf` definitions using their index as keys
    """

    def __init__(self, **kwargs):
        keys = ['name', 'snapshot', 'request', 'egroups', 'fkeys', 'lock']
        for key in keys:
            kwargs.setdefault(key, getattr(self, key))
            setattr(self, key, kwargs[key])
        self.encoders = {}
        self.faders = {}
        self.buttons = {}

        for kw in kwargs.get('encoders', []):
            self.add_encoder(**kw)

        for kw in kwargs.get('faders', []):
            self.add_fader(**kw)

        for kw in kwargs.get('buttons', []):
            self.add_button(**kw)

    def add_encoder(self, **kwargs) -> EncoderConf:
        """Create an :class:`EncoderConf` and add it to :attr:`encoders`

        Keyword arguments from this method will be used to create the instance
        """
        obj = EncoderConf(**kwargs)
        if obj.index in self.encoders:
            raise KeyError(f'Encoder {obj.index} already exists')
        self.encoders[obj.index] = obj
        return obj

    def add_fader(self, **kwargs) -> FaderConf:
        """Create a :class:`FaderConf` and add it to :attr:`faders`

        Keyword arguments from this method will be used to create the instance
        """
        obj = FaderConf(**kwargs)
        if obj.index in self.faders:
            raise KeyError(f'Fader {obj.index} already exists')
        self.faders[obj.index] = obj
        return obj

    def add_button(self, **kwargs) -> ButtonConf:
        """Create a :class:`ButtonConf` and add it to :attr:`buttons`

        Keyword arguments from this method will be used to create the instance
        """
        obj = ButtonConf(**kwargs)
        if obj.index in self.buttons:
            raise KeyError(f'Button {obj.index} already exists')
        self.buttons[obj.index] = obj
        return obj

    def as_dict(self) -> Dict:
        keys = ['name', 'snapshot', 'request', 'egroups', 'fkeys', 'lock']
        d = {key:getattr(self, key) for key in keys}
        d.update({'encoders':[], 'faders':[], 'buttons':[]})

        for obj in self.encoders.values():
            d['encoders'].append(dataclasses.asdict(obj))
        for obj in self.faders.values():
            d['faders'].append(dataclasses.asdict(obj))
        for obj in self.buttons.values():
            d['buttons'].append(dataclasses.asdict(obj))
        return d

    def build_bcl_lines(self) -> Sequence[str]:
        """Build the BCL commands for the preset as a list of strings
        """
        name = self.name
        if len(name) < 24:
            nfill = 24 - len(name)
            name = ''.join([name, ' '*nfill])
        elif len(name) > 24:
            raise ValueError('name must be 24 characters or less')

        lines = [
            '$preset',
            f"  .name '{name}'",
            f'  .egroups {self.egroups}',
            '  .snapshot {}'.format(bool_to_bcl(self.snapshot)),
            '  .request {}'.format(bool_to_bcl(self.request)),
            '  .fkeys {}'.format(bool_to_bcl(self.fkeys)),
            '  .lock {}'.format(bool_to_bcl(self.lock)),
            '  .init',
        ]
        for obj in self.encoders.values():
            lines.extend(obj.build_bcl_lines())

        for obj in self.faders.values():
            lines.extend(obj.build_bcl_lines())

        for obj in self.buttons.values():
            lines.extend(obj.build_bcl_lines())

        return lines

    def build_bcl_block(self) -> BCLBlock:
        """Build the BCL commands for the preset wrapped in a :class:`BCLBlock`
        """
        lines = self.build_bcl_lines()
        return BCLBlock(text_lines=lines)

    def build_sysex_messages(self) -> Sequence[mido.Message]:
        """Build the BCL commands for the preset as a sequence of Sysex messages
        """
        blk = self.build_bcl_block()
        return blk.build_sysex_messages()

    def build_store_block(self, preset_num: int) -> BCLBlock:
        """Build the BCL commands to store the preset to the given number, wrapped
        in a :class:`BCLBlock`
        """
        lines = [f'$store {preset_num}']
        return BCLBlock(text_lines=lines)

    def build_store_sysex(self, preset_num: int) -> Sequence[mido.Message]:
        """Build the BCL commands to store the preset to the given number, wrapped
        in a sequence of Sysex messages
        """
        blk = self.build_store_block(preset_num)
        return blk.build_sysex_messages()

    async def send(
        self,
        inport: aioport.InputPort,
        outport: aioport.OutputPort,
        store: bool = False,
        preset_num: int = 1
    ):
        """Send the preset to the device and optionally store it using the given
        midi ports

        Arguments:
            inport (aioport.InputPort): An open midi input port to receive
                BCL replies from
            outport (aioport.OutputPort): An open midi output port to send
                BCL messages to
            store: If True, store the preset in the device memory using the
                given *preset_num*. Default is False
            preset_num: If *store* is True this is will be the preset number
                stored on the device. Default is 1

        """
        blk = self.build_bcl_block()
        await blk.send(inport, outport)

        if store:
            blk = self.build_store_block(preset_num)
            await blk.send(inport, outport)

    async def send_to_port_name(
        self,
        name: str,
        store: bool = False,
        preset_num: int = 1
    ):
        """Send the preset to the device and optionally store it using the given
        port name

        Opens an :class:`.aioport.IOPort` matching the given name.
        The input/output ports are then used as described in the :meth:`send` method

        Arguments:
            name: The port name
            store: If True, store the preset in the device memory using the
                given *preset_num*. Default is False
            preset_num: If *store* is True this is will be the preset number
                stored on the device. Default is 1

        """
        ioport = aioport.IOPort(name)
        await ioport.open()
        try:
            await self.send(ioport.inport, ioport.outport, store, preset_num)
        finally:
            await ioport.close()
