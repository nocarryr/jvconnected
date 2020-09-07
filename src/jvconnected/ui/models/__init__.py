from . import device
from . import engine
from . import midi

def register_qml_types():
    device.register_qml_types()
    engine.register_qml_types()
    midi.register_qml_types()
