#! /usr/bin/env python

from loguru import logger

import argparse
import asyncio
from typing import List, Sequence, ByteString, ClassVar, Tuple, Dict, Optional

import mido

from jvconnected.interfaces.midi import aioport
from jvconnected.interfaces.midi import bcf_sysex
from jvconnected.interfaces.midi.mapper import MidiMapper, Map

class BCLBlock(bcf_sysex.BCLBlock):
    @logger.catch
    async def send(self, inport: aioport.InputPort, outport: aioport.OutputPort):
        async def get_response():
            while True:
                msg = await inport.receive(1)
                if msg is None:
                    raise asyncio.TimeoutError
                if msg.type != 'sysex':
                    inport.task_done()
                    continue
                resp = bcf_sysex.BCLReply.from_sysex_message(msg)
                inport.task_done()
                return resp
        items = self.build_sysex_items()
        for item in items:
            logger.debug(f'tx {item.message_index}: "{item.bcl_text}"')
            await outport.send(item.build_sysex_message())
            resp = await get_response()
            # logger.info(f'rx {resp.message_index}: {resp}')
            resp.raise_on_error()
            assert resp.message_index == item.message_index

    def print_output(self):
        items = self.build_sysex_items()
        for item in items:
            print(item.bcl_text)

    async def send_to_port_name(self, name: str):
        if name == '__stdout__':
            self.print_output()
            return
        ioport = aioport.IOPort(name)
        await ioport.open()
        try:
            await self.send(ioport.inport, ioport.outport)
        finally:
            await ioport.close()

class Preset(bcf_sysex.Preset):
    def build_bcl_block(self) -> BCLBlock:
        lines = self.build_bcl_lines()
        return BCLBlock(text_lines=lines)

    def build_store_block(self, preset_num: int) -> BCLBlock:
        lines = [f'$store {preset_num}']
        return BCLBlock(text_lines=lines)

    # async def send_block(self, blk: BCLBlock, port_name: str):


    async def send(self, inport: aioport.InputPort, outport: aioport.OutputPort):
        blk = self.build_bcl_block()
        await blk.send(inport, outport)

    async def send_to_port_name(self, name: str):
        blk = self.build_bcl_block()
        await blk.send_to_port_name(name)

def build_preset(mapper: Optional[MidiMapper] = None):
    def build_control(pst, map_obj: Map, control_ix, cam_ix, **kwargs):
        enc_ix = cam_ix * 8 + control_ix
        btn_ix = cam_ix * 16 + control_ix
        encoder_disp_mode = kwargs.get('encoder_disp_mode', '1dot')

        if map_obj.map_type.startswith('controller'):
            enc_mode = ''.join(['absolute', map_obj.map_type.lstrip('controller')])
            enc = pst.add_encoder(
                index=enc_ix, channel=cam_ix, mode=encoder_disp_mode,
                number=map_obj.controller, encoder_mode=enc_mode,
            )
        elif map_obj.map_type == 'adjust_controller':
            # tx = mido.Message('control_change', control=spec['controller'], value=0)
            # tx_str = ''.join([f'${b:X}' for b in tx.bytes()[:2]])
            # tx_str = f'{tx_str} ifp $7f ifn $00'
            pst.add_encoder(
                index=enc_ix, channel=cam_ix, mode=encoder_disp_mode,
                number=map_obj.controller, encoder_mode='relative-2',
            )
            # pst.add_button(
            #     index=btn_ix, channel=cam_ix,
            #     number=spec['increment_note'], message_type='note',
            # )
            # btn_ix += 8
            # pst.add_button(
            #     index=btn_ix, channel=cam_ix,
            #     number=spec['decrement_note'], message_type='note',
            # )
        else:
            print(f'no control built: control_ix={control_ix}, map_obj={map_obj}')

    if mapper is None:
        mapper = MidiMapper()
    pst = Preset(name='foo')
    iris_map = mapper['exposure.iris_pos']
    tally_pgm = mapper['tally.program']
    tally_pvw = mapper['tally.preview']
    # iris_map = DEFAULT_MAPPING['exposure']['iris_pos']
    # tally_pgm = DEFAULT_MAPPING['tally']['program']
    # tally_pvw = DEFAULT_MAPPING['tally']['preview']
    for cam_ix in range(4):

        # Iris mapped to faders 1-8
        pst.add_fader(
            index=cam_ix+1, channel=cam_ix,
            number=iris_map.controller, mode='absolute/14',
        )

        # Program tally on top button row, Preview on bottom
        pst.add_button(
            index=cam_ix+33, channel=cam_ix, value_max=100,
            message_type='note', number=tally_pgm.note,
        )
        pst.add_button(
            index=cam_ix+41, channel=cam_ix, value_max=100,
            message_type='note', number=tally_pvw.note,
        )

        control_ix = 1
        # for grpkey, grp in DEFAULT_MAPPING.items():
        for map_obj in mapper.iter_indexed():
            if map_obj.group_name == 'tally':
                continue
            # for spkey, spec in grp.items():
            if True:
                kw = {}
                if map_obj.name in ['red_normalized', 'blue_normalized', 'master_black_pos', 'detail_pos']:
                    kw['encoder_disp_mode'] = 'pan'
                else:
                    kw['encoder_disp_mode'] = 'bar'
                build_control(pst, map_obj, control_ix, cam_ix, **kw)
                control_ix += 1
    return pst

@logger.catch
def send_preset(port_name):
    pst = build_preset()
    asyncio.run(pst.send_to_port_name(port_name))

@logger.catch
def store_preset(port_name, preset_num):
    async def _do_it(pst):
        await pst.send_to_port_name(port_name)

        blk = pst.build_store_block(preset_num)
        await blk.send_to_port_name(port_name)

    pst = build_preset()
    asyncio.run(_do_it(pst))

def main():
    p = argparse.ArgumentParser()
    p.add_argument('-p', '--port-name', dest='port_name')
    p.add_argument('--stdout', dest='stdout', action='store_true')
    p.add_argument('--store', dest='store', action='store_true')
    p.add_argument('-n', '--num', dest='num', type=int, default=1, help='Preset number (if --store is used)')
    args = p.parse_args()
    if args.stdout:
        args.port_name = '__stdout__'
    elif not args.port_name:
        all_io_ports = set(mido.get_ioport_names())
        bcf_ports = [name for name in all_io_ports if 'BCF2000' in name]
        non_loop = [name for name in all_io_ports if 'through' not in name.lower()]
        if len(bcf_ports) == 1:
            args.port_name = bcf_ports[0]
        elif len(non_loop) == 1:
            args.port_name = non_loop[0]
        else:
            raise Exception(f'Could not find suitable port from "{all_io_ports}"')
    logger.info(f'Sending to {args.port_name}...')
    if args.store:
        store_preset(args.port_name, args.num)
        logger.info(f'Saved preset {args.num}')
    else:
        logger.success
        send_preset(args.port_name)
    logger.success(f'Preset sent to {args.port_name}')

if __name__ == '__main__':
    main()
