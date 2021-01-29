from typing import Tuple, Sequence
from pathlib import Path
import argparse

import numpy as np
from PIL import Image, ImageFont, ImageDraw

Size = Tuple[int, int]

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
for key, l in SMPTE_COLORS.copy().items():
    SMPTE_COLORS[key] = np.array([tuple(l)], dtype=RGB_DTYPE)

IMG_SIZE: Size = (480, 272)

IMG_DIR = Path(__file__).resolve().parent / 'test_images'


def build_full_frame_bars(size: Size = IMG_SIZE) -> np.ndarray:
    width, height = size
    color_names = ['white', 'yellow', 'cyan', 'green', 'magenta', 'blue']
    bar_width = width // len(color_names)
    extra_width = width % len(color_names)
    img_arr = np.zeros((width, height), dtype=RGB_DTYPE)
    for i, color_name in enumerate(color_names):
        start_ix = i * bar_width
        end_ix = start_ix + bar_width
        color = SMPTE_COLORS[color_name]
        img_arr[start_ix:end_ix, :] = color
    return img_arr

def rgb_arr_to_pil(a):
    av = a.view(np.uint8).reshape(a.shape + (-1,))
    return np.rot90(av)

def build_image_seq(img_dir: Path, size: Size = IMG_SIZE, count: int = 30) -> Sequence[Path]:
    width, height = size
    center_x, center_y = width // 2, height // 2
    font_size = width // 12
    padding = font_size // 10
    font = ImageFont.truetype('FreeMono.ttf', font_size)

    color_bars = build_full_frame_bars(size)
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
        txt_kwargs['fill'] = (255,255,255,255)
        draw.text(**txt_kwargs)
        img = Image.alpha_composite(img_base, img)
        img.convert(mode='RGB').save(fn, subsampling='4:2:2')
        filenames.append(fn)
    return filenames


def main():
    p = argparse.ArgumentParser()
    p.add_argument('-d', '--dir', dest='dir', default=IMG_DIR, help='Output directory')
    p.add_argument('-n', '--num', dest='num', default=30, type=int, help='Number of images to create')
    args = p.parse_args()
    args.dir = Path(args.dir)
    if not args.dir.exists():
        args.dir.mkdir()
    build_image_seq(args.dir, count=args.num)
    # print(filenames)

if __name__ == '__main__':
    main()
