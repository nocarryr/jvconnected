from PySide2 import QtCore


class GenericQObject(QtCore.QObject):
    def _generic_property_changed(self, attr, old_value, new_value):
        pass
    def _generic_setter(self, attr, value):
        cur_value = getattr(self, attr)
        if cur_value == value:
            return
        setattr(self, attr, value)
        sig_name = f'_n{attr}'
        sig = getattr(self, sig_name)
        sig.emit()
        self._generic_property_changed(attr, cur_value, value)

def connect_close_event(f):
    app = QtCore.QCoreApplication.instance()
    app.aboutToQuit.connect(f)
