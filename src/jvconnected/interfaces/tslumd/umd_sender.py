from loguru import logger
import asyncio
import string
import argparse
import enum
from typing import List, Dict, Tuple, Set

from pydispatch import Dispatcher, Property, DictProperty, ListProperty

from jvconnected.interfaces import Interface
from jvconnected.interfaces.tslumd.messages import Message, Display
from jvconnected.interfaces.tslumd import TallyColor, TallyType, Tally


class AnimateMode(enum.Enum):
    vertical = 1
    horizontal = 2

class TallyTypeGroup:
    tally_type: TallyType
    num_tallies: int
    tally_colors: List[TallyColor]
    def __init__(self, tally_type: TallyType, num_tallies: int):
        if tally_type == TallyType.no_tally:
            raise ValueError(f'TallyType cannot be {TallyType.no_tally}')
        self.tally_type = tally_type
        self.num_tallies = num_tallies
        self.tally_colors = [TallyColor.OFF for _ in range(num_tallies)]

    def reset_all(self, color: TallyColor = TallyColor.OFF):
        self.tally_colors[:] = [color for _ in range(self.num_tallies)]

    def update_tallies(self, tallies: List[Tally]) -> List[int]:
        attr = self.tally_type.name
        changed = []
        for i, tally in enumerate(tallies):
            color = self.tally_colors[i]
            cur_value = getattr(tally, attr)
            if cur_value == color:
                continue
            setattr(tally, attr, color)
            changed.append(i)
        return changed

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
    tally_groups: Dict[TallyType, TallyTypeGroup]
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
            self.tallies.append(tally)
        self.tally_groups = {}
        for tally_type in TallyType:
            if tally_type == TallyType.no_tally:
                continue
            tg = TallyTypeGroup(tally_type, self.num_tallies)
            self.tally_groups[tally_type] = tg
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
                if isinstance(item, (list, tuple, set)):
                    tallies = {t.index:t for t in item}
                else:
                    tallies = {item.index:item}
                for key in sorted(tallies.keys()):
                    tally = tallies[key]
                    msg.displays.append(tally.to_display())
                await self.send_message(msg)
                self.update_queue.task_done()

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

    def set_animate_mode(self, mode: AnimateMode):
        self.animate_mode = mode
        if mode == AnimateMode.vertical:
            self.cur_group = TallyType.rh_tally
            self.cur_index = -2
        elif mode == AnimateMode.horizontal:
            self.cur_index = 0
            self.cur_group = TallyType.no_tally
        for tg in self.tally_groups.values():
            tg.reset_all()

    def animate_tallies(self):
        if self.animate_mode == AnimateMode.vertical:
            self.animate_vertical()
        elif self.animate_mode == AnimateMode.horizontal:
            self.animate_horizontal()

    def animate_vertical(self):
        colors = [c for c in TallyColor if c != TallyColor.OFF]

        tg = self.tally_groups[self.cur_group]
        start_ix = self.cur_index
        tg.reset_all()

        for color in colors:
            ix = start_ix + color.value-1
            if 0 <= ix < self.num_tallies:
                tg.tally_colors[ix] = color
        start_ix += 1

        if start_ix > self.num_tallies:
            self.cur_index = -2
            if self.cur_group == TallyType.rh_tally:
                self.cur_group = TallyType.txt_tally
            elif self.cur_group == TallyType.txt_tally:
                self.cur_group = TallyType.lh_tally
            else:
                self.set_animate_mode(AnimateMode.horizontal)
        else:
            self.cur_index = start_ix

    def animate_horizontal(self):
        tally_types = [t for t in TallyType]
        while tally_types[0] != self.cur_group:
            t = tally_types.pop(0)
            tally_types.append(t)
        for i, t in enumerate(tally_types):
            if t == TallyType.no_tally:
                continue
            tg = self.tally_groups[t]
            tg.reset_all()
            try:
                color = TallyColor(i+1)
            except ValueError:
                color = TallyColor.OFF
            tg.tally_colors[self.cur_index] = color
        try:
            t = TallyType(self.cur_group.value+1)
            self.cur_group = t
        except ValueError:
            self.cur_index += 1
            self.cur_group = TallyType.no_tally
            if self.cur_index >= self.num_tallies:
                self.set_animate_mode(AnimateMode.vertical)

    @logger.catch
    async def update_loop(self):
        self.set_animate_mode(AnimateMode.vertical)

        def update_tallies():
            changed = set()
            for tg in self.tally_groups.values():
                _changed = tg.update_tallies(self.tallies)
                changed |= set(_changed)
            return changed

        await self.connected_evt.wait()

        while self.running:
            await asyncio.sleep(self.update_interval)
            if not self.running:
                break
            self.animate_tallies()
            changed_ix = update_tallies()
            changed_tallies = [self.tallies[i] for i in changed_ix]
            await self.update_queue.put(changed_tallies)

class ClientArgAction(argparse._AppendAction):
    _default_help = ' '.join([
        'Client(s) to send UMD messages to formatted as "<hostaddr>:<port>".',
        'Multiple arguments may be given.',
        'If nothing is provided, defaults to "127.0.0.1:65000"',
    ])
    def __init__(self,
                 option_strings,
                 dest,
                 nargs=None,
                 const=None,
                 default=[('127.0.0.1', 65000)],
                 type_=str,
                 choices=None,
                 required=False,
                 help=_default_help,
                 metavar=None):
        super().__init__(
            option_strings, dest, nargs, const, default,
            type_, choices, required, help, metavar,
        )

    def __call__(self, parser, namespace, values, option_string=None):
        addr, port = values.split(':')
        values = (addr, int(port))
        items = getattr(namespace, self.dest, None)
        if items == [('127.0.0.1', 65000)]:
            items = []
        else:
            items = argparse._copy_items(items)
        items.append(values)
        setattr(namespace, self.dest, items)

def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        '-c', '--client', dest='clients', action=ClientArgAction#, type=str,
    )
    args = p.parse_args()

    logger.info(f'Sending to clients: {args.clients!r}')

    loop = asyncio.get_event_loop()
    sender = UmdSender(clients=args.clients)
    loop.run_until_complete(sender.open())
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        loop.run_until_complete(sender.close())
    finally:
        loop.close()

if __name__ == '__main__':
    main()
