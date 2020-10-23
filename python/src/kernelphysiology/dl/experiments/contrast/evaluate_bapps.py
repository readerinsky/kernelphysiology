import numpy as np
import argparse
import sys
from skimage import io

import torch
import torchvision.transforms as torch_transforms

from kernelphysiology.dl.pytorch.models import model_utils
from kernelphysiology.dl.pytorch.utils.preprocessing import inv_normalise_tensor

from kernelphysiology.dl.experiments.contrast import pretrained_models
from kernelphysiology.utils import path_utils
from kernelphysiology.dl.pytorch.datasets import bapps
from kernelphysiology.dl.pytorch.utils import cv2_transforms

DISTORTIONS = [
    'cnn', 'color', 'deblur', 'frameinterp', 'superres', 'traditional'
]


def parse_arguments(args):
    parser = argparse.ArgumentParser(description='Variational AutoEncoders')
    model_parser = parser.add_argument_group('Model Parameters')
    model_parser.add_argument('--model_name', type=str)
    model_parser.add_argument('--model_path', type=str, default=None)
    model_parser.add_argument('--activation_layer', type=str)
    model_parser.add_argument('--db_dir', type=str)
    model_parser.add_argument('--split', type=str, default='val')
    model_parser.add_argument('--task', type=str, choices=['2afc', 'jnd'])
    model_parser.add_argument(
        '--distortion', type=str, default=None, choices=DISTORTIONS
    )
    model_parser.add_argument('--out_file', type=str)
    model_parser.add_argument('--target_size', type=int)
    model_parser.add_argument('--colour_space', type=str, default='rgb')
    model_parser.add_argument('--batch_size', type=int, default=16)
    model_parser.add_argument('-j', '--workers', type=int, default=4)
    model_parser.add_argument('--print', action='store_true', default=False)
    model_parser.add_argument('--vision_type', type=str, default='trichromat')
    return parser.parse_args(args)


def run_eval(db_loader, model, print_val):
    with torch.no_grad():
        all_results = []
        num_batches = db_loader.__len__()
        for i, (img_ref, img_p0, img_p1, gt) in enumerate(db_loader):
            img_ref = img_ref.cuda()
            img_p0 = img_p0.cuda()
            img_p1 = img_p1.cuda()
            gt = gt.squeeze().cuda()

            out_ref = model(img_ref)
            out_p0 = model(img_p0)
            out_p1 = model(img_p1)

            # compute the difference
            d0s = out_ref - out_p0
            d1s = out_ref - out_p1
            # collapse the differences
            d0s = d0s.mean(dim=(3, 2, 1))
            d1s = d1s.mean(dim=(3, 2, 1))

            d0_smaller = (d0s < d1s) * (1.0 - gt)
            d1_smaller = (d1s < d0s) * gt
            scores = d0_smaller + d1_smaller + (d1s == d0s) * 0.5
            all_results.extend(scores.detach().cpu().numpy())

            num_tests = num_batches * img_ref.shape[0]
            test_num = i * img_ref.shape[0]
            percent = float(test_num) / float(num_tests)
            if print_val is not None:
                print(
                    '%s %.2f [%d/%d]' % (
                        print_val, percent, test_num, num_tests
                    )
                )
    return all_results


def save_results(eval_results, out_file):
    save_path = out_file + '.pickle'
    path_utils.write_pickle(save_path, eval_results)
    return


def main(args):
    args = parse_arguments(args)
    if args.model_path is None:
        args.model_path = args.model_name
    colour_space = args.colour_space
    target_size = args.target_size

    # loading the model
    is_segmentation = False
    if 'deeplabv3_resnet' in args.model_name or 'fcn_resnet' in args.model_name:
        is_segmentation = True
    transfer_weights = [args.model_path, None, is_segmentation]
    model = pretrained_models.get_pretrained_model(
        args.model_name, transfer_weights
    )

    # selecting the layer
    model = pretrained_models.LayerActivation(
        pretrained_models.get_backbones(args.model_name, model),
        args.activation_layer
    )
    model = model.eval()
    model.cuda()

    mean, std = model_utils.get_preprocessing_function(
        colour_space, 'trichromat'
    )
    transform = torch_transforms.Compose([
        cv2_transforms.ToTensor(),
        cv2_transforms.Normalize(mean, std),
    ])

    distortions = DISTORTIONS if args.distortion is None else [args.distortion]

    eval_results = dict()
    for dist in distortions:
        print('Starting with %s' % dist)
        db = bapps.BAPPS2afc(
            root=args.db_dir, split=args.split, distortion=dist,
            transform=transform
        )
        db_loader = torch.utils.data.DataLoader(
            db, batch_size=args.batch_size, shuffle=False,
            num_workers=args.workers, pin_memory=True
        )
        print_val = dist if args.print else None
        eval_results[dist] = run_eval(db_loader, model, print_val)
    save_results(eval_results, args.out_file)


if __name__ == "__main__":
    main(sys.argv[1:])
