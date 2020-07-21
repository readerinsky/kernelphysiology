import numpy as np
import shutil
import os
import logging.config
from datetime import datetime
import json

from skimage import io

import torch
from torchvision.utils import save_image, make_grid
from torch.nn import functional as F

from kernelphysiology.dl.pytorch.utils.preprocessing import inv_normalise_tensor
from kernelphysiology.transformations import labels


def setup_logging_from_args(args):
    """
    Calls setup_logging, exports args and creates a ResultsLog class.
    Can resume training/logging if args.resume is set
    """

    def set_args_default(field_name, value):
        if hasattr(args, field_name):
            return eval('args.' + field_name)
        else:
            return value

    # Set default args in case they don't exist in args
    resume = set_args_default('resume', False)
    save_name = set_args_default('save_name', '')
    results_dir = set_args_default('results_dir', './results')

    if save_name is '':
        save_name = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    save_path = os.path.join(results_dir, save_name)
    if os.path.exists(save_path):
        shutil.rmtree(save_path)
    os.makedirs(save_path, exist_ok=True)
    log_file = os.path.join(save_path, 'log.txt')

    setup_logging(log_file, resume)
    export_args(args, save_path)
    return save_path


def setup_logging(log_file='log.txt', resume=False):
    """
    Setup logging configuration
    """
    if os.path.isfile(log_file) and resume:
        file_mode = 'a'
    else:
        file_mode = 'w'

    root_logger = logging.getLogger()
    if root_logger.handlers:
        root_logger.removeHandler(root_logger.handlers[0])
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s - %(levelname)s - %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S",
                        filename=log_file,
                        filemode=file_mode)
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter('%(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)


def export_args(args, save_path):
    """
    args: argparse.Namespace
        arguments to save
    save_path: string
        path to directory to save at
    """
    os.makedirs(save_path, exist_ok=True)
    json_file_name = os.path.join(save_path, 'args.json')
    with open(json_file_name, 'w') as fp:
        json.dump(dict(args._get_kwargs()), fp, sort_keys=True, indent=4)


def save_checkpoint(model, save_path):
    epoch = model['epoch']
    os.makedirs(os.path.join(save_path, 'checkpoints'), exist_ok=True)
    weights_path = os.path.join(save_path, 'checkpoints', f'model_{epoch}.pth')
    torch.save(model['state_dict'], weights_path)
    resume_path = os.path.join(save_path, 'checkpoints', 'last_epoch.pth')
    torch.save(model, resume_path)


def tensor_tosave(tensor, inv_func=None):
    imgs = []
    for i in range(tensor.shape[0]):
        img = tensor[i].cpu().numpy().transpose((1, 2, 0))
        if inv_func is not None:
            img = inv_func(img)
        else:
            img *= 255
            img = img.astype('uint8').squeeze()
        imgs.append(img)
    return imgs


def grid_save_reconstructions(out_dicts, ground_truths, model_outs, mean,
                              std, epoch, save_path, name):
    for key in out_dicts.keys():
        current_out = model_outs[key]
        current_gt = ground_truths[key]

        original = inv_normalise_tensor(current_gt, mean, std).detach()
        original = tensor_tosave(original, out_dicts[key]['vis_fun'])
        reconstructed = inv_normalise_tensor(current_out, mean, std).detach()
        reconstructed = tensor_tosave(reconstructed, out_dicts[key]['vis_fun'])

        original = np.concatenate(original, axis=1)
        reconstructed = np.concatenate(reconstructed, axis=1)
        both_together = np.concatenate([original, reconstructed], axis=0)
        io.imsave(
            '%s/%s_%.3d_%s.png' % (save_path, name, epoch, key),
            both_together
        )


def wavelet_visualise(tensor):
    rows = tensor.shape[0]
    cols = tensor.shape[1]
    img = np.zeros((rows * 2, cols * 2))
    img[:rows, :cols] = tensor[:, :, 0]
    img[rows:, :cols] = tensor[:, :, 1]
    img[:rows, cols:] = tensor[:, :, 2]
    img[rows:, cols:] = tensor[:, :, 3]
    img *= 255
    img = img.astype('uint8').squeeze()
    return img