from loguru import logger
import asyncio
from typing import Optional

class JpegSource:
    """Acquire preview images sequentially from the device

    This acts an Asynchronous Context Manager and an Asynchronous Iterator
    and should be used within an :keyword:`async with` block.  The individual
    image frames can then be retreived using an :keyword:`async for` loop::

        async with JpegSource(device) as src:
            async for image_bytes in src:
                process_image(image_bytes)

    """

    device: 'jvconnected.device.Device' #: The device instance
    fps: int = 30 #: Desired frame rate in frames per second
    def __init__(self, device: 'jvconnected.device.Device', fps: int = 30):
        self.device = device
        self.fps = fps
        self.loop = asyncio.get_event_loop()
        self.last_frame_time = None
        self.__encoding = False

    @property
    def client(self) -> 'jvconnected.client.Client':
        return self.device.client

    @property
    def image_uri(self) -> str:
        uri = f'/cgi-bin/get_jpg.cgi?SessionID={self.client.session_id}'
        return self.client._build_uri(uri)

    @property
    def encoding(self) -> bool:
        """``True`` if the camera's Jpeg encode function is enabled
        """
        return self.__encoding

    async def acquire(self):
        """Acquire the context manager and tell the device to begin Jpeg encoding
        """
        if self.encoding:
            return
        await self.client.request('JpegEncode', {'Operate':'Start'})
        logger.success('JpegEncode acquired')
        self.__encoding = True

    async def release(self):
        """Stop encoding on the device and release the context manager
        """
        logger.debug('releasing...')
        if self.encoding:
            await self.client.request('JpegEncode', {'Operate':'Stop'})
            logger.success('JpegEncode released')
        self.__encoding = False

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, *args):
        await self.release()

    async def wait_for_next_frame(self):
        """Wait for enough time to elapse to respect the required :attr:`fps`
        """
        now = self.loop.time()
        if self.last_frame_time is not None:
            elapsed = now - self.last_frame_time
            next_frame_time = self.last_frame_time + (1./self.fps)
            if now < next_frame_time:
                delta = next_frame_time - now
                await asyncio.sleep(delta)

    async def get_single_image(self) -> Optional[bytes]:
        """Get a single frame as a :class:`bytes` of Jpeg encoded data

        If necessary, wait before requesting to maintain the desired :attr:`fps`

        Note:
            The object must be acquired before calling this method, either by
            :meth:`acquire` or :keyword:`async with`

        """
        await self.wait_for_next_frame()
        if not self.encoding:
            self.last_frame_time = self.loop.time()
            return None
        img_uri = self.image_uri
        data = []
        async with self.client._client.stream('GET', img_uri) as resp:
            if resp.status_code != 200:
                return None
            async for chunk in resp.aiter_bytes():
                data.append(chunk)
        self.last_frame_time = self.loop.time()
        return b''.join(data)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.encoding:
            raise StopAsyncIteration
        return await self.get_single_image()
