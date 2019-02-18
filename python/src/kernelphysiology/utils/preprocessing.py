'''
Preprocessing functions.
'''


import numpy as np

from kernelphysiology.utils.imutils import gaussian_blur, gaussian_noise
from kernelphysiology.utils.imutils import s_p_noise, speckle_noise, poisson_noise
from kernelphysiology.utils.imutils import adjust_gamma, adjust_contrast, adjust_illuminant
from kernelphysiology.utils.imutils import random_occlusion, reduce_red_green, reduce_yellow_blue
from kernelphysiology.utils.imutils import reduce_chromaticity, reduce_lightness, rotate_hue
from kernelphysiology.utils.imutils import invert_chromaticity, invert_colour_opponency, invert_lightness


def occlusion_preprocessing(img, var, mask_radius=None, preprocessing_function=None):
    img = random_occlusion(img, object_instances=1, object_ratio=var) * 255
    if preprocessing_function:
        img = preprocessing_function(img)
    return img


def speckle_noise_preprocessing(img, var, mask_radius=None, preprocessing_function=None):
    img = speckle_noise(img, var, mask_radius=mask_radius) * 255
    if preprocessing_function:
        img = preprocessing_function(img)
    return img


def s_p_noise_preprocessing(img, amount, mask_radius=None, preprocessing_function=None):
    img = s_p_noise(img, amount, mask_radius=mask_radius) * 255
    if preprocessing_function:
        img = preprocessing_function(img)
    return img


def poisson_noise_preprocessing(img, _, mask_radius=None, preprocessing_function=None):
    img = poisson_noise(img, mask_radius=mask_radius) * 255
    if preprocessing_function:
        img = preprocessing_function(img)
    return img


def gaussian_noise_preprocessing(img, var, mask_radius=None, preprocessing_function=None):
    img = gaussian_noise(img, var, mask_radius=mask_radius) * 255
    if preprocessing_function:
        img = preprocessing_function(img)
    return img


def colour_constancy_preprocessing(img, illuminant, mask_radius=None, preprocessing_function=None):
    # FIXME: for now it's only one channel, make it a loop for all channels
    illuminant = (illuminant, 1, 1)
    img = adjust_illuminant(img, illuminant, mask_radius=mask_radius) * 255
    if preprocessing_function:
        img = preprocessing_function(img)
    return img


def gamma_preprocessing(img, amount, mask_radius=None, preprocessing_function=None):
    img = adjust_gamma(img, amount, mask_radius=mask_radius) * 255
    if preprocessing_function:
        img = preprocessing_function(img)
    return img


def gaussian_preprocessing(img, sigma, mask_radius=None, preprocessing_function=None):
    img = gaussian_blur(img, sigma, mask_radius=mask_radius) * 255
    if preprocessing_function:
        img = preprocessing_function(img)
    return img


def contrast_preprocessing(img, contrast, mask_radius=None, preprocessing_function=None):
    img = adjust_contrast(img, contrast, mask_radius=mask_radius) * 255
    if preprocessing_function:
        img = preprocessing_function(img)
    return img


def red_green_preprocessing(img, amount, mask_radius=None, preprocessing_function=None):
    img = reduce_red_green(img, amount, mask_radius=mask_radius) * 255
    if preprocessing_function:
        img = preprocessing_function(img)
    return img


def yellow_blue_preprocessing(img, amount, mask_radius=None, preprocessing_function=None):
    img = reduce_yellow_blue(img, amount, mask_radius=mask_radius) * 255
    if preprocessing_function:
        img = preprocessing_function(img)
    return img


def chromacity_preprocessing(img, amount, mask_radius=None, preprocessing_function=None):
    img = reduce_chromaticity(img, amount, mask_radius=mask_radius) * 255
    if preprocessing_function:
        img = preprocessing_function(img)
    return img


def lightness_preprocessing(img, amount, mask_radius=None, preprocessing_function=None):
    img = reduce_lightness(img, amount, mask_radius=mask_radius) * 255
    if preprocessing_function:
        img = preprocessing_function(img)
    return img


def invert_chromaticity_preprocessing(img, _, mask_radius=None, preprocessing_function=None):
    img = invert_chromaticity(img, mask_radius=mask_radius) * 255
    if preprocessing_function:
        img = preprocessing_function(img)
    return img


def invert_opponency_preprocessing(img, _, mask_radius=None, preprocessing_function=None):
    img = invert_colour_opponency(img, mask_radius=mask_radius) * 255
    if preprocessing_function:
        img = preprocessing_function(img)
    return img


def invert_lightness_preprocessing(img, _, mask_radius=None, preprocessing_function=None):
    img = invert_lightness(img, mask_radius=mask_radius) * 255
    if preprocessing_function:
        img = preprocessing_function(img)
    return img


def rotate_hue_preprocessing(img, amount, mask_radius=None, preprocessing_function=None):
    img = rotate_hue(img, amount, mask_radius=mask_radius) * 255
    if preprocessing_function:
        img = preprocessing_function(img)
    return img


def which_preprocessing(args):
    # TODO: betetr handling of functions that can take more than one element
    if args.contrasts is not None:
        image_manipulation_type = 'contrast'
        image_manipulation_values = np.array(args.contrasts)
        image_manipulation_function = contrast_preprocessing
    elif args.gaussian_sigma is not None:
        image_manipulation_type = 'Gaussian'
        image_manipulation_values = np.array(args.gaussian_sigma)
        image_manipulation_function = gaussian_preprocessing
    elif args.s_p_noise is not None:
        image_manipulation_type = 'salt_pepper'
        image_manipulation_values = np.array(args.s_p_noise)
        image_manipulation_function = s_p_noise_preprocessing
    elif args.speckle_noise is not None:
        image_manipulation_type = 'speckle_noise'
        image_manipulation_values = np.array(args.speckle_noise)
        image_manipulation_function = speckle_noise_preprocessing
    elif args.gaussian_noise is not None:
        image_manipulation_type = 'Gaussian_noise'
        image_manipulation_values = np.array(args.gaussian_noise)
        image_manipulation_function = gaussian_noise_preprocessing
    elif args.poisson_noise:
        image_manipulation_type = 'Poisson_noise'
        image_manipulation_values = np.array([0])
        image_manipulation_function = poisson_noise_preprocessing
    elif args.gammas is not None:
        image_manipulation_type = 'gamma'
        image_manipulation_values = np.array(args.gammas)
        image_manipulation_function = gamma_preprocessing
        # FIXME: for now it's only one channel, make it a loop for all channels
    elif args.illuminants is not None:
        image_manipulation_type = 'illuminants'
        image_manipulation_values = np.array(args.illuminants)
        image_manipulation_function = colour_constancy_preprocessing
    elif args.occlusion is not None:
        image_manipulation_type = 'occlusion'
        image_manipulation_values = np.array(args.occlusion)
        image_manipulation_function = occlusion_preprocessing
    elif args.red_green is not None:
        image_manipulation_type = 'red_green'
        image_manipulation_values = np.array(args.red_green)
        image_manipulation_function = red_green_preprocessing
    elif args.yellow_blue is not None:
        image_manipulation_type = 'yellow_blue'
        image_manipulation_values = np.array(args.yellow_blue)
        image_manipulation_function = yellow_blue_preprocessing
    elif args.chromaticity is not None:
        image_manipulation_type = 'chromaticity'
        image_manipulation_values = np.array(args.chromacity)
        image_manipulation_function = chromacity_preprocessing
    elif args.lightness is not None:
        image_manipulation_type = 'lightness'
        image_manipulation_values = np.array(args.lightness)
        image_manipulation_function = lightness_preprocessing
    elif args.invert_chromaticity:
        image_manipulation_type = 'invert_chromaticity'
        image_manipulation_values = np.array([0])
        image_manipulation_function = invert_chromaticity_preprocessing
    elif args.invert_opponency:
        image_manipulation_type = 'invert_opponency'
        image_manipulation_values = np.array([0])
        image_manipulation_function = invert_opponency_preprocessing
    elif args.invert_lightness:
        image_manipulation_type = 'invert_lightness'
        image_manipulation_values = np.array([0])
        image_manipulation_function = invert_lightness_preprocessing
    elif args.rotate_hue is not None:
        image_manipulation_type = 'rotate_hue'
        image_manipulation_values = np.array(args.rotate_hue)
        image_manipulation_function = rotate_hue_preprocessing
    return (image_manipulation_type, image_manipulation_values, image_manipulation_function)
