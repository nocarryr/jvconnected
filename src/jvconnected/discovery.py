from loguru import logger
import asyncio

from zeroconf import ServiceInfo, Zeroconf
from zeroconf.asyncio import AsyncZeroconf
from pydispatch import Dispatcher, Property, DictProperty

from jvconnected.utils import async_callback

PROCAM_FQDN = '_jvc_procam_web._tcp.local.'

class ProcamListener(object):
    def __init__(self, discovery: 'Discovery'):
        self.discovery = discovery

    async def get_service_info(self, zc: Zeroconf, type_: str, name: str) -> ServiceInfo:
        info = ServiceInfo(type_, name)
        r = await info.async_request(zc, 3000)
        if r:
            return info

    @async_callback
    async def remove_service(self, zc: Zeroconf, type_: str, name: str):
        logger.debug(f'Service {name} removed')
        disco = self.discovery
        if name in disco.procam_infos:
            info = disco.procam_infos[name]
            del disco.procam_infos[name]
        else:
            info = None
        disco.emit('on_service_removed', name, info=info)

    @async_callback
    async def add_service(self, zc: Zeroconf, type_: str, name: str):
        info = await self.get_service_info(zc, type_, name)
        if info is None:
            logger.warning(f'Could not resolve service "{type_}, {name}"')
            return
        logger.debug(f'Adding {info}')
        disco = self.discovery
        disco.procam_infos[info.name] = info
        disco.emit('on_service_added', info.name, info=info)

    @async_callback
    async def update_service(self, zc: Zeroconf, type_: str, name: str):
        info = await self.get_service_info(zc, type_, name)
        if info is None:
            logger.warning(f'Could not resolve service "{type_}, {name}"')
            return
        logger.debug(f'Update {info}')
        disco = self.discovery
        stored_info = disco.procam_infos[info.name]
        disco.procam_infos[info.name] = info
        disco.emit('on_service_updated', info.name, info=info, old=stored_info)

class Discovery(Dispatcher):
    """Listen for cameras using zeroconf

    Properties:
        procam_infos (dict): Container for discovered devices as instances of
            :class:`zeroconf.ServiceInfo`. The service names (fqdn) are used as keys

    :Events:
        .. event:: on_service_added(name, info=info)

            Fired when a new device is discovered

        .. event:: on_service_updated(name, info=info, old=old_info)

            Fired when an service is updated.
            The pre-existing :class:`~zeroconf.ServiceInfo` is passed for comparison

        .. event:: on_service_removed(name, info=info)

            Fired when an existing service is no longer available

    """
    procam_infos = DictProperty()
    _events_ = ['on_service_added', 'on_service_updated', 'on_service_removed']
    def __init__(self):
        self.running = False

    async def open(self):
        """Open the zeroconf browser and begin listening
        """
        if self.running:
            return
        loop = self.loop = asyncio.get_event_loop()
        azc = self.async_zeroconf = AsyncZeroconf()
        self.zeroconf = azc.zeroconf
        fqdn = PROCAM_FQDN
        listener = self.listener = ProcamListener(discovery=self)
        await azc.async_add_service_listener(fqdn, listener)
        self.running = True

    async def close(self):
        """Stop listening and close all connections
        """
        if not self.running:
            return
        await self.async_zeroconf.async_close()
        self.running = False

def main():
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
    return disco

if __name__ == '__main__':
    main()
