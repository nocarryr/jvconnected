from typing import Iterator, Tuple

from pydispatch import Dispatcher

from .base import Interface

class Registry(Dispatcher):
    """Registry for interface modules

    This is a singleton and should not be instanciated directly. Instead, it
    is accessed by :attr:`jvconnected.interfaces.registry`::

        >>> from jvconnected.interfaces import registry, Interface
        >>> class MyInterfaceClass(Interface):
        >>>     pass
        >>> registry.register('my_interface', MyInterfaceClass)
        >>> for name, cls in registry:
        >>>     print(name, cls.__name__)
        my_interface MyInterfaceClass

    Subclasses of :class:`~jvconnected.interfaces.base.Interface` added by the
    :meth:`register` method. The :class:`~jvconnected.engine.Engine` then
    instanciates them and adds them to its :attr:`~jvconnected.engine.Engine.interfaces`.

    :Events:
        .. event:: interface_added(name: str, cls: Interface)

            Fired when an interface is registered

        .. event:: interface_removed(name: str, cls: Interface)

            Fired when an interface is unregistered

    """
    _events_ = ['interface_added', 'interface_removed']
    __instance = None
    def __init__(self):
        if Registry._Registry__instance is not None:
            raise Exception('Only one instance of Registry allowed')
        Registry._Registry__instance = self
        self.__items = {}

    def register(self, name: str, cls):
        """Register an interface

        Arguments:
            name (str): The interface name
            cls: Subclass of :class:`Interface` to register
        """
        if not issubclass(cls, Interface):
            raise ValueError(f'class "{cls!r}" must be a subclass of {Interface!r}')
        if name in self:
            raise ValueError(f'Interface with name "{name}" already registered')
        self.__items[name] = cls
        self.emit('interface_added', name, cls)
    def unregister(self, name: str):
        """Unregister an interface

        Arguments:
            name (str): The interface name

        """
        if name not in self:
            raise ValueError(f'Interface with name "{name}" not registered')
        cls = self[name]
        del self.__items[name]
        self.emit('interface_removed', name, cls)
    def __getitem__(self, key: str) -> Interface:
        return self.__items[name]
    def __iter__(self) -> Iterator[Tuple[str, Interface]]:
        yield from self.__items.items()
    def keys(self) -> Iterator[str]:
        yield from self.__items.keys()
    def values(self) -> Iterator[Interface]:
        yield from self.__items.values()
    def __contains__(self, name: str):
        return name in self.__items

registry: Registry = Registry()
"""Single instance of :class:`Registry` to interact with"""
