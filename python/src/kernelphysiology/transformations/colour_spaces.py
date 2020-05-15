"""
Functions related to change or manipulation of colour spaces.
"""

import numpy as np
import sys

import cv2

from kernelphysiology.transformations import normalisations

dkl_from_rgb = np.array(
    [[+0.49995000, +0.50001495, +0.49999914],
     [+0.99998394, -0.29898596, +0.01714922],
     [-0.17577361, +0.15319546, -0.99994349]]
)

rgb_from_dkl = np.array(
    [[0.4251999971, +0.8273000025, +0.2267999991],
     [1.4303999955, -0.5912000011, +0.7050999939],
     [0.1444000069, -0.2360000005, -0.9318999983]]
)

xyz_from_lms = np.array(
    [[+1.99831835e+00, -1.18730329e+00, +1.88189487e-01],
     [+7.07957782e-01, -2.92384281e-01, +5.61719491e-09],
     [-2.22739159e-08, -1.46290052e-08, +9.98233271e-01]]
)

lms_from_xyz = np.array(
    [[-1.1408616727, +4.6327689355, +0.2150781317],
     [-2.7623985003, +7.7972892807, +0.5207743801],
     [-0.0000000659, +0.0000002176, +1.0017698683]]
)

rgb_from_xyz = np.array(
    [[+3.2404542, -0.9692660, +0.0556434],
     [-1.5371385, +1.8760108, -0.2040259],
     [-0.4985314, +0.0415560, +1.0572252]]
)

xyz_from_rgb = np.array(
    [[0.4124564323, 0.2126728463, 0.0193339041],
     [0.3575760763, 0.7151521672, 0.1191920282],
     [0.1804374803, 0.0721749996, 0.9503040737]]
)

lms_max = [+5.7892596814, +1.8562911671, +1.6269035027]
lms_min = [-2.7103601962, -3.5640037911, -0.4929387368]


def rgb012lms(x):
    return xyz2lms(rgb012xyz(x.copy()))


def rgb2lms(x):
    return rgb012lms(normalisations.rgb2double(x))


def rgb2lms01(x):
    x = rgb2lms(x)
    for i in range(3):
        x[:, :, i] /= (lms_max[i] - lms_min[i])
        x[:, :, i] += (abs(lms_min[i]) / (lms_max[i] - lms_min[i]))
    x = np.maximum(x, 0)
    x = np.minimum(x, 1)
    return x


def lms2rgb(x):
    return normalisations.uint8im(lms2rgb01(x))


def lms2rgb01(x):
    return xyz2rgb01(lms2xyz(x.copy()))


def lms012rgb01(x):
    x = x.copy()
    for i in range(3):
        x[:, :, i] -= (abs(lms_min[i]) / (lms_max[i] - lms_min[i]))
        x[:, :, i] *= (lms_max[i] - lms_min[i])
    x = lms2rgb01(x)
    x = np.maximum(x, 0)
    x = np.minimum(x, 1)
    return x


def lms012rgb(x):
    return normalisations.uint8im(lms012rgb01(x))


def lms2xyz(x):
    return np.dot(x, lms_from_xyz)


def xyz2lms(x):
    return np.dot(x, xyz_from_lms)


def rgb012xyz(x):
    return np.dot(x, rgb_from_xyz)


def rgb2xyz(x):
    return rgb012xyz(normalisations.rgb2double(x))


def xyz2rgb(x):
    return normalisations.uint8im(xyz2rgb01(x))


def xyz2rgb01(x):
    return np.dot(x, xyz_from_rgb)


def rgb012dkl(x):
    return np.dot(x, rgb_from_dkl)


def rgb2dkl(x):
    return rgb012dkl(normalisations.rgb2double(x))


def rgb2dkl01(x):
    x = rgb2dkl(x)
    x /= 2
    x[:, :, 1] += 0.5
    x[:, :, 2] += 0.5
    return x


def dkl2rgb(x):
    return normalisations.uint8im(dkl2rgb01(x))


def dkl2rgb01(x):
    return np.dot(x, dkl_from_rgb)


def dkl012rgb(x):
    return normalisations.uint8im(dkl012rgb01(x))


def dkl012rgb01(x):
    x = x.copy()
    x[:, :, 1] -= 0.5
    x[:, :, 2] -= 0.5
    x *= 2
    return dkl2rgb01(x)


def rgb2hsv01(x):
    assert x.dtype == 'uint8'
    x = cv2.cvtColor(x, cv2.COLOR_RGB2HSV)
    x = x.astype('float')
    x[:, :, 0] /= 180
    x[:, :, 1:] /= 255
    return x


def hsv012rgb(x):
    x[:, :, 0] *= (180 / 255)
    x = normalisations.uint8im(x)
    return cv2.cvtColor(x, cv2.COLOR_HSV2RGB)


def rgb2opponency(image_rgb, opponent_space='lab'):
    image_rgb = normalisations.rgb2double(image_rgb)
    if opponent_space is None:
        # it's already in opponency
        image_opponent = image_rgb
    elif opponent_space == 'lab':
        image_opponent = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2LAB)
    elif opponent_space == 'dkl':
        image_opponent = rgb012dkl(image_rgb)
    else:
        sys.exit('Not supported colour space %s' % opponent_space)
    return image_opponent


def opponency2rgb(image_opponent, opponent_space='lab'):
    if opponent_space is None:
        # it's already in rgb
        image_rgb = image_opponent
    elif opponent_space == 'lab':
        image_rgb = cv2.cvtColor(image_opponent, cv2.COLOR_LAB2RGB)
        image_rgb = normalisations.uint8im(image_rgb)
    elif opponent_space == 'dkl':
        image_rgb = dkl2rgb(image_opponent)
    else:
        sys.exit('Not supported colour space %s' % opponent_space)
    return image_rgb


def get_max_lightness(opponent_space='lab'):
    if opponent_space is None:
        # it's already in rgb
        max_lightness = 255
    elif opponent_space == 'lab':
        max_lightness = 100
    elif opponent_space == 'dkl':
        max_lightness = 2
    else:
        sys.exit('Not supported colour space %s' % opponent_space)
    return max_lightness
