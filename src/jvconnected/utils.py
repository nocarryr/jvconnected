from loguru import logger
import functools
import asyncio
import collections
from dataclasses import dataclass
from typing import Any, Iterator, Union, Tuple

from pydispatch import Dispatcher

def async_callback(fn):
    """Wrap a coroutine function or method (:keyword:`async def`) where a sync
    function is expected.

    The decorated function or method will be wrapped in an :class:`asyncio.Task`
    and scheduled on the current :ref:`event loop <asyncio-event-loop>`
    (within the context of the callback).

    Any exceptions will be caught and forwarded to the event loop through
    :meth:`asyncio.loop.call_exception_handler`.



    .. testsetup:: async_callback

        import asyncio
        from jvconnected.utils import async_callback

    .. testcode:: async_callback

        callback_event = asyncio.Event()

        @async_callback
        async def my_async_callback(*args, **kwargs):
            print(f'callback got: {args}, {kwargs}')
            callback_event.set()

        # Calling `my_async_callback` as a normal function
        my_async_callback('foo', bar='baz')

        # Run the loop until callback_event is set from inside the callback
        loop = asyncio.get_event_loop()
        loop.run_until_complete(callback_event.wait())

    .. testoutput:: async_callback

        callback got: ('foo',), {'bar': 'baz'}

    """
    def _error_handler(task):
        try:
            task.result()
        except Exception as exc:
            logger.exception(exc)
            loop = asyncio.get_running_loop()
            loop.call_exception_handler({'message':repr(exc), 'exception':exc})
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        task = asyncio.ensure_future(fn(*args, **kwargs))
        task.add_done_callback(_error_handler)
    return wrapper

class IndexedDict(Dispatcher):
    """A ``dict`` like container that tracks indices for its items

    :Events:
        .. event:: on_item_added(key=key, item=item, index=index_)

            Fired when an item is added

        .. event:: on_item_removed(key=key, item=item, index=index_)

            Fired when an item is removed

        .. event:: on_item_index_changed(key=key, item=item, old_index=cur_index, new_index=new_index)

            Fired when an item's index changes

    """
    _events_ = ['on_item_added', 'on_item_removed', 'on_item_index_changed']
    def __init__(self):
        self._data = {}
        self._index_key_map = {}
        self._key_index_map = {}

    @property
    def next_index(self):
        if not len(self._index_key_map):
            return 0
        return max(self._index_key_map.keys()) + 1

    def add(self, key: Any, item: Any, index_: int = -1) -> int:
        """Add an item

        Arguments:
            key: The dictionary key
            item: The dictionary value
            index_: The index for the item. If ``-1``, the item will be appended
                to the end, otherwise it will be inserted at the specified index

        Returns:
            int:
                The inserted item's index

        """
        assert key not in self._data
        if index_ == -1:
            index_ = self.next_index
        if index_ in self._index_key_map:
            self._pre_insert(index_)
        assert index_ not in self._index_key_map
        self._data[key] = item
        self._index_key_map[index_] = key
        self._key_index_map[key] = index_
        self.emit('on_item_added', key=key, item=item, index=index_)
        return index_

    def remove(self, key: Any):
        """Remove an item

        Arguments:
            key: The dictionary key

        Returns:
            The item that was removed

        """
        item = self._data[key]
        index_ = self._key_index_map[key]
        del self._key_index_map[key]
        del self._index_key_map[index_]
        del self._data[key]
        self.emit('on_item_removed', key=key, item=item, index=index_)
        return item

    def change_item_index(self, key: Any, new_index: int):
        """Change the index for an existing item.
        If necessary, change indices for any conflicting items

        Arguments:
            key: the dictionary key
            new_index (int): New index for the item

        """
        item = self._data[key]
        cur_index = self._key_index_map[key]
        del self._index_key_map[cur_index]
        if new_index in self._index_key_map:
            self._pre_insert(new_index)
        assert new_index not in self._index_key_map
        self._index_key_map[new_index] = key
        self._key_index_map[key] = new_index
        self.emit(
            'on_item_index_changed',
            key=key, item=item, old_index=cur_index, new_index=new_index,
        )

    def compact_indices(self, start_index: int = 0, max_change: int = 1):
        """Remove gaps in indices

        Arguments:
            start_index (int, optional): The index to start from
            max_change (int, optional): Limit index changes to this amount

        """
        cur_indices = [i for i in self.iter_indices(start_index)]
        cur_keys = [self._index_key_map[i] for i in cur_indices]
        expected_indices = []
        last_i = None
        for i in cur_indices:
            new_index = None
            if last_i is None:
                last_i = i
            elif last_i + 1 != i:
                next_i = last_i + 1
                diff = i - next_i
                if diff > max_change:
                    diff = max_change
                new_index = i - diff
                assert new_index > last_i
                i = new_index
            expected_indices.append(new_index)
            last_i = i
        for key, cur_index, new_index in zip(cur_keys, cur_indices, expected_indices):
            if new_index is None:
                continue
            if cur_index == new_index:
                continue
            assert new_index not in self._index_key_map.keys()
            # key = self._key_index_map[cur_index]
            self._set_item_index(key, new_index)

    def keys(self) -> Iterator[Any]:
        """Return an iterator of the dictionary keys, sorted by the item indices
        """
        for i in self.iter_indices():
            yield self._index_key_map[i]

    def values(self) -> Iterator[Any]:
        """Return an iterator of the dictionary values, sorted by the item indices
        """
        for key in self.keys():
            yield self[key]

    def items(self) -> Iterator[Tuple[Any, Any]]:
        """Return an iterator of the dictionary key, value pairs, sorted by the item indices
        """
        for key in self.keys():
            yield key, self[key]

    def iter_indices(self, start_index: int = 0) -> Iterator[int]:
        """Iterate through sorted indices starting from the one given

        Arguments:
            start_index (int, optional): The starting index, defaults to ``0``

        """
        for i in sorted(self._index_key_map.keys()):
            if i < start_index:
                continue
            yield i

    def iter_consecutive_indices(self, start_index: int = 0) -> Iterator[int]:
        """Iterate through sorted indices starting from the one given,
        but stop at the first gap

        Arguments:
            start_index (int, optional): The starting index, defaults to ``0``

        """
        last_i = None
        for i in self.iter_indices(start_index):
            if last_i is not None:
                if last_i + 1 != i:
                    break
            elif i != start_index:
                break
            yield i
            last_i = i

    def __getitem__(self, key: Any):
        return self._data[key]

    def __len__(self): return len(self._data)
    def __contains__(self, key: Any): return key in self._data

    def get(self, key: Any, default: Any = None):
        """Get an item by key
        """
        return self._data.get(key, default)

    def get_by_index(self, index_: int, default: Any = None):
        """Get an item by index

        Arguments:
            index_ (int): The item index to get
            default (optional): The default to return if no item exists with
                the given index, defaults to ``None``

        """
        if index_ not in self._index_key_map:
            return default
        key = self._index_key_map[index_]
        return self[key]

    def get_item_index(self, key: Any) -> int:
        """Get the index for the given key
        """
        return self._key_index_map[key]

    def _pre_insert(self, start_index: int):
        """Move existing items to the right
        """
        indices = [i for i in self.iter_consecutive_indices(start_index)]
        for i in reversed(indices):
            key = self._index_key_map[i]
            self._set_item_index(key, i+1)

    def _set_item_index(self, key: Any, new_index: int):
        assert new_index not in self._index_key_map
        item = self._data[key]
        cur_index = self._key_index_map[key]
        del self._index_key_map[cur_index]
        self._key_index_map[key] = new_index
        self._index_key_map[new_index] = key
        self.emit(
            'on_item_index_changed',
            key=key, item=item, old_index=cur_index, new_index=new_index,
        )

@dataclass
class NamedItem:
    """Helper class for :class:`NamedQueue`
    """
    key: Any
    """The item key"""

    item: Any
    """The item itself"""

class NamedQueue(asyncio.Queue):
    """A :class:`asyncio.Queue` subclass that stores items by user-defined keys.

    The items placed on the queue must be instances of :class:`NamedItem`.
    For convenience, there is a :meth:`create_item` contructor method.
    """

    @classmethod
    def create_item(self, key: Any, item: Any) -> NamedItem:
        """Create a :class:`NamedItem` to be put on the queue
        """
        return NamedItem(key=key, item=item)

    def _init(self, maxsize):
        self._queue = collections.deque()
        self._queue_items = {}

    def _put(self, item: NamedItem):
        self._queue_items[item.key] = item
        if item.key not in self._queue:
            self._queue.append(item.key)

    def _get(self) -> NamedItem:
        key = self._queue.popleft()
        item = self._queue_items[key]
        del self._queue_items[key]
        return item

    async def put(self, item: NamedItem):
        """Put a :class:`NamedItem` into the queue.

        If the queue is full, wait until a free
        slot is available before adding item.

        If an item with the same :attr:`~NamedItem.key` already exists in the
        queue, it will be replaced.
        """
        return await super().put(item)

    def put_nowait(self, item: NamedItem):
        return super().put_nowait(item)

    async def get(self) -> NamedItem:
        return await super().get()

    def get_nowait(self) -> NamedItem:
        return super().get_nowait()
