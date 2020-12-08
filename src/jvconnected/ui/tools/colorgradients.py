#! /bin/env python3

from pathlib import Path
import argparse
try:
    import numpy as np
except ImportError:
    np = None

try:
    from PIL import Image
except ImportError:
    Image = None

def build_wb_img(width: int = 64) -> np.ndarray:
    """Generate RGB pixel data for a `YUV`_ color plane

    Arguments:
        width (int): The size of the output array along the first axis. This will
            also be used for "height"

    Returns:
        numpy.ndarray: The output data with shape ``(width, height, 3)`` where
            the last axis contains the color values as floats (0..1) of
            red, green and blue

    .. _YUV: https://en.wikipedia.org/wiki/YUV
    """
    import numpy as _
    height = width
    hx = width // 2
    hy = height // 2

    xy_index = np.zeros((width, height, 2), dtype=int)
    xy_index[...,0] += np.arange(width)
    xy_index[...,1] += np.arange(height).reshape((height,1))

    y_arr = xy_index.sum(axis=-1)
    y_arr = np.rot90(y_arr)


    rgb = np.zeros((width, height, 3), dtype=np.float64)

    rgb[...,0] = xy_index[...,1] / height * -1 + 1
    rgb[...,1] = (y_arr / y_arr.max()) * -1 + 1
    rgb[...,2] = xy_index[...,0] / width

    return rgb

def plot_img(img_arr):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    im = ax.imshow(img_arr)
    plt.show()

def build_wb_img_file(filename: Path, width: int = 64):
    """Build a YUV color plane using :func:`build_wb_img` and save it as
    an image file.

    Arguments:
        filename (pathlib.Path): The filename for the output image. The image type
            will be determined from the extension
            as described in :meth:`PIL.Image.Image.save`
        width (int): The image width (and height)

    """
    img_arr = build_wb_img(width)
    im = Image.fromarray(np.uint8(img_arr*255))
    im.save(filename)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['plot', 'save'])
    p.add_argument('-w', '--width', dest='width', type=int, default=64)
    p.add_argument('-f', '--filename', dest='filename')
    p.add_argument('-y', '--overwrite', dest='overwrite', action='store_true')
    args = p.parse_args()

    if args.command == 'plot':
        rgb = build_wb_img(args.width)
        plot_img(rgb)
    elif args.command == 'save':
        args.filename = Path(args.filename)
        if args.filename.exists():
            if not args.overwrite:
                print(f'{args.filename} already exists. use "-y" to overwrite')
                return
        build_wb_img_file(Path(args.filename), args.width)

if __name__ == '__main__':
    main()
