import os
import sys
import time
import argparse
import logging

import torch.utils.data
from torch import optim
import torch.backends.cudnn as cudnn
from torch.utils.tensorboard import SummaryWriter
from torchvision import datasets, transforms
from torchvision.utils import save_image, make_grid

from kernelphysiology.dl.experiments.intrasimilarity.util import \
    setup_logging_from_args
from kernelphysiology.dl.experiments.intrasimilarity.model import *
from kernelphysiology.dl.pytorch.models import model_utils
from kernelphysiology.dl.pytorch.utils import misc
from kernelphysiology.dl.pytorch.utils.preprocessing import inv_normalise_tensor

models = {
    'custom': {'vqvae': VQ_CVAE, 'vqvae2': VQ_CVAE},
    'imagenet': {'vqvae': VQ_CVAE, 'vqvae2': VQ_CVAE},
    'cifar10': {'vae': CVAE, 'vqvae': VQ_CVAE, 'vqvae2': VQ_CVAE},
    'mnist': {'vae': VAE, 'vqvae': VQ_CVAE},
}
datasets_classes = {
    'custom': datasets.ImageFolder,
    'imagenet': datasets.ImageFolder,
    'cifar10': datasets.CIFAR10,
    'mnist': datasets.MNIST
}
dataset_train_args = {
    'custom': {},
    'imagenet': {},
    'cifar10': {'train': True, 'download': True},
    'mnist': {'train': True, 'download': True},
}
dataset_test_args = {
    'custom': {},
    'imagenet': {},
    'cifar10': {'train': False, 'download': True},
    'mnist': {'train': False, 'download': True},
}
dataset_n_channels = {
    'custom': 3,
    'imagenet': 3,
    'cifar10': 3,
    'mnist': 1,
}

dataset_transforms = {
    'custom': transforms.Compose(
        [transforms.Resize(256), transforms.CenterCrop(224),
         transforms.ToTensor(),
         transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))]),
    'imagenet': transforms.Compose(
        [transforms.Resize(256), transforms.CenterCrop(224),
         transforms.ToTensor(),
         # transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
         transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225))
         ]),
    'cifar10': transforms.Compose([transforms.ToTensor(),
                                   transforms.Normalize((0.5, 0.5, 0.5),
                                                        (0.5, 0.5, 0.5))]),
    'mnist': transforms.ToTensor()
}
default_hyperparams = {
    'custom': {'lr': 2e-4, 'k': 512, 'hidden': 128},
    'imagenet': {'lr': 2e-4, 'k': 512, 'hidden': 128},
    'cifar10': {'lr': 2e-4, 'k': 10, 'hidden': 256},
    'mnist': {'lr': 1e-4, 'k': 10, 'hidden': 64}
}


def main(args):
    parser = argparse.ArgumentParser(description='Variational AutoEncoders')

    parser.add_argument('-pnet', '--pos_net_path', type=str, required=True,
                        help='The path to network to be maximised.')
    parser.add_argument('-nnet', '--neg_net_path', type=str, required=True,
                        help='The path to network to be minimised.')

    model_parser = parser.add_argument_group('Model Parameters')
    model_parser.add_argument('--model', default='vae',
                              choices=['vae', 'vqvae'],
                              help='autoencoder variant to use: vae | vqvae')
    model_parser.add_argument('--batch-size', type=int, default=128,
                              metavar='N',
                              help='input batch size for training (default: 128)')
    model_parser.add_argument('--hidden', type=int, metavar='N',
                              help='number of hidden channels')
    model_parser.add_argument('-k', '--dict-size', type=int, dest='k',
                              metavar='K',
                              help='number of atoms in dictionary')
    model_parser.add_argument('--lr', type=float, default=None,
                              help='learning rate')
    model_parser.add_argument('--vq_coef', type=float, default=None,
                              help='vq coefficient in loss')
    model_parser.add_argument('--commit_coef', type=float, default=None,
                              help='commitment coefficient in loss')
    model_parser.add_argument('--kl_coef', type=float, default=None,
                              help='kl-divergence coefficient in loss')

    training_parser = parser.add_argument_group('Training Parameters')
    training_parser.add_argument('--dataset', default='cifar10',
                                 choices=['mnist', 'cifar10', 'imagenet',
                                          'custom'],
                                 help='dataset to use: mnist | cifar10 | imagenet | custom')
    training_parser.add_argument('--dataset_dir_name', default='',
                                 help='name of the dir containing the dataset if dataset == custom')
    training_parser.add_argument('--data-dir', default='/media/ssd/Datasets',
                                 help='directory containing the dataset')
    training_parser.add_argument('--epochs', type=int, default=20, metavar='N',
                                 help='number of epochs to train (default: 10)')
    training_parser.add_argument('--max-epoch-samples', type=int, default=50000,
                                 help='max num of samples per epoch')
    training_parser.add_argument('--no-cuda', action='store_true',
                                 default=False,
                                 help='enables CUDA training')
    training_parser.add_argument('--seed', type=int, default=1, metavar='S',
                                 help='random seed (default: 1)')
    training_parser.add_argument('--gpus', default='0',
                                 help='gpus used for training - e.g 0,1,3')

    logging_parser = parser.add_argument_group('Logging Parameters')
    logging_parser.add_argument('--log-interval', type=int, default=10,
                                metavar='N',
                                help='how many batches to wait before logging training status')
    logging_parser.add_argument('--results-dir', metavar='RESULTS_DIR',
                                default='./results',
                                help='results dir')
    logging_parser.add_argument('--save-name', default='',
                                help='saved folder')
    logging_parser.add_argument('--data-format', default='json',
                                help='in which format to save the data')
    args = parser.parse_args(args)
    args.cuda = not args.no_cuda and torch.cuda.is_available()
    dataset_dir_name = args.dataset if args.dataset != 'custom' else args.dataset_dir_name

    # other two networks
    (neg_net, _) = model_utils.which_network_classification(
        args.pos_net_path, num_classes=1000
    )
    (pos_net, _) = model_utils.which_network_classification(
        args.neg_net_path, num_classes=1000
    )
    if args.gpu is not None:
        neg_net = neg_net.cuda(args.gpu)
        pos_net = pos_net.cuda(args.gpu)

    for param in pos_net.parameters():
        param.requires_grad = False
    for param in neg_net.parameters():
        param.requires_grad = False

    args.mean = [0.485, 0.456, 0.406]
    args.std = [0.229, 0.224, 0.225]

    args.criterion_pos = nn.CrossEntropyLoss().cuda(args.gpu)
    args.criterion_neg = nn.CrossEntropyLoss().cuda(args.gpu)

    lr = args.lr or default_hyperparams[args.dataset]['lr']
    k = args.k or default_hyperparams[args.dataset]['k']
    hidden = args.hidden or default_hyperparams[args.dataset]['hidden']
    num_channels = dataset_n_channels[args.dataset]

    save_path = setup_logging_from_args(args)
    writer = SummaryWriter(save_path)

    torch.manual_seed(args.seed)
    if args.cuda:
        torch.cuda.manual_seed_all(args.seed)
        args.gpus = [int(i) for i in args.gpus.split(',')]
        torch.cuda.set_device(args.gpus[0])
        cudnn.benchmark = True
        torch.cuda.manual_seed(args.seed)

    model = models[args.dataset][args.model](hidden, k=k,
                                             num_channels=num_channels)
    if args.cuda:
        model.cuda()

    optimizer = optim.Adam(model.parameters(), lr=lr)
    scheduler = optim.lr_scheduler.StepLR(
        optimizer, 10 if args.dataset == 'imagenet' else 30, 0.5
    )

    kwargs = {'num_workers': 8, 'pin_memory': True} if args.cuda else {}
    dataset_train_dir = os.path.join(args.data_dir, dataset_dir_name)
    dataset_test_dir = os.path.join(args.data_dir, dataset_dir_name)
    if args.dataset in ['imagenet', 'custom']:
        dataset_train_dir = os.path.join(args.data_dir, 'train')
        dataset_test_dir = os.path.join(args.data_dir, 'validation')
    train_loader = torch.utils.data.DataLoader(
        datasets_classes[args.dataset](dataset_train_dir,
                                       transform=dataset_transforms[
                                           args.dataset],
                                       **dataset_train_args[args.dataset]),
        batch_size=args.batch_size, shuffle=True, **kwargs)
    test_loader = torch.utils.data.DataLoader(
        datasets_classes[args.dataset](dataset_test_dir,
                                       transform=dataset_transforms[
                                           args.dataset],
                                       **dataset_test_args[args.dataset]),
        batch_size=args.batch_size, shuffle=False, **kwargs)

    for epoch in range(1, args.epochs + 1):
        train_losses = train(
            epoch, model, train_loader, optimizer, args.cuda, args.log_interval,
            save_path, args, writer, pos_net, neg_net
        )
        test_losses = test_net(epoch, model, test_loader, args.cuda, save_path,
                               args, writer, pos_net, neg_net)
        save_checkpoint(model, epoch, save_path)

        for k in train_losses.keys():
            name = k.replace('_train', '')
            train_name = k
            test_name = k.replace('train', 'test')
            writer.add_scalars(
                name, {'train': train_losses[train_name],
                       'test': test_losses[test_name], }
            )
        scheduler.step()


def train(epoch, model, train_loader, optimizer, cuda, log_interval, save_path,
          args, writer, pos_net, neg_net):
    losses_neg = misc.AverageMeter()
    losses_pos = misc.AverageMeter()
    top1_neg = misc.AverageMeter()
    top1_pos = misc.AverageMeter()

    model.train()
    loss_dict = model.latest_losses()
    losses = {k + '_train': 0 for k, v in loss_dict.items()}
    epoch_losses = {k + '_train': 0 for k, v in loss_dict.items()}
    start_time = time.time()
    batch_idx, data = None, None
    for batch_idx, (data, target) in enumerate(train_loader):
        if cuda:
            data = data.cuda()
        optimizer.zero_grad()
        outputs = model(data)

        output_neg = neg_net(outputs)
        loss_neg = args.criterion_neg(output_neg, target)
        acc1_neg, acc5_pos = misc.accuracy(output_neg, target, topk=(1, 5))
        losses_neg.update(loss_neg.item(), data.size(0))
        top1_neg.update(acc1_neg[0], data.size(0))

        output_pos = pos_net(outputs)
        loss_pos = args.criterion_pos(output_pos, target)
        acc1_pos, acc5_pos = misc.accuracy(output_pos, target, topk=(1, 5))
        losses_pos.update(loss_pos.item(), data.size(0))
        top1_pos.update(acc1_pos[0], data.size(0))

        loss = model.loss_function(data, *outputs) + (loss_pos / loss_neg)
        loss.backward()
        optimizer.step()
        latest_losses = model.latest_losses()
        for key in latest_losses:
            losses[key + '_train'] += float(latest_losses[key])
            epoch_losses[key + '_train'] += float(latest_losses[key])

        if batch_idx % log_interval == 0:
            for key in latest_losses:
                losses[key + '_train'] /= log_interval
            loss_string = ' '.join(
                ['{}: {:.6f}'.format(k, v) for k, v in losses.items()])
            logging.info(
                'Train Epoch: {epoch} [{batch:5d}/{total_batch} '
                '({percent:2d}%)]   time: {time:3.2f}   {loss}'
                ' Lp: {loss_pos:.3f} Ap: {acc_pos:.3f}'
                ' Ln: {loss_neg:.3f} An: {acc_neg:.3f}'
                    .format(epoch=epoch, batch=batch_idx * len(data),
                            total_batch=len(train_loader) * len(data),
                            percent=int(100. * batch_idx / len(train_loader)),
                            time=time.time() - start_time, loss=loss_string,
                            loss_pos=losses_pos.avg, acc_pos=top1_pos.avg,
                            loss_neg=losses_neg.avg, acc_neg=top1_neg.avg))
            start_time = time.time()
            for key in latest_losses:
                losses[key + '_train'] = 0
        if batch_idx in [18, 1650, (len(train_loader) - 1)]:
            save_reconstructed_images(data, epoch, outputs[0], save_path,
                                      'reconstruction_train')
            write_images(data, outputs, writer, 'train', args.mean, args.std)

        if args.dataset in ['imagenet', 'custom'] and batch_idx * len(
                data) > args.max_epoch_samples:
            break

    for key in epoch_losses:
        if args.dataset != 'imagenet':
            epoch_losses[key] /= (
                    len(train_loader.dataset) / train_loader.batch_size)
        else:
            epoch_losses[key] /= (
                    len(train_loader.dataset) / train_loader.batch_size)
    loss_string = '\t'.join(
        ['{}: {:.6f}'.format(k, v) for k, v in epoch_losses.items()])
    logging.info('====> Epoch: {} {}'.format(epoch, loss_string))
    # writer.add_histogram('dict frequency', outputs[3], bins=range(args.k + 1))
    # model.print_atom_hist(outputs[3])
    return epoch_losses


def test_net(epoch, model, test_loader, cuda, save_path, args, writer, pos_net,
             neg_net):
    model.eval()
    loss_dict = model.latest_losses()
    losses = {k + '_test': 0 for k, v in loss_dict.items()}
    i, data = None, None
    with torch.no_grad():
        for i, (data, _) in enumerate(test_loader):
            if cuda:
                data = data.cuda()
            outputs = model(data)
            model.loss_function(data, *outputs)
            latest_losses = model.latest_losses()
            for key in latest_losses:
                losses[key + '_test'] += float(latest_losses[key])
            if i == 0:
                write_images(data, outputs, writer, 'test', args.mean, args.std)

                save_reconstructed_images(data, epoch, outputs[0], save_path,
                                          'reconstruction_test')
            if args.dataset == 'imagenet' and i * len(data) > 1000:
                break

    for key in losses:
        if args.dataset not in ['imagenet', 'custom']:
            losses[key] /= (len(test_loader.dataset) / test_loader.batch_size)
        else:
            losses[key] /= (i * len(data))
    loss_string = ' '.join(
        ['{}: {:.6f}'.format(k, v) for k, v in losses.items()])
    logging.info('====> Test set losses: {}'.format(loss_string))
    return losses


def write_images(data, outputs, writer, suffix, mean, std):
    # original = data.mul(0.5).add(0.5)
    original = inv_normalise_tensor(data, mean, std)
    original_grid = make_grid(original[:6])
    writer.add_image(f'original/{suffix}', original_grid)
    # reconstructed = outputs[0].mul(0.5).add(0.5)
    reconstructed = inv_normalise_tensor(outputs[0], mean, std)
    reconstructed_grid = make_grid(reconstructed[:6])
    writer.add_image(f'reconstructed/{suffix}', reconstructed_grid)


def save_reconstructed_images(data, epoch, outputs, save_path, name):
    size = data.size()
    n = min(data.size(0), 8)
    batch_size = data.size(0)
    comparison = torch.cat(
        [data[:n], outputs.view(batch_size, size[1], size[2], size[3])[:n]]
    )
    save_image(
        comparison.cpu(),
        os.path.join(save_path, name + '_' + str(epoch) + '.png'), nrow=n,
        normalize=True
    )


def save_checkpoint(model, epoch, save_path):
    os.makedirs(os.path.join(save_path, 'checkpoints'), exist_ok=True)
    checkpoint_path = os.path.join(save_path, 'checkpoints',
                                   f'model_{epoch}.pth')
    torch.save(model.state_dict(), checkpoint_path)


if __name__ == "__main__":
    main(sys.argv[1:])