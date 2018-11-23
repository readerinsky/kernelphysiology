'''
Testing a Keras model of vairous datasets for different image manipulations.
'''


import commons

import sys
import numpy as np
import time
import datetime

import tensorflow as tf
import keras
from keras.utils import multi_gpu_model

from kernelphysiology.dl.keras.prominent_utils import test_prominent_prepares, test_arg_parser
from kernelphysiology.dl.keras.prominent_utils import get_preprocessing_function, get_top_k_accuracy
from kernelphysiology.dl.keras.prominent_utils import which_network, which_dataset
from kernelphysiology.utils.imutils import uniform_noise_colour, gaussian_blur, s_p_noise
from kernelphysiology.utils.imutils import adjust_gamma, adjust_contrast, adjust_illuminant


def uniform_noise_preprocessing(img, width, preprocessing_function=None):
    img = uniform_noise_colour(img, width, 1, np.random.RandomState(seed=1)) * 255
    if preprocessing_function:
        img = preprocessing_function(img)
    return img


def colour_constancy_preprocessing(img, illuminant, preprocessing_function=None):
    img = adjust_illuminant(img, illuminant) * 255
    if preprocessing_function:
        img = preprocessing_function(img)
    return img


def gamma_preprocessing(img, amount, preprocessing_function=None):
    img = adjust_gamma(img, amount) * 255
    if preprocessing_function:
        img = preprocessing_function(img)
    return img


def s_p_preprocessing(img, amount, preprocessing_function=None):
    img = s_p_noise(img, amount) * 255
    if preprocessing_function:
        img = preprocessing_function(img)
    return img


def gaussian_preprocessing(img, win_size, preprocessing_function=None):
    img = gaussian_blur(img, win_size) * 255
    if preprocessing_function:
        img = preprocessing_function(img)
    return img


def contrast_preprocessing(img, contrast, preprocessing_function=None):
    img = adjust_contrast(img, contrast) * 255
    if preprocessing_function:
        img = preprocessing_function(img)
    return img


if __name__ == "__main__":
    start_stamp = time.time()
    start_time = datetime.datetime.fromtimestamp(start_stamp).strftime('%Y-%m-%d_%H_%M_%S')
    print('Starting at: ' + start_time)

    args = test_arg_parser(sys.argv[1:])
    args = test_prominent_prepares(args)

    dataset_name = args.dataset.lower()

    if args.contrasts is not None:
        image_manipulation_type = 'contrast'
        image_manipulation_values = np.array(args.contrasts) / 100
        image_manipulation_function = contrast_preprocessing
    elif args.gaussian_sigma is not None:
        image_manipulation_type = 'Gaussian'
        image_manipulation_values = np.array(args.gaussian_sigma)
        image_manipulation_function = gaussian_preprocessing
    elif args.s_p_noise is not None:
        image_manipulation_type = 'salt and pepper'
        image_manipulation_values = np.array(args.s_p_noise)
        image_manipulation_function = s_p_preprocessing
    elif args.uniform_noise is not None:
        image_manipulation_type = 'uniform noise'
        image_manipulation_values = np.array(args.uniform_noise)
        image_manipulation_function = uniform_noise_preprocessing
    elif args.gammas is not None:
        image_manipulation_type = 'gamma'
        image_manipulation_values = np.array(args.gammas)
        image_manipulation_function = gamma_preprocessing

    results_top1 = np.zeros((image_manipulation_values.shape[0], len(args.networks)))
    results_topk = np.zeros((image_manipulation_values.shape[0], len(args.networks)))

    # maybe if only one preprocessing is used, the generators can be called only once
    for j, network_name in enumerate(args.networks):
        # w1hich architecture
        args = which_network(args, network_name)
        for i, manipulation_value in enumerate(image_manipulation_values):
            preprocessing = args.preprocessings[j]
            current_manipulation_preprocessing = lambda img : image_manipulation_function(img, manipulation_value, 
                                                                                          preprocessing_function=get_preprocessing_function(preprocessing))
            args.validation_preprocessing_function = current_manipulation_preprocessing

            print('Processing network %s and %s %f' % (network_name, image_manipulation_type, manipulation_value))

            # which dataset
            # reading it after the model, because each might have their own
            # specific size
            args = which_dataset(args, dataset_name)

            top_k_acc = get_top_k_accuracy(args.top_k)
            metrics = ['accuracy', top_k_acc]
            opt = keras.optimizers.SGD(lr=1e-1, momentum=0.9, decay=1e-4)
            if len(args.gpus) == 1:
                # the compilation being necessary is a bug of keras
                args.model.compile(loss='categorical_crossentropy', optimizer=opt, metrics=metrics)
                current_results = args.model.evaluate_generator(generator=args.validation_generator, verbose=1,
                                                                workers=args.workers, use_multiprocessing=args.use_multiprocessing)
            else:
                with tf.device('/cpu:0'):
                    args.model.compile(loss='categorical_crossentropy', optimizer=opt, metrics=metrics)
                parallel_model = multi_gpu_model(args.model, gpus=args.gpus)
                parallel_model.compile(loss='categorical_crossentropy', optimizer=opt, metrics=metrics)
                current_results = parallel_model.evaluate_generator(generator=args.validation_generator, verbose=1,
                                                                    workers=args.workers, use_multiprocessing=args.use_multiprocessing)
            results_top1[i, j] = current_results[1]
            results_topk[i, j] = current_results[2]

            # saving the results in a CSV format
            # it's redundant to store the results as each loop, but this is
            # good for when it crashes
            np.savetxt(args.output_file + '_top1.csv', results_top1, delimiter=',')
            np.savetxt(args.output_file + '_top%d.csv' % args.top_k, results_topk, delimiter=',')

    finish_time = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d_%H_%M_%S')
    print('Finishing at: ' + finish_time)