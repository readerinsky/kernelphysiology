"""
Functions related to change or manipulation of colour spaces.
"""

import numpy as np
import sys

from skimage.color import rgb2lab, lab2rgb

from kernelphysiology.transformations.normalisations import min_max_normalise
#from kernelphysiology.utils.imutils import im2double

dkl_from_rgb = np.array(
    [[0.49995, 0.50001495, 0.49999914],
     [0.99998394, -0.29898596, 0.01714922],
     [-0.17577361, 0.15319546, -0.99994349]]
)

rgb_from_dkl = np.array(
    [[0.4252, 1.4304, 0.1444],
     [0.8273, -0.5912, -0.2360],
     [0.2268, 0.7051, -0.9319]]
).T


def rgb2dkl(x):
    # FIXME
    # x = im2double(x)
    x = x.astype('float32') / 255
    return np.dot(x, rgb_from_dkl)


def dkl2rgb(x):
    rgb_im = np.dot(x, dkl_from_rgb)
    rgb_im = np.maximum(rgb_im, 0)
    rgb_im = np.minimum(rgb_im, 1)
    rgb_im *= 255
    return rgb_im.astype('uint8')


def rgb2opponency(image_rgb, colour_space='lab'):
    if colour_space is None:
        # it's already in opponency
        image_opponent = image_rgb
    elif colour_space == 'lab':
        image_opponent = rgb2lab(image_rgb)
    elif colour_space == 'dkl':
        image_opponent = rgb2dkl(image_rgb)
    else:
        sys.exit('Not supported colour space %s' % colour_space)
    return image_opponent


def opponency2rgb(image_opponent, colour_space='lab'):
    # TODO: this is a hack to solve the problem of when the image is already in
    #  the desired colour space.
    if colour_space is None:
        # it's already in rgb
        image_rgb = image_opponent
    elif colour_space == 'lab':
        image_rgb = lab2rgb(image_opponent)
    elif colour_space == 'dkl':
        image_rgb = dkl2rgb(image_opponent)
        image_rgb = min_max_normalise(image_rgb)
    else:
        sys.exit('Not supported colour space %s' % colour_space)
    return image_rgb


def get_max_lightness(colour_space='lab'):
    if colour_space is None:
        # it's already in rgb
        max_lightness = 255
    elif colour_space == 'lab':
        max_lightness = 100
    elif colour_space == 'dkl':
        max_lightness = 2
    else:
        sys.exit('Not supported colour space %s' % colour_space)
    return max_lightness
