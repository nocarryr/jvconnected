from __future__ import annotations

from PySide6.QtCore import QObject, Property as QProperty


class Property[Instance: (QObject), T](QProperty):
    """Override of :class:`~PySide6.QtCore.Property` to constrain the `Instance`
    as an alias to :obj:`~typing.Self` as well as the type of the property value
    (the first parameter to ``__init__``).

    This way, the instance type is known to be the same as the one used in
    the getter and setter methods.

    In other words, this is a properly typed descriptor for Qt properties through
    the use of this module's type stub.
    """
