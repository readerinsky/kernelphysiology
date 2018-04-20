run /home/arash/Software/repositories/kernelphysiology/matlab/src/kernelphysiology.m

NetNames = {'vgg16', 'vgg19', 'alexnet', 'googlenet', 'inceptionv3', 'resnet50', 'resnet101', 'vgg3c4x', 'vgg5x'};

DatasetName = 'ilsvrc-test';
% AnalysisDir = '/home/arash/Software/repositories/kernelphysiology/analysis/kernelsactivity/';
AnalysisDir = '/home/deeplearning/Desktop/';

for i = 9:numel(NetNames)
  NetwrokName = NetNames{i};
  outdir = [AnalysisDir, NetwrokName, '/'];
  mkdir(outdir);
  fprintf('Processing network %s\n', NetwrokName);
  DatasetActivationDifferentContrasts(NetwrokName, DatasetName, outdir);
end
