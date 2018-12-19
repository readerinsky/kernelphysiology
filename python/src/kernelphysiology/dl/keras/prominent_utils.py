'''
Utility functions for training prominent networks.
'''


import os
import glob
import argparse
import datetime
import time
import numpy as np
import warnings
import socket
import math

from kernelphysiology.dl.keras.cifar import cifar_train
from kernelphysiology.dl.keras.stl import stl_train
from kernelphysiology.dl.keras.imagenet import imagenet_train

from kernelphysiology.utils.imutils import adjust_contrast, gaussian_blur, adjust_illuminant
from kernelphysiology.utils.imutils import s_p_noise, gaussian_noise
from kernelphysiology.utils.path_utils import create_dir

from kernelphysiology.dl.keras.models.utils import which_architecture, which_network
from kernelphysiology.dl.keras.models.utils import get_preprocessing_function

from kernelphysiology.dl.keras.utils import get_input_shape


def augmented_preprocessing(img, illuminant_range=None, contrast_range=None,
                            gaussian_sigma_range=None, salt_pepper_range=None,
                            gaussian_noise_range=None,
                            preprocessing_function=None):
    # FIXME: make the augmentations smarter: e.g. half normal, half crazy illumiant
    if gaussian_sigma_range is not None:
        img = gaussian_blur(img, np.random.uniform(*gaussian_sigma_range)) * 255
    if illuminant_range is not None:
        illuminant = np.random.uniform(*illuminant_range, 3)
        img = adjust_illuminant(img, illuminant) * 255
    if contrast_range is not None:
        img = adjust_contrast(img, np.random.uniform(*contrast_range)) * 255
    if salt_pepper_range is not None:
        img = s_p_noise(img, np.random.uniform(*salt_pepper_range)) * 255
    if gaussian_noise_range is not None:
        img = gaussian_noise(img, np.random.uniform(*gaussian_noise_range)) * 255
    if preprocessing_function is not None:
        img = preprocessing_function(img)
    return img


def test_prominent_prepares(args):
    output_file = None
    if os.path.isdir(args.network_name):
        dirname = args.network_name
        output_dir = os.path.join(dirname, args.experiment_name)
        create_dir(output_dir)
        output_file = os.path.join(output_dir, 'contrast_results')
        networks = sorted(glob.glob(dirname + '*.h5'))
        preprocessings = [args.preprocessing] * len(networks)
    elif os.path.isfile(args.network_name):
        networks = []
        preprocessings = []
        with open(args.network_name) as f:
            lines = f.readlines()
            for line in lines:
                tokens = line.strip().split(',')
                networks.append(tokens[0])
                preprocessings.append(tokens[1])
    else:
        networks = [args.network_name.lower()]
        preprocessings = [args.preprocessing]

    if not output_file:
        current_time = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d_%H_%M_%S')
        output_dir = args.experiment_name
        create_dir(output_dir)
        output_file = os.path.join(output_dir, 'contrast_results' + current_time)

    args.networks = networks
    args.preprocessings = preprocessings
    args.output_file = output_file

    return args


def train_prominent_prepares(args):
    dataset_name = args.dataset.lower()
    network_name = args.network_name.lower()

    # choosing the preprocessing function
    if not args.preprocessing:
        args.preprocessing = network_name

    # which augmentation we're handling
    if args.illuminant_range is not None:
        illuminant_range = np.array([args.illuminant_range, 1])
    else:
        illuminant_range = None
    if args.contrast_range is not None:
        contrast_range = np.array([args.contrast_range, 100]) / 100
        # FIXME: add local variations
#        local_contrast_variation = args.local_contrast_variation / 100
    else:
        contrast_range = None
    if args.gaussian_sigma is not None:
        gaussian_sigma_range = np.array([0, args.gaussian_sigma])
    else:
        gaussian_sigma_range = None
    if args.s_p_amount is not None:
        salt_pepper_range = np.array([0, args.s_p_amount])
    else:
        salt_pepper_range = None
    if args.gaussian_amount is not None:
        gaussian_noise_range = np.array([0, args.gaussian_amount])
    else:
        gaussian_noise_range = None

    # creating the augmentation lambda
    current_augmentation_preprocessing = lambda img: augmented_preprocessing(img,
                                                                             illuminant_range=illuminant_range, contrast_range=contrast_range,
                                                                             gaussian_sigma_range=gaussian_sigma_range,
                                                                             salt_pepper_range=salt_pepper_range,
                                                                             gaussian_noise_range=gaussian_noise_range,
                                                                             preprocessing_function=get_preprocessing_function(args.preprocessing))
    args.train_preprocessing_function = current_augmentation_preprocessing

    # we don't want augmentation for validation set
    args.validation_preprocessing_function = get_preprocessing_function(args.preprocessing)

    # which dataset
    args = which_dataset(args, dataset_name)

    if args.steps_per_epoch is None:
        args.steps_per_epoch = args.train_samples / args.batch_size
    if args.validation_steps is None:
        args.validation_steps = args.validation_samples / args.batch_size

    if args.load_weights is not None:
        # which network
        args = which_network(args, args.load_weights)
    else:
        # which architecture
        args.model = which_architecture(args)

    return args


def which_dataset(args, dataset_name):
    if dataset_name == 'cifar10':
        if hasattr(args, 'train_preprocessing_function'):
            args = cifar_train.prepare_cifar10_generators(args)
        else:
            args = cifar_train.cifar10_validatoin_generator(args)
    elif dataset_name == 'cifar100':
        if hasattr(args, 'train_preprocessing_function'):
            args = cifar_train.prepare_cifar100_generators(args)
        else:
            args = cifar_train.cifar100_validatoin_generator(args)
    elif dataset_name == 'stl10':
        if hasattr(args, 'train_preprocessing_function'):
            args = stl_train.prepare_stl10_generators(args)
        else:
            args = stl_train.stl10_validation_generator(args)
    elif dataset_name == 'imagenet':
        # TODO: this is not the nicest way to distinguish between train and validaiton
        if hasattr(args, 'train_preprocessing_function'):
            args = imagenet_train.prepare_imagenet(args)
        else:
            args = imagenet_train.validation_generator(args)
    return args


def common_arg_parser(description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(dest='dataset', type=str, help='Which dataset to be used')
    parser.add_argument(dest='network_name', type=str, help='Which network to be used')

    parser.add_argument('--name', dest='experiment_name', type=str, default='Ex', help='The name of the experiment (default: Ex)')

    # TODO: this is just now for imagenet
    parser.add_argument('--train_dir', type=str, default=None, help='The path to the train directory (default: None)')
    parser.add_argument('--validation_dir', type=str, default=None, help='The path to the validation directory (default: None)')

    # TODO: make the argument list nicer according to test or train ...
    parser.add_argument('--gpus', nargs='+', type=int, default=[0], help='List of GPUs to be used (default: [0])')
    parser.add_argument('--workers', type=int, default=1, help='Number of workers for image generator (default: 1)')

    parser.add_argument('--batch_size', type=int, default=32, help='Batch size (default: 32)')
    parser.add_argument('--target_size', type=int, default=224, help='Target size (default: 224)')
    parser.add_argument('--crop_centre', action='store_true', default=False, help='Crop the image to its centre (default: False)')
    parser.add_argument('--preprocessing', type=str, default=None, help='The preprocessing function (default: network preprocessing function)')
    parser.add_argument('--top_k', type=int, default=5, help='Accuracy of top K elements (default: 5)')

    return parser


def activation_arg_parser(argvs):
    parser = common_arg_parser('Analysing activation of prominent nets of Keras.')

    parser.add_argument('--contrasts', nargs='+', type=float, default=[100], help='List of contrasts to be evaluated (default: [100])')

    return check_args(parser, argvs)


def test_arg_parser(argvs):
    parser = common_arg_parser('Test prominent nets of Keras for different contrasts.')

    image_degradation_group = parser.add_mutually_exclusive_group()
    image_degradation_group.add_argument('--contrasts', nargs='+', type=float, default=None, help='List of contrasts to be evaluated (default: None)')
    image_degradation_group.add_argument('--gaussian_sigma', nargs='+', type=float, default=None, help='List of Gaussian sigmas to be evaluated (default: None)')
    image_degradation_group.add_argument('--s_p_noise', nargs='+', type=float, default=None, help='List of salt and pepper noise to be evaluated (default: None)')
    image_degradation_group.add_argument('--speckle_noise', nargs='+', type=float, default=None, help='List of speckle noise to be evaluated (default: None)')
    image_degradation_group.add_argument('--gaussian_noise', nargs='+', type=float, default=None, help='List of Gaussian noise to be evaluated (default: None)')
    image_degradation_group.add_argument('--poisson_noise', action='store_true', default=False, help='Poisson noise to be evaluated (default: False)')
    image_degradation_group.add_argument('--gammas', nargs='+', type=float, default=None, help='List of gammas to be evaluated (default: None)')
    image_degradation_group.add_argument('--illuminants', nargs='+', type=float, default=None, help='List of illuminations to be evaluated (default: None)')

    return check_args(parser, argvs)


def train_arg_parser(argvs):
    parser = common_arg_parser('Training prominent nets of Keras.')

    # better handling the parameters, e.g. pretrained ones are only for imagenet
    parser.add_argument('--area1layers', type=int, default=None, help='The number of layers in area 1 (default: None)')

    weights_group = parser.add_mutually_exclusive_group()
    weights_group.add_argument('--load_weights', type=str, default=None, help='Whether loading weights from a model (default: None)')
    weights_group.add_argument('--initialise', type=str, default=None, help='Whether using a specific initialisation of weights (default: None)')
    parser.add_argument('--tog_sigma', type=float, default=1, help='Sigma of ToG initialisation (default: 1)')
    parser.add_argument('--tog_surround', type=float, default=5, help='Surround enlargement in ToG initialisation (default: 5)')
    parser.add_argument('--g_sigmax', type=float, default=1, help='Sigma-x of Gaussian initialisation (default: 1)')
    parser.add_argument('--g_sigmay', type=float, default=None, help='Sigma-y of Gaussian initialisation (default: None)')
    parser.add_argument('--g_meanx', type=float, default=0, help='Mean-x of Gaussian initialisation (default: 0)')
    parser.add_argument('--g_meany', type=float, default=0, help='Mean-y of Gaussian initialisation (default: 0)')
    parser.add_argument('--g_theta', type=float, default=0, help='Theta of Gaussian initialisation (default: 0)')
    parser.add_argument('--gg_sigma', type=float, default=1, help='Sigma of Gaussian gradient initialisation (default: 1)')
    parser.add_argument('--gg_theta', type=float, default=math.pi/2, help='Theta of Gaussian gradient initialisation (default: 1)')
    parser.add_argument('--gg_seta', type=float, default=1, help='Seta of Gaussian gradient initialisation (default: 1)')

    parser.add_argument('--optimiser', type=str, default='adam', help='The optimiser to be used (default: adam)')
    parser.add_argument('--lr', type=float, default=None, help='The learning rate parameter of optimiser (default: None)')
    parser.add_argument('--decay', type=float, default=None, help='The decay weight parameter of optimiser (default: None)')
    parser.add_argument('--exp_decay', type=float, default=None, help='The exponential decay (default: None)')
    parser.add_argument('--lr_schedule', type=str, default=None, help='The custom learning rate scheduler (default: None)')

    parser.add_argument('--epochs', type=int, default=50, help='Number of epochs (default: 50)')
    parser.add_argument('--initial_epoch', type=int, default=0, help='The initial epoch number (default: 0)')
    parser.add_argument('--log_period', type=int, default=0, help='The period of logging the epochs weights (default: 0)')
    parser.add_argument('--steps_per_epoch', type=int, default=None, help='Number of steps per epochs (default: number of samples divided by the batch size)')
    parser.add_argument('--validation_steps', type=int, default=None, help='Number of steps for validations (default: number of samples divided by the batch size)')

    parser.add_argument('--noshuffle', dest='shuffle', action='store_false', default=True, help='Whether to stop shuffling data (default: False)')
    parser.add_argument('--horizontal_flip', action='store_true', default=False, help='Whether to perform horizontal flip data (default: False)')
    parser.add_argument('--vertical_flip', action='store_true', default=False, help='Whether to perform vertical flip (default: False)')
    parser.add_argument('--zoom_range', type=float, default=0, help='Value for zoom agumentation (default: 0)')
    parser.add_argument('--width_shift_range', type=float, default=0, help='Value for width shift agumentation (default: 0)')
    parser.add_argument('--height_shift_range', type=float, default=0, help='Value for height shift agumentation (default: 0)')

    parser.add_argument('--contrast_range', type=float, default=None, help='Value to perform contrast agumentation (default: None)')
    parser.add_argument('--local_contrast_variation', type=float, default=0, help='Value to deviate local contrast augmentation (default: 0)')
    parser.add_argument('--illuminant_range', type=float, default=None, help='Value to perform illumination agumentation (default: None)')
    parser.add_argument('--local_illuminant_variation', type=float, default=0, help='Value to deviate local illumination augmentation (default: 0)')
    parser.add_argument('--gaussian_sigma', type=float, default=None, help='Value to perform Gaussian blurring agumentation (default: None)')
    parser.add_argument('--s_p_amount', type=float, default=None, help='Value to perform salt&pepper agumentation (default: None)')
    parser.add_argument('--gaussian_amount', type=float, default=None, help='Value to perform Gaussian noise agumentation (default: None)')

    return check_args(parser, argvs)


def check_args(parser, argvs):
    # NOTE: this is just in order to get rid of EXIF warnigns
    warnings.filterwarnings("ignore", "(Possibly )?corrupt EXIF data", UserWarning)

    args = parser.parse_args(argvs)
    # TODO: more checking for GPUs
    os.environ["CUDA_VISIBLE_DEVICES"] = ', '.join(str(e) for e in args.gpus)

    args.target_size = (args.target_size, args.target_size)
    # check the input shape
    args.input_shape = get_input_shape(args.target_size)

    # workers
    if args.workers > 1:
        args.use_multiprocessing = True
    else:
        args.use_multiprocessing = False

    if args.dataset == 'imagenet':
        # TODO: just for the ease of working in my machiens
        if args.train_dir is None:
            args.train_dir = '/home/arash/Software/imagenet/raw-data/train/'
        if args.validation_dir is None:
            if socket.gethostname() == 'awesome':
                args.validation_dir = '/home/arash/Software/imagenet/raw-data/validation/'
            else:
                args.validation_dir = '/home/arash/Software/repositories/kernelphysiology/data/computervision/ilsvrc/ilsvrc2012/raw-data/validation/'

    return args