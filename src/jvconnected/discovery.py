from loguru import logger
import asyncio
from zeroconf import ServiceBrowser, Zeroconf, ZeroconfServiceTypes
from pydispatch import Dispatcher
from pydispatch.properties import Property, DictProperty

PROCAM_FQDN = '_jvc_procam_web._tcp.local.'

class ProcamListener(object):
    def __init__(self, loop):
        self.loop = loop
        self.notify_queue = asyncio.Queue(loop=loop)

    def remove_service(self, zeroconf, type_, name):
        logger.debug(f'Service {name} removed')
        self.notify('removed', name)

    def add_service(self, zeroconf, type_, name):
        info = zeroconf.get_service_info(type_, name)
        logger.debug(f'Adding {info}')
        self.notify('added', info)

    def notify(self, msg, info):
        asyncio.run_coroutine_threadsafe(self._notify(msg, info), loop=self.loop)

    async def _notify(self, msg, data):
        item = dict(msg=msg, data=data)
        await self.notify_queue.put(item)

class Discovery(Dispatcher):
    """Listen for cameras using zeroconf

    Properties:
        procam_infos (dict): Container for discovered devices as instances of
            :class:`zeroconf.ServiceInfo`. The service names (fqdn) are used as keys

    :Events:
        .. event:: on_service_added(name, info=info)

            Fired when a new device is discovered

        .. event:: on_service_removed(name, info=info)

            Fired when an existing service is no longer available

    """
    procam_infos = DictProperty()
    _events_ = ['on_service_added', 'on_service_removed']
    def __init__(self):
        self.running = False

    async def open(self):
        """Open the zeroconf browser and begin listening
        """
        if self.running:
            return
        loop = self.loop = asyncio.get_event_loop()
        zc = self.zeroconf = Zeroconf()
        fqdn = PROCAM_FQDN
        listener = self.listener = ProcamListener(loop=loop)
        browser = self.browser = ServiceBrowser(zc, fqdn, listener)
        self._notify_loop = asyncio.ensure_future(self._get_notifications())
        self.running = True

    async def close(self):
        """Stop listening and close all connections
        """
        if not self.running:
            return
        self.zeroconf.close()
        await self.listener.notify_queue.put(None)
        await self._notify_loop
        self.running = False

    async def _get_notifications(self):
        while self.running:
            item = await self.listener.notify_queue.get()
            if item is None:
                logger.debug('notify loop exiting')
                self.listener.notify_queue.task_done()
                break
            logger.debug(f'handling notify item: {item}')
            if item['msg'] == 'added':
                info = item['info']
                self.procam_infos[info.name] = info
                self.emit('on_service_added', name, info=info)
            elif item['msg'] == 'removed':
                name = item['name']
                if name in self.procam_infos:
                    info = self.procam_infos[name]
                    del self.procam_infos[name]
                else:
                    info = None
                self.emit('on_service_removed', name, info=info)
            else:
                logger.warning(f'unhandled notification: {item}')
            self.listener.notify_queue.task_done()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    disco = Discovery()

    try:
        loop.run_until_complete(disco.open())
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            loop.run_until_complete(disco.close())
    finally:
        loop.close()
