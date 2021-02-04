from loguru import logger
import asyncio
import dataclasses
from dataclasses import dataclass, field
import enum
import struct
from typing import List, Tuple

from pydispatch import Dispatcher, Property, DictProperty, ListProperty

from jvconnected.interfaces import Interface

class Flags(enum.IntFlag):
    """Message flags
    """
    NO_FLAGS = 0 #: No flags set
    UTF16 = 1
    """Indicates text formatted as ``UTF-16LE`` if set, otherwise ``UTF-8``"""

    SCONTROL = 2
    """Indicates the message contains ``SCONTROL`` data if set, otherwise ``DMESG``
    """

class TallyColor(enum.IntEnum):
    """Color enum for tally indicators"""
    OFF = 0   #: Off
    RED = 1   #: Red
    GREEN = 2 #: Green
    AMBER = 3 #: Amber

@dataclass
class Display:
    """A single tally "display"
    """
    index: int #: The display index
    rh_tally: TallyColor = TallyColor.OFF #: Right hand tally indicator
    txt_tally: TallyColor = TallyColor.OFF #: Text tally indicator
    lh_tally: TallyColor = TallyColor.OFF #: Left hand tally indicator
    brightness: int = 3 #: Display brightness (from 0 to 3)
    text: str = '' #: Text to display
    @classmethod
    def from_dmsg(cls, flags: Flags, dmsg: bytes) -> Tuple['Display', bytes]:
        """Construct an instance from a ``DMSG`` portion of received message.

        Any remaining message data after the relevant ``DMSG`` is returned along
        with the instance.
        """
        hdr = struct.unpack('>2H', dmsg[:4])
        dmsg = dmsg[4:]
        ctrl = hdr[1]
        kw = dict(
            index=hdr[0],
            rh_tally=TallyColor(ctrl & 0b11),
            txt_tally=TallyColor(ctrl >> 2 & 0b11),
            lh_tally=TallyColor(ctrl >> 4 & 0b11),
            brightness=ctrl >> 6 & 0b11,
        )
        is_control_data = ctrl & 0x0f == 0x0f
        if is_control_data:
            raise ValueError('Control data undefined for UMDv5.0')
        else:
            txt_byte_len = struct.unpack('>H', dmsg[:2])[0]
            dmsg = dmsg[2:]
            txt_bytes = dmsg[:txt_byte_len]
            dmsg = dmsg[txt_byte_len:]
            if Flags.UTF16 in flags:
                txt = txt_bytes.decode('UTF-16le')
            else:
                txt = txt_bytes.decode('UTF-8')
            kw['text'] = txt
        return cls(**kw), dmsg

@dataclass
class Message:
    """A single UMDv5 message packet
    """
    version: int = 0 #: Protocol minor version
    flags: int = Flags.NO_FLAGS
    screen: int = 0 #: Screen index
    displays: List[Display] = field(default_factory=list)
    """A list of :class:`Display` instances"""

    scontrol: bytes = b''
    """SCONTROL data (if present).  Not currently implemented"""

    @classmethod
    def parse(cls, msg: bytes) -> Tuple['Message', bytes]:
        """Parse incoming message data to create a :class:`Message` instance.

        Any remaining message data after parsing is returned along with the instance.
        """
        data = struct.unpack('>HBBH', msg[:6])
        byte_count, version, flags, screen = data
        kw = dict(
            version=version,
            flags=Flags(flags),
            screen=screen,
        )
        remaining = msg[byte_count:]
        msg = msg[6:byte_count]
        obj = cls(**kw)
        if Flags.is_control_data in obj.flags:
            obj.scontrol = msg
            return obj
        while len(msg):
            disp, msg = Display.from_dmsg(msg)
            obj.displays.append(disp)
        return obj, remaining
