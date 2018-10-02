'''
Training the IMAGENET dataset.
'''


from __future__ import absolute_import
from __future__ import division
from __future__ import print_function


from kernelphysiology.dl.keras.imagenet import imagenet


def prepare_imagenet(args):
    args.num_classes = 1000

    args.train_generator = imagenet.train_generator(args.train_dir, batch_size=args.batch_size,
                                                    target_size=args.target_size,
                                                    preprocessing_function=args.preprocessing_function,
                                                    horizontal_flip=args.horizontal_flip,
                                                    vertical_flip=args.vertical_flip)

    args.validation_generator = imagenet.validation_generator(args.validation_dir, batch_size=args.batch_size, target_size=args.target_size, preprocessing_function=args.preprocessing_function)

    return args


def validation_generator(args):
    args.num_classes = 1000

    args.validation_generator = imagenet.validation_generator(args.validation_dir, batch_size=args.batch_size, target_size=args.target_size, preprocessing_function=args.preprocessing_function)

    return args