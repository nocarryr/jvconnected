from loguru import logger
import asyncio
from numbers import Number
from typing import Union, Dict, Any, List, Iterable, Sequence

import mido
from pydispatch import Dispatcher, Property, DictProperty

from jvconnected.interfaces.paramspec import ParameterGroupSpec, ParameterSpec, BaseParameterSpec
from .mapper import Map

NumOrBool = Union[Number, bool]

class MappedDevice(Dispatcher):
    """Manages midi input and output for a single :class:`~jvconnected.device.Device`

    Arguments:
        midi_io: The parent :class:`~.midi_io.MidiIO` instance
        midi_channel (int): Midi channel to use (0 to 15)
        device: The :class:`~jvconnected.device.Device` instance

    Attributes:
        param_specs (Dict[str, ParameterGroupSpec]): A dict of
            :class:`jvconnected.interfaces.paramspec.ParameterGroupSpec` instances
        mapped_params (Dict[str, MappedParameter]): A dict of :class:`MappedParameter`
            instances stored with the :attr:`MappedParameter.name` as keys

    """
    def __init__(self,
                 midi_io: 'jvconnected.interfaces.midi.MidiIO',
                 midi_channel: int,
                 device:'jvconnected.device.Device',
                 mapper:'jvconnected.interfaces.mapper.MidiMapper'):

        self.loop = asyncio.get_event_loop()
        self.midi_io = midi_io
        self.midi_channel = midi_channel
        self.device = device
        self.param_specs = {}
        self.mapped_params = {}
        self.mapper = mapper
        for cls in ParameterGroupSpec.all_parameter_group_cls():
            pg = cls(device=device)
            self.param_specs[pg.name] = pg
            for m in mapper.values():
                if m.group_name != pg.name:
                    continue
                param_spec = pg.parameters[m.name]
                mp_cls = CONTROLLER_CLS[m.map_type]
                kw = {}
                if mp_cls is MappedNoteParam:
                    kw['note'] = m.note
                else:
                    kw['controller'] = m.controller
                mapped_param = mp_cls(self, param_spec, m, **kw)
                self.mapped_params[mapped_param.name] = mapped_param


    async def handle_incoming_messages(self, msgs: Iterable[mido.Message]):
        """Dispatch incoming messages to all :class:`MappedParameter` instances

        The :meth:`MappedParameter.handle_incoming_messages` method is called for
        each parameter instance in :attr:`mapped_params`
        """
        coros = set()
        for mapped_param in self.mapped_params.values():
            coros.add(mapped_param.handle_incoming_messages(msgs))
        try:
            await asyncio.gather(*coros)
        except Exception as exc:
            logger.exception(exc)

    @logger.catch
    async def send_all_parameters(self):
        """Send values for all mapped parameters (full refresh)
        """
        msgs = []
        for mapped_param in self.mapped_params.values():
            value = mapped_param.get_current_value()
            if value is None:
                continue
            msg = mapped_param.build_message(value)
            if isinstance(msg, (list, tuple)):
                msgs.extend(list(msg))
            else:
                msgs.append(msg)
        await self.send_messages(msgs)

    async def send_message(self, msg: mido.Message):
        """Send the given message with :attr:`midi_io`
        """
        await self.midi_io.send_message(msg)

    async def send_messages(self, msgs: Sequence[mido.Message]):
        """Send a sequence of messages with :attr:`midi_io`
        """
        await self.midi_io.send_messages(msgs)


class MappedParameter(Dispatcher):
    """Handles midi input and output for a single parameter within a
    :class:`jvconnected.device.ParameterGroup`

    Attributes:
        mapped_device (:class:`MappedDevice`): The parent :class:`MappedDevice` instance
        param_group (ParameterGroupSpec): The :class:`~.paramspec.ParameterGroupSpec`
            definition that describes the parameter
        map_obj (:class:`.mapper.Map`): The midi mapping definition
        name (str): Unique name of the parameter as defined by the
            :attr:`~.mapper.Map.full_name` of the :attr:`map_obj`
        param_spec: The :class:`~.paramspec.ParameterSpec` instance within the
            :attr:`param_group`
        channel (int): The midi channel to use, typically gathered from :attr:`mapped_device`

    """
    name = None
    channel = 0
    value_min: int = 0
    """Minimum value for the parameter as it exists in the
    :class:`jvconnected.device.ParameterGroup`
    """

    value_max: int = 1
    """Maximum value for the parameter as it exists in the
    :class:`jvconnected.device.ParameterGroup`
    """

    def __init__(self, mapped_device: MappedDevice, param_spec: BaseParameterSpec, map_obj: Map, **kwargs):
        self.mapped_device = mapped_device
        loop = mapped_device.loop
        self.param_group = param_spec.param_group_spec
        self.param_spec = param_spec
        self.name = self.param_spec.full_name
        self.map_obj = map_obj
        self.channel = kwargs.get('channel', mapped_device.midi_channel)
        if hasattr(self.param_spec.value_type, 'value_min'):
            self.value_min = self.param_spec.value_type.value_min
            self.value_max = self.param_spec.value_type.value_max
        self.param_spec.bind_async(loop, value=self.on_param_spec_value_changed)

    @property
    def is_14_bit(self) -> bool:
        """True if the :attr:`map_obj` uses 14 bit values
        """
        return self.map_obj.is_14_bit

    @property
    def midi_max(self) -> int:
        """Maximum value for MIDI data

        Will be 127 (``0x7f``) in most cases.  If :attr:`is_14_bit`, the value
        will be 16383 (``0x3fff``).
        """
        if self.is_14_bit:
            return 16383
        return 0x7f

    @property
    def midi_range(self) -> int:
        """Total range of MIDI values calculated as :attr:`midi_max` + 1
        """
        return self.midi_max + 1

    @property
    def value_range(self) -> Number:
        r"""Total range of values calculated as

        .. math::

            V_{offset} &=
                \begin{cases}
                    1, & \quad \text{if }V_{min} = 0\\
                    0, & \quad \text{if }V_{min}\ne 0
                \end{cases}\\
            V_{range} &= V_{max} - V_{min} + V_{offset}

        where :math:`V_{min}` = :attr:`value_min` and
        :math:`V_{max}` is :attr:`value_max`
        """
        r = self.value_max - self.value_min
        if self.value_min == 0:
            r += 1
        return r

    async def handle_incoming_messages(self, msgs: Iterable[mido.Message]):
        for msg in msgs:
            if not self.message_valid(msg):
                continue
            await self._handle_incoming_message(msg)

    async def _handle_incoming_message(self, msg: mido.messages.BaseMessage):
        pass

    def message_valid(self, msg: mido.messages.BaseMessage) -> bool:
        """Check the incoming message parameters to determine whether it should
        be handled by this object
        """
        if msg.channel != self.channel:
            return False
        return True

    def scale_to_midi(self, value: NumOrBool) -> int:
        r"""Scale the given value to the range allowed in midi messages

        For boolean input, the result will be

        .. math::

            result =
                \begin{cases}
                    M_{max}, & \quad \text{if value is true}\\
                    0,       & \quad \text{otherwise}
                \end{cases}

        For numeric input

        .. math::

            result = \frac{value - V_{min}}{V_{range}} \cdot M_{max}

        where :math:`M_{max}` = :attr:`midi_max`, :math:`M_{range}` = :attr:`midi_range`,
        :math:`V_{min}` = :attr:`value_min` and :math:`V_{range}` = :attr:`value_range`
        """
        m_max, m_range = self.midi_max, self.midi_range
        if isinstance(value, bool):
            return m_max if value else 0
        r = (value - self.value_min) / self.value_range
        return int(r * m_max)

    def scale_from_midi(self, value: int) -> int:
        r"""Scale a value from the midi range to the :attr:`param_spec` range

        .. math::

            result = \frac{value}{M_{range}} \cdot V_{range} + V_{min}

        where :math:`M_{range}` = :attr:`midi_range`, :math:`V_{min}` = :attr:`value_min`
        and :math:`V_{range}` = :attr:`value_range`
        """
        m_max, m_range = self.midi_max, self.midi_range
        r = value / m_range
        return int(r * self.value_range + self.value_min)

    def get_message_type(self, value: NumOrBool) -> str:
        """Get the :class:`mido.Message` type argument for an outgoing :class:`mido.Message`
        with the given value.

        Typically one of ``['control_change', 'note_on', 'note_off', 'pitchwheel']``

        """
        raise NotImplementedError

    def get_message_kwargs(self, value: NumOrBool) -> Dict:
        """Get keyword arguments to build an outgoing :class:`mido.Message` with
        the given value

        """
        return {'channel':self.channel}

    def build_message(self, value: NumOrBool) -> mido.Message:
        """Create a :class:`mido.Message` to send for the given parameter value

        Uses :meth:`get_message_type` and :meth:`get_message_kwargs` for message
        arguments
        """
        msg_type = self.get_message_type(value)
        kw = self.get_message_kwargs(value)
        return mido.Message(msg_type, **kw)

    def get_current_value(self) -> Any:
        """Get the current device value
        """
        return self.param_spec.get_param_value()

    @logger.catch
    async def on_param_spec_value_changed(self, instance, value, **kwargs):
        msg = self.build_message(value)
        if self.is_14_bit:
            assert isinstance(msg, list)
            assert len(msg) == 2
            await self.mapped_device.send_messages(msg)
        else:
            await self.mapped_device.send_message(msg)


class MappedController(MappedParameter):
    """:class:`MappedParameter` subclass that uses midi control-change messages

    Attributes:
        controller (int): The controller number

    """
    controller = None
    value_min = 0
    value_max = 1
    def __init__(self, mapped_device: MappedDevice, param_spec: BaseParameterSpec, map_obj: Map, **kwargs):
        super().__init__(mapped_device, param_spec, map_obj, **kwargs)
        self.controller = kwargs['controller']

    async def _handle_incoming_message(self, msg: mido.Message):
        value = self.scale_from_midi(msg.value)
        logger.debug(f'setting {self.param_spec.name} to {value} (msg.value={msg.value}), value_range={self.value_range}')
        await self.param_group.set_param_value(self.param_spec.name, value)

    def message_valid(self, msg: mido.messages.BaseMessage) -> bool:
        if msg.type != 'control_change':
            return False
        if msg.control != self.controller:
            return False
        return super().message_valid(msg)

    def get_message_type(self, value: NumOrBool) -> str:
        return 'control_change'

    def get_message_kwargs(self, value: NumOrBool) -> Dict:
        kw = super().get_message_kwargs(value)
        kw['control'] = self.controller
        kw['value'] = self.scale_to_midi(value)
        return kw

class MappedAliasController(MappedController):
    def __init__(self, mapped_device: MappedDevice, param_spec: BaseParameterSpec, map_obj: Map, **kwargs):
        super().__init__(mapped_device, param_spec, map_obj, **kwargs)
        self.name = self.map_obj.full_name
        loop = mapped_device.loop
        self.param_spec.unbind(self)
        self.param_spec.bind_async(
            loop,
            **{self.property_name:self.on_param_spec_value_changed}
        )

    @property
    def property_name(self) -> str:
        return self.map_obj.property_name

    def get_current_value(self):
        return getattr(self.param_spec, self.property_name)

    async def _handle_incoming_message(self, msg: mido.Message):
        value = self.scale_from_midi(msg.value)
        logger.debug(f'setting {self.property_name} to {value} (msg.value={msg.value}), value_range={self.value_range}')
        setattr(self.param_spec, self.property_name, value)

class MappedController14Bit(MappedController):
    """A :class:`MappedController` using 14-bit Midi values
    """

    @property
    def controller_msb(self) -> int:
        """The controller index containing the most-significant 7 bits

        This will always be equal to the :attr:`controller` value
        """
        return self.map_obj.controller_msb

    @property
    def controller_lsb(self) -> int:
        """The controller index containing the least-significant 7 bits

        Per the MIDI 1.0 specification, this will be :attr:`controller_msb` + 32
        """
        return self.map_obj.controller_lsb

    async def handle_incoming_messages(self, msgs: Iterable[mido.Message]):
        ctrl_lsb, ctrl_msb = self.controller_lsb, self.controller_msb
        msg_lsb, msg_msb = None, None
        for msg in msgs:
            if msg.type != 'control_change':
                continue
            if msg.channel != self.channel:
                continue
            if msg.control == ctrl_lsb:
                msg_lsb = msg
            elif msg.control == ctrl_msb:
                msg_msb = msg
        if msg_msb is None:
            if msg_lsb is not None:
                logger.warning(f'No MSB message found: msg_lsb={msg_lsb}')
            return
        value = msg_msb.value << 7
        if msg_lsb is not None:
            value |= msg_lsb.value
        value = self.scale_from_midi(value)
        # logger.info(f'{self.param_spec.name}: {msg_msb=}, {msg_lsb=}, {value=}, {value_scaled=}')
        logger.debug(f'setting {self.param_spec.name} to {value}')
        await self.param_group.set_param_value(self.param_spec.name, value)

    def message_valid(self, msg: mido.messages.BaseMessage) -> bool:
        if msg.type != 'control_change':
            return False
        if msg.control != self.controller_lsb or msg.control != self.controller_msb:
            return False
        return msg.channel == self.channel

    def build_message(self, value: NumOrBool) -> List[mido.Message]:
        value = self.scale_to_midi(value)
        msg_list = [
            mido.Message(
                'control_change',
                channel=self.channel,
                control=self.controller_msb,
                value=value >> 7,
            ),
            mido.Message(
                'control_change',
                channel=self.channel,
                control=self.controller_lsb,
                value=value & 0x7f,
            ),
        ]
        return msg_list

class MappedNoteParam(MappedParameter):
    """:class:`MappedParameter` subclass that uses midi note messages

    Intended for boolean values. Sends a ``note_on`` message with velocity
    of ``127`` for True and ``0`` for False.

    Incoming ``note_on`` messages with velocity < 0 are treated as
    ``True``, velocity == 0 and ``note_off`` messages are considered ``False``.

    Attributes:
        note (int): The midi note number

    """
    note = None

    def __init__(self, mapped_device: MappedDevice, param_spec: BaseParameterSpec, map_obj: Map, **kwargs):
        super().__init__(mapped_device, param_spec, map_obj, **kwargs)
        self.note = kwargs['note']

    async def _handle_incoming_message(self, msg: mido.Message):
        if msg.type == 'note_on':
            value = msg.velocity > 0
        else:
            value = False
        await self.param_group.set_param_value(self.param_spec.name, value)

    def message_valid(self, msg: mido.messages.BaseMessage) -> bool:
        if msg.type not in ['note_on', 'note_off']:
            return False
        if msg.note != self.note:
            return False
        return super().message_valid(msg)

    def get_message_type(self, value: NumOrBool) -> str:
        return 'note_on'

    def get_message_kwargs(self, value: NumOrBool) -> Dict:
        kw = super().get_message_kwargs(value)
        kw['note'] = self.note
        if not isinstance(value, bool):
            v = self.scale_to_midi(value)
            value = v == 127
        kw['velocity'] = 127 if value else 0
        return kw

class AdjustController(MappedController):
    """A :class:`MappedController` that sends outgoing messages like
    :class:`MappedController`, but incoming messages will either increment (>=64)
    or decrement (<64) the value.

    The use case for this would be for parameters that lack a direct setter method,
    but instead rely on adjustment methods.

    An example would be the :attr:`~jvconnected.device.ExposureParams.gain_pos`
    attribute of :class:`jvconnected.device.ExposureParams` where the value can
    only be changed using the :meth:`~jvconnected.device.ExposureParams.increase_gain`
    and :meth:`~jvconnected.device.ExposureParams.decrease_gain` methods.

    """
    def __init__(self, mapped_device: MappedDevice, param_spec: BaseParameterSpec, map_obj: Map, **kwargs):
        super().__init__(mapped_device, param_spec, map_obj, **kwargs)

    async def _handle_incoming_message(self, msg: mido.Message):
        if msg.value >= 64:
            logger.debug(f'incrementing {self.param_spec.name}')
            await self.param_group.increment_param_value(self.param_spec.name)
        else:
            logger.debug(f'decrementing {self.param_spec.name}')
            await self.param_group.decrement_param_value(self.param_spec.name)

    def message_valid(self, msg: mido.messages.BaseMessage) -> bool:
        if msg.type != 'control_change':
            return False
        if msg.control != self.controller:
            return False
        return super().message_valid(msg)

    def get_message_type(self, value: NumOrBool) -> str:
        return 'control_change'

    def get_message_kwargs(self, value: NumOrBool) -> Dict:
        kw = super().get_message_kwargs(value)
        kw['control'] = self.controller
        kw['value'] = self.scale_to_midi(value)
        return kw

CONTROLLER_CLS = {
    'controller':MappedController,
    'controller/14':MappedController14Bit,
    'note':MappedNoteParam,
    'adjust_controller':AdjustController,
    'alias_controller':MappedAliasController,
}
