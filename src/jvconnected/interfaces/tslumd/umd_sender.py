from loguru import logger
import asyncio
import string
import argparse
from typing import Dict, Tuple, Set

from pydispatch import Dispatcher, Property, DictProperty, ListProperty

from jvconnected.interfaces import Interface
from jvconnected.interfaces.tslumd.messages import Message, Display
from jvconnected.interfaces.tslumd import TallyColor, Tally

class UmdProtocol(asyncio.DatagramProtocol):
    def __init__(self, sender: 'UmdSender'):
        self.sender = sender
    def connection_made(self, transport):
        logger.debug(f'transport={transport}')
        self.transport = transport
        self.sender.connected_evt.set()
    # def connection_lost(self, exc):
    #     logger.exception(exc)
    def datagram_received(self, data, addr):
        pass

class UmdSender(Dispatcher):
    tallies = ListProperty()
    running = Property(False)
    # connected = Property(False)
    num_tallies = 8
    tx_interval = .3
    update_interval = 1
    def __init__(self, clients=None):
        self.clients = set()
        if clients is not None:
            for client in clients:
                self.clients.add(client)
        for i in range(self.num_tallies):
            tally = Tally(i, text=string.ascii_uppercase[i])
            tally.bind(on_update=self.on_tally_updated)
            self.tallies.append(tally)
        self.loop = asyncio.get_event_loop()
        # self.update_lock = asyncio.Lock()
        self.update_queue = asyncio.Queue()
        self.update_task = None
        self.tx_task = None
        self.connected_evt = asyncio.Event()

    async def open(self):
        if self.running:
            return
        self.connected_evt.clear()
        logger.debug('UmdSender.open()')
        self.running = True
        self.transport, self.protocol = await self.loop.create_datagram_endpoint(
            lambda: UmdProtocol(self),
            local_addr=('127.0.0.1', 60001),
            # reuse_port=True,
        )
        self.tx_task = asyncio.create_task(self.tx_loop())
        self.update_task = asyncio.create_task(self.update_loop())
        logger.success('UmdSender running')

    async def close(self):
        if not self.running:
            return
        logger.debug('UmdSender.close()')
        self.running = False
        self.update_task.cancel()
        try:
            await self.update_task
        except asyncio.CancelledError:
            pass
        self.update_task = None
        await self.update_queue.put(False)
        await self.tx_task
        self.tx_task = None

        self.transport.close()
        logger.success('UmdSender closed')

    @logger.catch
    async def tx_loop(self):
        async def get_queue_item(timeout):
            try:
                item = await asyncio.wait_for(self.update_queue.get(), timeout)
            except asyncio.TimeoutError:
                item = None
            return item

        await self.connected_evt.wait()

        while self.running:
            item = await get_queue_item(self.tx_interval)
            if item is False:
                self.update_queue.task_done()
                break
            elif item is None:
                await self.send_full_update()
            else:
                indices = set()
                msg = self._build_message()
                tallies = {}
                # msg.displays.append(item)
                tallies[item.index] = item
                # indices.add(item.index)
                self.update_queue.task_done()
                while not self.update_queue.empty():
                    item = self.update_queue.get_nowait()
                    if item in [False, None]:
                        break
                    # elif item.index in indices:
                    #     break
                    # msg.displays.append(item)
                    # indices.add(item.index)
                    tallies[item.index] = item
                    self.update_queue.task_done()
                for key in sorted(tallies.keys()):
                    tally = tallies[key]
                    msg.displays.append(tally.to_display())
                await self.send_message(msg)

    async def send_message(self, msg: Message):
        data = msg.build_message()
        # coros = []
        # logger.debug(f'tx: {msg}')
        for client in self.clients:
            # coros.append(self.transport.sendto(data, client))
            self.transport.sendto(data, client)
        # await asyncio.gather(*coros)

    async def send_full_update(self):
        msg = self._build_message()
        for tally in self.tallies:
            disp = tally.to_display()
            msg.displays.append(disp)
        await self.send_message(msg)

    def _build_message(self) -> Message:
        return Message()

    @logger.catch
    async def update_loop(self):
        def roll(l: list):
            item = l.pop(0)
            l.append(item)

        def iter_colors():
            while True:
                yield from TallyColor.__members__.keys()
        colors = {
            'rh':[], 'lh':[], 'txt':[]
        }
        # color_names = list(TallyColor.__members__.keys())
        color_iter = iter_colors()
        last_key = None
        for key in colors:
            for i in range(self.num_tallies):
                cur_color = next(color_iter)

                if last_key is not None:
                    if colors[last_key][i] == cur_color:
                        cur_color = next(color_iter)
                colors[key].append(cur_color)
            last_key = key

        def set_tally_colors():
            for i, tally in enumerate(self.tallies):
                for key, color_names in colors.items():
                    attr = f'{key}_tally'
                    color = getattr(TallyColor, color_names[i])
                    setattr(tally, attr, color)

        await self.connected_evt.wait()

        while self.running:
            await asyncio.sleep(self.update_interval)
            if not self.running:
                break
            for l in colors.values():
                roll(l)
            set_tally_colors()

    def on_tally_updated(self, tally: Tally, props_changed):
        for prop in props_changed:
            val = getattr(tally, prop)
            logger.debug(f'{tally!r}.{prop} = {val}')
        if not self.running:
            return
        self.update_queue.put_nowait(tally)

def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        '-c', '--client', dest='clients', action='append', type=str,
        help=' '.join([
            'Client(s) to send UMD messages to formatted as "<hostaddr>:<port>".',
            'Multiple arguments may be given.',
            'If nothing is provided, defaults to "127.0.0.1:65000"',
        ]),
    )
    args = p.parse_args()

    if args.clients is None or not len(args.clients):
        args.clients = ['127.0.0.1:65000']
    clients = []
    for client in args.clients:
        addr, port = client.split(':')
        clients.append((addr, int(port)))

    logger.info(f'Sending to clients: {clients}')

    loop = asyncio.get_event_loop()
    sender = UmdSender(clients=clients)
    loop.run_until_complete(sender.open())
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        loop.run_until_complete(sender.close())
    finally:
        loop.close()

if __name__ == '__main__':
    main()
