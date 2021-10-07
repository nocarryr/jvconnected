from loguru import logger
import asyncio
from typing import List, Sequence

import mido
import rtmidi
from pydispatch import Dispatcher, Property, DictProperty, ListProperty

from jvconnected.utils import IOType
from jvconnected.interfaces import Interface
from jvconnected.interfaces.midi.aioport import InputPort, OutputPort
from jvconnected.interfaces.midi.mapped_device import MappedDevice
from jvconnected.interfaces.midi.mapper import MidiMapper

class MidiIO(Interface):
    """Midi interface handler

    Properties:
        inport_names (List[str]): list of input port names to use (as ``str``)
        outport_names (List[str]): list of output port names to use (as ``str``)
        inports (Dict[str, InputPort]): Mapping of :class:`~.aioport.InputPort`
            instances stored with the names as keys
        outports (Dict[str, OutputPort]): Mapping of :class:`~.aioport.OutputPort`
            instances stored with the names as keys
        mapped_devices (Dict[str, MappedDevice]): Mapping of
            :class:`~.mapped_device.MappedDevice` instances stored with
            the device id as keys

    :Events:

        .. event:: port_state(io_type: jvconnected.utils.IOType, name: str, state: bool)

            Fired when a port is added or removed using one of :meth:`add_input`,
            :meth:`add_output`, :meth:`remove_input`, :meth:`remove_output`.

            :param io_type: The type of port (input or output)
            :type io_type: :class:`jvconnected.utils.IOType`
            :param str name: The port name
            :param bool state: ``True`` if the port was added, ``False`` if it
                was removed

    """
    inport_names = ListProperty(copy_on_change=True)
    outport_names = ListProperty(copy_on_change=True)
    inports = DictProperty()
    outports = DictProperty()
    mapped_devices = DictProperty()
    mapper = Property()
    interface_name = 'midi'
    _events_ = ['port_state']
    def __init__(self):
        super().__init__()
        self._consume_tasks = {}
        self._reading_config = False
        self._port_lock = asyncio.Lock()
        self._refresh_event = asyncio.Event()
        self._refresh_task = None
        self.mapper = MidiMapper()
        self.bind_async(
            self.loop,
            inport_names=self.on_inport_names,
            outport_names=self.on_outport_names,
        )
        self.bind(config=self.read_config)

    @classmethod
    def get_available_inputs(cls) -> List[str]:
        """Get all detected input port names
        """
        return mido.get_input_names()

    @classmethod
    def get_available_outputs(cls) -> List[str]:
        """Get all detected output port names
        """
        return mido.get_output_names()

    async def set_engine(self, engine: 'jvconnected.engine.Engine'):
        if engine is self.engine:
            return
        await super().set_engine(engine)
        self.automap_engine_devices()
        engine.bind(devices=self.automap_engine_devices)

    def automap_engine_devices(self, *args, **kwargs):
        """Map the engine's devices by index
        """
        config = self.engine.config
        for conf_device in config.indexed_devices.values():
            device_id = conf_device.id
            device_index = conf_device.device_index
            if device_index > 15:
                break
            device = self.engine.devices.get(device_id)
            mapped_device = self.mapped_devices.get(device_index)

            if device is None:
                if mapped_device is not None:
                    self.unmap_device(device_index)
            elif mapped_device is None:
                self.map_device(device_index, device)
            elif device is not mapped_device.device:
                self.map_device(device_index, device)

    @logger.catch
    async def open(self):
        """Open any configured input and output ports and begin communication
        """
        if self.running:
            return
        logger.debug('MidiIO.open()')
        self.running = True
        await self.open_ports()
        self._refresh_task = asyncio.ensure_future(self.periodic_refresh())
        logger.success('MidiIO running')

    async def close(self):
        """Stop communication and close all input and output ports
        """
        if not self.running:
            return
        logger.debug('MidiIO.close()')
        self.running = False
        self._refresh_event.set()
        await self._refresh_task
        self._refresh_task = None
        await self.close_ports()
        logger.success('MidiIO stopped')

    async def open_ports(self):
        """Open any configured input and output ports.
        (Called by :meth:`open`)
        """
        for name in self.inport_names:
            await self.add_input(name)
        for name in self.outport_names:
            await self.add_output(name)

    async def close_ports(self):
        """Close all running input and output ports
        (Called by :meth:`close`)
        """
        coros = set()
        for port in self.inports.values():
            coros.add(port.close())
        for port in self.outports.values():
            coros.add(port.close())
        await asyncio.gather(*coros)

    async def add_input(self, name: str):
        """Add an input port

        The port name will be added to :attr:`inport_names` and stored in the
        :attr:`config`.

        If MidiIO is :attr:`running`, an instance of :class:`~.aioport.InputPort`
        will be created and added to :attr:`inports`.

        Arguments:
            name (str): The port name (as it appears in :meth:`get_available_inputs`)

        """
        async with self._port_lock:
            logger.info(f'add_input: {name}')
            if name not in self.inport_names:
                self.inport_names.append(name)
            if name in self.inports:
                raise ValueError(f'Input "{name}" already open')
            port = InputPort(name)
            logger.debug(f'port: {port}')
            self.inports[name] = port
            port.bind_async(self.loop, running=self.on_inport_running)
            if self.running:
                try:
                    await port.open()
                except rtmidi.SystemError as exc:
                    await port.close()
                    del self.inports[name]
                    logger.exception(exc)
                    return
        self.emit('port_state', IOType.INPUT, name, True)

    async def add_output(self, name: str):
        """Add an output port

        The port name will be added to :attr:`outport_names` and stored in the
        :attr:`config`.

        If MidiIO is :attr:`running`, an instance of :class:`~.aioport.OutputPort`
        will be created and added to :attr:`outports`.

        Arguments:
            name (str): The port name (as it appears in :meth:`get_available_outputs`)

        """
        async with self._port_lock:
            if name not in self.outport_names:
                self.outport_names.append(name)
            if self.running:
                if name in self.outports:
                    raise ValueError(f'Output "{name}" already open')
                port = OutputPort(name)
                logger.debug(f'port: {port}')
                self.outports[name] = port
                try:
                    await port.open()
                except rtmidi.SystemError as exc:
                    await port.close()
                    del self.outports[name]
                    logger.exception(exc)
                    return
        self.emit('port_state', IOType.OUTPUT, name, True)

    async def close_inport(self, name: str):
        port = self.inports[name]
        port.unbind(self)
        await port.close()
        task = self._consume_tasks.get(name)
        if task is not None:
            await task
            del self._consume_tasks[name]

    async def remove_input(self, name: str):
        """Remove an input port from :attr:`inports` and :attr:`inport_names`

        If the port exists in :attr:`inports`, it will be closed and removed.

        Arguments:
            name (str): The port name

        """
        async with self._port_lock:
            if name in self.inports:
                await self.close_inport(name)
                del self.inports[name]
            if name in self.inport_names:
                self.inport_names.remove(name)
        self.emit('port_state', IOType.INPUT, name, False)

    async def remove_output(self, name: str):
        """Remove an output port from :attr:`outports` and :attr:`outport_names`

        If the port exists in :attr:`outports`, it will be closed and removed.

        Arguments:
            name (str): The port name

        """
        async with self._port_lock:
            if name in self.outports:
                port = self.outports[name]
                await port.close()
                del self.outports[name]
            if name in self.outport_names:
                self.outport_names.remove(name)
        self.emit('port_state', IOType.OUTPUT, name, False)

    @logger.catch
    async def periodic_refresh(self):
        while self.running:
            try:
                r = await asyncio.wait_for(self._refresh_event.wait(), 30)
            except asyncio.TimeoutError:
                r = False
            if r:
                break
            coros = set()
            for mapped_device in self.mapped_devices.values():
                coros.add(mapped_device.send_all_parameters())
            if len(coros):
                logger.debug('refreshing midi data')
                await asyncio.gather(*coros)

    @logger.catch
    async def consume_incoming_messages(self, port: InputPort):
        while self.running and port.running:
            msgs = await port.receive_many(timeout=.5)
            if msgs is None:
                continue
            logger.opt(lazy=True).debug(
                '{x}', x=lambda: '\n'.join([f'MIDI rx: {msg}' for msg in msgs])
            )
            coros = set()
            for device in self.mapped_devices.values():
                coros.add(device.handle_incoming_messages(msgs))
            if len(coros):
                await asyncio.gather(*coros)

    async def send_message(self, msg: mido.messages.messages.BaseMessage):
        """Send a message to all output ports in :attr:`outports`

        Arguments:
            msg: The :class:`Message <mido.Message>` to send

        """
        coros = set()
        for port in self.outports.values():
            if port.running:
                coros.add(port.send(msg))
        if len(coros):
            await asyncio.gather(*coros)
            logger.opt(lazy=True).debug(f'MIDI tx: {msg}')

    async def send_messages(self, msgs: Sequence[mido.Message]):
        """Send a message to all output ports in :attr:`outports`

        Arguments:
            msgs: A sequence of :class:`Messages <mido.Message>` to send

        """
        coros = set()
        for port in self.outports.values():
            if port.running:
                coros.add(port.send_many(*msgs))
        if len(coros):
            await asyncio.gather(*coros)
            logger.opt(lazy=True).debug(
                '{x}', x=lambda: '\n'.join([f'MIDI tx: {msg}' for msg in msgs])
            )

    def map_device(self, midi_channel: int, device: 'jvconnected.device.Device'):
        """Connect a :class:`jvconnected.device.Device` to a :class:`.mapped_device.MappedDevice`
        """
        if not 0 <= midi_channel <= 15:
            raise ValueError('midi_channel must be between 0 and 15')
        if midi_channel in self.mapped_devices:
            self.unmap_device(midi_channel)
        m = MappedDevice(self, midi_channel, device, self.mapper)
        self.mapped_devices[midi_channel] = m
        logger.debug(f'mapped device: {m}')

    def unmap_device(self, midi_channel: int):
        """Unmap a device
        """
        if midi_channel not in self.mapped_devices:
            return
        logger.debug(f'unmap device: {self.mapped_devices[midi_channel]}')
        del self.mapped_devices[midi_channel]

    async def on_engine_running(self, instance, value, **kwargs):
        if instance is not self.engine:
            return
        if value:
            if not self.running:
                await self.open()
        else:
            await self.close()

    def update_config(self, *args, **kwargs):
        """Update the :attr:`config` with current state
        """
        if self._reading_config:
            return
        d = self.get_config_section()
        if d is None:
            return
        d['inport_names'] = self.inport_names.copy()
        d['outport_names'] = self.outport_names.copy()

    def read_config(self, *args, **kwargs):
        d = self.get_config_section()
        if d is None:
            return
        self._reading_config = True
        for attr in ['inport_names', 'outport_names']:
            conf_val = d.get(attr, [])
            prop_val = getattr(self, attr)
            if conf_val == prop_val:
                continue
            setattr(self, attr, conf_val.copy())
        self._reading_config = False

    async def on_inport_names(self, instance, value, **kwargs):
        self.update_config()
        # if not self.running:
        #     return
        # if self._port_lock.locked():
        #     return
        # old = kwargs['old']
        # new_values = set(old) - set(value)
        # removed_values = set(value) - set(old)
        # logger.info(f'on_inport_names: {value}, new_values: {new_values}, removed_values: {removed_values}')
        # for name in removed_values:
        #     if name in self.inports:
        #         await self.remove_input(name)
        # for name in new_values:
        #     if name not in self.inports:
        #         await self.add_input(name)

    async def on_outport_names(self, instance, value, **kwargs):
        self.update_config()
        # if not self.running:
        #     return
        # old = kwargs['old']
        # new_values = set(old) - set(value)
        # removed_values = set(value) - set(old)
        # for name in removed_values:
        #     if name in self.outports:
        #         await self.remove_output(name)
        # for name in new_values:
        #     if name not in self.outports:
        #         await self.add_output(name)
        # self.update_config()

    async def on_inport_running(self, port, value, **kwargs):
        logger.debug(f'{self}.on_inport_running({port}, {value})')
        if port is not self.inports.get(port.name):
            return
        if value:
            logger.debug(f'starting consume task for {port}')
            assert port.name not in self._consume_tasks
            task = asyncio.ensure_future(self.consume_incoming_messages(port))
            self._consume_tasks[port.name] = task
            logger.debug(f'consume task running for {port}')
        else:
            logger.debug(f'stopping consume task for {port}')
            task = self._consume_tasks.get(port.name)
            if task is not None:
                await task
                del self._consume_tasks[port.name]
