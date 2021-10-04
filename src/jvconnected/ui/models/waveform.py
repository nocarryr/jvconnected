"""
.. currentmodule:: jvconnected.ui.models.waveform

Functions used by :class:`jvconnected.ui.models.devicepreview.CameraPreview`
to generate waveform display.

.. note::
    This module is experimental and the math involved is most assuredly
    incorrect.  It should not be used where correctness is required.


Waveform Functions
------------------

.. autofunction:: get_waveform_arr

.. autofunction:: get_waveform_qimage

.. autofunction:: get_yprime_rgb


Image I/O Functions
-------------------

.. autofunction:: qimg_to_rgb_arr

.. autofunction:: img_arr_to_qimg

.. autofunction:: rasterize_wfm_arr


Graticule Functions
-------------------

.. autofunction:: get_graticules

.. autofunction:: paint_graticules


Types
-----

.. autodata:: RGBArray

.. autodata:: RGBArrayF

.. autodata:: WFMArray

.. autodata:: WFM_dtype


"""
from typing import List, Tuple, Sequence, Union, Dict, Optional, NewType

from PySide2 import QtCore, QtGui
from PySide2.QtCore import Qt, QPointF, QLineF, QRect, QRectF
from PySide2.QtGui import QImage, QColor, QPainterPath
from PIL import Image, ImageDraw

import numpy as np
import numpy.typing as npt
from numpy.lib import recfunctions as rfn

# Pixel_dtype = np.dtype([
#     ('x', int),
#     ('y', int),
# ])
# RGB_dtype = np.dtype([
#     ('r', np.float64),
#     ('g', np.float64),
#     ('b', np.float64),
# ])
WFM_dtype = np.dtype([
    # ('rgb', RGB_dtype),
    ('yprime', np.float64),
    ('xpos', np.float64),
    ('ypos', np.float64),
])
"""A :term:`structured data type` for waveform data

:param yprime: :class:`np.float64` containing the result of :func:`get_yprime_rgb`
:param xpos: :class:`np.float64` containing the element's x-axis position
    normalized to the range of 0 to 1
:param ypos: :class:`np.float64` containing the element's y-axis position
    normalized to the range of 0 to 1. This is calculated as
    :math:`Ypos = Yprime - (16/255)`
"""

RGBArrayF = NewType('RGBArrayF', npt.NDArray[np.float64])
"""3d array of floats with shape ``(height, width, color)`` (sorted as RGB)

The values are normalized (ranging from 0 to 1)
"""

RGBArray = NewType('RGBArray', npt.NDArray[np.uint8])
"""3d array of :class:`np.uint8` with shape ``(height, width, color)`` (sorted as RGBA)

The values are 8-bit (ranging from 0 to 255)
"""

WFMArray = NewType('WFMArray', npt.NDArray[WFM_dtype])
"""2d array using the :class:`WFM_dtype` with shape ``(height, width)``
"""

FloatArray = NewType('FloatArray', npt.NDArray[np.float])
"""Array of float
"""

Coeff = NewType('Coeff', Tuple[float, float, float])
"""YCbCr transform coefficients

:param Kr:
:type Kr: float
:param Kg:
:type Kg: float
:param Kb:
:type Kb: float
"""

COLOR_COEFFICIENTS: Dict[str, Coeff] = {
    'NTSC':(.3, .59, .11),
    'Rec601':(.299, .587, .114),
    'Rec709':(.2126, .7152, .0722),

}
# NTSC_coeff = (.3, .59, .11)
# Rec601_coeff = (.299, .587, .114)
# Rec709_coeff = (.2126, .7152, .0722)

def calc_color_matrices(coeff: Union[str, Coeff]) -> Tuple[FloatArray, FloatArray]:
    if isinstance(coeff, str):
        coeff = COLOR_COEFFICIENTS[coeff]
    Kr, Kg, Kb = coeff
    Ymin, Ymax = 16, 235
    Cmin, Cmax = 16, 240

    Y = np.array([Kr, (1-Kr-Kb), Kb])
    Cb = .5 * (np.array([0, 0, 1]) - Y) / (1-Kb)
    Cr = .5 * (np.array([1, 0, 0]) - Y) / (1-Kr)
    Y *= Ymax - Ymin
    Cb *= Cmax - Cmin
    Cr *= Cmax - Cmin

    yuv_mtrx = np.vstack([Y, Cb, Cr])
    rgb_mtrx = np.linalg.inv(yuv_mtrx)
    return yuv_mtrx, rgb_mtrx

    # yuv_mtrx = np.array([
    #     [Kr, Kg, Kb],
    #     [-.5*(Kr/(1-Kb)), -.5*(Kg/(1-Kb)), .5],
    #     [.5, -.5*(Kg/(1-Kr)), -.5*(Kb/(1-Kr))]
    # ])
    # rgb_mtrx = np.array([
    #     [1, 0, 2-2*Kr],
    #     [1, -(Kb/Kg)*(2-2*Kb), -(Kr/Kg)*(2-2*Kr)],
    #     [1, 2-2*Kb, 0]
    # ])
    # assert np.allclose(np.linalg.inv(yuv_mtrx), rgb_mtrx)
    # return yuv_mtrx, rgb_mtrx

# def get_rec709_matrices():
#     return calc_color_matrices('Rec709')
#
# YCbCrTransform, sRGBTransform = get_rec709_matrices()
# YCbCrTransform = np.array([
#     [.2126, .7152, .0722],
#     [-.1146, -.3854, .5],
#     [.5, -.4542, -.0458]
# ])
# sRGBTransform = np.array([
#     [1, 0, 1.5748],
#     [1, -.1873, -.4681],
#     [1, 1.8556, 0]
# ])

def get_yprime(rgb: Sequence[float]) -> float:
    r,g,b = rgb
    y = 0.2126*r + 0.7152*g + 0.0722*b
    return y

def get_yprime_rgb(rgb: RGBArrayF) -> npt.NDArray[float]:
    """Calculate the :math:`Y'` (luma) value for the given RGB values according
    to `ITU-R BT.709`_

    .. math::

        Y' = 0.2126\cdot R' + 0.7152\cdot G' + 0.0722\cdot B'


    Arguments:
        rgb (:data:`RGBArrayF`): The N-D input with last axis containing RGB float
            values

    Returns:
        An array of float with same shape as the input along all but the last axis


    .. _ITU-R BT.709: https://en.wikipedia.org/wiki/YCbCr#ITU-R_BT.709_conversion
    """
    y = 0.2126*rgb[...,0] + 0.7152*rgb[...,1] + 0.0722*rgb[...,2]
    return y

def get_waveform_arr(rgb_arr: RGBArrayF) -> WFMArray:
    """Calculate a waveform array as a set of xy points

    The values for ``'xpos'`` and ``'ypos'`` in the result represent the waveform's
    points for each line of the input image where ``'ypos'`` is the luma component.
    The ``'yprime'`` field is the original :math:`Y'` value and ``'ypos'`` has
    the "footroom" of :math:`16/255` subtracted from it.
    All fields are normalized (ranging from 0 to 1).

    Arguments:
        rgb_arr (:data:`RGBArrayF`): The input image array

    Returns:
        :data:`WFMArray`
            Array with the same shape as the input along the first two axes
            (height, width)

    """
    h, w = rgb_arr.shape[:2]

    wfm_arr = np.zeros((h,w), dtype=WFM_dtype)
    # wfm_arr['rgb'] = rgb_arr
    wfm_arr['yprime'] = get_yprime_rgb(rgb_arr)
    wfm_arr['xpos'] = np.reshape(np.linspace(0, 1, w), (1, w))
    wfm_arr['ypos'] = wfm_arr['yprime'] - (16/255)
    return wfm_arr

def get_waveform_qimage(qimg: QImage) -> WFMArray:
    """Calculate a waveform array from a :class:`QtGui.QImage` using
    :func:`get_waveform_arr`
    """
    rgb_arr = qimg_to_rgb_arr(qimg)
    return get_waveform_arr(rgb_arr)

def qimg_to_rgb_arr(qimg: QImage) -> RGBArrayF:
    """Convert a :class:`QtGui.QImage` to an :data:`RGBArrayF`
    """
    fmt = QImage.Format_RGB32
    if qimg.format() != fmt:
        qimg = qimg.convertToFormat(fmt)

    width, height = qimg.width(), qimg.height()
    num_pixels = width * height

    bfr = qimg.constBits()
    int_arr = np.frombuffer(bfr, dtype=np.uint8, count=num_pixels*4)

    bgra_arr = int_arr.reshape((height, width, 4)) / 255

    # Format_RGB32 stored as 0xffRRGGBB
    # so take only the first 3 items but in reverse
    rgb_arr = bgra_arr[...,2::-1]

    return rgb_arr


def get_graticules(
    rect: QRect
) -> Tuple[Dict[float, float], Dict[float, QLineF]]:
    """Get a set of graticules scaled to fit within the given :class:`QtCore.QRect`

    The scale ranges from -20 to 120 (ire) in increments of 10. An extra value of
    7.5 ire is included (NTSC setup level)

    Arguments:
        rect (:class:`QtCore.QRect`): The bounding box as a :class:`QtCore.QRect`

    Returns
    -------
    ire_vals : dict
        A mapping of ire values to their normalized positions
    lines : dict
        A mapping of :class:`QtCore.QLineF` objects with their ire values as keys
    """

    # Overall scale: -20 to 120
    # ire_vals = {
    #     0: 0,
    #     7.5: 16 / 255,      # NTSC black
    #     100: 235 / 255,
    # }
    ire_vals = {}
    # scale_factor = 255/219
    vmax = 120
    vmin = -20
    vsize = vmax - vmin
    ires = [-20, -10, 0, 7.5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120]
    def ire_to_pos_norm(ire):
        v = ire
        # v = (ire * 219 + 16) / 255# * scale_factor
        return (v - vmin) / vsize

    for ire in ires:
        ire_vals[ire] = ire_to_pos_norm(ire)

    lines = {}

    rect_w = rect.width()
    rect_h = rect.height()

    w_scale = rect_w - 1
    h_scale = rect_h - 1


    for ire, pos_norm in ire_vals.items():
        pos_y = (pos_norm * h_scale - h_scale) * -1
        lines[float(ire)] = QLineF(0, pos_y, rect_w, pos_y)

    return ire_vals, lines

def paint_graticules(
    painter: 'QtGui.QPainter', rect: QRect
) -> Tuple[Dict[float, float], Dict[float, QLineF]]:
    """Draw graticules and text markers using the QPainter api

    Graticules are calculated using :func:`get_graticules` then drawn on the
    given :class:`QtGui.QPainter`. IRE value labels are then drawn alternating
    on the left and right sides

    Arguments:
        painter (:class:`QtGui.QPainter`): The QPainter to draw with
        rect (:class:`QtGui.QRect`): The bounding box to use for drawing

    Returns
    -------
    ire_vals : dict
        A mapping of ire values to their normalized positions
    lines : dict
        A mapping of :class:`QtCore.QLineF` objects with their ire values as keys
    """

    ire_vals, graticules = get_graticules(rect)

    rect_w = rect.width()
    rect_h = rect.height()

    vertical_sp = graticules[10].y1() - graticules[20].y1()
    txt_flags = Qt.TextSingleLine

    bounding_rect = QtCore.QRectF(0, 0, rect_w, rect_h)

    font = QtGui.QFont('monospace', 12)
    fmetrics = QtGui.QFontMetrics(font)
    txt_box = fmetrics.size(txt_flags, '100')
    # logger.debug(f'{vertical_sp=}, {txt_box=}')
    while txt_box.height() > vertical_sp * .75:
        if font.pointSize() - 1 < 1:
            break
        font.setPointSize(font.pointSize() - 1)
        fmetrics = QtGui.QFontMetrics(font)
        txt_box = fmetrics.size(txt_flags, '100')
        # logger.debug(f'{vertical_sp=}, {txt_box=}')

    # logger.info('graticules font size: {}'.format(font.pointSize()))

    lh_flags = Qt.AlignLeft | Qt.AlignTop# | Qt.TextSingleLine
    rh_flags = Qt.AlignRight | Qt.AlignTop# | Qt.TextSingleLine


    painter.setFont(font)
    painter.setPen(QColor('yellow'))
    # logger.debug(f'graticule rect: {rect}')
    # logger.debug(f'graticules: {graticules}')

    txt_left = True
    for ire, line in graticules.items():
        ypos = line.y1()
        if ire == 0 or ire == 100:
            painter.setPen(QColor('white'))
        else:
            painter.setPen(QColor('yellow'))
        painter.drawLine(line)

        _txt_box = QRectF(0, 0, txt_box.width(), txt_box.height())

        if txt_left:
            _txt_box.moveTopLeft(QPointF(0, ypos))
            if bounding_rect | _txt_box == bounding_rect:
                painter.drawText(_txt_box, f'{ire:g}', lh_flags)
        else:
            _txt_box.moveTopRight(QPointF(rect_w, ypos))
            if bounding_rect | _txt_box == bounding_rect:
                painter.drawText(_txt_box, f'{ire:g}', rh_flags)
        txt_left = not txt_left
    return ire_vals, graticules

def rasterize_wfm_arr(wfm_arr: WFMArray) -> RGBArray:
    """Convert a waveform array into a rasterized image array

    Arguments:
        wfm_arr (:data:`WFMArray`): The input waveform array

    Returns:
        :data:`RGBArray`
            Image array with same shape as the input along the first two axes
            (height, width)
    """
    vmin, vmax = -20, 120
    vsize = vmax - vmin
    in_height, in_width = wfm_arr.shape
    w_scale = in_width - 1
    h_scale = in_height - 1

    img_arr = np.zeros((in_height, in_width, 4), dtype=np.uint8)

    # src_rgb = rfn.structured_to_unstructured(wfm_arr['rgb'])
    # src_rgb = np.asarray(src_rgb * 255, dtype=np.uint8)
    # alpha = np.zeros((in_height, in_width), dtype=np.uint8)
    # alpha[:] = 255
    # src_rgb = np.dstack((src_rgb, alpha))

    wfm_arr['ypos'] = (wfm_arr['ypos'] * 100 / vmax * vsize - vmin) / vsize * h_scale
    # ypos = (wfm_arr['ypos'] * 100 / vmax * vsize - vmin) / vsize * h_scale
    # ypos_w = ypos * h_scale
    # wfm_range = (wfm_arr['ypos'].min(), wfm_arr['ypos'].max())
    # ypos_range = (ypos.min(), ypos.max())
    # ypos_w_range = (ypos_w.min(), ypos_w.max())
    # print(f'{wfm_range=}, {ypos_range=}, {ypos_w_range=}, {in_height=}')
    # wfm_arr['ypos'] = ypos

    wfm_arr['xpos'] *= w_scale

    # rows = np.rint(wfm_arr['ypos'])
    rows = np.asarray(np.rint(wfm_arr['ypos']), dtype=int)

    # cols = np.rint(wfm_arr['xpos'] * w_scale)
    cols = np.asarray(np.rint(wfm_arr['xpos']), dtype=int)

    # # img_arr[rows, cols, 3] = 255
    # img_arr[rows,cols,:] = src_rgb[rows,cols,:]
    # # img_arr[rows,cols,3] = 255
    # assert img_arr.dtype == np.uint8

    img_arr[rows, cols, :] = 255

    return img_arr

def img_arr_to_qimg(
    img_arr: RGBArray, output_rect: Optional[QRect] = None
) -> 'QtGui.QImage':
    """Convert the given :data:`RGBArray` to a :class:`QtGui.QImage`

    Arguments:
        img_arr (:data:`RGBArray`): The array to convert
        output_rect (class:`QtCore.QRect`, optional): If given, the result will be
            scaled to this size
    """

    if output_rect is None:
        out_height, out_width = wfm_arr.shape
        output_rect = QRect(0, 0, out_width, out_height)
    else:
        out_width, out_height = output_rect.width(), output_rect.height()
    in_height, in_width = img_arr.shape[:2]
    in_rect = QRect(0, 0, in_width, in_height)

    # # img_arr = np.ascontiguousarray(np.rot90(img_arr), dtype=np.uint8)
    # img_arr = np.ascontiguousarray(img_arr, dtype=np.uint8)
    # bpl = in_width * 4
    # qimg = QtGui.QImage(img_arr.data, in_width, in_height, bpl, QtGui.QImage.Format_ARGB32)

    im = Image.fromarray(img_arr, mode='RGBA')
    qimg = im.toqimage()
    if in_rect != output_rect:
        qimg = qimg.scaled(output_rect.size())
    return qimg.mirrored(False, True)

def draw_wfm_pillow(rect: QRect, wfm_arr: WFMArray) -> QImage:
    vmin, vmax = -20, 120
    vsize = vmax - vmin

    in_height, in_width = wfm_arr.shape
    in_rect = QRect(0, 0, in_width, in_height)

    rect_h, rect_w = rect.height(), rect.width()
    h_scale = rect_h - 1
    w_scale = rect_w - 1

    wfm_arr['ypos'] = (wfm_arr['ypos'] * 100 / vmax * vsize - vmin) / vsize * h_scale
    wfm_arr['xpos'] *= w_scale

    img = Image.new('RGBA', (rect_w, rect_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    xy_arr = rfn.structured_to_unstructured(wfm_arr[['xpos', 'ypos']])

    for y in range(in_height):
        d.line(xy_arr[y], fill=(255, 255, 255, 255), width=1)

    qimg = im.toqimage()
    if in_rect != rect:
        qimg = qimg.scaled(rect.size())
    return qimg.mirrored(False, True)



def paint_waveform_arr(
    rect: QRect, wfm_arr: WFMArray
) -> QPainterPath:

    rect_w = rect.width()
    rect_h = rect.height()
    w_scale = rect_w - 1
    h_scale = rect_h - 1

    vmin, vmax = -20, 120
    vsize = vmax - vmin

    ypos = wfm_arr['ypos']
    ypos = (wfm_arr['ypos'] * 100 / vmax * vsize - vmin) / vsize
    ypos_w = (ypos * h_scale - h_scale) * -1
    wfm_range = (wfm_arr['ypos'].min(), wfm_arr['ypos'].max())
    ypos_range = (ypos.min(), ypos.max())
    ypos_w_range = (ypos_w.min(), ypos_w.max())
    # print(f'{wfm_range=}, {ypos_range=}, {ypos_w_range=}, {rect_h=}')
    wfm_arr['ypos'] = ypos_w

    h, w = wfm_arr.shape

    wfm_arr['xpos'] *= w_scale

    xy_arr = rfn.structured_to_unstructured(wfm_arr[['xpos', 'ypos']])

    paths = QPainterPath()
    for y in range(h):
        path = QPainterPath()
        y_arr = xy_arr[y]
        for x in range(w):
            xy = y_arr[x]
            if x > 0:
                path.lineTo(xy[0], xy[1])
            else:
                path.moveTo(xy[0], xy[1])

        paths.addPath(path)
    return paths
