function DatasetActivationDifferentContrasts(NetwrokName, DatasetName, outdir)

%% Network details
if strcmpi(NetwrokName, 'vgg16')
  net = vgg16;
elseif strcmpi(NetwrokName, 'vgg19')
  net = vgg19;
elseif strcmpi(NetwrokName, 'vgg3c4x')
  net = load('vgg3c4x.mat');
  net = net.net;
elseif strcmpi(NetwrokName, 'vgg5x')
  net = load('vgg5x.mat');
  net = net.net;
elseif strcmpi(NetwrokName, 'googlenet')
  net = googlenet;
elseif strcmpi(NetwrokName, 'inceptionv3')
  net = inceptionv3;
elseif strcmpi(NetwrokName, 'alexnet')
  net = alexnet;
elseif strcmpi(NetwrokName, 'resnet50')
  net = resnet50;
elseif strcmpi(NetwrokName, 'resnet101')
  net = resnet101;
elseif strcmpi(NetwrokName, 'inceptionresnetv2')
  net = inceptionresnetv2;
elseif strcmpi(NetwrokName, 'squeezenet')
  net = squeezenet;
end

%% Dataset details

% path of the dataset
if strcmpi(DatasetName, 'voc2012')
  DatasetPath = '/home/arash/Software/repositories/kernelphysiology/data/computervision/voc2012/JPEGImages/';
  ImageList = dir(sprintf('%s*.jpg', DatasetPath));
elseif strcmpi(DatasetName, 'ilsvrc2017')
  DatasetPath = '/home/arash/Software/repositories/kernelphysiology/data/computervision/ilsvrc/ilsvrc2017/Data/DET/test/';
  ImageList = dir(sprintf('%s*.JPEG', DatasetPath));
elseif strcmpi(DatasetName, 'ilsvrc-test')
  DatasetPath = '/home/ImageNet/Val_Images_RGB/';
  ImageList = dir(sprintf('%s*.png', DatasetPath));
end

NumImages = numel(ImageList);

outdir = sprintf('%s/%s/', outdir, DatasetName);

if ~exist(outdir, 'dir')
  mkdir(outdir);
end

%% Compute activation of kernels for different contrasts
SelectedImages = 1:NumImages;

layers = ConvInds(net, inf);

parfor i = SelectedImages
  inim = imread([DatasetPath, ImageList(i).name]);
  [~, ImageBaseName, ~] = fileparts(ImageList(i).name);
  ImageOutDir = sprintf('%s%s/', outdir, ImageBaseName);
  ActivationReport(i) = ActivationDifferentContrasts(net, inim, ImageOutDir, false, layers);
end

save([outdir, 'ActivationReport.mat'], 'ActivationReport');

end
