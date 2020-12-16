import asyncio

from pydispatch import Dispatcher, Property

class Interface(Dispatcher):
    """Base interface class

    Subclasses must override the :meth:`open` and :meth:`close` methods.
    In order to operate with the :class:`~jvconnected.engine.Engine`, the class
    should be added to the :attr:`~jvconnected.interfaces.registry`

    Properties:
        running (bool): Run state

    Attributes:
        loop: The :class:`asyncio.BaseEventLoop` associated with the instance

    """
    running = Property(False)
    def __init__(self, *args, **kwargs):
        self._engine = None
        self.loop = asyncio.get_event_loop()

    @property
    def engine(self) -> 'jvconnected.engine.Engine':
        """Instance of :class:`jvconnected.engine.Engine`
        """
        return self._engine

    async def set_engine(self, engine: 'jvconnected.engine.Engine'):
        """Attach the interface to a running instance of :class:`jvconnected.engine.Engine`

        This will be called automatically by the engine if the class is in the
        :attr:`jvconnected.interfaces.registry`.

        If the engine is running, the interface will start (using the :meth:`open` method).
        Otherwise it will automatically start when the engine does.
        """
        if engine is self.engine:
            return
        assert self.engine is None
        self._engine = engine
        if engine.running:
            await self.open()
        engine.bind_async(
            self.loop,
            running=self.on_engine_running,
        )

    async def open(self):
        """Open all communication methods
        """
        raise NotImplementedError

    async def close(self):
        """Stop communication
        """
        raise NotImplementedError

    async def on_engine_running(self, instance, value, **kwargs):
        if instance is not self.engine:
            return
        if value:
            if not self.running:
                await self.open()
        else:
            await self.close()
