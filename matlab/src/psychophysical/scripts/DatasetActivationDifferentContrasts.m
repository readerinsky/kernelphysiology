function DatasetActivationDifferentContrasts(NetwrokName, DatasetName, outdir)

%% Network details
if isa(NetwrokName, 'SeriesNetwork') || isa(NetwrokName, 'DAGNetwork')
  net = NetwrokName;
elseif strcmpi(NetwrokName, 'vgg16')
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

imdb = [];

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
elseif strcmpi(DatasetName, 'cifar10')
  imdb = load('/home/arash/Software/repositories/kernelphysiology/matlab/data/datasets/cifar/cifar10/imdb-org.mat');
elseif strcmpi(DatasetName, 'cifar100')
  imdb = load('/home/arash/Software/repositories/kernelphysiology/matlab/data/datasets/cifar/cifar100/imdb-org.mat');
end

outdir = sprintf('%s/%s/', outdir, DatasetName);

if ~exist(outdir, 'dir')
  mkdir(outdir);
end

%% Compute activation of kernels for different contrasts
layers = ConvInds(net, inf);

if ~isempty(imdb)
  TestImages = uint8(imdb.images.data(:, :, :, imdb.images.set == 3));
  ActivationReport = PerformWithImdb(net, TestImages, layers, outdir);
else
  ActivationReport = PerformWithImageList(net, ImageList, layers, outdir);
end

save([outdir, 'ActivationReport.mat'], 'ActivationReport');

end

function ActivationReport = PerformWithImdb(net, TestImages, layers, outdir)

NumImages = size(TestImages, 4);
parfor i = 1:NumImages
  inim = TestImages(:, :, :, i);
  ImageBaseName = sprintf('im%.6i', i);
  ImageOutDir = sprintf('%s%s/', outdir, ImageBaseName);
  ActivationReport(i) = ActivationDifferentContrasts(net, inim, ImageOutDir, false, layers);
end

end

function ActivationReport = PerformWithImageList(net, ImageList, layers, outdir)

NumImages = numel(ImageList);
parfor i = 1:NumImages
  inim = imread([ImageList(i).folder, '/', ImageList(i).name]);
  [~, ImageBaseName, ~] = fileparts(ImageList(i).name);
  ImageOutDir = sprintf('%s%s/', outdir, ImageBaseName);
  ActivationReport(i) = ActivationDifferentContrasts(net, inim, ImageOutDir, false, layers);
end

end
