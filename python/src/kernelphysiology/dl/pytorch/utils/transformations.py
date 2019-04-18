"""
Transformations on tensors without going to CPU.
"""

import warnings
from scipy import linalg
import torch

np_xyz_from_rgb = [[0.412453, 0.357580, 0.180423],
                   [0.212671, 0.715160, 0.072169],
                   [0.019334, 0.119193, 0.950227]]
xyz_from_rgb = torch.tensor(np_xyz_from_rgb)

np_rgb_from_xyz = linalg.inv(np_xyz_from_rgb)
rgb_from_xyz = torch.tensor(np_rgb_from_xyz)

xyz_ref_white = (0.95047, 1., 1.08883)


def rgb2xyz(img_rgb):
    arr = img_rgb.clone()
    mask = arr > 0.04045
    arr[mask] = ((arr[mask] + 0.055) / 1.055).pow(2.4)
    arr[~mask] /= 12.92

    img_xyz = torch.empty(img_rgb.shape, dtype=torch.float)
    for i in range(3):
        x_r = arr[0,] * xyz_from_rgb[i, 0]
        y_g = arr[1,] * xyz_from_rgb[i, 1]
        z_b = arr[2,] * xyz_from_rgb[i, 2]
        img_xyz[i,] = x_r + y_g + z_b

    return img_xyz


def xyz2rgb(img_xyz):
    arr = img_xyz.clone()
    # Follow the algorithm from http://www.easyrgb.com/index.php
    # except we don't multiply/divide by 100 in the conversion
    img_rgb = torch.empty(img_xyz.shape, dtype=torch.float)
    for i in range(3):
        x_r = arr[0,] * rgb_from_xyz[i, 0]
        y_g = arr[1,] * rgb_from_xyz[i, 1]
        z_b = arr[2,] * rgb_from_xyz[i, 2]
        img_rgb[i,] = x_r + y_g + z_b

    mask = img_rgb > 0.0031308
    img_rgb[mask] = 1.055 * img_rgb[mask].pow(1 / 2.4) - 0.055
    img_rgb[~mask] *= 12.92
    img_rgb = img_rgb.clamp(0, 1)
    return img_rgb


def xyz2lab(img_xyz):
    arr = img_xyz.clone()

    # scale by CIE XYZ tristimulus values of the reference white point
    for i in range(3):
        arr[i,] /= xyz_ref_white[i]

    # Nonlinear distortion and linear transformation
    mask = arr > 0.008856
    arr[mask] = arr[mask].pow(1 / 3)
    arr[~mask] = 7.787 * arr[~mask] + 16. / 116.

    x = arr[0,]
    y = arr[1,]
    z = arr[2,]

    # Vector scaling
    L = (116. * y) - 16.
    a = 500.0 * (x - y)
    b = 200.0 * (y - z)

    img_lab = torch.empty(img_xyz.shape, dtype=torch.float)
    img_lab[0,] = L
    img_lab[1,] = a
    img_lab[2,] = b
    return img_lab


def lab2xyz(img_lab):
    arr = img_lab.clone()

    L = arr[0,]
    a = arr[1,]
    b = arr[2,]
    y = (L + 16.) / 116.
    x = (a / 500.) + y
    z = y - (b / 200.)

    invalid = torch.nonzero(z < 0)
    print(invalid)
    if invalid.shape[0] > 0:
        warnings.warn(
            'Color data out of range: Z < 0 in %s pixels' % invalid[0].size)
        z[invalid] = 0

    img_xyz = torch.empty(img_lab.shape, dtype=torch.float)
    img_xyz[0,] = x
    img_xyz[1,] = y
    img_xyz[2,] = z

    mask = img_xyz > 0.2068966
    img_xyz[mask] = img_xyz[mask].pow(3.)
    img_xyz[~mask] = (img_xyz[~mask] - 16.0 / 116.) / 7.787

    # rescale to the reference white (illuminant)
    for i in range(3):
        img_xyz[i,] *= xyz_ref_white[i]
    return img_xyz


def rgb2lab(rgb):
    return xyz2lab(rgb2xyz(rgb))


def lab2rgb(lab):
    return xyz2rgb(lab2xyz(lab))
