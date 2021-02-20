from loguru import logger

from jvconnected.interfaces import registry

try:
    import mido
    MIDI_AVAILABLE = True
except ImportError:
    MIDI_AVAILABLE = False

if MIDI_AVAILABLE:
    from .midi_io import MidiIO
    registry.register(MidiIO)
else:
    MidiIO = None
    logger.warning('''Midi interface unavailable.
    To enable midi support, install the dependencies using
    "pip install jvconnected[midi]"''')
