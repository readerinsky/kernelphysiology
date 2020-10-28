"""

"""

import os

import torch
import torch.nn as nn

from torchvision.models import segmentation
from torchvision.models import detection

from kernelphysiology.dl.pytorch.models import model_utils
from kernelphysiology.dl.pytorch.models import resnet_simclr
from kernelphysiology.dl.experiments.contrast.models.transparency import tranmod
from kernelphysiology.dl.experiments.contrast.models.cityscape import citymode
from kernelphysiology.dl.experiments.contrast import contrast_utils


class LayerActivation(nn.Module):
    def __init__(self, model, layer_name, conv_bn_relu='relu'):
        super(LayerActivation, self).__init__()

        # FIXME: only for resnet at this point
        self.relu = None
        self.sub_layer = None
        self.sub_conv = None

        whole_layers = ['layer%d' % e for e in range(1, 6)]
        if layer_name in whole_layers:
            print('Activation for the whole %s' % layer_name)
            last_areas = [4, 5, 6, 7, 8]
            lind = last_areas[int(layer_name[-1])]
            self.features = nn.Sequential(*list(model.children())[:lind])
        elif layer_name == 'fc':
            self.features = model
        elif layer_name == 'avgpool':
            self.features = nn.Sequential(*list(model.children()))
        else:
            if conv_bn_relu == 'relu':
                self.relu = nn.ReLU(inplace=True)
                which_fun = model_utils._get_bn
            elif conv_bn_relu == 'bn':
                which_fun = model_utils._get_bn
            else:
                which_fun = model_utils._get_conv

            name_split = layer_name.split('.')
            sub_layer = None
            sub_conv = None
            # -3 because the features were autogenerated and start from 4
            area_num = int(name_split[0]) - 3
            layer_num = int(name_split[1])
            conv_num = int(name_split[2][-1])
            last_areas = [1, 4, 5, 6, 7]
            last_area = last_areas[area_num]
            if area_num > 0:
                layerx = list(model.children())[last_areas[area_num]]
                sub_layer, sub_conv = which_fun(layerx, layer_num, conv_num)
            self.features = nn.Sequential(*list(model.children())[:last_area])
            self.sub_layer = sub_layer
            self.sub_conv = sub_conv

    def forward(self, x):
        x = self.features(x)
        if self.sub_layer is not None:
            x = self.sub_layer(x)
        if self.sub_conv is not None:
            x = self.sub_conv(x)
        if self.relu is not None:
            x = self.relu(x)
        return x


def _cityscape_features(model, network_name, layer, grey_width):
    if type(layer) is str:
        if layer == 'mod1':
            layer = 1
            org_classes = 8388608
        elif layer == 'mod2':
            layer = 2
            org_classes = 16777216
        elif layer == 'mod3':
            layer = 3
            org_classes = 33554432
        elif layer == 'mod4':
            layer = 4
            org_classes = 16777216
        elif layer == 'mod5':
            layer = 5
            org_classes = 33554432
        elif layer == 'mod6':
            layer = 6
            org_classes = 67108864
        elif layer == 'mod7':
            layer = 7
            org_classes = 134217728
    else:
        org_classes = 512
    features = nn.Sequential(*list(model.children())[:layer])
    return features, org_classes


def _resnet_features(model, network_name, layer, grey_width):
    if type(layer) is str:
        if layer == 'layer1':
            layer = 4
            if grey_width:
                if network_name in ['resnet18', 'resnet34']:
                    org_classes = 849408
                else:
                    org_classes = 849408
            else:
                if network_name in ['resnet18', 'resnet34']:
                    org_classes = 524288
                else:
                    org_classes = 524288
        elif layer == 'layer2':
            layer = 5
            if grey_width:
                if network_name in ['resnet18', 'resnet34']:
                    org_classes = 849408
                else:
                    org_classes = 3397632
            else:
                if network_name in [
                    'resnet18', 'resnet34',
                    'resnet18_custom', 'deeplabv3_resnet18_custom'
                ]:
                    org_classes = 524288
                else:
                    org_classes = 2097152
        elif layer == 'layer3':
            layer = 6
            if grey_width:
                if network_name in ['resnet18', 'resnet34']:
                    org_classes = 424704
                else:
                    org_classes = 1698816
            else:
                if network_name in [
                    'resnet18', 'resnet34',
                    'resnet18_custom', 'deeplabv3_resnet18_custom'
                ]:
                    org_classes = 262144
                else:
                    org_classes = 1048576
        elif layer == 'layer4':
            layer = 7
            if grey_width:
                if network_name in ['resnet18', 'resnet34']:
                    org_classes = 215040
                elif 'deeplabv3_' in network_name or 'fcn_' in network_name:
                    org_classes = 3397632
                else:
                    org_classes = 860160
            else:
                if network_name in [
                    'resnet18', 'resnet34',
                    'resnet18_custom', 'deeplabv3_resnet18_custom'
                ]:
                    org_classes = 131072
                elif 'custom' not in network_name and (
                        'deeplabv3_' in network_name or 'fcn_' in network_name
                ):
                    org_classes = 2097152
                else:
                    org_classes = 524288
        elif layer == 'layer5':
            layer = 8
            if grey_width:
                if network_name in ['resnet18', 'resnet34']:
                    org_classes = 215040
                elif 'deeplabv3_' in network_name or 'fcn_' in network_name:
                    org_classes = 3397632
                else:
                    org_classes = 860160
            else:
                if network_name in [
                    'resnet18', 'resnet34',
                    'resnet18_custom', 'deeplabv3_resnet18_custom'
                ]:
                    org_classes = 65536
                elif 'custom' not in network_name and (
                        'deeplabv3_' in network_name or 'fcn_' in network_name
                ):
                    org_classes = 4194304
                elif network_name == 'transparency':
                    org_classes = 1048576
                else:
                    org_classes = 262144
    else:
        org_classes = 512
    features = nn.Sequential(*list(model.children())[:layer])
    return features, org_classes


def _mobilenet_v2_features(model, network_name, layer, grey_width):
    layer = int(layer[1:])
    org_classes = [
        1698816, 849408, 318528, 318528, 106176, 106176, 106176, 53760, 53760,
        53760, 53760, 80640, 80640, 80640, 35200, 35200, 35200, 70400, 281600,
    ]
    features = nn.Sequential(*list(model.features.children())[:layer + 1])
    return features, org_classes[layer]


class VGG(nn.Module):

    def __init__(self, model, network_name, layer, grey_width):
        super(VGG, self).__init__()
        self.classifier = None
        if type(layer) is str:
            layer_parts = layer.split('_')
            block = layer_parts[0]
            bind = int(layer_parts[1])
            if block == 'classifier':
                selected_features = []
                for l in list(model.children())[:-1]:
                    selected_features.append((l))
                self.features = nn.Sequential(*selected_features)

                selected_classifier = []
                for i, l in enumerate(list(list(model.children())[-1])):
                    selected_classifier.append((l))
                    if i == bind:
                        break
                self.classifier = nn.Sequential(*selected_classifier)
                self.org_classes = 4096
            elif network_name == 'vgg11_bn':
                selected_features = []
                for i, l in enumerate(list(list(model.children())[-3])):
                    selected_features.append((l))
                    if i == bind:
                        break
                self.features = nn.Sequential(*selected_features)
                all_org_classes = [
                    0, 0, 0, 3397632,
                    0, 0, 0, 1698816,
                    0, 0, 0, 0, 0, 0, 849408,
                    0, 0, 0, 0, 0, 0, 419328,
                    0, 0, 0, 0, 0, 0, 97280
                ]
                self.org_classes = all_org_classes[i]
        else:
            self.org_classes = 25088
            self.features = nn.Sequential(*list(model.children())[:layer])

    def forward(self, x):
        x = self.features(x)
        if self.classifier is not None:
            x = torch.flatten(x, 1)
            x = self.classifier(x)
        return x


def _vgg_features(model, network_name, layer, grey_width):
    features = VGG(model, network_name, layer)
    org_classes = features.org_classes
    return features, org_classes


def get_pretrained_model(network_name, transfer_weights):
    if '_scratch' in network_name:
        model = model_utils.which_architecture(
            network_name.replace('_scratch', '')
        )
    elif os.path.isfile(transfer_weights[0]):
        # FIXME: cheap hack!
        if 'vggface2/deeplabv3_' in transfer_weights[0]:
            model = contrast_utils.FaceModel(network_name, transfer_weights)
        else:
            (model, _) = model_utils.which_network(
                transfer_weights[0], transfer_weights[2],
                num_classes=1000 if 'class' in transfer_weights[2] else 21
            )
    elif ('maskrcnn_' in network_name or 'fasterrcnn_' in network_name
          or 'keypointrcnn_' in network_name
    ):
        model = detection.__dict__[network_name](pretrained=True)
    elif 'deeplabv3_' in network_name or 'fcn_' in network_name:
        model = segmentation.__dict__[network_name](pretrained=True)
    elif network_name == 'transparency':
        model = tranmod()
    elif network_name == 'cityscape':
        model = citymode()
    elif network_name == 'simclr':
        model = resnet_simclr.ResNetSimCLR('resnet50', 128)
        dpath = '/home/arash/Software/repositories/kernelphysiology/data/simclr_resnet50.pth'
        simclr_pretrained = torch.load(dpath, map_location='cpu')
        model.load_state_dict(simclr_pretrained)
    else:
        (model, _) = model_utils.which_network(
            transfer_weights[0], 'classification', num_classes=1000
        )
    return model


def get_backbones(network_name, model):
    if ('maskrcnn_' in network_name or 'fasterrcnn_' in network_name
            or 'keypointrcnn_' in network_name
    ):
        return model.backbone.body
    elif 'deeplabv3_' in network_name or 'fcn_' in network_name:
        return model.backbone
    elif network_name == 'transparency':
        return model.encoder
    elif network_name == 'simclr':
        return model.features
    return model


class NewClassificationModel(nn.Module):
    def __init__(self, network_name, transfer_weights=None, grey_width=True,
                 num_classes=2):
        super(NewClassificationModel, self).__init__()

        checkpoint = None
        # assuming network_name is path
        if transfer_weights is None:
            checkpoint = torch.load(network_name, map_location='cpu')
            network_name = checkpoint['arch']
            transfer_weights = checkpoint['transfer_weights']

        model = get_pretrained_model(network_name, transfer_weights)
        if '_scratch' in network_name:
            network_name = network_name.replace('_scratch', '')
        model = get_backbones(network_name, model)

        # print(model)
        layer = -1
        if len(transfer_weights) >= 2:
            layer = transfer_weights[1]

        if ('maskrcnn_' in network_name or 'fasterrcnn_' in network_name
                or 'keypointrcnn_' in network_name
                or 'deeplabv3_' in network_name or 'fcn_' in network_name
                or network_name == 'transparency' or network_name == 'simclr'
                or 'resnet' in network_name or 'resnext' in network_name
        ):
            features, org_classes = _resnet_features(
                model, network_name, layer, grey_width
            )
        elif network_name == 'cityscape':
            features, org_classes = _cityscape_features(
                model, network_name, layer, grey_width
            )
        elif 'vgg' in network_name:
            features, org_classes = _vgg_features(
                model, network_name, layer, grey_width
            )
        elif 'mobilenet_v2' in network_name:
            features, org_classes = _mobilenet_v2_features(
                model, network_name, layer, grey_width
            )
        self.features = features
        # self.avgpool = nn.AdaptiveAvgPool2d((1, 1))
        self.fc = nn.Linear(org_classes, num_classes)

        if checkpoint is not None:
            self.load_state_dict(checkpoint['state_dict'])

    def forward(self, x):
        x = self.features(x)
        # x = self.avgpool(x)
        # print(x.shape)
        x = x.view(x.size(0), -1)
        # print(x.shape)
        x = self.fc(x)
        return x
