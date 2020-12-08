from typing import Any, Callable
from PySide2 import QtCore


class GenericQObject(QtCore.QObject):
    """Utility class to remove some of the boilerplate code
    needed to implement :class:`QtCore.Property` attributes.

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
        """To be used in the 'getter' method for a :class:`QtCore.Property`

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
