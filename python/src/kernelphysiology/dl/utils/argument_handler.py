'''
Handling input arguments for training/testing a network.
'''


import os
import sys
import glob
import argparse
import datetime
import time
import numpy as np
import warnings
import math

from kernelphysiology.utils.path_utils import create_dir
from kernelphysiology.dl.utils import default_configs
from kernelphysiology.dl.keras.datasets.utils import get_default_target_size
from kernelphysiology.dl.keras.utils import get_input_shape


def test_prominent_prepares(experiment_name, network_arg, preprocessing=None):
    output_file = None
    if os.path.isdir(network_arg):
        dirname = network_arg
        output_dir = os.path.join(dirname, experiment_name)
        create_dir(output_dir)
        output_file = os.path.join(output_dir, 'results_')
        networks = sorted(glob.glob(dirname + '*.h5'))
        network_names = []
        preprocessings = [preprocessing] * len(networks)
    elif os.path.isfile(network_arg):
        networks = []
        preprocessings = []
        network_names = []
        with open(network_arg) as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                tokens = line.strip().split(',')
                networks.append(tokens[0])
                if len(tokens) > 1:
                    preprocessings.append(tokens[1])
                else:
                    preprocessings.append(preprocessing)
                if len(tokens) > 2:
                    network_names.append(tokens[2])
                else:
                    network_names.append('network_%03d' % i)
    else:
        networks = [network_arg.lower()]
        network_names = [network_arg.lower()]
        # choosing the preprocessing function
        if preprocessing is None:
            preprocessing = network_arg.lower()
        preprocessings = [preprocessing]

    if not output_file:
        current_time = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d_%H_%M_%S')
        output_dir = experiment_name
        create_dir(output_dir)
        output_file = os.path.join(output_dir, 'results_' + current_time)

    return (networks, network_names, preprocessings, output_file)


def common_arg_parser(description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(dest='dataset', type=str, help='Which dataset to be used')
    parser.add_argument(dest='network_name', type=str, help='Which network to be used')

    parser.add_argument('--experiment_name', type=str, default='Ex', help='The name of the experiment (default: Ex)')

    data_dir_group = parser.add_argument_group('data path')
    data_dir_group.add_argument('--data_dir', type=str, default=None, help='The path to the data directory (default: None)')
    data_dir_group.add_argument('--train_dir', type=str, default=None, help='The path to the train directory (default: None)')
    data_dir_group.add_argument('--validation_dir', type=str, default=None, help='The path to the validation directory (default: None)')

    parser.add_argument('--gpus', nargs='+', type=int, default=[0], help='List of GPUs to be used (default: [0])')
    parser.add_argument('--workers', type=int, default=1, help='Number of workers for image generator (default: 1)')

    parser.add_argument('--batch_size', type=int, default=None, help='Batch size (default: according to dataset)')
    parser.add_argument('--target_size', type=int, default=None, help='Target size (default: according to dataset)')
    parser.add_argument('--preprocessing', type=str, default=None, help='The preprocessing function (default: network preprocessing function)')
    parser.add_argument('--dynamic_gt', nargs='+', type=str, default=None, help='Generating dynamically ground-truth (default: None)')
    parser.add_argument('--top_k', type=int, default=None, help='Accuracy of top K elements (default: None)')
    parser.add_argument('--task_type', type=str, default=None, help='The task to prform by network (default: None)')

    return parser


def activation_arg_parser(argvs):
    # FIXME: update activation pipeline
    parser = common_arg_parser('Analysing activation of prominent nets of Keras.')

    parser.add_argument('--contrasts', nargs='+', type=float, default=[1], help='List of contrasts to be evaluated (default: [1])')

    return check_args(parser, argvs, 'activation')


def test_arg_parser(argvs):
    parser = common_arg_parser('Test prominent nets of Keras for different contrasts.')
    parser.add_argument('--validation_crop_type', type=str, default='centre', choices=['random', 'centre','none'], help='What type of crop (default: centre)')
    parser.add_argument('--mask_radius', type=float, default=None, help='Apply image destortion to this radius from centre (default: None)')
    parser.add_argument('--image_limit', type=int, default=None, help='Number of images to be evaluated (default: None)')
    parser.add_argument('--opponent_space', type=str, default='lab', choices=['lab', 'dkl'], help='The default colour opponent space (default: lab)')
    parser.add_argument('--distance', type=float, default=1, help='Simulating the viewing distance (default: 1)')

    image_degradation_group = parser.add_mutually_exclusive_group()
    image_degradation_group.add_argument('--contrasts', nargs='+', type=float, default=None, help='List of contrasts to be evaluated (default: None)')
    image_degradation_group.add_argument('--gaussian_sigma', nargs='+', type=float, default=None, help='List of Gaussian sigmas to be evaluated (default: None)')
    image_degradation_group.add_argument('--s_p_noise', nargs='+', type=float, default=None, help='List of salt and pepper noise to be evaluated (default: None)')
    image_degradation_group.add_argument('--speckle_noise', nargs='+', type=float, default=None, help='List of speckle noise to be evaluated (default: None)')
    image_degradation_group.add_argument('--gaussian_noise', nargs='+', type=float, default=None, help='List of Gaussian noise to be evaluated (default: None)')
    image_degradation_group.add_argument('--poisson_noise', action='store_true', default=False, help='Poisson noise to be evaluated (default: False)')
    image_degradation_group.add_argument('--gammas', nargs='+', type=float, default=None, help='List of gammas to be evaluated (default: None)')
    image_degradation_group.add_argument('--illuminants', nargs='+', type=float, default=None, help='List of illuminations to be evaluated (default: None)')
    image_degradation_group.add_argument('--occlusion', nargs='+', type=float, default=None, help='List of occlusions to be evaluated (default: None)')
    image_degradation_group.add_argument('--chromaticity', nargs='+', type=float, default=None, help='List of chromaticity to be evaluated (default: None)')
    image_degradation_group.add_argument('--red_green', nargs='+', type=float, default=None, help='List of red-green to be evaluated (default: None)')
    image_degradation_group.add_argument('--yellow_blue', nargs='+', type=float, default=None, help='List of yellow-blue to be evaluated (default: None)')
    image_degradation_group.add_argument('--lightness', nargs='+', type=float, default=None, help='List of lightness to be evaluated (default: None)')
    image_degradation_group.add_argument('--invert_chromaticity', action='store_true', default=False, help='Inverting chromaticity to be evaluated (default: None)')
    image_degradation_group.add_argument('--invert_opponency', action='store_true', default=False, help='Inverting colour opponency to be evaluated (default: None)')
    image_degradation_group.add_argument('--invert_lightness', action='store_true', default=False, help='Inverting lightness to be evaluated (default: None)')
    image_degradation_group.add_argument('--rotate_hue', nargs='+', type=float, default=None, help='Rotating hues to be evaluated (default: None)')
    image_degradation_group.add_argument('--keep_red', nargs='+', type=float, default=None, help='List of keeping red to be evaluated (default: None)')
    image_degradation_group.add_argument('--keep_blue', nargs='+', type=float, default=None, help='List of keeping blue to be evaluated (default: None)')
    image_degradation_group.add_argument('--keep_green', nargs='+', type=float, default=None, help='List of keeping green to be evaluated (default: None)')

    logging_group = parser.add_argument_group('logging')
    logging_group.add_argument('--validation_steps', type=int, default=None, help='Number of steps for validations (default: number of samples divided by the batch size)')

    return check_args(parser, argvs, 'testing')


def train_arg_parser(argvs):
    parser = common_arg_parser('Training prominent nets of Keras.')
    parser.add_argument('--crop_type', type=str, default='random', choices=['random', 'centre', 'none'], help='What type of crop (default: random)')
    parser.add_argument('--validation_crop_type', type=str, default='centre', choices=['random', 'centre','none'], help='What type of crop (default: centre)')
    parser.add_argument('--output_types', type=str, nargs='+', default=[], help='What type of outputs to consider in model (default: None)')

    # better handling the parameters, e.g. pretrained ones are only for imagenet
    architecture_group = parser.add_argument_group('architecture')
    architecture_group.add_argument('--area1layers', type=int, default=None, help='The number of layers in area 1 (default: None)')
    architecture_group.add_argument('--pyramid_conv', type=int, default=1, help='The number of pyramids for convolutions (default: 1)')
    architecture_group.add_argument('--num_kernels', type=int, default=16, help='The number of convolutional kernels (default: 16)')

    trainable_group = architecture_group.add_argument_group('layers')
    trainable_group = trainable_group.add_mutually_exclusive_group()
    trainable_group.add_argument('--trainable_layers', type=str, default=None, help='Which layerst to train (default: all layers)')
    trainable_group.add_argument('--untrainable_layers', type=str, default=None, help='Which layerst not to train (default: None)')

    initialisation_group = parser.add_argument_group('initialisation')
    weights_group = initialisation_group.add_mutually_exclusive_group()
    weights_group.add_argument('--load_weights', type=str, default=None, help='Whether loading weights from a model (default: None)')
    initialisation_choices = ['dog', 'randdog', 'sog', 'randsog', 'dogsog', 'g1', 'g2', 'gaussian', 'all']
    weights_group.add_argument('--initialise', type=str, default=None, choices=initialisation_choices, help='Whether using a specific initialisation of weights (default: None)')
    initialisation_group.add_argument('--same_channels', action='store_true', default=False, help='Identical initial weights for channels of a kernel (default: False)')
    initialisation_group.add_argument('--tog_sigma', type=float, default=1, help='Sigma of ToG (default: 1)')
    initialisation_group.add_argument('--tog_surround', type=float, default=5, help='Surround enlargement in ToG (default: 5)')
    initialisation_group.add_argument('--g_sigmax', type=float, default=1, help='Sigma-x of Gaussian (default: 1)')
    initialisation_group.add_argument('--g_sigmay', type=float, default=None, help='Sigma-y of Gaussian (default: None)')
    initialisation_group.add_argument('--g_meanx', type=float, default=0, help='Mean-x of Gaussian (default: 0)')
    initialisation_group.add_argument('--g_meany', type=float, default=0, help='Mean-y of Gaussian (default: 0)')
    initialisation_group.add_argument('--g_theta', type=float, default=0, help='Theta of Gaussian (default: 0)')
    initialisation_group.add_argument('--gg_sigma', type=float, default=1, help='Sigma of Gaussian gradient (default: 1)')
    initialisation_group.add_argument('--gg_theta', type=float, default=math.pi/2, help='Theta of Gaussian gradient (default: pi/2)')
    initialisation_group.add_argument('--gg_seta', type=float, default=0.5, help='Seta of Gaussian gradient (default: 0.5)')

    optimisation_group = parser.add_argument_group('optimisation')
    optimisation_group.add_argument('--optimiser', type=str, default='adam', help='The optimiser to be used (default: adam)')
    optimisation_group.add_argument('--lr', type=float, default=None, help='The learning rate parameter (default: None)')
    optimisation_group.add_argument('--decay', type=float, default=None, help='The decay weight parameter (default: None)')
    optimisation_group.add_argument('--exp_decay', type=float, default=None, help='The exponential decay (default: None)')
    optimisation_group.add_argument('--lr_schedule', type=str, default=None, help='The custom learning rate scheduler (default: None)')
    optimisation_group.add_argument('--epochs', type=int, default=50, help='Number of epochs (default: 50)')
    optimisation_group.add_argument('--initial_epoch', type=int, default=0, help='The initial epoch number (default: 0)')

    plateau_group = parser.add_argument_group('plateau')
    plateau_group.add_argument('--plateau_monitor', type=str, default='val_loss', help='The monitor metric (default: val_loss)')
    plateau_group.add_argument('--plateau_factor', type=float, default=0.1, help='The reduction factor (default: 0.1)')
    plateau_group.add_argument('--plateau_patience', type=float, default=5, help='The patience (default: 5)')
    plateau_group.add_argument('--plateau_min_delta', type=float, default=0.001, help='The min_delta (default: 0.001)')
    plateau_group.add_argument('--plateau_min_lr', type=float, default=0.5e-6, help='The min_lr (default: 0.5e-6)')

    logging_group = parser.add_argument_group('logging')
    logging_group.add_argument('--log_period', type=int, default=0, help='The period of logging the epochs weights (default: 0)')
    logging_group.add_argument('--steps_per_epoch', type=int, default=None, help='Number of steps per epochs (default: number of samples divided by the batch size)')
    logging_group.add_argument('--validation_steps', type=int, default=None, help='Number of steps for validations (default: number of samples divided by the batch size)')

    keras_augmentation_group = parser.add_argument_group('keras augmentation')
    keras_augmentation_group.add_argument('--noshuffle', dest='shuffle', action='store_false', default=True, help='Stop shuffling data (default: False)')
    keras_augmentation_group.add_argument('--horizontal_flip', action='store_true', default=False, help='Perform horizontal flip data (default: False)')
    keras_augmentation_group.add_argument('--vertical_flip', action='store_true', default=False, help='Perform vertical flip (default: False)')
    keras_augmentation_group.add_argument('--zoom_range', type=float, default=0, help='Range of zoom agumentation (default: 0)')
    keras_augmentation_group.add_argument('--width_shift_range', type=float, default=0, help='Range of width shift (default: 0)')
    keras_augmentation_group.add_argument('--height_shift_range', type=float, default=0, help='Range of height shift (default: 0)')

    our_augmentation_group = parser.add_argument_group('our augmentation')
    our_augmentation_group.add_argument('--num_augmentation', type=int, default=None, help='Number of types at each instance (default: None)')
    our_augmentation_group.add_argument('--contrast_range', nargs='+', type=float, default=None, help='Contrast lower limit (default: None)')
    our_augmentation_group.add_argument('--local_contrast_variation', type=float, default=0, help='Contrast local variation (default: 0)')
    our_augmentation_group.add_argument('--illuminant_range', nargs='+', type=float, default=None, help='Lower illuminant limit (default: None)')
    our_augmentation_group.add_argument('--local_illuminant_variation', type=float, default=0, help='Illuminant local variation (default: 0)')
    our_augmentation_group.add_argument('--gaussian_sigma', nargs='+', type=float, default=None, help='Gaussian blurring upper limit (default: None)')
    our_augmentation_group.add_argument('--s_p_amount', nargs='+', type=float, default=None, help='Salt&pepper upper limit (default: None)')
    our_augmentation_group.add_argument('--gaussian_amount', nargs='+', type=float, default=None, help='Gaussian noise upper limit (default: None)')
    our_augmentation_group.add_argument('--speckle_amount', nargs='+', type=float, default=None, help='Speckle noise upper limit (default: None)')
    our_augmentation_group.add_argument('--gamma_range', nargs='+', type=float, default=None, help='Gamma lower and upper limits (default: None)')
    our_augmentation_group.add_argument('--poisson_noise', action='store_true', default=False, help='Poisson noise (default: False)')
    our_augmentation_group.add_argument('--mask_radius', nargs='+', type=float, default=None, help='Augmentation within this radius (default: None)')
    our_augmentation_group.add_argument('--chromatic_contrast', nargs='+', type=float, default=None, help='Chromatic contrast lower limit (default: None)')
    our_augmentation_group.add_argument('--luminance_contrast', nargs='+', type=float, default=None, help='Luminance contrast lower limit (default: None)')
    our_augmentation_group.add_argument('--red_green', nargs='+', type=float, default=None, help='List of red-green to be evaluated (default: None)')
    our_augmentation_group.add_argument('--yellow_blue', nargs='+', type=float, default=None, help='List of yellow-blue to be evaluated (default: None)')

    return check_training_args(parser, argvs)


def check_args(parser, argvs, script_type):
    # NOTE: this is just in order to get rid of EXIF warnigns
    warnings.filterwarnings("ignore", "(Possibly )?corrupt EXIF data", UserWarning)

    args = parser.parse_args(argvs)
    args.script_type = script_type

    # setting task type
    args.task_type = check_task_type(args.dataset, args.task_type)

    # setting the target size
    if args.target_size is None:
        args.target_size = get_default_target_size(args.dataset)
    else:
        args.target_size = (args.target_size, args.target_size)
    # check the input shape
    args.input_shape = get_input_shape(args.target_size)

    # setting the default top_k
    if args.top_k is None:
        if args.dataset == 'imagenet':
            args.top_k = 5

    # setting the batch size
    if args.batch_size is None:
        if args.dataset == 'imagenet':
            if args.script_type == 'training':
                args.batch_size = 32
            if args.script_type == 'testing':
                args.batch_size = 64
            if args.script_type == 'activation':
                args.batch_size = 32
        elif 'cifar' in args.dataset or 'stl' in args.dataset:
            if args.script_type == 'training':
                args.batch_size = 256
            if args.script_type == 'testing':
                args.batch_size = 512
            if args.script_type == 'activation':
                args.batch_size = 256
        else:
            sys.exit('batch_size is required for dataset %s' % (args.dataset))

    # TODO: more checking for GPUs
    os.environ["CUDA_VISIBLE_DEVICES"] = ', '.join(str(e) for e in args.gpus)

    # workers
    if args.workers > 1:
        args.use_multiprocessing = True
    else:
        args.use_multiprocessing = False

    # handling the paths
    (args.train_dir, args.validation_dir, args.data_dir) = default_configs.get_default_dataset_paths(args.dataset, args.train_dir, args.validation_dir, args.data_dir)

    return args


def check_training_args(parser, argvs):
    args = check_args(parser, argvs, 'training')

    # checking augmentation parameters
    if args.num_augmentation is not None:
        # TODO make them one variable with name and make sure they're two elements
        augmentation_types = []
        if args.illuminant_range is not None:
            args.illuminant_range = np.array(args.illuminant_range)
            augmentation_types.append('illuminant')
        if args.contrast_range is not None:
            args.contrast_range = np.array(args.contrast_range)
            augmentation_types.append('contrast')
        if args.gaussian_sigma is not None:
            args.gaussian_sigma = np.array(args.gaussian_sigma)
            augmentation_types.append('blur')
        if args.s_p_amount is not None:
            args.s_p_amount = np.array(args.s_p_amount)
            augmentation_types.append('s_p')
        if args.gaussian_amount is not None:
            args.gaussian_amount = np.array(args.gaussian_amount)
            augmentation_types.append('gaussian')
        if args.speckle_amount is not None:
            args.speckle_amount = np.array(args.speckle_amount)
            augmentation_types.append('speckle')
        if args.gamma_range is not None:
            args.gamma_range = np.array(args.gamma_range)
            augmentation_types.append('gamma')
        if args.poisson_noise is True:
            augmentation_types.append('poisson')
        if args.chromatic_contrast is not None:
            args.chromatic_contrast = np.array(args.chromatic_contrast)
            augmentation_types.append('chromatic_contrast')
        if args.luminance_contrast is not None:
            args.luminance_contrast = np.array(args.luminance_contrast)
            augmentation_types.append('luminance_contrast')
        if args.yellow_blue is not None:
            args.yellow_blue = np.array(args.yellow_blue)
            augmentation_types.append('yellow_blue')
        if args.red_green is not None:
            args.red_green = np.array(args.red_green)
            augmentation_types.append('red_green')

        # there should be at least one sort of augmentation in this case
        if not augmentation_types:
            sys.exit('When num_augmentation flag is used, at least one sort of augmentation should be specified')
        else:
            args.augmentation_types = np.array(augmentation_types)

    return args


def check_task_type(dataset, task_type=None):
    if 'imagenet' in dataset or 'cifar' in dataset or 'stl' in dataset:
        if task_type is not None and task_type != 'classification':
            warnings.warn('Invalid task_type %s: %s only supports classification' % (task_type, dataset))
        task_type = 'classification'
    elif 'coco' in dataset:
        # TODO: add other tasks as well
        task_type = 'detection'
    return task_type