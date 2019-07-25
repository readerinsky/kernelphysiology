"""
Helpers functions for models in Pytorch.
"""

import os
import sys

import torch
import torch.nn as nn
import torchvision.models as pmodels

try:
    from torch.hub import load_state_dict_from_url
except ImportError:
    from torch.utils.model_zoo import load_url as load_state_dict_from_url

from kernelphysiology.dl.pytorch import models as custom_models


def _get_conv(module, layer_num, conv_num):
    sub_layer = [*module[:layer_num]]
    sub_layer = nn.Sequential(*sub_layer)

    module_list = list(module[layer_num].children())
    if (isinstance(module[layer_num], pmodels.resnet.BasicBlock) or
            isinstance(module[layer_num], custom_models.resnet.BasicBlock)):
        conv_ind = (conv_num - 1) * 3 + 2
    else:
        conv_ind = (conv_num - 1) * 2 + 2
    sub_conv = nn.Sequential(*module_list[:conv_ind])
    return sub_layer, sub_conv


class LayerActivation(nn.Module):
    def __init__(self, model, layer_name):
        super(LayerActivation, self).__init__()

        # FIXME: only for resnet at this point
        name_split = layer_name.split('.')
        last_layer = 4
        sub_layer = None
        sub_conv = None
        if 'layer' in name_split[0]:
            layer_num = int(name_split[1])
            conv_num = int(name_split[2][-1])
            if name_split[0] == 'layer1':
                layerx = model.layer1
                last_layer = 4
            elif name_split[0] == 'layer2':
                layerx = model.layer2
                last_layer = 5
            elif name_split[0] == 'layer3':
                layerx = model.layer3
                last_layer = 6
            elif name_split[0] == 'layer4':
                layerx = model.layer4
                last_layer = 7
            sub_layer, sub_conv = _get_conv(layerx, layer_num, conv_num)
        self.features = nn.Sequential(*list(model.children())[:last_layer])
        self.sub_layer = sub_layer
        self.sub_conv = sub_conv

    def forward(self, x):
        x = self.features(x)
        if self.sub_layer is not None:
            x = self.sub_layer(x)
        if self.sub_conv is not None:
            x = self.sub_conv(x)
        return x


class IntermediateModel(nn.Module):
    def __init__(self, original_model, num_categories, dr_rate, model_name):
        super(IntermediateModel, self).__init__()
        if 'densenet' in model_name:
            layer_number = 1
        else:
            layer_number = 2

        if 'resnet' in model_name:
            num_ftrs = original_model.fc.in_features
        elif model_name == "alexnet":
            num_ftrs = original_model.classifier[6].in_features
        elif 'vgg' in model_name:
            num_ftrs = 512 * 7 * 7
        elif 'densenet' in model_name:
            num_ftrs = original_model.classifier.in_features

        self.features = nn.Sequential(
            *list(original_model.children())[:-layer_number])
        if 'vgg' in model_name:
            self.pool = nn.AdaptiveAvgPool2d((7, 7))
        else:
            self.pool = nn.AdaptiveAvgPool2d((1, 1))
        self.dropout = nn.Dropout(p=dr_rate)
        self.fc = nn.Linear(num_ftrs, num_categories)

    def forward(self, x):
        x = self.features(x)
        x = self.pool(x)
        x = x.view(x.size(0), -1)
        x = self.dropout(x)
        x = self.fc(x)
        return x


def which_network_classification(network_name, dataset, kill_kernels=None,
                                 kill_planes=None):
    if os.path.isfile(network_name):
        checkpoint = torch.load(network_name, map_location='cpu')
        customs = None
        if 'customs' in checkpoint:
            customs = checkpoint['customs']
        model = which_architecture(checkpoint['arch'], customs=customs)

        # TODO: for each dataset a class of network should be defined
        if dataset == 'leaf':
            num_ftrs = model.fc.in_features
            model.fc = nn.Linear(num_ftrs, 30)
        elif dataset == 'fruits':
            num_ftrs = model.fc.in_features
            model.fc = nn.Linear(num_ftrs, 23)
        elif dataset == 'wcs':
            model = IntermediateModel(model, 330, 0, checkpoint['arch'])
        elif dataset == 'wcs_full':
            model = IntermediateModel(model, 1600, 0, checkpoint['arch'])

        model.load_state_dict(checkpoint['state_dict'])
        target_size = checkpoint['target_size']
    elif network_name == 'inception_v3':
        target_size = 299
        model = pmodels.__dict__[network_name](
            pretrained=True, aux_logits=False)
    else:
        model = pmodels.__dict__[network_name](pretrained=True)
        target_size = 224
    # TODO: move to a seperate function
    if kill_kernels is not None:
        layer_name = ''
        for k_item in kill_kernels:
            if k_item.isdigit():
                kernel_index = int(k_item)
                if layer_name == '':
                    sys.exit(
                        'The order of kernels to be killed should follow '
                        'layer name and kernel indices. Invalid layer name %s' %
                        layer_name
                    )
                else:
                    print(
                        'Removing layer %s kernel %d' %
                        (layer_name, kernel_index)
                    )
                    # check whether planes are specified
                    if kill_planes is not None:
                        axis_num = None
                        for p_item in kill_planes:
                            if p_item.isdigit():
                                plane_index = int(p_item)
                                if axis_num == None:
                                    sys.exit(
                                        'The order of planes to be killed '
                                        'should follow ax_number and plane '
                                        'indices. Invalid axis %d' % axis_num
                                    )
                                else:
                                    print(
                                        'Removing axis %d plane %d' %
                                        (axis_num, plane_index)
                                    )
                                    if axis_num == 0:
                                        model.state_dict()[layer_name][
                                        kernel_index, plane_index, :, :
                                        ] = 0
                                    elif axis_num == 1:
                                        model.state_dict()[layer_name][
                                        kernel_index, :, plane_index,
                                        ] = 0
                                    elif axis_num == 2:
                                        model.state_dict()[layer_name][
                                        kernel_index, :, :, plane_index,
                                        ] = 0
                            else:
                                # pattern ax_NUMBER
                                axis_num = int(p_item.split('_')[-1])
                    else:
                        model.state_dict()[layer_name][kernel_index,] = 0
            else:
                layer_name = k_item
    return model, target_size


def which_network(network_name, task_type, dataset, kill_kernels=None,
                  kill_planes=None):
    # FIXME: network should be acosiated to dataset
    if task_type == 'classification':
        (model, target_size) = which_network_classification(
            network_name,
            dataset,
            kill_kernels,
            kill_planes
        )
    return model, target_size


def which_architecture(network_name, customs=None):
    if customs is None:
        if network_name == 'inception_v3':
            model = pmodels.__dict__[network_name](
                pretrained=False, aux_logits=False)
        else:
            model = pmodels.__dict__[network_name](pretrained=False)
    else:
        pooling_type = customs['pooling_type']
        if 'in_chns' in customs:
            in_chns = customs['in_chns']
        else:
            # assuming if it doesn't exist, it's 3
            in_chns = 3
        model = custom_models.__dict__[network_name](pretrained=False,
                                                     pooling_type=pooling_type,
                                                     in_chns=in_chns)
    return model


# TODO: use different values fo preprocessing
def get_preprocessing_function(colour_space, chromaticity):
    mean = [0.5, 0.5, 0.5]
    std = [0.25, 0.25, 0.25]
    if colour_space == 'rgb':
        mean = [0.485, 0.456, 0.406]
        std = [0.229, 0.224, 0.225]
    elif colour_space == 'lab' or colour_space == 'lms':
        if 'dichromat' in chromaticity or 'anopia' in chromaticity:
            mean = [0.5, 0.5]
            std = [0.25, 0.25]
        elif chromaticity == 'monochromat':
            mean = [0.5]
            std = [0.25]
    return mean, std
