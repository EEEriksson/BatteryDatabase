%% Batixt Load
% Script that loads all data files that starts with Nyq in a directory.
% This is taylored for the Batixt EIS instrument data.
CSVFiles=dir('Nyq*.mat'); %
EIS_n={}; %% temporary variable for storing the data
for ii=1:length(CSVFiles)
    % disp(['Analysing ' num2str(ii) ' of ' num2str(length(CSVFiles)) ' - ' CSVFiles(ii).name])
    fileName=CSVFiles(ii).name;
    %load(CSVFiles(ii).name);
    load(fileName)
    if ii>1
    else
        EIS_n{ii}.theFreqs=real(Nyquist(3,:));
        EIS_n{ii}.cellInfo=char(DescriptData(1,:));
    end
    EIS_n{ii}.EIS=Nyquist(1,:);
    EIS_n{ii}.fileName=fileName;
    EIS_n{ii}.U_oc=NumericalData(2);
    EIS_n{ii}.DateTime=NumericalData(22:27);
    %EIS_n{ii}.cellInfo=char(DescriptData(1,:));
    EIS_n{ii}.sat=false;
    %FileList=[FileList, ',''' CSVFiles(ii).name ''''];
end
EISData=EIS_n;
clear EIS_n Nyquist NumericalData 