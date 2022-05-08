#! /usr/bin/env python

from loguru import logger

import argparse
import asyncio
from typing import (
    List, Sequence, ByteString, ClassVar, Tuple, Dict, Optional, Union,
)

import mido

from jvconnected.interfaces.midi import bcf_sysex
from jvconnected.interfaces.midi.bcf_sysex import Preset, BCLBlock
from jvconnected.interfaces.midi.mapper import MidiMapper, Map


def build_preset(mapper: Optional[MidiMapper] = None) -> Preset:
    """Build a :class:`~.bcf_sysex.Preset` from the definitions in the given
    :class:`~.mapper.MidiMapper`

    Each of the :class:`~.mapper.Map` definitions will be assigned as encoders
    within an encoder group on the BCF. Since there are four encoder groups,
    this allows for control of up to four cameras, using the
    :attr:`midi channel <.bcf_sysex.ControlBase.channel>` to match the
    :attr:`~jvconnected.device.Device.device_index` of the camera(s).

    In addition, the map definition for "exposure.iris_pos" will be assigned to
    the first four faders. This allows iris control of four cameras from the
    faders.

    """
    def build_control(pst, map_obj: Map, control_ix, cam_ix, **kwargs):
        enc_ix = cam_ix * 8 + control_ix
        btn_ix = cam_ix * 16 + control_ix
        encoder_disp_mode = kwargs.get('encoder_disp_mode', '1dot')

        if map_obj.map_type.startswith('controller'):
            enc_mode = ''.join(['absolute', map_obj.map_type.lstrip('controller')])
            enc = pst.add_encoder(
                index=enc_ix, channel=cam_ix, mode=encoder_disp_mode,
                number=map_obj.controller, encoder_mode=enc_mode,
                value_default=0,
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

        # Iris mapped to faders 1-4
        pst.add_fader(
            index=cam_ix+1, channel=cam_ix,
            number=iris_map.controller, mode='absolute/14',
            value_default=0
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
    pst = build_preset()
    if args.stdout:
        def print_output(obj: Union[BCLBlock, Preset]):
            if isinstance(obj, Preset):
                obj = obj.build_bcl_block()
            for item in obj.build_sysex_items():
                print(item.bcl_text)
        print_output(pst)
        if args.store:
            blk = pst.build_store_block(args.num)
            print_output(blk)
    else:
        asyncio.run(pst.send_to_port_name(args.port_name, args.store, args.num))
        log_msg = f'Preset sent to {args.port_name}'
        if args.store:
            log_msg = f'{log_msg} and store as preset {args.num}'
        logger.success(log_msg)

if __name__ == '__main__':
    main()
