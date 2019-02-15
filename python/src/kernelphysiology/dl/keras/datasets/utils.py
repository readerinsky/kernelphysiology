'''
The utility functoins for datasets.
'''


import commons

import socket
import sys
import os
import numpy as np
import skimage
import logging

from kernelphysiology.dl.keras.datasets.cifar import cifar_train
from kernelphysiology.dl.keras.datasets.stl import stl_train
from kernelphysiology.dl.keras.datasets.imagenet import imagenet_train
from kernelphysiology.dl.keras.datasets.coco import coco


def which_dataset(args, dataset_name):
    if dataset_name == 'cifar10':
        if args.script_type == 'training':
            args = cifar_train.prepare_cifar10_generators(args)
        else:
            args = cifar_train.cifar10_validatoin_generator(args)
    elif dataset_name == 'cifar100':
        if args.script_type == 'training':
            args = cifar_train.prepare_cifar100_generators(args)
        else:
            args = cifar_train.cifar100_validatoin_generator(args)
    elif dataset_name == 'stl10':
        if args.script_type == 'training':
            args = stl_train.prepare_stl10_generators(args)
        else:
            args = stl_train.stl10_validation_generator(args)
    elif dataset_name == 'imagenet':
        if args.script_type == 'training':
            args = imagenet_train.prepare_imagenet(args)
        else:
            args = imagenet_train.validation_generator(args)
    elif dataset_name == 'coco':
        if args.script_type == 'training':
            args = coco.train_config(args)
        else:
            args = coco.validation_config(args)
    return args


def get_default_num_classes(dataset):
    if dataset == 'imagenet':
        num_classes = 1000
    elif dataset == 'cifar10' or dataset == 'stl10':
        num_classes = 10
    elif dataset == 'cifar100':
        num_classes = 100
    else:
        sys.exit('Default num_classes is not defined for dataset %s' % (dataset))
    return num_classes


def get_default_target_size(dataset):
    if dataset == 'imagenet':
        target_size = 224
    elif dataset == 'cifar10' or dataset == 'cifar100' or dataset == 'stl10':
        target_size = 32
    else:
        sys.exit('Default target_size is not defined for dataset %s' % (dataset))

    target_size = (target_size, target_size)
    return target_size


def get_default_dataset_paths(args):
    if args.dataset == 'imagenet':
        # NOTE: just for the ease of working in my machiens
        if args.train_dir is None:
            args.train_dir = '/home/arash/Software/imagenet/raw-data/train/'
        if args.validation_dir is None:
            if socket.gethostname() == 'awesome' or socket.gethostname() == 'nickel':
                args.validation_dir = '/home/arash/Software/imagenet/raw-data/validation/'
            else:
                args.validation_dir = '/home/arash/Software/repositories/kernelphysiology/data/computervision/ilsvrc/ilsvrc2012/raw-data/validation/'
    elif args.dataset == 'cifar10':
        if args.data_dir is None:
            args.data_dir = os.path.join(commons.python_root, 'data/datasets/cifar/cifar10/')
    elif args.dataset == 'cifar100':
        if args.data_dir is None:
            args.data_dir = os.path.join(commons.python_root, 'data/datasets/cifar/cifar100/')
    elif args.dataset == 'stl10':
        if args.data_dir is None:
            args.data_dir = os.path.join(commons.python_root, 'data/datasets/stl/stl10/')
    if args.dataset == 'coco':
        # NOTE: just for the ease of working in my machiens
        # FIXME
        if args.train_dir is None:
            args.train_dir = '/home/arash/Software/coco'
        if args.validation_dir is None:
            if socket.gethostname() == 'awesome' or socket.gethostname() == 'nickel':
                args.validation_dir = '/home/arash/Software/coco/'
            else:
                args.validation_dir = '/home/arash/Software/repositories/kernelphysiology/data/computervision/ilsvrc/ilsvrc2012/raw-data/validation/'           
    else:
        sys.exit('Unsupported dataset %s' % (args.dataset))
    return args
