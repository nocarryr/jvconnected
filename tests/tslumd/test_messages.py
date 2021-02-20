from pathlib import Path
import json

import pytest

from jvconnected.interfaces.tslumd import TallyColor
from jvconnected.interfaces.tslumd.messages import Message, Display, Flags

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / 'data'
MESSAGE_FILE = DATA_DIR / 'uhs500-message.umd'
MESSAGE_JSON = DATA_DIR / 'uhs500-tally.json'

@pytest.fixture
def uhs500_msg_bytes() -> bytes:
    """Real message data received from an AV-UHS500 switcher
    """
    return MESSAGE_FILE.read_bytes()

@pytest.fixture
def uhs500_msg_parsed() -> Message:
    """Expected :class:`~jvconnected.interfaces.tslumd.messages.Message` object
    matching data from :func:`uhs500_msg_bytes`
    """
    data = json.loads(MESSAGE_JSON.read_text())
    data['scontrol'] = b''
    displays = []
    for disp in data['displays']:
        for key in ['rh_tally', 'txt_tally', 'lh_tally']:
            disp[key] = getattr(TallyColor, disp[key])
        displays.append(Display(**disp))
    data['displays'] = displays
    return Message(**data)

def test_uhs_message(uhs500_msg_bytes, uhs500_msg_parsed):
    parsed, remaining = Message.parse(uhs500_msg_bytes)
    assert not len(remaining)
    assert parsed == uhs500_msg_parsed

def test_messages():
    msgobj = Message(version=1, screen=5)
    rh_tallies = [getattr(TallyColor, attr) for attr in ['RED','OFF','GREEN','AMBER']]
    lh_tallies = [getattr(TallyColor, attr) for attr in ['GREEN','RED','OFF','RED']]
    txt_tallies = [getattr(TallyColor, attr) for attr in ['OFF','GREEN','AMBER','GREEN']]
    txts = ['foo', 'bar', 'baz', 'blah']
    indices = [4,3,7,1]
    for i in range(4):
        disp = Display(
            index=indices[i], rh_tally=rh_tallies[i], lh_tally=lh_tallies[i],
            txt_tally=txt_tallies[i], text=txts[i], brightness=i,
        )
        msgobj.displays.append(disp)

    parsed, remaining = Message.parse(msgobj.build_message())
    assert not len(remaining)

    for i in range(len(rh_tallies)):
        disp1, disp2 = msgobj.displays[i], parsed.displays[i]
        assert disp1.rh_tally == disp2.rh_tally == rh_tallies[i]
        assert disp1.lh_tally == disp2.lh_tally == lh_tallies[i]
        assert disp1.txt_tally == disp2.txt_tally == txt_tallies[i]
        assert disp1.text == disp2.text == txts[i]
        assert disp1.index == disp2.index == indices[i]
        assert disp1 == disp2

    for attr in ['version', 'flags', 'screen', 'scontrol']:
        assert getattr(msgobj, attr) == getattr(parsed, attr)

    assert msgobj == parsed
