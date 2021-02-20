import asyncio
from typing import ClassVar, Optional, Dict

from pydispatch import Dispatcher, Property

class Interface(Dispatcher):
    """Base interface class

    Subclasses must override the :meth:`open` and :meth:`close` methods.
    In order to operate with the :class:`~jvconnected.engine.Engine`, the class
    should be added to the :attr:`~jvconnected.interfaces.registry`

    Properties:
        running (bool): Run state
        config: Instance of :class:`jvconnected.config.Config`. This is gathered
            from the :attr:`engine` after :meth:`set_engine` has been called.

    """
    running = Property(False)
    config = Property()

    loop: asyncio.BaseEventLoop
    """The :class:`asyncio.BaseEventLoop` associated with the instance"""

    interface_name: ClassVar[str] = ''
    """Unique name for the interface. Must be defined by subclasses"""

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
        self.config = engine.config
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

    def get_config_section(self) -> Optional[Dict]:
        """Get or create a section within the :attr:`config` specific to this
        interface.

        The returned :class:`dict` can be used to retreive or store
        interface-specific configuration data.

        Returns ``None`` if :attr:`config` has not been set.
        """
        conf = self.config
        if conf is None:
            return None
        main_section = conf.get('interfaces')
        if main_section is None:
            main_section = conf['interfaces'] = {}
        d = main_section.get(self.interface_name)
        if d is None:
            d = main_section[self.interface_name] = {}
        return d
