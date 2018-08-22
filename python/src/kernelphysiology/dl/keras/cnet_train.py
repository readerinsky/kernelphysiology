'''
Train a simple DNN on CIFAR 10 or 100.
'''


import os
import commons
import time
import datetime
import argparse

import tensorflow as tf
import keras
from keras.utils import multi_gpu_model
from keras.callbacks import CSVLogger, ModelCheckpoint, LearningRateScheduler

import kernelphysiology.dl.keras.contrast_net as cnet

from kernelphysiology.dl.keras.cifar import cifar_train
from kernelphysiology.dl.keras.stl import stl_train

from kernelphysiology.utils.imutils import adjust_contrast


def start_training(args):
    print('x_train shape:', args.x_train.shape)
    print(args.x_train.shape[0], 'train samples')
    print(args.x_test.shape[0], 'test samples')

    print('Processing with %d layers in area 1' % args.area1_nlayers)
    args.model_name += str(args.area1_nlayers)
    args.log_dir = os.path.join(args.save_dir, args.model_name)
    if not os.path.isdir(args.log_dir):
        os.mkdir(args.log_dir)
    csv_logger = CSVLogger(os.path.join(args.log_dir, 'log.csv'), append=False, separator=';')
    check_points = ModelCheckpoint(os.path.join(args.log_dir, 'weights.{epoch:05d}.h5'), period=args.log_period)

    args.area1_nlayers = int(args.area1_nlayers)
    
    model = cnet.build_classifier_model(confs=args)

    initial_lr = 1e-3
    def lr_scheduler(epoch):
        if epoch < 20:
            return initial_lr
        elif epoch < 40:
            return initial_lr / 2
        elif epoch < 50:
            return initial_lr / 4
        elif epoch < 60:
            return initial_lr / 8
        elif epoch < 70:
            return initial_lr / 16
        elif epoch < 80:
            return initial_lr / 32
        elif epoch < 90:
            return initial_lr / 64
        else:
            return initial_lr / 128
    args.callbacks = [check_points, csv_logger, LearningRateScheduler(lr_scheduler)]

    # TODO: proper analysis on differnt optimisers
#    opt = keras.optimizers.rmsprop(lr=0.0001, decay=1e-6)
    opt = keras.optimizers.Adam(initial_lr)

    # Let's train the model using RMSprop
    if args.multi_gpus == None:
        model.compile(loss='categorical_crossentropy', optimizer=opt, metrics=['accuracy'])
        args.model = model
        args.parallel_model = None
    else:
        with tf.device('/cpu:0'):
            model.compile(loss='categorical_crossentropy', optimizer=opt, metrics=['accuracy'])
            args.model = model
        parallel_model = multi_gpu_model(args.model, gpus=args.multi_gpus)
        parallel_model.compile(loss='categorical_crossentropy', optimizer=opt, metrics=['accuracy'])
        args.parallel_model = parallel_model

    # to train the network with a different contrast
    args.x_train = adjust_contrast(args.x_train, args.train_contrast / 100) * 255

    args.x_train = cnet.preprocess_input(args.x_train)
    args.x_test = cnet.preprocess_input(args.x_test)
    
    args = cnet.train_model(args)

    # Score trained model.
    scores = args.model.evaluate(args.x_test, args.y_test, verbose=1)
    print('Test loss:', scores[0])
    print('Test accuracy:', scores[1])


if __name__ == "__main__":
    start_stamp = time.time()
    start_time = datetime.datetime.fromtimestamp(start_stamp).strftime('%Y-%m-%d_%H_%M_%S')
    print('Starting at: ' + start_time)

    parser = argparse.ArgumentParser(description='Training CNET.')
    parser.add_argument(dest='dataset', type=str, help='Which dataset to be used')
    parser.add_argument('--a1', dest='area1_nlayers', type=int, default=1, help='The number of layers in area 1 (default: 1)')
    parser.add_argument('--a1nb', dest='area1_batchnormalise', action='store_false', default=True, help='Whether to include batch normalisation between layers of area 1 (default: True)')
    parser.add_argument('--a1na', dest='area1_activation', action='store_false', default=True, help='Whether to include activation between layers of area 1 (default: True)')
    parser.add_argument('--a1reduction', dest='area1_reduction', action='store_true', default=False, help='Whether to include a reduction layer in area 1 (default: False)')
    parser.add_argument('--a1dilation', dest='area1_dilation', action='store_true', default=False, help='Whether to include dilation in kernels in area 1 (default: False)')
    parser.add_argument('--dog', dest='add_dog', action='store_true', default=False, help='Whether to add a DoG layer (default: False)')
    parser.add_argument('--mg', dest='multi_gpus', type=int, default=None, help='The number of GPUs to be used (default: None)')
    parser.add_argument('--name', dest='experiment_name', type=str, default='', help='The name of the experiment (default: None)')
    parser.add_argument('--batch_size', dest='batch_size', type=int, default=32, help='Batch size (default: 64)')
    parser.add_argument('--epochs', dest='epochs', type=int, default=50, help='Number of epochs (default: 50)')
    parser.add_argument('--log_period', dest='log_period', type=int, default=0, help='The period of logging the network (default: 0)')
    parser.add_argument('--train_contrast', dest='train_contrast', type=int, default=100, help='The level of contrast to be used at training (default: 100)')
    parser.add_argument('--data_augmentation', dest='data_augmentation', action='store_true', default=False, help='Whether to augment data (default: False)')

    args = parser.parse_args()
    which_model = args.dataset.lower()
    # preparing arguments
    args.save_dir = os.path.join(commons.python_root, 'data/nets/%s/%s/' % (''.join([i for i in which_model if not i.isdigit()]), which_model))
    args.dog_path = os.path.join(args.save_dir, 'dog.h5')

    # preparing the name of the model
    args.model_name = 'keras_%s_area_%s_%s_' % (which_model, args.experiment_name, args.train_contrast)
    if args.area1_batchnormalise:
        args.model_name += 'bnr_'
    if args.area1_activation:
        args.model_name += 'act_'
    if args.area1_reduction:
        args.model_name += 'red_'
    if args.area1_dilation:
        args.model_name += 'dil_'
    if args.add_dog:
        args.model_name += 'dog_'

    # which model to run
    if which_model == 'cifar10':
        args = cifar_train.prepare_cifar10(args)
    elif which_model == 'cifar100':
        args = cifar_train.prepare_cifar100(args)
    elif which_model == 'stl10':
        args = stl_train.prepare_stl10(args)

    start_training(args)

    finish_stamp = time.time()
    finish_time = datetime.datetime.fromtimestamp(finish_stamp).strftime('%Y-%m-%d_%H_%M_%S')
    duration_time = (finish_stamp - start_stamp) / 60
    print('Finishing at: %s - Duration %.2f minutes.' % (finish_time, duration_time))