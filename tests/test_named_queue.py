import asyncio
import string
import pytest
from typing import Optional, Dict, List

from jvconnected.utils import NamedQueue, NamedItem

@pytest.mark.asyncio
async def test_named_queue():
    queue = NamedQueue()

    async def fill_queue(items: Dict, use_gather: bool = False):
        async def _put_item(key, item):
            qitem = queue.create_item(key, item)
            await queue.put(qitem)

        coros = []
        for key, val in items.items():
            coro = _put_item(key, val)
            if use_gather:
                coros.append(coro)
            else:
                await coro
        if use_gather:
            await asyncio.gather(*coros)


    async def drain_queue(expected: Optional[Dict] = None, use_gather: bool = False) -> List[NamedItem]:
        items = []

        async def _get_item():
            item = await queue.get()
            items.append(item)
            if expected is not None:
                assert item.key in expected
                assert expected[item.key] == item.item

        if use_gather:
            coros = []
            for _ in range(queue.qsize()):
                coros.append(_get_item())
            await asyncio.gather(*coros)
        else:
            while not queue.empty():
                await _get_item()

        return items



    all_keys = tuple(c for c in string.ascii_letters)

    # Simple sanity test
    # Place items then immediately retrieve them
    expected = {key:i for i, key in enumerate(all_keys)}
    await fill_queue(expected)

    assert queue.qsize() == len(expected)
    await drain_queue(expected)


    # Now fill up the queue again, then change the first 10 items
    await fill_queue(expected)

    assert queue.qsize() == len(expected)

    changed = {key:expected[key] * -1 for key in all_keys[:10]}
    await fill_queue(changed)
    expected.update(changed)

    assert queue.qsize() == len(expected) == len(all_keys)

    await drain_queue(expected)


    #
    # Repeat, but use asyncio.gather with multiple tasks
    #


    # Simple sanity test
    # Place items then immediately retrieve them
    expected = {key:i for i, key in enumerate(all_keys)}
    await fill_queue(expected, use_gather=True)

    assert queue.qsize() == len(expected)
    await drain_queue(expected, use_gather=True)


    # Now fill up the queue again, then change the first 10 items
    await fill_queue(expected, use_gather=True)

    assert queue.qsize() == len(expected)

    changed = {key:expected[key] * -1 for key in all_keys[:10]}
    await fill_queue(changed, use_gather=True)
    expected.update(changed)

    assert queue.qsize() == len(expected) == len(all_keys)

    await drain_queue(expected, use_gather=True)
