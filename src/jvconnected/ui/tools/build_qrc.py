#! /usr/bin/env python

"""
Generate resources needed for the UI and compile them using the `Qt Resouce System`_

.. _Qt Resouce System: https://doc.qt.io/qt-5/resources.html

"""
import shlex
import subprocess
from pathlib import Path
from typing import Sequence
from setuptools import Command

import PySide2
PYSIDE_DIR = Path(PySide2.__file__).parent

from jvconnected.ui import get_resource_filename
from jvconnected.ui.tools.qrc_utils import QRCDocument
from jvconnected.ui.tools.colorgradients import build_wb_img_file
from jvconnected.ui.tools import fontawesome as fa

QML_QRC = get_resource_filename('qml.qrc')
QML_DIR = get_resource_filename('qml')
QML_SCRIPT = get_resource_filename('rc_qml.py')

IMG_QRC = get_resource_filename('images.qrc')
IMG_SCRIPT = get_resource_filename('rc_images.py')
IMG_DIR = get_resource_filename('img')
IMG_SIZES = (64, 128, 256)

STYLE_CONF = get_resource_filename('qtquickcontrols2.conf')
STYLE_QRC = get_resource_filename('style.qrc')
STYLE_SCRIPT = get_resource_filename('rc_style.py')

def rcc(qrc_file: Path, rc_script: Path):
    """Run `pyside2-rcc`_, the PySide2 wrapper for `rcc`_ to compile resources
    into a python module

    Arguments:
        qrc_file (pathlib.Path): The qrc filename containing resource definitions
        rc_script (pathlib.Path): The filename for the python module to generate


    .. _rcc: https://doc.qt.io/qt-5/rcc.html
    .. _pyside2-rcc: https://doc.qt.io/qtforpython/tutorials/basictutorial/qrcfiles.html

    """
    rcc_bin = PYSIDE_DIR / 'rcc'
    cmd_str = f'{rcc_bin} -g python -o "{rc_script}" "{qrc_file}"'
    subprocess.run(shlex.split(cmd_str))


def build_images(qrc_file: Path = IMG_QRC, img_dir: Path = IMG_DIR,
                 qrc_script: Path = IMG_SCRIPT, build_rcc: bool = True,
                 sizes: Sequence[int] = IMG_SIZES):
    """Generate and/or compile the YUV plane images used for the white balance
    paint control

    Arguments:
        qrc_file (pathlib.Path): The qrc filename to register the images in
        img_dir (pathlib.Path): Directory to build images in
        qrc_script (pathlib.Path): Filename for script to generate
            (if ``build_rcc`` is ``True``)
        build_rcc (bool): If True, compile the resources to a
            Python module using :func:`rcc`
        sizes (Sequence[int]): The image sizes to create

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
    if build_rcc:
        rcc(qrc_file, qrc_script)

def pack_qml(qrc_file: Path = QML_QRC, qml_dir: Path = QML_DIR,
             qrc_script: Path = QML_SCRIPT, build_rcc: bool = True):
    """Find all qml files found in the given directory then add definitions
    for them in the given qrc file.

    Arguments:
        qrc_file (pathlib.Path): The qrc filename to register the files in
        qml_dir (pathlib.Path): The root directory containing qml files
        qrc_script (pathlib.Path): Filename for script to generate
            (if ``build_rcc`` is ``True``)
        build_rcc (bool): If True, compile the resources to a
            Python module using :func:`rcc`

    """
    if qrc_file.exists():
        qrc_doc = QRCDocument.from_file(qrc_file)
        removed = qrc_doc.remove_missing_files()
        for f in removed:
            print(f'Removed non-existent "{f.filename_abs}" from qrc document')
    else:
        qrc_doc = QRCDocument.create(base_path=qrc_file.parent)
    for pattern in ['**/*.qml', '**/qmldir']:
        for p in qml_dir.glob(pattern):
            qrc_doc.add_file(p)
    qrc_doc.write(qrc_file)
    if build_rcc:
        rcc(qrc_file, qrc_script)

def build_style(conf_file: Path = STYLE_CONF,
                qrc_file: Path = STYLE_QRC,
                qrc_script: Path = STYLE_SCRIPT):
    """Build the `Qt Quick Controls Configuration File`_ into the
    Qt Resouce System

    Arguments:
        conf_file: The configuration file
        qrc_file: The qrc filename to register the config file in
        qrc_script: Filename for the :func:`rcc` script to generate

    .. _Qt Quick Controls Configuration File: https://doc.qt.io/qt-5.15/qtquickcontrols2-configuration.html
    """
    qrc_doc = QRCDocument.create(base_path=qrc_file.parent)
    qrc_doc.add_file(conf_file)
    qrc_doc.write(qrc_file)
    rcc(qrc_file, qrc_script)

def build_fa():
    fa.main()

class BuildQRC(Command):
    description = "Build qml and image resources"
    user_options = []
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass
    def run(self):
        main()

def main():
    build_images()
    pack_qml()
    fa.main()
    build_style()

if __name__ == '__main__':
    main()
