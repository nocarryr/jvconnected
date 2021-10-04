from typing import List, Tuple, Sequence, Union
from numbers import Number, Rational
from pathlib import Path
from fractions import Fraction
from dataclasses import dataclass
import enum
import argparse

import numpy as np
from numpy.lib import recfunctions as rfn
from PIL import Image, ImageFont, ImageDraw

from jvconnected.ui.models.waveform import COLOR_COEFFICIENTS, calc_color_matrices

SizeT = Tuple[int, int]

RGB_DTYPE = np.dtype([
    ('r', np.uint8),
    ('g', np.uint8),
    ('b', np.uint8),
])

SMPTE_COLORS = {
    'full_white':[235, 235, 235],
    'white':[180, 180, 180],
    'yellow':[235, 235, 16],
    'cyan':[16, 235, 235],
    'green':[16, 235, 16],
    'magenta':[235, 16, 235],
    'red':[235, 16, 16],
    'blue':[16, 16, 235],
    'black':[16, 16, 16],
}

SMPTE_75P_COLORS = {
    'full_white':[235, 235, 235],
    'white':[180, 180, 180],
    'yellow':[180, 180, 16],
    'cyan':[16, 180, 180],
    'green':[16, 180, 16],
    'magenta':[180, 16, 180],
    'red':[180, 16, 16],
    'blue':[16, 16, 180],
    'black':[16, 16, 16],
    '+Q':[72, 16, 118],
    '+I':[106, 52, 16],
    '-I':[16, 70, 106],
}

SMPTE_RP219_2002_COLORS = [
    {
        'white':[180, 180, 180],
        'yellow':[180, 180, 16],
        'cyan':[16, 180, 180],
        'green':[16, 180, 16],
        'magenta':[180, 16, 180],
        'red':[180, 16, 16],
        'blue':[16, 16, 180],
        'grey40':[104, 104, 104],
    },{
        'cyan':[16, 235, 235],
        '+I':[106, 52, 16],
        'white':[180, 180, 180],
        'blue':[16, 16, 235],
    },{
        'yellow':[235, 235, 16],
        'black': [16, 16, 16],
        'ramp_full':[235, 235, 235],
        'red':[235, 16, 16],
    },{
        'grey15':[49, 49, 49],
        'black':[16, 16, 16],
        'white':[235, 235, 235],
        '-2':[12, 12, 12],
        '+2':[20, 20, 20],
        '+4':[25, 25, 25],
    },
]

@dataclass
class Point:
    x: Number = 0
    y: Number = 0
    def copy(self) -> 'Point':
        return Point(x=self.x, y=self.y)

@dataclass
class Size:
    w: Number = 0
    h: Number = 0
    def copy(self) -> 'Size':
        return Size(w=self.w, h=self.h)

@dataclass
class Rect:
    pos: Point
    size: Size

    def copy(self) -> 'Rect':
        return Rect(pos=self.pos.copy(), size=self.size.copy())

    @property
    def left(self) -> Number:
        return self.pos.x
    @property
    def right(self) -> Number:
        return self.pos.x + self.size.w
    @property
    def top(self) -> Number:
        return self.pos.y
    @property
    def bottom(self) -> Number:
        return self.pos.y + self.size.h

    @property
    def top_left(self) -> Point:
        return self.pos
    @property
    def top_right(self) -> Point:
        return Point(x=self.right, y=self.top)
    @property
    def bottom_left(self) -> Point:
        return Point(x=self.left, y=self.bottom)
    @property
    def bottom_right(self) -> Point:
        return Point(x=self.right, y=self.bottom)

class ColorSpace(enum.Enum):
    rgb = enum.auto()
    YCbCr = enum.auto()

@dataclass
class ColorBar:
    color: Union[np.ndarray, str]
    rect: Rect
    color_space: ColorSpace = ColorSpace.rgb

def build_rp219_2002_dims():

    def build_pattern_bars(
        pattern_index: int,
        defs: List[Tuple[str, Rational, Rational]],
        y: Rational,
    ) -> List[ColorBar]:

        result = []
        colors = SMPTE_RP219_2002_COLORS[pattern_index]
        last_rect = None
        for name, width, height in defs:
            if last_rect is None:
                rect = Rect(
                    pos=Point(x=Fraction(0,1), y=y),
                    size=Size(w=width, h=height),
                )
            else:
                rect = last_rect.copy()
                rect.pos.x = last_rect.right
                rect.size.w = width

            if name == 'ramp':
                color = name
            else:
                color = colors[name]
            result.append(ColorBar(color=color, rect=rect))
            last_rect = rect
        return result


    patterns = []
    all_bar_objs = []

    a = Fraction(1, 1)
    a_three_quarters = Fraction(3, 4)

    w_c = a_three_quarters / 7
    w_d = Fraction(1, 4) / 2
    w_grey40 = w_d

    p1_height = Fraction(7, 12)
    p2_height = Fraction(1, 12)
    p3_height = Fraction(1, 12)
    p4_height = Fraction(3, 12)

    cur_y = Fraction(0, 1)

    h = p1_height
    pattern = [('grey40', w_grey40, h)]
    color_names = ['white', 'yellow', 'cyan', 'green', 'magenta', 'red', 'blue']
    pattern.extend([(name, w_c, h) for name in color_names])
    pattern.append(('grey40', w_grey40, h))
    patterns.append(pattern)
    all_bar_objs.append(build_pattern_bars(0, pattern, cur_y))
    cur_y += h

    h = p2_height
    w_ramp = a_three_quarters - w_c
    pattern = [
        ('cyan', w_grey40, h), ('+I', w_c, h), ('white', w_ramp, h), ('blue', w_grey40, h)
    ]
    patterns.append(pattern)
    all_bar_objs.append(build_pattern_bars(1, pattern, cur_y))
    cur_y += h

    h = p3_height
    pattern = [
        ('yellow', w_grey40, h), ('black', w_c, h), ('ramp', w_ramp, h), ('red', w_grey40, h)
    ]
    patterns.append(pattern)
    all_bar_objs.append(build_pattern_bars(2, pattern, cur_y))
    cur_y += h

    h = p4_height
    w_pluge = w_c / 3
    pattern = [
        ('grey15', w_grey40, h), ('black', Fraction(3, 2) * w_c, h),
        ('white', 2 * w_c, h), ('black', Fraction(5, 6) * w_c, h),
        ('-2', w_pluge, h), ('black', w_pluge, h),
        ('+2', w_pluge, h), ('black', w_pluge, h), ('+4', w_pluge, h),
        ('black', w_c, h), ('grey15', w_grey40, h),
    ]
    patterns.append(pattern)
    all_bar_objs.append(build_pattern_bars(3, pattern, cur_y))

    return patterns, all_bar_objs


for key, l in SMPTE_COLORS.copy().items():
    SMPTE_COLORS[key] = np.array([tuple(l)], dtype=RGB_DTYPE)
for key, l in SMPTE_75P_COLORS.copy().items():
    SMPTE_75P_COLORS[key] = np.array([tuple(l)], dtype=RGB_DTYPE)
for i, d in enumerate(SMPTE_RP219_2002_COLORS):
    for key, l in d.items():
        SMPTE_RP219_2002_COLORS[i][key] = np.array([tuple(l)], dtype=RGB_DTYPE)

SMPTE_RP219_2002_DIMENSIONS, SMPTE_RP219_2002_BARS = build_rp219_2002_dims()


# def normalize_yuv(yuv):
#     norm = np.zeros(yuv.shape, dtype=YUV_DTYPE)
#     norm['y'] = (yuv['y'] - 16) / 219
#     norm['u'] = (yuv['u'] - 128) / 224
#     norm['v'] = (yuv['v'] - 128) / 224
#     return norm
#
# def yuv_to_rgb_mtx(yuv, coeff='Rec709'):
#     coeff = COLOR_COEFFICIENTS[coeff]
#     YCbCrTransform, sRGBTransform = calc_color_matrices(coeff)
#     Kr, Kg, Kb = coeff
#     # Ymin, Ymax = 16, 235
#     # Cmin, Cmax = 16, 240
#
#     # yuv_norm = normalize_yuv(yuv)
#     yuv_norm = yuv
#     yuv_unstr = rfn.structured_to_unstructured(yuv_norm)
#     assert yuv_unstr.shape[0] == 1
#
#     # rgb = sRGBTransform @ yuv_unstr[0]
#     rgb = np.einsum('...ij,...j->...i', sRGBTransform, yuv_unstr)
#     return rgb# + 16 / 219 * 255


# def yuv_to_rgb(yuv, coeff = 'Rec709'):
#
#     # Adapted from https://github.com/colour-science/colour/blob/15112dbe824aab0f21447e0db4a046a28a06f43a/colour/models/rgb/ycbcr.py#L448-L574
#     coeff = COLOR_COEFFICIENTS[coeff]
#     # YCbCrTransform, sRGBTransform = calc_color_matrices(coeff)
#     Kr, Kg, Kb = coeff
#     Ymin, Ymax = 16, 235
#     Cmin, Cmax = 16, 240
#     Yrange = Ymax - Ymin
#     Crange = Cmax - Cmin
#     RGB_min, RGB_max = 16, 235
#     RGB_range = RGB_max - RGB_min
#
#     yuv = np.asarray(yuv, dtype=yuv.dtype)
#
#     Y, Cb, Cr = yuv['y'], yuv['u'], yuv['v']
#
#     Y -= Ymin
#     Cb -= (Cmax + Cmin) / 2
#     Cr -= (Cmax + Cmin) / 2
#     Y *= 1 / Yrange
#     Cb *= 1 / Crange
#     Cr *= 1 / Crange
#     R = Y + (2 - 2 * Kr) * Cr
#     B = Y + (2 - 2 * Kb) * Cb
#     G = (Y - Kr * R - Kb * B) / (1 - Kr - Kb)
#
#     rgb = np.zeros(R.shape, dtype=RGB_DTYPE)
#     rgb['r'] = np.rint(R * RGB_range + RGB_min)
#     rgb['g'] = np.rint(G * RGB_range + RGB_min)
#     rgb['b'] = np.rint(B * RGB_range + RGB_min)
#     return rgb


IMG_SIZE: SizeT = (480, 272)

IMG_DIR = Path(__file__).resolve().parent / 'test_images'


def build_full_frame_bars(size: SizeT = IMG_SIZE) -> np.ndarray:
    width, height = size
    color_names = ['full_white', 'yellow', 'cyan', 'green', 'magenta', 'blue', 'black']
    bar_width = width // len(color_names)
    extra_width = width % len(color_names)
    img_arr = np.zeros((width, height), dtype=RGB_DTYPE)
    for i, color_name in enumerate(color_names):
        start_ix = i * bar_width
        end_ix = start_ix + bar_width
        color = SMPTE_COLORS[color_name]
        img_arr[start_ix:end_ix, :] = color
    return img_arr

def build_rp219_2002_bars(img_size: SizeT = IMG_SIZE) -> np.ndarray:
    img_width, img_height = img_size
    img_arr = np.zeros((img_width, img_height), dtype=RGB_DTYPE)

    for pattern in SMPTE_RP219_2002_BARS:
        for color_bar in pattern:
            rect = color_bar.rect
            start_x = int(rect.left * img_width)
            start_y = int(rect.top * img_height)
            end_x = int(rect.right * img_width)
            end_y = int(rect.bottom * img_height)

            if isinstance(color_bar.color, str) and color_bar.color == 'ramp':
                w = end_x - start_x
                yramp = np.rint(np.linspace(16, 235, w)).reshape((w,1))
                color_bar.color = np.zeros((w,1), dtype=RGB_DTYPE)
                color_bar.color['r'] = yramp
                color_bar.color['g'] = yramp
                color_bar.color['b'] = yramp

            img_arr[start_x:end_x,start_y:end_y] = color_bar.color
    return img_arr


def rgb_arr_to_pil(a):
    av = a.view(np.uint8).reshape(a.shape + (-1,))
    av = av[:,::-1,:]
    return np.rot90(av)


def build_image_seq(
    img_dir: Path, size: SizeT = IMG_SIZE,
    count: int = 30, full_frame: bool = False
) -> Sequence[Path]:

    width, height = size
    center_x, center_y = width // 2, height // 2
    font_size = width // 12
    padding = font_size // 10
    font = ImageFont.truetype('FreeMono.ttf', font_size)

    if full_frame:
        color_bars = build_full_frame_bars(size)
    else:
        color_bars = build_rp219_2002_bars(size)
    img_base = Image.fromarray(rgb_arr_to_pil(color_bars))
    alpha = Image.new(mode='L', size=size)
    img_base.putalpha(alpha)

    filenames = []

    for i in range(count):
        num_str = f'{i:04d}'
        fn = img_dir / f'{num_str}.jpg'
        img = Image.new(img_base.mode, size)
        draw = ImageDraw.Draw(img)
        txt_kwargs = dict(
            xy=(center_x, center_y), text=num_str,
            font=font, align='center', anchor='mm',
        )
        bbox = list(draw.textbbox(**txt_kwargs))
        bbox[0] -= padding
        bbox[1] -= padding
        bbox[2] += padding
        bbox[3] += padding
        draw.rectangle(bbox, fill=(16,16,16,255))
        txt_kwargs['fill'] = (235,235,235,255)
        draw.text(**txt_kwargs)
        img = Image.alpha_composite(img_base, img)
        img.convert(mode='RGB').save(fn, subsampling='4:4:4')
        filenames.append(fn)
    return filenames


def main():
    p = argparse.ArgumentParser()
    p.add_argument('-d', '--dir', dest='dir', default=IMG_DIR, help='Output directory')
    p.add_argument('-n', '--num', dest='num', default=30, type=int, help='Number of images to create')
    p.add_argument('--full-frame', dest='full_frame', action='store_true')
    args = p.parse_args()
    args.dir = Path(args.dir)
    if not args.dir.exists():
        args.dir.mkdir()
    build_image_seq(args.dir, count=args.num, full_frame=args.full_frame)
    # print(filenames)

if __name__ == '__main__':
    main()
