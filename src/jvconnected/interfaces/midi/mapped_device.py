from loguru import logger
import asyncio
from numbers import Number
from typing import Union, Dict, Any

import mido
from pydispatch import Dispatcher, Property, DictProperty

from jvconnected.interfaces.paramspec import ParameterGroupSpec, ParameterSpec, BaseParameterSpec

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
            for param_spec in pg.parameter_list:
                if param_spec.full_name in self.mapper:
                    m = self.mapper[param_spec.full_name]
                    mp_cls = CONTROLLER_CLS[m.map_type]
                    kw = {}
                    if mp_cls is MappedNoteParam:
                        kw['note'] = m.note
                    else:
                        kw['controller'] = m.controller
                    mapped_param = mp_cls(self, param_spec, m.name, **kw)
                    self.mapped_params[mapped_param.name] = mapped_param

    async def handle_incoming_message(self, msg: mido.messages.BaseMessage):
        """Dispatch an incoming message to all :class:`MappedParameter` instances

        The :meth:`MappedParameter.handle_incoming_message` method is called for
        each parameter instance in :attr:`mapped_params`
        """
        coros = set()
        for mapped_param in self.mapped_params.values():
            coros.add(mapped_param.handle_incoming_message(msg))
        await asyncio.gather(*coros)

    async def send_all_parameters(self):
        """Send values for all mapped parameters (full refresh)
        """
        coros = set()
        for mapped_param in self.mapped_params.values():
            value = mapped_param.get_current_value()
            msg = mapped_param.build_message(value)
            coros.add(self.send_message(msg))
        await asyncio.gather(*coros)

    async def send_message(self, msg: mido.Message):
        """Send the given message with :attr:`midi_io`
        """
        await self.midi_io.send_message(msg)


class MappedParameter(Dispatcher):
    """Handles midi input and output for a single parameter within a
    :class:`jvconnected.device.ParameterGroup`

    Attributes:
        mapped_device (MappedDevice): The parent :class:`MappedDevice` instance
        param_group (ParameterGroupSpec): The :class:`~jvconnected.interfaces.paramspec.ParameterGroupSpec`
            definition that describes the parameter
        param_name (str): The parameter name within the param_group
        name (str): Unique name of the parameter as defined by
            :attr:`jvconnected.interfaces.paramspec.ParameterSpec.full_name`
        param_spec: The :class:`~jvconnected.interfaces.paramspec.ParameterSpec`
            instance within the :attr:`param_group`
        channel (int): The midi channel to use, typically gathered from :attr:`mapped_device`
        value_min (int): Minimum value for the parameter as it exists in the
            :class:`jvconnected.device.ParameterGroup`
        value_max (int): Maximum value for the parameter as it exists in the
            :class:`jvconnected.device.ParameterGroup`

    """
    name = None
    channel = 0
    value_min = 0
    value_max = 1

    def __init__(self, mapped_device: MappedDevice, param_spec: BaseParameterSpec, param_name: str, **kwargs):
        self.mapped_device = mapped_device
        loop = mapped_device.loop
        self.param_group = param_spec.param_group_spec
        self.param_spec = param_spec
        self.name = self.param_spec.full_name
        self.channel = kwargs.get('channel', mapped_device.midi_channel)
        if hasattr(self.param_spec.value_type, 'value_min'):
            self.value_min = self.param_spec.value_type.value_min
            self.value_max = self.param_spec.value_type.value_max
        self.param_spec.bind_async(loop, value=self.on_param_spec_value_changed)

    @property
    def value_range(self) -> Number:
        """Total range of values calculated as ``value_max - value_min``
        """
        return self.value_max - self.value_min

    async def handle_incoming_message(self, msg: mido.messages.BaseMessage):
        """Process an incoming message

        If the message is valid for this object, the appropriate setter methods
        will by called on the :attr:`param_spec`

        """
        if not self.message_valid(msg):
            return
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
        """Scale the given value to a range of 0 to 127

        If the given value is :any:`bool`, this will return ``127`` for ``True``
        and ``0`` for ``False``.

        Otherwise the result will be :math:`((value - vmin) / vrange * 127`

        """
        if isinstance(value, bool):
            return 127 if value else 0
        r = (value - self.value_min) / self.value_range
        return int(r * 127)

    def scale_from_midi(self, value: int) -> int:
        """Scale a value from :math:`[0,1,..,127]` to the range expected by the
        parameter. This results in :math:`(value / 127) * vrange + vmin`

        """
        r = value / 127
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

    async def on_param_spec_value_changed(self, instance, value, **kwargs):
        msg = self.build_message(value)
        await self.mapped_device.send_message(msg)



class MappedController(MappedParameter):
    """:class:`MappedParameter` subclass that uses midi control-change messages

    Attributes:
        controller (int): The controller number

    """
    controller = None
    value_min = 0
    value_max = 1
    def __init__(self, mapped_device: MappedDevice, param_spec: BaseParameterSpec, param_name: str, **kwargs):
        super().__init__(mapped_device, param_spec, param_name, **kwargs)
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

    def __init__(self, mapped_device: MappedDevice, param_spec: BaseParameterSpec, param_name: str, **kwargs):
        super().__init__(mapped_device, param_spec, param_name, **kwargs)
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

    An example would be the :attr:`~jvconnected.device.ExposureParams.gain`
    attribute of :class:`jvconnected.device.ExposureParams` where the value can
    only be changed using the :meth:`~jvconnected.device.ExposureParams.increase_gain`
    and :meth:`~jvconnected.device.ExposureParams.decrease_gain` methods.

    """
    def __init__(self, mapped_device: MappedDevice, param_spec: BaseParameterSpec, param_name: str, **kwargs):
        super().__init__(mapped_device, param_spec, param_name, **kwargs)

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
    'note':MappedNoteParam,
    'adjust_controller':AdjustController,
}
