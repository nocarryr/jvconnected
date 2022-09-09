import sys
import asyncio
import functools
from typing import Any, Callable, Coroutine, NamedTuple
from PySide2 import QtCore


class GenericQObject(QtCore.QObject):
    """Utility class to remove some of the boilerplate code
    needed to implement :class:`~PySide2.QtCore.Property` attributes.

    The intended pattern uses the following naming convention::

        class MyQtObject(GenericQObject):
            _n_fooValue = Signal()      # The 'notify' signal to emit on changes

            def __init__(self, *args):
                self._fooValue = 0      # The instance attribute containing the value

            def _get_fooValue(self):
                return self._fooValue

            def _set_fooValue(self, value):
                self._generic_setter('_fooValue', value)

            fooValue = Property(_get_fooValue, _set_fooValue, notify=_n_fooValue)


    """
    def _generic_property_changed(self, attr: str, old_value: Any, new_value: Any):
        """Fired by :meth:`_generic_setter` on value changes (after the notify
        signal emission)

        :meta public:
        """
        pass

    def _generic_setter(self, attr: str, value: Any):
        """To be used in the 'getter' method for a :class:`~PySide2.QtCore.Property`

        Arguments:
            attr (str): The instance attribute name containing the Property value
            value: The value passed from the original setter

        :meta public:
        """
        cur_value = getattr(self, attr)
        if cur_value == value:
            return
        setattr(self, attr, value)
        sig_name = f'_n{attr}'
        sig = getattr(self, sig_name)
        sig.emit()
        self._generic_property_changed(attr, cur_value, value)

def connect_close_event(f: Callable):
    """Connect the app ``aboutToQuit`` signal to the provided callback function
    """
    app = QtCore.QCoreApplication.instance()
    app.aboutToQuit.connect(f)

def connect_async_close_event(fn: Coroutine):
    app = QtCore.QCoreApplication.instance()

    @functools.wraps(fn)
    def wrapper():
        task = asyncio.create_task(fn())
        while not task.done():
            QtCore.QCoreApplication.instance().processEvents()
    QtCore.QCoreApplication.instance().aboutToQuit.connect(wrapper)


def AnnotatedQtSignal(**kwargs):
    """Allows :external+PySide6:class:`~PySide6.QtCore.PySide6.QtCore.Signal`
    methods to be annotated with arguments and types

    The keyword arguments should be in the form of
    ``AnnotatedQtSignal(arg_name=arg_type)``

    .. code-block:: python

        from PySide2.QtCore import QObject, Signal
        from jvconnected.ui.utils import AnnotatedQtSignal as AnnoSignal

        class MyObject(QObject):
            my_signal: AnnoSignal(name=str, value=int) = Signal(str, int)
            '''Description of ``my_signal``'''


    This allows a custom Sphinx extension to include the annotated argument names
    with their types (as a normal method would appear) instead of the types only.

    .. note::

        This does not yet support type checking and will very likely fail against
        MyPy checks. It only exists for documentation purposes.
    """
    try:
        module = sys._getframe(1).f_globals.get('__name__', '__main__')
    except (AttributeError, ValueError):
        module = None
    nm_tpl = NamedTuple(AnnotatedQtSignal.__qualname__, **kwargs)
    if module is not None:
        nm_tpl.__module__ = module
    return nm_tpl
