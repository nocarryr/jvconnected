import pytest

from jvconnected.interfaces.netlinx import client

@pytest.fixture
def tally_messages():
    messages = {'PGM':{}, 'PVW':{}, 'ALL':set()}
    for i in range(32):
        for key in ['PGM', 'PVW']:
            if i not in messages[key]:
                messages[key][i] = {}
            for val, sval in ((True, '1'), (False, '0')):
                msg = f'<TALLY.{key}:{i}={sval}>'
                tally_p = client.TallyParameter(tally_type=key, index=i, value=val)
                assert tally_p.to_api_string() == msg
                messages[key][i][val] = tally_p
                messages['ALL'].add(msg)
    return messages

def test_message_parsing(tally_messages):
    all_msg_str = 'blahblah\n'.join(tally_messages['ALL'])
    all_msg_str = f'FOO.\n IGNOREME{all_msg_str}BAR\nbaz'
    parsed_messages = set()
    for msg, remaining in client.iter_messages(all_msg_str):
        if not len(msg):
            assert remaining == 'BAR\nbaz'
            continue
        assert msg not in parsed_messages
        parsed_messages.add(msg)
    assert parsed_messages == tally_messages['ALL']

@pytest.mark.asyncio
async def test_client_message_parsing(tally_messages):
    all_msg_str = 'blahblah\n'.join(tally_messages['ALL'])
    all_msg_str = f'FOO.\n IGNOREME{all_msg_str}BAR\nbaz'

    obj = client.NetlinxClient()

    results = await obj.handle_incoming(all_msg_str)

    for result in results:
        assert isinstance(result, client.TallyParameter)
        tally_p = tally_messages[result.tally_type][result.index][result.value]
        assert result == tally_p
        assert result.to_api_string() == tally_p.to_api_string()
