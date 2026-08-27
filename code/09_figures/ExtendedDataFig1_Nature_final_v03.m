% Release copy: paths are supplied through NEE_RELEASE_DATA_ROOT and NEE_OUTPUT_ROOT.
function FigS1_Nature_final_v03()
% FIGS1_NATURE_FINAL_V03
% Layout-only final polish for Supplementary Figure S1.
% Scientific values are read from the locked v01 plotting summaries.
% No source table, summary table, threshold, count or definition is changed.

rootOut = getenv('NEE_OUTPUT_ROOT');
summaryDir = fullfile(getenv('NEE_RELEASE_DATA_ROOT'),'figure_inputs','ExtendedDataFig1');
matlabDir = rootOut;
previewDir = rootOut;


mapFile = fullfile(summaryDir, 'S1_domain_map_qc.csv');
availabilityFile = fullfile(summaryDir, 'S1_data_availability_summary.csv');
eventFile = fullfile(summaryDir, 'S1_event_inventory_summary.csv');
regionalFile = fullfile(summaryDir, 'S1_regional_qc_summary.csv');

outFig = fullfile(matlabDir, 'FigS1_Nature_final_v03.fig');
outPdf = fullfile(matlabDir, 'FigS1_Nature_final_v03.pdf');
outPng = fullfile(matlabDir, 'FigS1_Nature_final_v03.png');
outPreview = fullfile(previewDir, 'FigS1_Nature_final_v03_preview.png');

assert(isfile(mapFile) && isfile(availabilityFile) && isfile(eventFile) && ...
    isfile(regionalFile), 'One or more locked v01 plotting summaries are missing.');

domainMap = readtable(mapFile, 'VariableNamingRule', 'preserve');
availabilityTable = readtable(availabilityFile, 'VariableNamingRule', 'preserve');
eventInventory = readtable(eventFile, 'VariableNamingRule', 'preserve');
regionalTable = readtable(regionalFile, 'VariableNamingRule', 'preserve');

%% Science-lock assertions
qc = string(domainMap.qc_flag);
passMask = qc == "PASS";
noEventMask = qc == "NO_TRAIN_EVENTS";
partialMask = qc == "PARTIAL_STATIC";
assert(height(domainMap) == 16616, 'Frozen forest-domain size changed.');
assert(sum(passMask) == 14241, 'PASS count changed.');
assert(sum(noEventMask) == 2363, 'No-training-event count changed.');
assert(sum(partialMask) == 12, 'Partial-static count changed.');

availabilityLabels = string(availabilityTable.field);
availabilityPercent = availabilityTable.availability_percent;
expectedAvailability = [100; 100; 100; 94.8363023591719; ...
    94.6196437168994; 85.7787674530573];
assert(isequal(availabilityLabels, ["Forest cover"; "Intact forest"; ...
    "Canopy height"; "Human modification"; "Biomass"; ...
    "Training-event support"]), 'Availability categories changed.');
assert(all(abs(availabilityPercent - expectedAvailability) < 1e-10), ...
    'Availability percentages changed.');

scaleOrder = string(eventInventory.scale);
eventN = eventInventory.event_count;
durationP25 = eventInventory.duration_p25_months;
durationMedian = eventInventory.duration_median_months;
durationP75 = eventInventory.duration_p75_months;
assert(isequal(scaleOrder, ["D1"; "D3"; "D6"]), 'SPEI scale order changed.');
assert(isequal(eventN, [90971; 101957; 87221]), 'Event counts changed.');
assert(isequal(durationP25, [2; 2; 3]) && ...
    isequal(durationMedian, [3; 3; 5]) && ...
    isequal(durationP75, [4; 5; 8]), 'Duration statistics changed.');

regions = string(regionalTable.large_region);
regionTotal = regionalTable.total_cells;
regionPass = regionalTable.pass_cells;
regionPassPercent = regionalTable.pass_percent;
assert(isequal(regions, ["Asia"; "North America"; "South America"; ...
    "Europe"; "Oceania"; "Africa"; "Other"]), 'Region order changed.');
assert(isequal(regionTotal, [5018;3913;2850;1811;1466;1200;358]), ...
    'Regional totals changed.');
assert(isequal(regionPass, [4259;3587;2732;1680;803;1023;157]), ...
    'Regional PASS counts changed.');

%% Coordinated publication palette
mapBlue = [27 96 128] ./ 255;
mapOrange = [231 158 0] ./ 255;
charcoal = [42 47 52] ./ 255;
midGray = [132 141 149] ./ 255;
lightGray = [225 230 233] ./ 255;
paleBlue = [232 242 247] ./ 255;
paleOrange = [252 241 216] ./ 255;

availabilityColors = [ ...
    30 75 118; ...
    43 101 145; ...
    71 124 160; ...
    38 137 148; ...
    77 161 164; ...
    27 143 107] ./ 255;

scaleColors = [ ...
    34 117 150; ...
    42 157 143; ...
    77 137 104] ./ 255;

retentionLow = [124 190 181] ./ 255;
retentionHigh = [26 91 123] ./ 255;
shadePosition = max(0,min(1,(regionPassPercent - 40) ./ 60));
retentionColors = (1-shadePosition) .* retentionLow + shadePosition .* retentionHigh;

%% A4 portrait canvas
fig = figure('Color','w','Units','inches','Position',[0.4 0.25 8.27 11.69], ...
    'PaperUnits','inches','PaperSize',[8.27 11.69], ...
    'PaperPosition',[0 0 8.27 11.69], 'PaperPositionMode','manual', ...
    'ToolBar','none','MenuBar','none','NumberTitle','off', ...
    'Name','Supplementary Figure S1 - final polish', ...
    'Visible','on','WindowStyle','normal');

annotation(fig,'textbox',[0.075 0.964 0.88 0.024], ...
    'String','Study domain, screening, coverage and data quality', ...
    'FontName','Arial','FontSize',12.2,'FontWeight','bold', ...
    'Color',charcoal,'EdgeColor','none','Margin',0,'VerticalAlignment','middle');

%% (a) Compact verified eligibility gate
axA = axes(fig,'Position',[0.075 0.855 0.88 0.075],'Visible','off');
hold(axA,'on'); xlim(axA,[0 1]); ylim(axA,[0 1]);
panelHeader(axA,'(a)','Verified forest-domain eligibility gate');

boxX = [0.01 0.265 0.52 0.775];
boxW = 0.205;
boxColors = {paleBlue,paleBlue,paleBlue,paleOrange};
lineColors = {mapBlue,mapBlue,mapBlue,mapOrange};
boxText = {sprintf('Annual forest cover\n2001-2020'), ...
    sprintf('Supported record\n>= 16 annual observations'), ...
    sprintf('Forest criterion\nmean cover >= 30%%'), ...
    sprintf('Frozen study domain\nn = 16,616 cells')};
for ii = 1:4
    rectangle(axA,'Position',[boxX(ii) 0.19 boxW 0.52], ...
        'Curvature',0.05,'FaceColor',boxColors{ii}, ...
        'EdgeColor',lineColors{ii},'LineWidth',1.0);
    text(axA,boxX(ii)+boxW/2,0.45,boxText{ii},'HorizontalAlignment','center', ...
        'VerticalAlignment','middle','FontName','Arial','FontSize',7.2, ...
        'FontWeight','bold','Color',charcoal,'Interpreter','none');
    if ii < 4
        annotationArrow(fig,axA,boxX(ii)+boxW+0.008,boxX(ii+1)-0.008,0.45,mapBlue);
    end
end
text(axA,0.99,0.02, ...
    'Criteria verified from frozen production code; intermediate screen counts unavailable', ...
    'HorizontalAlignment','right','FontName','Arial','FontSize',6.2, ...
    'Color',midGray,'Interpreter','none');

%% (b) Enlarged global map - primary visual anchor
axB = axes(fig,'Position',[0.082 0.493 0.865 0.325]);
hold(axB,'on');
try
    coast = load('coastlines');
    plot(axB,coast.coastlon,coast.coastlat,'Color',[0.68 0.72 0.75], ...
        'LineWidth',0.48,'HandleVisibility','off');
catch
end
scatter(axB,domainMap.lon(noEventMask),domainMap.lat(noEventMask),6.2,mapOrange,'filled', ...
    'MarkerFaceAlpha',0.76,'MarkerEdgeColor','none','HandleVisibility','off');
scatter(axB,domainMap.lon(passMask),domainMap.lat(passMask),6.5,mapBlue,'filled', ...
    'MarkerFaceAlpha',0.58,'MarkerEdgeColor','none','HandleVisibility','off');
scatter(axB,domainMap.lon(partialMask),domainMap.lat(partialMask),16,charcoal,'filled', ...
    'MarkerEdgeColor','w','LineWidth',0.35,'HandleVisibility','off');
hPass = scatter(axB,nan,nan,22,mapBlue,'filled', ...
    'DisplayName',sprintf('PASS (n = %s)',fmtint(sum(passMask))));
hNoEvent = scatter(axB,nan,nan,22,mapOrange,'filled', ...
    'DisplayName',sprintf('No training events (n = %s)',fmtint(sum(noEventMask))));
hPartial = scatter(axB,nan,nan,22,charcoal,'filled', ...
    'DisplayName',sprintf('Partial static data (n = %s)',fmtint(sum(partialMask))));
xlim(axB,[-180 180]); ylim(axB,[-60 85]);
xticks(axB,-120:60:120); yticks(axB,-60:30:60);
grid(axB,'on');
set(axB,'FontName','Arial','FontSize',7,'TickDir','out','Box','off', ...
    'GridColor',[0.86 0.89 0.91],'GridAlpha',0.48,'Layer','bottom');
xlabel(axB,'Longitude','FontName','Arial','FontSize',7.6);
ylabel(axB,'Latitude','FontName','Arial','FontSize',7.6);
panelHeader(axB,'(b)','Global forest-domain coverage and frozen QC state');
legend(axB,[hPass hNoEvent hPartial],'Location','southoutside', ...
    'Orientation','horizontal','Box','off','FontName','Arial','FontSize',6.7);

%% (c) Refined compact availability bars
axC = axes(fig,'Position',[0.125 0.305 0.35 0.130]);
yAvail = 1:numel(availabilityLabels);
bC = barh(axC,yAvail,availabilityPercent,0.68, ...
    'FaceColor','flat','EdgeColor','none');
bC.CData = availabilityColors;
hold(axC,'on');
plot(axC,[100 100],[0.42 numel(yAvail)+0.58],':', ...
    'Color',[0.48 0.54 0.58],'LineWidth',0.8);
for ii = 1:numel(yAvail)
    text(axC,101.2,yAvail(ii),sprintf('%.1f%%',availabilityPercent(ii)), ...
        'FontName','Arial','FontSize',6.7,'Color',charcoal, ...
        'HorizontalAlignment','left','VerticalAlignment','middle');
end
set(axC,'YDir','reverse','YTick',yAvail,'YTickLabel',availabilityLabels, ...
    'FontName','Arial','FontSize',6.7,'TickDir','out','Box','off');
xlim(axC,[0 109]); xticks(axC,0:20:100);
xlabel(axC,'Available cells (%)','FontName','Arial','FontSize',7.2);
grid(axC,'on'); axC.YGrid = 'off';
axC.GridColor = [0.90 0.92 0.93]; axC.GridAlpha = 0.60;
panelHeader(axC,'(c)','Input availability within the frozen domain');

%% (d) Refined compact event inventory
axD = axes(fig,'Position',[0.590 0.305 0.35 0.130]);
bD = bar(axD,1:3,eventN./1000,0.68,'FaceColor','flat','EdgeColor','none');
bD.CData = scaleColors;
hold(axD,'on');
for ii = 1:3
    text(axD,ii,eventN(ii)./1000+2.0,sprintf('%s events',fmtint(eventN(ii))), ...
        'HorizontalAlignment','center','FontName','Arial','FontSize',6.6, ...
        'FontWeight','bold','Color',charcoal);
    text(axD,ii,6.0,sprintf('%.0f [%.0f-%.0f] mo',durationMedian(ii), ...
        durationP25(ii),durationP75(ii)), ...
        'HorizontalAlignment','center','FontName','Arial','FontSize',6.4, ...
        'FontWeight','bold','Color','w');
end
set(axD,'XTick',1:3,'XTickLabel',{'SPEI-1','SPEI-3','SPEI-6'}, ...
    'FontName','Arial','FontSize',7,'TickDir','out','Box','off');
ylim(axD,[0 112]);
ylabel(axD,'Detected events (x10^3)','FontName','Arial','FontSize',7.2);
grid(axD,'on'); axD.XGrid = 'off';
axD.GridColor = [0.90 0.92 0.93]; axD.GridAlpha = 0.60;
panelHeader(axD,'(d)','Drought-event inventory and duration support');

%% (e) Regional reference bars plus retention-gradient foreground
axE = axes(fig,'Position',[0.160 0.080 0.78 0.158]);
yRegion = 1:numel(regions);
hAll = barh(axE,yRegion,regionTotal,0.66,'FaceColor',lightGray, ...
    'EdgeColor','none','DisplayName','All forest-domain cells');
hold(axE,'on');
hRetain = barh(axE,yRegion,regionPass,0.42,'FaceColor','flat', ...
    'EdgeColor','none','DisplayName','QC PASS (shade = retention)');
hRetain.CData = retentionColors;
for ii = 1:numel(regions)
    text(axE,regionTotal(ii)+85,yRegion(ii),sprintf('%.1f%%',regionPassPercent(ii)), ...
        'FontName','Arial','FontSize',6.7,'Color',charcoal, ...
        'HorizontalAlignment','left','VerticalAlignment','middle');
end
set(axE,'YDir','reverse','YTick',yRegion,'YTickLabel',regions, ...
    'FontName','Arial','FontSize',7,'TickDir','out','Box','off');
xlim(axE,[0 5550]);
xlabel(axE,'Number of 0.5 degree grid cells','FontName','Arial','FontSize',7.2);
grid(axE,'on'); axE.YGrid = 'off';
axE.GridColor = [0.90 0.92 0.93]; axE.GridAlpha = 0.60;
panelHeader(axE,'(e)','Regional coverage and QC retention');
legend(axE,[hAll hRetain],'Location','east','Box','off', ...
    'FontName','Arial','FontSize',6.4);
text(axE,0.995,0.02,'Labels: QC PASS / regional total', ...
    'Units','normalized','HorizontalAlignment','right','VerticalAlignment','bottom', ...
    'FontName','Arial','FontSize',6.0,'Color',midGray);

%% Export
set(findall(fig,'-property','FontName'),'FontName','Arial');
allAxes = findall(fig,'Type','axes');
for ii = 1:numel(allAxes)
    try
        axtoolbar(allAxes(ii),{});
    catch
    end
end
set(fig,'Visible','on','WindowStyle','normal');
drawnow;
savefig(fig,outFig);
set(fig,'Renderer','painters','InvertHardcopy','off');
print(fig,outPdf,'-dpdf','-painters','-r300');
exportgraphics(fig,outPng,'Resolution',600,'BackgroundColor','white');
exportgraphics(fig,outPreview,'Resolution',200,'BackgroundColor','white');

fprintf('Created %s\n',outFig);
fprintf('Created %s\n',outPdf);
fprintf('Created %s\n',outPng);
fprintf('Created %s\n',outPreview);
end

function panelHeader(ax,labelText,titleText)
text(ax,-0.075,1.075,labelText,'Units','normalized','FontName','Arial', ...
    'FontSize',9.2,'FontWeight','bold','Color',[42 47 52]./255, ...
    'HorizontalAlignment','left','VerticalAlignment','bottom','Clipping','off');
text(ax,0,1.075,titleText,'Units','normalized','FontName','Arial', ...
    'FontSize',8.8,'FontWeight','bold','Color',[42 47 52]./255, ...
    'HorizontalAlignment','left','VerticalAlignment','bottom','Clipping','off');
end

function annotationArrow(fig,ax,x1,x2,y,colorValue)
axPos = ax.Position;
fx1 = axPos(1) + x1 .* axPos(3);
fx2 = axPos(1) + x2 .* axPos(3);
fy = axPos(2) + y .* axPos(4);
annotation(fig,'arrow',[fx1 fx2],[fy fy],'Color',colorValue,'LineWidth',1.0, ...
    'HeadLength',5,'HeadWidth',5);
end

function out = fmtint(value)
out = sprintf('%.0f',value);
for kk = (length(out)-2):-3:2
    out = [out(1:kk-1) ',' out(kk:end)]; %#ok<AGROW>
end
end


