#! /usr/bin/env python

import shlex
import subprocess
from pathlib import Path

from jvconnected.ui import get_resource_filename
from jvconnected.ui.tools.qrc_utils import QRCDocument
from jvconnected.ui.tools.colorgradients import build_wb_img_file

IMG_QRC = get_resource_filename('images.qrc')
IMG_SCRIPT = get_resource_filename('rc_images.py')
IMG_DIR = get_resource_filename('img')
BASE_PATH = IMG_DIR.parent
IMG_SIZES = (64, 128, 256)

def rcc(qrc_file: Path, rc_script: Path):
    print(f'QRC_FILE: "{qrc_file}", RC_SCRIPT: "{rc_script}"')
    cmd_str = f'pyside2-rcc -o "{rc_script}" "{qrc_file}"'
    subprocess.run(shlex.split(cmd_str))


def build_images(qrc_file: Path, img_dir: Path, *sizes):
    if not img_dir.exists():
        img_dir.mkdir(parents=True)
    if qrc_file.exists():
        qrc_doc = QRCDocument.from_file(qrc_file)
    else:
        qrc_doc = QRCDocument.create(base_path=BASE_PATH)
    # resource_el = qrc_doc.element.find(".//qresource[@prefix='/']")
    resource_el = None
    for o in qrc_doc.walk():
        if o.tag == 'qresource' and o.prefix == '/':
            resource_el = o
            break
    if resource_el is None:
        resource_el = qrc_doc.add_child(tag='qresource', prefix='/')
    for size in sizes:
        fn = img_dir / f'YUV_UV_plane_{size}x{size}.png'
        if not fn.exists():
            build_wb_img_file(fn, size)
        el = qrc_doc.search_for_file(fn)
        if el is None:
            el = resource_el.add_child(tag='file', filename=fn.relative_to(BASE_PATH))
    qrc_doc.write(qrc_file)




def main():
    build_images(IMG_QRC, IMG_DIR, *IMG_SIZES)
    rcc(IMG_QRC, IMG_SCRIPT)



if __name__ == '__main__':
    main()
