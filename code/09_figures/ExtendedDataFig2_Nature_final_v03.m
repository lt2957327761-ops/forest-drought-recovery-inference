% Release copy: paths are supplied through NEE_RELEASE_DATA_ROOT and NEE_OUTPUT_ROOT.
function FigS2_Nature_final_v03_editable()
%FIGS2_NATURE_FINAL_V03_EDITABLE Final optimized Supplementary Figure S2.
%   Reads one frozen source CSV, generates three controlled color-scale
%   tests, a comparison preview, and the final editable FIG/PDF/PNG.

close all force;

sourceFile = fullfile(getenv('NEE_RELEASE_DATA_ROOT'),'figure_inputs','ExtendedDataFig2','FIGS8_censor_endpoint_maps.csv');
outDir = fileparts(mfilename('fullpath'));

figPath = fullfile(outDir,'FigS2_Nature_final_v03.fig');
pdfPath = fullfile(outDir,'FigS2_Nature_final_v03.pdf');
pngPath = fullfile(outDir,'FigS2_Nature_final_v03.png');
testAPath = fullfile(outDir,'S2_COLOR_TEST_A_FULL_RANGE.png');
testBPath = fullfile(outDir,'S2_COLOR_TEST_B_ROBUST_CAP.png');
testCPath = fullfile(outDir,'S2_COLOR_TEST_C_DISCRETE_BINS.png');
comparisonPath = fullfile(outDir,'S2_COLOR_SCALE_COMPARISON.png');

assert(isfile(sourceFile),'Frozen source file not found: %s',sourceFile);
T = readtable(sourceFile,'VariableNamingRule','preserve');
required = {'lon','lat','right_censor_rate_all_period','current_2024_endpoint_category'};
assert(all(ismember(required,T.Properties.VariableNames)),'Frozen source schema is incomplete.');

lon = double(T.lon);
lat = double(T.lat);
rcRate = double(T.right_censor_rate_all_period);
endpoint = double(T.current_2024_endpoint_category);

validA = isfinite(lon) & isfinite(lat) & isfinite(rcRate);
validB = isfinite(lon) & isfinite(lat) & isfinite(endpoint) & ismember(endpoint,[0 1 2]);
x = rcRate(validA);
assert(nnz(validA)==14277,'Unexpected panel (a) eligible-cell count.');
assert(nnz(validB)==5516,'Unexpected panel (b) eligible-cell count.');
assert(min(x)==0 && max(x)==0.75,'Unexpected all-period right-censoring range.');

quantileProb = [0.05 0.10 0.25 0.50 0.75 0.90 0.95 0.975 0.99];
q = linear_quantiles(x,quantileProb);
robustCap = q(8);
assert(abs(robustCap-0.1407407407407407)<1e-12,'Unexpected P97.5 display cap.');

endpointCounts = [sum(endpoint(validB)==0),sum(endpoint(validB)==1),sum(endpoint(validB)==2)];
assert(isequal(endpointCounts,[2492 1388 1636]),'Unexpected endpoint category counts.');
endpointPct = 100*endpointCounts/sum(endpointCounts);

rcBin = assign_scientific_bins(rcRate);
binCounts = zeros(1,7);
for k = 1:7
    binCounts(k) = sum(validA & rcBin==k);
end
assert(isequal(binCounts,[10771 1357 1336 514 192 85 22]),'Unexpected right-censoring bin counts.');
binPct = 100*binCounts/sum(binCounts);

RC_ANCHORS = [ ...
    250 249 180; ...
    214 231 158; ...
    167 207 137; ...
    105 176 145; ...
     57 139 157; ...
     32 101 154; ...
     16  61 115] / 255;
RC_CONTINUOUS = interp1(linspace(0,1,7),RC_ANCHORS,linspace(0,1,256),'linear');
RC_DISCRETE = RC_ANCHORS;
RC_LABELS = {'0','>0-0.05','>0.05-0.10','>0.10-0.15','>0.15-0.20','>0.20-0.30','>0.30'};

C_OBSERVED = [0.78 0.79 0.80];
C_MIXED = [0.90 0.55 0.05];
C_RC = [0.77 0.43 0.67];
CAT_COLORS = [C_OBSERVED;C_MIXED;C_RC];
CAT_LABELS = {'All observed','Mixed','All right-censored'};

% Controlled color tests: identical map geometry, data and linework.
create_single_color_test(testAPath,'A: Full range (0-0.75)', ...
    'full',lon,lat,rcRate,validA,rcBin,RC_CONTINUOUS,RC_DISCRETE,RC_LABELS,robustCap);
create_single_color_test(testBPath,sprintf('B: Robust cap (P97.5 = %.3f)',robustCap), ...
    'cap',lon,lat,rcRate,validA,rcBin,RC_CONTINUOUS,RC_DISCRETE,RC_LABELS,robustCap);
create_single_color_test(testCPath,'C: Fixed scientific bins', ...
    'bins',lon,lat,rcRate,validA,rcBin,RC_CONTINUOUS,RC_DISCRETE,RC_LABELS,robustCap);
create_color_comparison(comparisonPath,lon,lat,rcRate,validA,rcBin, ...
    RC_CONTINUOUS,RC_DISCRETE,RC_LABELS,robustCap);

FS.panel = 15;
FS.title = 12.5;
FS.legend = 10.2;
FS.cbLabel = 10.8;
FS.cbTick = 9.2;
FS.mapNote = 9.4;

fig = figure('Color','w','Units','centimeters','Position',[1 1 18.5 25.5], ...
    'Renderer','painters','Name','Supplementary Figure S2 v03', ...
    'NumberTitle','off','Toolbar','none','MenuBar','none','Visible','off');
set(fig,'PaperUnits','centimeters','PaperPosition',[0 0 18.5 25.5], ...
    'PaperSize',[18.5 25.5],'InvertHardcopy','off');

POS.A = [0.055 0.625 0.89 0.315];
POS.ALEG = [0.12 0.573 0.76 0.024];
POS.B = [0.055 0.235 0.89 0.285];
POS.BLEG = [0.155 0.185 0.69 0.026];
POS.C1 = [0.065 0.032 0.405 0.102];
POS.C2 = [0.535 0.038 0.41 0.096];

% Panel (a): selected fixed scientific bins.
axA = axes(fig,'Position',POS.A,'Color','w');
draw_discrete_rc_map(axA,lon,lat,rcBin,validA,RC_DISCRETE,12);
panel_title(axA,'(a)','All-period right censoring',FS);
text(axA,0.985,1.045,sprintf('n = %s cells',format_integer(nnz(validA))), ...
    'Units','normalized','HorizontalAlignment','right','VerticalAlignment','middle', ...
    'FontName','Arial','FontSize',FS.mapNote,'Color',[0.38 0.40 0.43], ...
    'Clipping','off');
disable_toolbar(axA);

axAL = axes(fig,'Position',POS.ALEG,'Color','w');
draw_discrete_strip(axAL,RC_DISCRETE,RC_LABELS,FS.cbTick);
xlabel(axAL,'Right-censored fraction','FontName','Arial','FontSize',FS.cbLabel);
disable_toolbar(axAL);

% Panel (b): unchanged frozen endpoint categories.
axB = axes(fig,'Position',POS.B,'Color','w');
setup_world_map(axB);
for k = 0:2
    idx = validB & endpoint==k;
    [xp,yp] = equal_earth(lon(idx),lat(idx));
    scatter(axB,xp,yp,13,CAT_COLORS(k+1,:),'filled', ...
        'MarkerEdgeColor','none','MarkerFaceAlpha',0.97);
end
draw_map_overlay(axB);
panel_title(axB,'(b)','2024 endpoint status',FS);
text(axB,0.985,1.045,sprintf('n = %s cells with 2024 status',format_integer(nnz(validB))), ...
    'Units','normalized','HorizontalAlignment','right','VerticalAlignment','middle', ...
    'FontName','Arial','FontSize',FS.mapNote,'Color',[0.38 0.40 0.43], ...
    'Clipping','off');
disable_toolbar(axB);

axBL = axes(fig,'Position',POS.BLEG,'Color','w');
draw_category_legend(axBL,CAT_COLORS,CAT_LABELS,FS.legend);
disable_toolbar(axBL);

% Panel (c): two aligned descriptive summaries.
annotation(fig,'textbox',[0.055 0.143 0.05 0.025],'String','(c)', ...
    'LineStyle','none','FontName','Arial','FontSize',FS.panel,'FontWeight','bold', ...
    'HorizontalAlignment','left','VerticalAlignment','middle');
annotation(fig,'textbox',[0.10 0.143 0.42 0.025],'String','Quantitative summary', ...
    'LineStyle','none','FontName','Arial','FontSize',FS.title,'FontWeight','bold', ...
    'HorizontalAlignment','left','VerticalAlignment','middle');

axC1 = axes(fig,'Position',POS.C1,'Color','w');
draw_endpoint_composition(axC1,endpointPct,CAT_COLORS,CAT_LABELS);
disable_toolbar(axC1);

axC2 = axes(fig,'Position',POS.C2,'Color','w');
draw_rc_distribution(axC2,binPct,RC_DISCRETE);
disable_toolbar(axC2);

drawnow;
allAxes = findall(fig,'Type','axes');
for i = 1:numel(allAxes)
    disable_toolbar(allAxes(i));
end
drawnow;

% IMPORTANT FOR EDITABLE .FIG:
% The figure was constructed with Visible='off'. If it is saved in that
% state, opening the FIG later can look like "nothing happened". Force the
% final figure visible before savefig so MATLAB GUI can reopen it normally.
set(fig,'Visible','on','WindowStyle','normal');
try
    set(fig,'MenuBar','figure');
catch
end
try
    set(fig,'ToolBar','figure');
catch
end
drawnow;

savefig(fig,figPath);
print(fig,pdfPath,'-dpdf','-painters');
print(fig,pngPath,'-dpng','-r600');
% Keep final figure open for manual MATLAB editing.

fprintf('Created final outputs:\n%s\n%s\n%s\n',figPath,pdfPath,pngPath);
fprintf('Created color tests and comparison:\n%s\n%s\n%s\n%s\n', ...
    testAPath,testBPath,testCPath,comparisonPath);
end

function q = linear_quantiles(x,p)
x = sort(double(x(:)));
n = numel(x);
q = zeros(size(p));
for i = 1:numel(p)
    h = 1 + (n-1)*p(i);
    lo = floor(h);
    hi = ceil(h);
    if lo==hi
        q(i) = x(lo);
    else
        q(i) = x(lo) + (h-lo)*(x(hi)-x(lo));
    end
end
end

function bin = assign_scientific_bins(v)
bin = nan(size(v));
bin(v==0) = 1;
bin(v>0 & v<=0.05) = 2;
bin(v>0.05 & v<=0.10) = 3;
bin(v>0.10 & v<=0.15) = 4;
bin(v>0.15 & v<=0.20) = 5;
bin(v>0.20 & v<=0.30) = 6;
bin(v>0.30) = 7;
end

function create_single_color_test(outPath,titleText,scheme,lon,lat,rcRate,valid,rcBin,continuousMap,discreteMap,labels,cap)
fig = figure('Color','w','Units','centimeters','Position',[1 1 18.5 11], ...
    'Renderer','painters','NumberTitle','off','Toolbar','none','MenuBar','none','Visible','off');
set(fig,'PaperUnits','centimeters','PaperPosition',[0 0 18.5 11], ...
    'PaperSize',[18.5 11],'InvertHardcopy','off');
ax = axes(fig,'Position',[0.055 0.28 0.89 0.62],'Color','w');
draw_scale_map(ax,scheme,lon,lat,rcRate,valid,rcBin,continuousMap,discreteMap,cap,11);
text(ax,-0.01,1.05,titleText,'Units','normalized','FontName','Arial', ...
    'FontSize',12.5,'FontWeight','bold','HorizontalAlignment','left', ...
    'VerticalAlignment','middle','Clipping','off');
text(ax,0.985,1.05,'n = 14,277 cells','Units','normalized','FontName','Arial', ...
    'FontSize',9.2,'Color',[0.38 0.40 0.43],'HorizontalAlignment','right', ...
    'VerticalAlignment','middle','Clipping','off');
axL = axes(fig,'Position',[0.12 0.08 0.76 0.065],'Color','w');
draw_scale_legend(axL,scheme,continuousMap,discreteMap,labels,cap,8.8);
xlabel(axL,'Right-censored fraction','FontName','Arial','FontSize',10.2);
disable_toolbar(ax);
disable_toolbar(axL);
drawnow;
print(fig,outPath,'-dpng','-r300');
close(fig);
end

function create_color_comparison(outPath,lon,lat,rcRate,valid,rcBin,continuousMap,discreteMap,labels,cap)
fig = figure('Color','w','Units','centimeters','Position',[1 1 24 38], ...
    'Renderer','painters','NumberTitle','off','Toolbar','none','MenuBar','none','Visible','off');
set(fig,'PaperUnits','centimeters','PaperPosition',[0 0 24 38], ...
    'PaperSize',[24 38],'InvertHardcopy','off');

mapPos = [0.055 0.715 0.89 0.24; 0.055 0.392 0.89 0.24; 0.055 0.069 0.89 0.24];
legPos = [0.16 0.668 0.68 0.020; 0.16 0.345 0.68 0.020; 0.09 0.022 0.82 0.020];
schemes = {'full','cap','bins'};
titles = {'A: Full range (0-0.75)',sprintf('B: Robust capped (P97.5 = %.3f)',cap),'C: Fixed scientific bins'};
for r = 1:3
    ax = axes(fig,'Position',mapPos(r,:),'Color','w');
    draw_scale_map(ax,schemes{r},lon,lat,rcRate,valid,rcBin,continuousMap,discreteMap,cap,10);
    text(ax,-0.01,1.045,titles{r},'Units','normalized','FontName','Arial', ...
        'FontSize',12.2,'FontWeight','bold','HorizontalAlignment','left', ...
        'VerticalAlignment','middle','Clipping','off');
    axL = axes(fig,'Position',legPos(r,:),'Color','w');
    draw_scale_legend(axL,schemes{r},continuousMap,discreteMap,labels,cap,8.4);
    xlabel(axL,'Right-censored fraction','FontName','Arial','FontSize',9.6);
    disable_toolbar(ax);
    disable_toolbar(axL);
end
drawnow;
print(fig,outPath,'-dpng','-r300');
close(fig);
end

function draw_scale_map(ax,scheme,lon,lat,rcRate,valid,rcBin,continuousMap,discreteMap,cap,markerSize)
switch scheme
    case 'full'
        setup_world_map(ax);
        [xp,yp] = equal_earth(lon(valid),lat(valid));
        scatter(ax,xp,yp,markerSize,rcRate(valid),'filled','MarkerEdgeColor','none','MarkerFaceAlpha',0.96);
        colormap(ax,continuousMap);
        caxis(ax,[0 0.75]);
        draw_map_overlay(ax);
    case 'cap'
        setup_world_map(ax);
        [xp,yp] = equal_earth(lon(valid),lat(valid));
        scatter(ax,xp,yp,markerSize,min(rcRate(valid),cap),'filled','MarkerEdgeColor','none','MarkerFaceAlpha',0.96);
        colormap(ax,continuousMap);
        caxis(ax,[0 cap]);
        draw_map_overlay(ax);
    case 'bins'
        draw_discrete_rc_map(ax,lon,lat,rcBin,valid,discreteMap,markerSize);
    otherwise
        error('Unknown scale scheme: %s',scheme);
end
end

function draw_scale_legend(ax,scheme,continuousMap,discreteMap,labels,cap,fontSize)
switch scheme
    case 'full'
        draw_continuous_strip(ax,continuousMap,0.75,[0 0.1 0.2 0.3 0.4 0.5 0.75], ...
            {'0','0.1','0.2','0.3','0.4','0.5','0.75'},fontSize);
    case 'cap'
        ticks = [0 0.025 0.05 0.075 0.10 0.125 cap];
        tickLabels = {'0','0.025','0.05','0.075','0.10','0.125',sprintf('>=%.3f',cap)};
        draw_continuous_strip(ax,continuousMap,cap,ticks,tickLabels,fontSize);
    case 'bins'
        draw_discrete_strip(ax,discreteMap,labels,fontSize);
end
end

function draw_continuous_strip(ax,cmap,maxValue,ticks,tickLabels,fontSize)
gradient = linspace(0,maxValue,512);
imagesc(ax,[0 maxValue],[0 1],gradient);
set(ax,'YTick',[],'XLim',[0 maxValue],'YLim',[0 1], ...
    'XTick',ticks,'XTickLabel',tickLabels,'TickDir','out', ...
    'TickLength',[0.008 0.008],'FontName','Arial','FontSize',fontSize, ...
    'LineWidth',0.55,'Box','on');
colormap(ax,cmap);
caxis(ax,[0 maxValue]);
end

function draw_discrete_strip(ax,colors,labels,fontSize)
n = size(colors,1);
hold(ax,'on');
axis(ax,[0 n 0 1]);
for k = 1:n
    rectangle(ax,'Position',[k-1 0 1 1],'FaceColor',colors(k,:), ...
        'EdgeColor','w','LineWidth',0.8);
end
set(ax,'YTick',[],'XTick',(0.5:1:n-0.5),'XTickLabel',labels, ...
    'TickDir','out','TickLength',[0.008 0.008],'FontName','Arial', ...
    'FontSize',fontSize,'LineWidth',0.55,'Box','on');
end

function draw_discrete_rc_map(ax,lon,lat,bin,valid,colors,markerSize)
setup_world_map(ax);
for k = 1:7
    idx = valid & bin==k;
    [xp,yp] = equal_earth(lon(idx),lat(idx));
    scatter(ax,xp,yp,markerSize,colors(k,:),'filled', ...
        'MarkerEdgeColor','none','MarkerFaceAlpha',0.97);
end
draw_map_overlay(ax);
end

function draw_category_legend(ax,colors,labels,fontSize)
axis(ax,[0 1 0 1]);
hold(ax,'on');
xPos = [0.08 0.395 0.68];
for k = 1:3
    scatter(ax,xPos(k),0.55,68,colors(k,:),'filled','MarkerEdgeColor','none');
    text(ax,xPos(k)+0.032,0.55,labels{k},'FontName','Arial', ...
        'FontSize',fontSize,'HorizontalAlignment','left', ...
        'VerticalAlignment','middle','Color',[0.12 0.13 0.15]);
end
axis(ax,[0 1 0 1]);
axis(ax,'off');
end

function draw_endpoint_composition(ax,pct,colors,labels)
axis(ax,[0 100 0 1]);
axis(ax,'off');
hold(ax,'on');
text(ax,0,0.97,'2024 endpoint composition','FontName','Arial','FontSize',10.2, ...
    'FontWeight','bold','HorizontalAlignment','left','VerticalAlignment','middle');
left = 0;
for k = 1:3
    rectangle(ax,'Position',[left 0.43 pct(k) 0.30], ...
        'FaceColor',colors(k,:),'EdgeColor','w','LineWidth',1.0);
    center = left+pct(k)/2;
    textColor = [0.10 0.11 0.13];
    if k==3
        textColor = [1 1 1];
    end
    text(ax,center,0.58,sprintf('%.1f%%',pct(k)),'FontName','Arial', ...
        'FontSize',9.4,'FontWeight','bold','Color',textColor, ...
        'HorizontalAlignment','center','VerticalAlignment','middle');
    text(ax,center,0.24,labels{k},'FontName','Arial','FontSize',7.9, ...
        'Color',[0.20 0.21 0.23],'HorizontalAlignment','center', ...
        'VerticalAlignment','middle');
    left = left+pct(k);
end
end

function draw_rc_distribution(ax,pct,colors)
hold(ax,'on');
bar(ax,1:7,pct,0.78,'FaceColor','flat','EdgeColor','none','CData',colors);
distLabels = {'0','(0,.05]','(.05,.10]','(.10,.15]', ...
    '(.15,.20]','(.20,.30]','>.30'};
set(ax,'XLim',[0.4 7.6],'YLim',[0 82],'YTick',[0 25 50 75], ...
    'XTick',1:7,'XTickLabel',distLabels, ...
    'FontName','Arial','FontSize',6.7,'TickDir','out','LineWidth',0.65, ...
    'Box','off','Layer','top','XTickLabelRotation',0,'TickLabelInterpreter','none');
ylabel(ax,'% of eligible cells','FontName','Arial','FontSize',8.8);
title(ax,'All-period distribution','FontName','Arial','FontSize',10.2, ...
    'FontWeight','bold','HorizontalAlignment','left');
ax.Title.Units = 'normalized';
ax.Title.Position(1) = 0;
for k = 1:7
    text(ax,k,pct(k)+1.5,sprintf('%.1f',pct(k)),'FontName','Arial', ...
        'FontSize',7.2,'HorizontalAlignment','center','VerticalAlignment','bottom', ...
        'Color',[0.18 0.19 0.21]);
end
end

function setup_world_map(ax)
hold(ax,'on');
set(ax,'Color','w','Visible','off','Layer','top');
axis(ax,'equal');
xlim(ax,[-2.75 2.75]);
ylim(ax,[-1.36 1.36]);
gridColor = [0.89 0.90 0.91];
for lon = -120:60:120
    lat = linspace(-89.5,89.5,500);
    [xg,yg] = equal_earth(lon*ones(size(lat)),lat);
    plot(ax,xg,yg,'Color',gridColor,'LineWidth',0.42);
end
for lat = -60:30:60
    lon = linspace(-180,180,800);
    [xg,yg] = equal_earth(lon,lat*ones(size(lon)));
    plot(ax,xg,yg,'Color',gridColor,'LineWidth',0.42);
end
draw_projection_frame(ax,[0.59 0.61 0.63],0.62);
end

function draw_map_overlay(ax)
coast = load('coastlines.mat');
[xc,yc] = equal_earth(coast.coastlon,coast.coastlat);
plot(ax,xc,yc,'Color',[0.25 0.27 0.29],'LineWidth',0.55);
draw_projection_frame(ax,[0.47 0.49 0.51],0.70);
end

function draw_projection_frame(ax,color,lineWidth)
latSide = linspace(-89.9,89.9,500);
lonTop = linspace(-180,180,800);
[x1,y1] = equal_earth(-180*ones(size(latSide)),latSide);
[x2,y2] = equal_earth(lonTop,89.9*ones(size(lonTop)));
[x3,y3] = equal_earth(180*ones(size(latSide)),fliplr(latSide));
[x4,y4] = equal_earth(fliplr(lonTop),-89.9*ones(size(lonTop)));
plot(ax,[x1 x2 x3 x4 x1(1)],[y1 y2 y3 y4 y1(1)], ...
    'Color',color,'LineWidth',lineWidth);
end

function panel_title(ax,label,titleText,FS)
text(ax,-0.015,1.045,label,'Units','normalized','FontName','Arial', ...
    'FontSize',FS.panel,'FontWeight','bold','HorizontalAlignment','left', ...
    'VerticalAlignment','middle','Clipping','off');
text(ax,0.045,1.045,titleText,'Units','normalized','FontName','Arial', ...
    'FontSize',FS.title,'FontWeight','bold','HorizontalAlignment','left', ...
    'VerticalAlignment','middle','Clipping','off');
end

function [x,y] = equal_earth(lon,lat)
A1 = 1.340264;
A2 = -0.081106;
A3 = 0.000893;
A4 = 0.003796;
M = sqrt(3)/2;
lambda = deg2rad(double(lon));
phi = deg2rad(double(lat));
theta = asin(M.*sin(phi));
theta2 = theta.^2;
theta6 = theta2.^3;
den = 3.*(9*A4.*theta.^8+7*A3.*theta6+3*A2.*theta2+A1);
x = 2*sqrt(3).*lambda.*cos(theta)./den;
y = A4.*theta.^9+A3.*theta.^7+A2.*theta.^3+A1.*theta;
end

function disable_toolbar(ax)
try
    axtoolbar(ax,{});
catch
end
try
    ax.Toolbar.Visible = 'off';
catch
end
end

function s = format_integer(n)
s = sprintf('%d',n);
insertAt = numel(s)-2;
while insertAt>1
    s = [s(1:insertAt-1) ',' s(insertAt:end)]; %#ok<AGROW>
    insertAt = insertAt-3;
end
end
