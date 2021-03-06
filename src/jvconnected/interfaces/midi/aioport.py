from loguru import logger
import asyncio
import queue
from typing import Optional, Any
from numbers import Number

import mido
from pydispatch import Dispatcher, Property, DictProperty

class BasePort(Dispatcher):
    """Async wrapper for :any:`mido.ports`

    Arguments:
        name (str): The port name

    Properties:
        name (str): The port name
        running (bool): Current run state

    Attributes:
        stopped (asyncio.Event):

    """
    MAX_QUEUE = 100
    name = Property()
    running = Property(False)
    def __init__(self, name: str):
        self.name = name
        self.loop = asyncio.get_event_loop()
        # self.queue = asyncio.Queue(self.MAX_QUEUE)
        # self.running = asyncio.Event()
        self.stopped = asyncio.Event()
        self.port = None

    async def open(self) -> bool:
        """Open the midi port

        Returns:
            bool: ``True`` if the port was successfully opened

        """
        if self.running:
            return False
        self.running = True
        self.port = await self._build_port()
        # if port is not None:
        #     self.name = self.port.name
        logger.debug(f'{self}.port: {self.port}')
        logger.success(f'{self} running')
        return True

    async def close(self):
        """Close the midi port
        """
        if not self.running:
            return False
        self.running = False
        await self._close_port()
        self.stopped.set()
        logger.success(f'{self} closed')
        return True

    async def __aenter__(self):
        await self.open()
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def _build_port(self):
        raise NotImplementedError

    async def _close_port(self):
        raise NotImplementedError

    def __repr__(self):
        return f'<{self.__class__}: "{self}">'

    def __str__(self):
        return self.name


class InputPort(BasePort):
    """Async wrapper around :class:`mido.ports.BaseInput`

    Attributes:
        queue (asyncio.Queue): Message queue for the port

    """
    def __init__(self, name: str):
        super().__init__(name)
        self.queue = asyncio.Queue(self.MAX_QUEUE)

    async def receive(self, timeout: Optional[Number] = None) -> Optional[mido.Message]:
        """Wait for an incoming message

        Arguments:
            timeout (float, optional): Time to wait for a message.
                if ``None``, wait until an item is available

        Returns:
            An instance of :class:`mido.Message`.  If timeout was provided and
            no message was retrieved, ``None`` will be returned.

        """
        return await self.queue_get(timeout)

    async def queue_get(self, timeout: Optional[Number] = None) -> Any:
        """Convenience method for :meth:`~asyncio.Queue.get` on the :attr:`queue`

        Arguments:
            timeout (float, optional): Time to wait for an item on the queue.
                if ``None``, wait until an item is available

        """
        if timeout is None:
            item = await self.queue.get()
        else:
            try:
                item = await asyncio.wait_for(self.queue.get(), timeout)
            except asyncio.TimeoutError:
                item = None
        return item

    def task_done(self):
        """Convenience method for :attr:`queue` :meth:`~asyncio.Queue.task_done`
        """
        self.queue.task_done()

    async def _build_port(self) -> mido.ports.BaseOutput:
        port = None
        port = mido.open_input(self.name, callback=self._inport_callback)
        # try:
        #     port = mido.open_input(self.name, callback=self._inport_callback)
        # except Exception as exc:
        #     if port is not None:
        #         port.close()
        #         port = None
        #     logger.exception(exc)
        #     raise
        return port

    async def _close_port(self):
        port = self.port
        if port is not None:
            port.close()
        self.port = None

    def _inport_callback(self, msg: mido.messages.BaseMessage):
        async def enqueue(_msg):
            await self.queue.put(_msg)
        asyncio.run_coroutine_threadsafe(enqueue(msg), loop=self.loop)



class OutputPort(BasePort):
    """Async wrapper around :class:`mido.ports.BaseOutput`

    Attributes:
        queue (queue.Queue): Message queue for the port. Since the output port
            operates in a separate thread, this is a thread-based queue (not
            async)

    """
    def __init__(self, name: Optional[str] = None):
        super().__init__(name)
        self._send_loop_task = None
        self.queue = queue.Queue()

    async def open(self) -> bool:
        did_open = await super().open()
        if did_open:
            # self._send_loop_task = asyncio.ensure_future(self._send_loop())
            self._send_loop_task = self.loop.run_in_executor(None, self._blocking_send_loop)
        return did_open

    async def send(self, msg: mido.Message):
        """Send a message

        The message will be placed on the :attr:`queue` and sent from a separate
        thread

        Arguments:
            msg: The :class:`mido.Message` to send

        """
        # await self.queue.put(msg)
        self.queue.put_nowait(msg)

    async def _build_port(self) -> mido.ports.BaseOutput:
        port = None
        port = mido.open_output(self.name)
        return port

    async def _close_port(self):
        # try:
        #     self.queue.put_nowait(False)
        # except asyncio.QueueFull:
        #     pass
        self.queue.put_nowait(None)
        t = self._send_loop_task
        if t is not None:
            await t
        self._send_loop_task = None
        port = self.port
        if port is not None:
            port.close()
        self.port = None

    def _blocking_send_loop(self):
        self.port.reset()
        while self.running:
            try:
                msg = self.queue.get(timeout=.5)
            except queue.Empty:
                continue
            if msg is None:
                break
            self.port.send(msg)
            self.queue.task_done()

    # async def _send_loop(self):
    #     self.port.reset()
    #     while self.running:
    #         msg = await self.queue_get(timeout=.5)
    #         if msg is None:
    #             continue
    #         if msg is False:
    #             self.task_done()
    #             break
    #         self.port.send(msg)
    #         self.task_done()


class IOPort(BasePort):
    inport = Property()
    outport = Property()

    async def _build_port(self):
        self.inport = InputPort(self.name)
        self.outport = OutputPort(self.name)

        await self.inport.open()
        await self.outport.open()
        return None

    async def _close_port(self):
        if self.inport is not None:
            await self.inport.close()
            self.inport = None
        if self.outport is not None:
            await self.outport.close()
            self.outport = None
