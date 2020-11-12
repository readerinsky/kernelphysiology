import numpy as np
import os
import sys
import random

import torch
from torchvision import transforms

from skimage import color
from skimage import metrics
import cv2
from kernelphysiology.dl.pytorch.datasets import data_loaders

from kernelphysiology.dl.pytorch.vaes import model as vqmodel
from kernelphysiology.dl.pytorch.utils.preprocessing import inv_normalise_tensor
from kernelphysiology.transformations import colour_spaces

from kernelphysiology.dl.pytorch.utils import cv2_transforms
from kernelphysiology.dl.pytorch.utils import cv2_preprocessing
from kernelphysiology.transformations import normalisations
from kernelphysiology.dl.pytorch.vaes import vanilla_vae
from kernelphysiology.utils import imutils
import argparse


def parse_arguments(args):
    parser = argparse.ArgumentParser(description='Variational AutoEncoders')
    parser.add_argument('--model_path')
    parser.add_argument(
        '--model', default='vqvae',
        help='autoencoder variant to use: vae | vqvae'
    )
    parser.add_argument(
        '--batch_size', type=int, default=128, metavar='N',
        help='input batch size for training (default: 128)'
    )
    parser.add_argument('--k', type=int, dest='k', metavar='K',
                        help='number of atoms in dictionary')
    parser.add_argument('--kl', type=int, dest='kl',
                        help='number of atoms in dictionary')
    parser.add_argument('--cos_dis', action='store_true',
                        default=False, help='cosine distance')
    parser.add_argument('--exclude', type=int, default=0, metavar='K',
                        help='number of atoms in dictionary')
    parser.add_argument('--colour_space', type=str, default=None,
                        help='The type of output colour space.')
    parser.add_argument('--target_size', type=int, default=224,
                        dest='target_size', help='target_size of image')
    parser.add_argument(
        '--de',
        action='store_true',
        default=False,
        help='Compute DeltaE (default: False)'
    )

    parser.add_argument(
        '--dataset', default=None,
        help='dataset to use: mnist | cifar10 | imagenet | coco | custom'
    )
    parser.add_argument(
        '--category',
        type=str,
        default=None,
        help='The specific category (default: None)'
    )
    parser.add_argument(
        '--validation_dir',
        type=str,
        default=None,
        help='The path to the validation directory (default: None)'
    )
    parser.add_argument(
        '--out_dir',
        type=str,
        default=None,
        help='The path to the validation directory (default: None)'
    )
    parser.add_argument('--random_seed', default=0, type=int)
    parser.add_argument('--noise', type=str, default=None)

    return parser.parse_args(args)


def main(args):
    args = parse_arguments(args)

    if args.random_seed < 0:
        os.environ['PYTHONHASHSEED'] = str(args.random_seed)
        torch.manual_seed(args.random_seed)
        torch.cuda.manual_seed_all(args.random_seed)
        torch.cuda.manual_seed(args.random_seed)
        np.random.seed(args.random_seed)
        random.seed(args.random_seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False

    weights_net = torch.load(args.model_path, map_location='cpu')
    if args.model == 'vae':
        network = vanilla_vae.VanillaVAE(latent_dim=args.k, in_channels=3)
    else:
        network = vqmodel.VQ_CVAE(128, k=args.k, kl=args.kl, in_chns=3,
                                  cos_distance=args.cos_dis)
    network.load_state_dict(weights_net)
    if args.exclude > 0:
        which_vec = [args.exclude - 1]
        print(which_vec)
        network.state_dict()['emb.weight'][:, which_vec] = 0
    elif args.exclude < 0:
        which_vec = [*range(8)]
        which_vec.remove(abs(args.exclude) - 1)
        print(which_vec)
        network.state_dict()['emb.weight'][:, which_vec] = 0
    network.cuda()
    network.eval()

    if not os.path.exists(args.out_dir):
        os.mkdir(args.out_dir)

    args.in_colour_space = args.colour_space[:3]
    args.out_colour_space = args.colour_space[4:]

    mean = (0.5, 0.5, 0.5)
    std = (0.5, 0.5, 0.5)
    transform_funcs = transforms.Compose([
        cv2_transforms.Resize(args.target_size + 32),
        cv2_transforms.CenterCrop(args.target_size),
        cv2_transforms.ToTensor(),
        cv2_transforms.Normalize(mean, std)
    ])

    intransform_funs = []
    if args.noise is not None:
        if args.noise == 'sp':
            noise_fun = imutils.s_p_noise
            kwargs = {'amount': 0.01, 'seed': args.random_seed}
        elif args.noise == 'gaussian':
            noise_fun = imutils.gaussian_noise
            kwargs = {'amount': 0.01, 'seed': args.random_seed}
        elif args.noise == 'speckle':
            noise_fun = imutils.speckle_noise
            kwargs = {'amount': 0.01, 'seed': args.random_seed}
        intransform_funs.append(
            cv2_preprocessing.UniqueTransformation(
                noise_fun, **kwargs
            )
        )
    if args.in_colour_space != ' rgb':
        intransform_funs.append(
            cv2_preprocessing.ColourSpaceTransformation(args.in_colour_space)
        )
    intransform = transforms.Compose(intransform_funs)

    if args.dataset == 'imagenet':
        test_loader = torch.utils.data.DataLoader(
            data_loaders.ImageFolder(
                root=args.validation_dir,
                intransform=intransform,
                outtransform=None,
                transform=transform_funcs
            ),
            batch_size=args.batch_size, shuffle=False
        )
    elif args.dataset == 'celeba':
        test_loader = torch.utils.data.DataLoader(
            data_loaders.CelebA(
                root=args.validation_dir,
                intransform=intransform,
                outtransform=None,
                transform=transform_funcs,
                split='test'
            ),
            batch_size=args.batch_size, shuffle=False
        )
    else:
        test_loader = torch.utils.data.DataLoader(
            data_loaders.CategoryImages(
                root=args.validation_dir,
                # FIXME
                category=args.category,
                intransform=intransform,
                outtransform=None,
                transform=transform_funcs
            ),
            batch_size=args.batch_size, shuffle=False
        )
    export(test_loader, network, mean, std, args)


def export(data_loader, model, mean, std, args):
    all_des = []
    all_ssim = []
    all_psnr = []
    with torch.no_grad():
        for i, (img_readies, img_target, img_paths) in enumerate(data_loader):
            img_readies = img_readies.cuda()
            out_rgb = model(img_readies)
            out_rgb = out_rgb[0].detach().cpu()
            img_readies = img_readies.detach().cpu()

            for img_ind in range(out_rgb.shape[0]):
                img_path = img_paths[img_ind]
                print(img_path)
                img_ready = img_readies[img_ind].unsqueeze(0)

                org_img_tmp = inv_normalise_tensor(img_ready, mean, std)
                org_img_tmp = org_img_tmp.numpy().squeeze().transpose(1, 2, 0)
                # org_img.append(org_img_tmp)

                if args.in_colour_space == 'lab':
                    org_img_tmp = np.uint8(org_img_tmp * 255)
                    org_img_tmp = cv2.cvtColor(org_img_tmp, cv2.COLOR_LAB2RGB)
                elif args.in_colour_space == 'hsv':
                    org_img_tmp = colour_spaces.hsv012rgb(org_img_tmp)
                elif args.in_colour_space == 'lms':
                    org_img_tmp = colour_spaces.lms012rgb(org_img_tmp)
                elif args.in_colour_space == 'yog':
                    org_img_tmp = colour_spaces.yog012rgb(org_img_tmp)
                elif args.in_colour_space == 'dkl':
                    org_img_tmp = colour_spaces.dkl012rgb(org_img_tmp)
                else:
                    org_img_tmp = normalisations.uint8im(org_img_tmp)

                # if os.path.exists(img_path.replace(cat_in_dir, rgb_dir)):
                #     rec_rgb_tmp = cv2.imread(
                #         img_path.replace(cat_in_dir, rgb_dir))
                #     rec_rgb_tmp = cv2.cvtColor(rec_rgb_tmp, cv2.COLOR_BGR2RGB)
                # else:
                rec_img_tmp = inv_normalise_tensor(
                    out_rgb[img_ind].unsqueeze(0), mean, std)
                rec_img_tmp = rec_img_tmp.numpy().squeeze().transpose(1, 2, 0)
                rec_img_tmp = cv2.resize(
                    rec_img_tmp, (org_img_tmp.shape[1], org_img_tmp.shape[0])
                )
                if args.out_colour_space == 'lab':
                    rec_img_tmp = np.uint8(rec_img_tmp * 255)
                    rec_img_tmp = cv2.cvtColor(rec_img_tmp, cv2.COLOR_LAB2RGB)
                elif args.out_colour_space == 'hsv':
                    rec_img_tmp = colour_spaces.hsv012rgb(rec_img_tmp)
                elif args.out_colour_space == 'lms':
                    rec_img_tmp = colour_spaces.lms012rgb(rec_img_tmp)
                elif args.out_colour_space == 'yog':
                    rec_img_tmp = colour_spaces.yog012rgb(rec_img_tmp)
                elif args.out_colour_space == 'dkl':
                    rec_img_tmp = colour_spaces.dkl012rgb(rec_img_tmp)
                else:
                    rec_img_tmp = normalisations.uint8im(rec_img_tmp)

                ssim = metrics.structural_similarity(org_img_tmp, rec_img_tmp,
                                                     multichannel=True)
                all_ssim.append(ssim)
                psnr = metrics.peak_signal_noise_ratio(org_img_tmp, rec_img_tmp)
                all_psnr.append(psnr)

                if args.de:
                    img_org = color.rgb2lab(org_img_tmp)
                    img_res = color.rgb2lab(rec_img_tmp)
                    de = color.deltaE_ciede2000(img_org, img_res)
                    all_des.append([np.mean(de), np.median(de), np.max(de)])

            np.savetxt(args.out_dir + '/ssim_' + args.colour_space + '.txt',
                       np.array(all_ssim))
            np.savetxt(args.out_dir + '/psnr_' + args.colour_space + '.txt',
                       np.array(all_psnr))
            if args.de:
                np.savetxt(args.out_dir + '/de_' + args.colour_space + '.txt',
                           np.array(all_des))


if __name__ == "__main__":
    main(sys.argv[1:])
