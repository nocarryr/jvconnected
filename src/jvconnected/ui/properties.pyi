from __future__ import annotations
from typing import (
    Unpack, TypedDict, NotRequired, Optional, Callable, Self, overload
)

from PySide6.QtCore import QObject, Signal, Property as QProperty

class _PropertyKwArgs(TypedDict):
    freset: NotRequired[Optional[Callable]]
    doc: NotRequired[str]
    designable: NotRequired[bool]
    scriptable: NotRequired[bool]
    stored: NotRequired[bool]
    user: NotRequired[bool]
    constant: NotRequired[bool]
    final: NotRequired[bool]



class Property[Instance: (QObject), T](QProperty):
    def __init__(
        self,
        type_: type[T],
        fget: Callable[[Instance], T]|None = None,
        fset: Callable[[Instance, T], None]|None = None,
        *,
        notify: Optional[Signal] = None,
        **kwargs: Unpack[_PropertyKwArgs]
    ) -> None: ...

    @overload
    def __get__(self, instance: None, owner: type[Instance]) -> Self: ...
    @overload
    def __get__(self, instance: Instance, owner: type[Instance]) -> T: ...
    def __get__(self, instance: Instance|None, owner: type[Instance]) -> T|Self: ...

    def __set__(self, instance: Instance, value: T) -> None: ...
