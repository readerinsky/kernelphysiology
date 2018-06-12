function PairwiseReport = AnalyseActivationReportPairwise(ActivationReportPath)
%AnalyseActivationReportPairwise Summary of this function goes here
%   Detailed explanation goes here

outdir = fileparts(ActivationReportPath);

%% Creating the matrix contrast versus accuracy

PairwiseReportpPath = [outdir, '/PairwiseReport.mat'];
if ~exist(PairwiseReportpPath, 'file')
  ActivationReport = load(ActivationReportPath);
  ActivationReport = ActivationReport.ActivationReport;
  
  NumImages = numel(ActivationReport);
  
  [nContrasts, ~, NumLayers] = size(ActivationReport(1).CompMatrix);
  
  nComparisons = nContrasts - 1;
  MaxAvgs = zeros(NumImages, nComparisons, NumLayers);
  HistAvgs = zeros(NumImages, nComparisons, NumLayers);
  
  for i = 1:NumImages
    for t = 1:nComparisons
      EqTopTmp = ContrastVsAccuracy(ActivationReport(i), false, [1:t - 1, t + 1:nComparisons]);
      
      MaxAvgs(i, t, :) = EqTopTmp.MaxAvg;
      HistAvgs(i, t, :) = EqTopTmp.HistAvg;
    end
  end
  
  PairwiseReport.avgs.max = MaxAvgs;
  PairwiseReport.avgs.hist = HistAvgs;
  
  save(PairwiseReportpPath, 'PairwiseReport');
else
  PairwiseReport = load(PairwiseReportpPath);
  PairwiseReport = PairwiseReport.PairwiseReport;
end

%% printing the results
fprintf('Printing for max\n');
PrintAverageKernelMatchings(PairwiseReport.avgs.max);
fprintf('Printing for hist\n');
PrintAverageKernelMatchings(PairwiseReport.avgs.hist);

end

function PrintAverageKernelMatchings(PairwiseReport)

[~, nComparisons, nLayers] = size(PairwiseReport);

for i = 1:nComparisons
  meanvals = mean(PairwiseReport(:, i, :));
  fprintf(sprintf('%s\n', repmat('%.2f ', [1, nLayers])), meanvals);
end

end