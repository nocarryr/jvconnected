from __future__ import annotations
import typing as tp
import asyncio
import enum
from dataclasses import dataclass, field

class ConnectionState(enum.IntFlag):
    """State used in :class:`ReconnectStatus`
    """
    UNKNOWN = enum.auto()
    """Unknown state"""

    SCHEDULING = enum.auto()
    """A task is being scheduled to reconnect, but it has not begun execution"""

    SLEEPING = enum.auto()
    """The :attr:`ReconnectStatus.task` is waiting before attempting to reconnect"""

    ATTEMPTING = enum.auto()
    """The connection is being established"""

    CONNECTED = enum.auto()
    """Connection attempt success"""

    FAILED = enum.auto()
    """Connection has been lost"""

    DISCONNECT = enum.auto()
    """User manually disconnected"""


class RemovalReason(enum.Enum):
    """Possible values used in :event:`.engine.Engine.on_device_removed`
    """

    UNKNOWN = enum.auto()
    """Unknown reason"""

    OFFLINE = enum.auto()
    """The device is no longer on the network"""

    TIMEOUT = enum.auto()
    """Communication was lost due to a timeout. Reconnection will be attempted"""

    AUTH = enum.auto()
    """Authentication with the device failed, likely due to invalid credentials"""

    USER = enum.auto()
    """User manually removed the device"""

    SHUTDOWN = enum.auto()
    """The engine is shutting down"""


@dataclass
class ReconnectStatus:
    """Holds state used in device reconnect methods
    """
    device_id: str
    """The associated device id"""

    state: ConnectionState = ConnectionState.UNKNOWN
    """Current :class:`ConnectionState`"""

    reason: RemovalReason = RemovalReason.UNKNOWN
    """The :class:`RemovalReason` for disconnect"""

    task: Optional[asyncio.Task] = None
    """The current :class:`asyncio.Task` scheduled to reconnect"""

    num_attempts: int = 0
    """Number of reconnect attempts"""

    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    notify: asyncio.Condition = field(default_factory=asyncio.Condition)

    async def set_state(self, state: ConnectionState):
        """Set the :attr:`state`
        """
        async with self.notify:
            self.state = state
            self.notify.notify_all()

    async def wait_for_state(self, state: ConnectionState, timeout: float|int|None = None):
        """Wait for a specific :attr:`state` value(s)

        Arguments:
            state: May be a single :class:`ConnectionState` member or a
                combination of multiple members (using bitwise OR ``|``)
            timeout: If not None, wait the given number of seconds for the
                state. Otherwise, wait indefinitely.

        Raises:
            asyncio.TimeoutError
                If the state was not set within the given timeout
        """
        def predicate():
            if state == ConnectionState.UNKNOWN:
                return self.state == state
            else:
                return state & self.state > 0

        async with self.notify:
            coro = self.notify.wait_for(predicate)
            if timeout is not None:
                await asyncio.wait_for(coro, timeout)
            else:
                await coro

    async def wait_for_connect_or_failure(self, timeout: float|int|None = None):
        """Shortcut to wait for ``CONNECTED`` or ``FAILED``
        """
        state = ConnectionState.CONNECTED | ConnectionState.FAILED
        await self.wait_for_state(state, timeout)

    async def __aenter__(self):
        await self.lock.acquire()
        return None

    async def __aexit__(self, *args):
        self.lock.release()
