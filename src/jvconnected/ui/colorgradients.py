#! /bin/env python3

from pathlib import Path
import argparse
try:
    import numpy as np
except ImportError:
    np = None

def build_wb_img(width: int = 64):
    import numpy as _
    height = width
    hx = width // 2
    hy = height // 2

    # ix_arr = np.round(np.linspace(0, width, hx))
    # ix_arr = np.concatenate((ix_arr, np.flip(ix_arr)))
    # ix_arr = np.asarray(ix_arr, dtype=int)

    # xy_index = np.zeros((width, height, 2), dtype=int)
    # xy_index[...,0] += ix_arr
    # xy_index[...,1] += ix_arr.reshape((height,1))
    # # xy_index[...,1] += np.arange(height).reshape((height,1))

    xy_index = np.zeros((width, height, 2), dtype=int)
    xy_index[...,0] += np.arange(width)
    # xy_index2[...,1] += ix_arr.reshape((height,1))
    xy_index[...,1] += np.arange(height).reshape((height,1))

    y_arr = xy_index.sum(axis=-1)
    y_arr = np.rot90(y_arr)


    rgb = np.zeros((width, height, 3), dtype=np.float64)

    rgb[...,0] = xy_index[...,1] / height * -1 + 1
    rgb[...,1] = (y_arr / y_arr.max()) * -1 + 1
    # rgb[...,1] += 1
    rgb[...,2] = xy_index[...,0] / width



    # r = np.rot90(np.tile(np.linspace(0, 1, height), width).reshape(width, height))
    # b = np.tile(np.linspace(0, 1, width), height).reshape(width, height)
    # g =
    # rgb = np.rot90(rgb)

    return rgb

def plot_img(img_arr):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    im = ax.imshow(img_arr)
    plt.show()

def build_wb_img_file(filename: Path, width: int = 64):
    from matplotlib import image

    img_arr = build_wb_img(width)
    image.imsave(str(filename), img_arr)


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
