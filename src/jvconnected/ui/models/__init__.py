from . import device
from . import devicepreview
from . import engine
from . import midi
from . import tslumd

def register_qml_types():
    device.register_qml_types()
    devicepreview.register_qml_types()
    engine.register_qml_types()
    midi.register_qml_types()
    tslumd.register_qml_types()
