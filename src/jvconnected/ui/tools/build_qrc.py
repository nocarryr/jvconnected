#! /usr/bin/env python

"""
Generate resources needed for the UI and compile them using the `Qt Resouce System`_

.. _Qt Resouce System: https://doc.qt.io/qt-5/resources.html

"""
import shlex
import subprocess
from pathlib import Path

from jvconnected.ui import get_resource_filename
from jvconnected.ui.tools.qrc_utils import QRCDocument
from jvconnected.ui.tools.colorgradients import build_wb_img_file

IMG_QRC = get_resource_filename('images.qrc')
IMG_SCRIPT = get_resource_filename('rc_images.py')
IMG_DIR = get_resource_filename('img')
IMG_SIZES = (64, 128, 256)

def rcc(qrc_file: Path, rc_script: Path):
    """Run `pyside2-rcc`_, the PySide2 wrapper for `rcc`_ to compile resources
    into a python module

    Arguments:
        qrc_file (pathlib.Path): The qrc filename containing resource definitions
        rc_script (pathlib.Path): The filename for the python module to generate


    .. _rcc: https://doc.qt.io/qt-5/rcc.html
    .. _pyside2-rcc: https://doc.qt.io/qtforpython/tutorials/basictutorial/qrcfiles.html

    """
    cmd_str = f'pyside2-rcc -o "{rc_script}" "{qrc_file}"'
    subprocess.run(shlex.split(cmd_str))


def build_images(qrc_file: Path, img_dir: Path, *sizes):
    """Generate and/or compile the YUV plane images used for the white balance
    paint control

    Arguments:
        qrc_file (pathlib.Path): The qrc filename to register the images in
        img_dir (pathlib.Path): Directory to build images in

    """
    if not img_dir.exists():
        img_dir.mkdir(parents=True)
    if qrc_file.exists():
        qrc_doc = QRCDocument.from_file(qrc_file)
    else:
        qrc_doc = QRCDocument.create(base_path=qrc_file.parent)
    for size in sizes:
        fn = img_dir / f'YUV_UV_plane_{size}x{size}.png'
        if not fn.exists():
            build_wb_img_file(fn, size)
        qrc_doc.add_file(fn)
    qrc_doc.write(qrc_file)


def main():
    build_images(IMG_QRC, IMG_DIR, *IMG_SIZES)
    rcc(IMG_QRC, IMG_SCRIPT)

if __name__ == '__main__':
    main()
