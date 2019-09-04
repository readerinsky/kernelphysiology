"""
Pytorch training script for various datasets and image manipulations.
"""

import os
import sys
import random
import time
import warnings
import numpy as np

import torch
import torch.nn as nn
import torch.nn.parallel
import torch.backends.cudnn as cudnn
import torch.distributed as dist
import torch.optim
import torch.multiprocessing as mp
import torch.utils.data
import torch.utils.data.distributed
import torchvision.transforms as transforms
import torchvision.models as models

from kernelphysiology.dl.pytorch import models as custom_models
from kernelphysiology.dl.pytorch.utils import preprocessing
from kernelphysiology.dl.pytorch.utils.misc import AverageMeter
from kernelphysiology.dl.pytorch.utils.misc import accuracy
from kernelphysiology.dl.pytorch.utils.misc import adjust_learning_rate
from kernelphysiology.dl.pytorch.utils.misc import save_checkpoint
from kernelphysiology.dl.pytorch.models.utils import get_preprocessing_function
from kernelphysiology.dl.pytorch.datasets.utils import get_train_dataset
from kernelphysiology.dl.pytorch.datasets.utils import get_validation_dataset
from kernelphysiology.dl.pytorch.datasets.utils import is_dataset_pil_image
from kernelphysiology.dl.utils.default_configs import get_default_target_size
from kernelphysiology.dl.utils import prepare_training
from kernelphysiology.dl.utils import argument_handler
from kernelphysiology.utils.path_utils import create_dir

best_acc1 = 0


def main(argv):
    args = argument_handler.pytorch_train_arg_parser(argv)
    if args.lr is None:
        args.lr = 0.1
    if args.decay is None:
        args.decay = 1e-4
    # FIXME: cant take more than one GPU
    args.gpus = args.gpus[0]

    # TODO: why load weights is False?
    args.out_dir = prepare_training.prepare_output_directories(
        dataset_name=args.dataset, network_name=args.network_name,
        optimiser='sgd', load_weights=False,
        experiment_name=args.experiment_name, framework='pytorch'
    )

    if args.seed is not None:
        random.seed(args.seed)
        torch.manual_seed(args.seed)
        cudnn.deterministic = True
        warnings.warn(
            'You have chosen to seed training. '
            'This will turn on the CUDNN deterministic setting, '
            'which can slow down your training considerably! '
            'You may see unexpected behavior when restarting from checkpoints.'
        )

    if args.gpus is not None:
        warnings.warn(
            'You have chosen a specific GPU. This will completely '
            'disable data parallelism.'
        )

    if args.dist_url == "env://" and args.world_size == -1:
        args.world_size = int(os.environ["WORLD_SIZE"])

    args.distributed = args.world_size > 1 or args.multiprocessing_distributed

    ngpus_per_node = torch.cuda.device_count()
    if args.multiprocessing_distributed:
        # Since we have ngpus_per_node processes per node, the total world_size
        # needs to be adjusted accordingly
        args.world_size = ngpus_per_node * args.world_size
        # Use torch.multiprocessing.spawn to launch distributed processes: the
        # main_worker process function
        mp.spawn(
            main_worker, nprocs=ngpus_per_node, args=(ngpus_per_node, args)
        )
    else:
        # Simply call main_worker function
        main_worker(ngpus_per_node, args)


def main_worker(ngpus_per_node, args):
    global best_acc1

    mean, std = get_preprocessing_function(
        args.colour_space, args.colour_transformation
    )

    if args.gpus is not None:
        print("Use GPU: {} for training".format(args.gpus))

    if args.distributed:
        if args.dist_url == "env://" and args.rank == -1:
            args.rank = int(os.environ["RANK"])
        if args.multiprocessing_distributed:
            # For multiprocessing distributed training, rank needs to be the
            # global rank among all the processes
            args.rank = args.rank * ngpus_per_node + args.gpus
        dist.init_process_group(
            backend=args.dist_backend,
            init_method=args.dist_url,
            world_size=args.world_size,
            rank=args.rank
        )
    # create model
    # TODO: num_classes should be added to saves file, probably?
    if args.custom_arch:
        print('Custom model!')
        model = custom_models.__dict__[args.network_name](
            pooling_type=args.pooling_type,
            in_chns=len(mean),
            num_classes=args.num_classes
        )
    elif args.pretrained:
        print("=> using pre-trained model '{}'".format(args.network_name))
        model = models.__dict__[args.network_name](pretrained=True)
    else:
        print("=> creating model '{}'".format(args.network_name))
        model = models.__dict__[args.network_name]()

    if args.distributed:
        # For multiprocessing distributed, DistributedDataParallel constructor
        # should always set the single device scope, otherwise,
        # DistributedDataParallel will use all available devices.
        if args.gpus is not None:
            torch.cuda.set_device(args.gpus)
            model.cuda(args.gpus)
            # When using a single GPU per process and per
            # DistributedDataParallel, we need to divide the batch size
            # ourselves based on the total number of GPUs we have
            args.batch_size = int(args.batch_size / ngpus_per_node)
            args.workers = int(args.workers / ngpus_per_node)
            model = torch.nn.parallel.DistributedDataParallel(
                model, device_ids=[args.gpus]
            )
        else:
            model.cuda()
            # DistributedDataParallel will divide and allocate batch_size to all
            # available GPUs if device_ids are not set
            model = torch.nn.parallel.DistributedDataParallel(model)
    elif args.gpus is not None:
        torch.cuda.set_device(args.gpus)
        model = model.cuda(args.gpus)
    else:
        # DataParallel will divide and allocate batch_size to all available GPUs
        if (args.network_name.startswith('alexnet') or
                args.network_name.startswith('vgg')):
            model.features = torch.nn.DataParallel(model.features)
            model.cuda()
        else:
            model = torch.nn.DataParallel(model).cuda()

    # define loss function (criterion) and optimizer
    criterion = nn.CrossEntropyLoss().cuda(args.gpus)

    # optimiser
    optimizer = torch.optim.SGD(
        model.parameters(),
        args.lr,
        momentum=args.momentum,
        weight_decay=args.decay
    )

    model_progress = []
    # optionally resume from a checkpoint
    # TODO: it would be best if resume load the architecture from this file
    # TODO: merge with which_architecture
    if args.resume:
        if os.path.isfile(args.resume):
            print("=> loading checkpoint '{}'".format(args.resume))
            checkpoint = torch.load(args.resume, map_location='cpu')
            args.initial_epoch = checkpoint['epoch']
            best_acc1 = checkpoint['best_acc1']
            if args.gpus is not None:
                # best_acc1 may be from a checkpoint from a different GPU
                best_acc1 = best_acc1.to(args.gpus)
            model.load_state_dict(checkpoint['state_dict'])
            optimizer.load_state_dict(checkpoint['optimizer'])
            print(
                "=> loaded checkpoint '{}' (epoch {})".format(
                    args.resume, checkpoint['epoch']
                )
            )
            # FIXME: not the most robust solution
            model_progress_path = args.resume.replace(
                'checkpoint.pth.tar', 'model_progress.csv'
            )
            if os.path.exists(model_progress_path):
                model_progress = np.loadtxt(model_progress_path, delimiter=',')
                model_progress = model_progress.tolist()
        else:
            print("=> no checkpoint found at '{}'".format(args.resume))

    cudnn.benchmark = True

    normalize = transforms.Normalize(mean=mean, std=std)

    colour_transformations = preprocessing.colour_transformation(
        args.colour_transformation, args.colour_space
    )
    chns_transformation = preprocessing.channel_transformation(
        args.colour_transformation, args.colour_space
    )
    other_transformations = []
    if args.num_augmentations != 0:
        augmentations = preprocessing.RandomAugmentationTransformation(
            args.augmentation_settings, args.num_augmentations,
            is_dataset_pil_image(args.dataset)
        )
        other_transformations.append(augmentations)

    target_size = get_default_target_size(args.dataset)

    # loading the training set
    train_dataset = get_train_dataset(
        args.dataset, args.train_dir, colour_transformations,
        other_transformations, chns_transformation, normalize, target_size,
        args.augment_labels
    )

    if args.distributed:
        train_sampler = torch.utils.data.distributed.DistributedSampler(
            train_dataset
        )
    else:
        train_sampler = None

    train_loader = torch.utils.data.DataLoader(
        train_dataset,
        batch_size=args.batch_size, shuffle=(train_sampler is None),
        num_workers=args.workers, pin_memory=True,
        sampler=train_sampler
    )

    # loading validation set
    validation_dataset = get_validation_dataset(
        args.dataset, args.validation_dir, colour_transformations, [],
        chns_transformation, normalize, target_size,
    )

    val_loader = torch.utils.data.DataLoader(
        validation_dataset,
        batch_size=args.batch_size, shuffle=False,
        num_workers=args.workers, pin_memory=True
    )

    # preparing the output folder
    create_dir(args.out_dir)
    file_path = os.path.join(args.out_dir, 'model_progress.csv')

    # training on epoch
    for epoch in range(args.initial_epoch, args.epochs):
        if args.distributed:
            train_sampler.set_epoch(epoch)
        adjust_learning_rate(optimizer, epoch, args)

        # if doing label augmentation, shuffle the labels
        if args.augment_labels:
            train_loader.dataset.shuffle_augmented_labels()

        # train for one epoch
        train_log = train(
            train_loader, model, criterion, optimizer, epoch, args
        )

        # evaluate on validation set
        validation_log = validate(
            val_loader, model, criterion, args
        )

        model_progress.append([*train_log, *validation_log])

        # remember best acc@1 and save checkpoint
        acc1 = validation_log[2]
        is_best = acc1 > best_acc1
        best_acc1 = max(acc1, best_acc1)

        if not args.multiprocessing_distributed or (
                args.multiprocessing_distributed
                and args.rank % ngpus_per_node == 0):
            save_checkpoint(
                {
                    'epoch': epoch + 1,
                    'arch': args.network_name,
                    'customs': {'pooling_type': args.pooling_type,
                                'in_chns': len(mean)},
                    'state_dict': model.state_dict(),
                    'best_acc1': best_acc1,
                    'optimizer': optimizer.state_dict(),
                    'target_size': target_size,
                },
                is_best, out_folder=args.out_dir
            )
        np.savetxt(file_path, np.array(model_progress), delimiter=',')


def train(train_loader, model, criterion, optimizer, epoch, args):
    batch_time = AverageMeter()
    data_time = AverageMeter()
    losses = AverageMeter()
    top1 = AverageMeter()
    top5 = AverageMeter()

    if args.top_k is None:
        topks = (1,)
    else:
        topks = (1, args.top_k)

    # switch to train mode
    model.train()

    end = time.time()
    for i, (input_image, target) in enumerate(train_loader):
        # measure data loading time
        data_time.update(time.time() - end)

        if args.gpus is not None:
            input_image = input_image.cuda(args.gpus, non_blocking=True)
        target = target.cuda(args.gpus, non_blocking=True)

        # compute output
        output = model(input_image)
        loss = criterion(output, target)

        # measure accuracy and record loss
        acc1, acc5 = accuracy(output, target, topk=topks)
        losses.update(loss.item(), input_image.size(0))
        top1.update(acc1[0], input_image.size(0))
        top5.update(acc5[0], input_image.size(0))

        # compute gradient and do SGD step
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        # measure elapsed time
        batch_time.update(time.time() - end)
        end = time.time()

        # printing the accuracy at certain intervals
        if i % args.print_freq == 0:
            print(
                'Epoch: [{0}][{1}/{2}]\t'
                'Time {batch_time.val:.3f} ({batch_time.avg:.3f})\t'
                'Data {data_time.val:.3f} ({data_time.avg:.3f})\t'
                'Loss {loss.val:.4f} ({loss.avg:.4f})\t'
                'Acc@1 {top1.val:.3f} ({top1.avg:.3f})\t'
                'Acc@5 {top5.val:.3f} ({top5.avg:.3f})'.format(
                    epoch, i, len(train_loader), batch_time=batch_time,
                    data_time=data_time, loss=losses, top1=top1, top5=top5
                )
            )
    return [epoch, batch_time.avg, losses.avg, top1.avg, top5.avg]


def validate(val_loader, model, criterion, args):
    batch_time = AverageMeter()
    losses = AverageMeter()
    top1 = AverageMeter()
    top5 = AverageMeter()

    if args.top_k is None:
        topks = (1,)
    else:
        topks = (1, args.top_k)

    # switch to evaluate mode
    model.eval()

    with torch.no_grad():
        end = time.time()
        for i, (input_image, target) in enumerate(val_loader):
            if args.gpus is not None:
                input_image = input_image.cuda(args.gpus, non_blocking=True)
            target = target.cuda(args.gpus, non_blocking=True)

            # compute output
            output = model(input_image)
            loss = criterion(output, target)

            # measure accuracy and record loss
            acc1, acc5 = accuracy(output, target, topk=topks)
            losses.update(loss.item(), input_image.size(0))
            top1.update(acc1[0], input_image.size(0))
            top5.update(acc5[0], input_image.size(0))

            # measure elapsed time
            batch_time.update(time.time() - end)
            end = time.time()

            # printing the accuracy at certain intervals
            if i % args.print_freq == 0:
                print(
                    'Test: [{0}/{1}]\t'
                    'Time {batch_time.val:.3f} ({batch_time.avg:.3f})\t'
                    'Loss {loss.val:.4f} ({loss.avg:.4f})\t'
                    'Acc@1 {top1.val:.3f} ({top1.avg:.3f})\t'
                    'Acc@5 {top5.val:.3f} ({top5.avg:.3f})'.format(
                        i, len(val_loader), batch_time=batch_time, loss=losses,
                        top1=top1, top5=top5
                    )
                )
        # printing the accuracy of the epoch
        print(
            ' * Acc@1 {top1.avg:.3f} Acc@5 {top5.avg:.3f}'.format(
                top1=top1, top5=top5
            )
        )

    return [batch_time.avg, losses.avg, top1.avg, top5.avg]


if __name__ == '__main__':
    main(sys.argv[1:])
