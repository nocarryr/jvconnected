import asyncio
import string
from dataclasses import dataclass
from typing import List, Tuple, Dict, Iterable, Any, Optional

import pytest

from jvconnected.utils import async_callback

@dataclass
class QueueItem:
    loop: Any
    pargs: Tuple[Any]
    keyword_args: Dict[str, Any]

class Listener:
    def __init__(self, maxsize=0):
        self.queue = asyncio.Queue(maxsize)

    @async_callback
    async def callback(self, *args, **kwargs):
        loop = asyncio.get_event_loop()
        item = QueueItem(loop=loop, pargs=args, keyword_args=kwargs)
        print(f'callback: {item=}')
        await self.queue.put(item)
        exc = kwargs.get('async_exception')
        if exc is not None:
            raise exc

    async def get(self, timeout=None):
        if timeout is None or timeout <= 0:
            return await self.queue.get()
        try:
            result = await asyncio.wait_for(self.queue.get(), timeout)
        except asyncio.TimeoutError:
            result = None
        return result

    def task_done(self):
        self.queue.task_done()

    def empty(self):
        return self.queue.empty()

def build_items_expected(
    keys: Iterable[str], loop: Optional[asyncio.BaseEventLoop] = None
) -> List[QueueItem]:

    if loop is None:
        loop = asyncio.get_event_loop()
    result = []
    for i, c in enumerate(keys):
        item = QueueItem(loop=loop, pargs=(i,), keyword_args={c:i})
        result.append(item)
    return result

@pytest.mark.asyncio
async def test_async_callback_values():
    loop = asyncio.get_event_loop()
    keys = [c for c in string.ascii_lowercase]
    listener = Listener()

    items_expected = build_items_expected(keys)

    for item in items_expected:
        print(f'calling cb: {item=}')
        listener.callback(*item.pargs, **item.keyword_args.copy())

    items_received = []

    while len(items_received) < len(items_expected):
        item = await listener.get(timeout=10)
        if item is None:
            raise asyncio.TimeoutError
        print(f'retreived: {item=}')
        items_received.append(item)
        listener.task_done()

    await asyncio.sleep(.1)
    assert listener.empty()

    assert items_expected == items_received


@pytest.mark.asyncio
async def test_async_callback_exceptions_caught():
    loop = asyncio.get_event_loop()
    listener = Listener()

    class MyException(Exception):
        pass

    exc_queue = asyncio.Queue()

    def exc_handler(_loop, context):
        exc = context['exception']
        exc_queue.put_nowait(exc)

    loop.set_exception_handler(exc_handler)

    with pytest.raises(MyException):
        listener.callback('foo', async_exception=MyException)

        exc = await asyncio.wait_for(exc_queue.get(), timeout=5)
        raise exc
