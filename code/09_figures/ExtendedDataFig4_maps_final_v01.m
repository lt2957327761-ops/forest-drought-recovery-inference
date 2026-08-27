% Release copy: paths are supplied through NEE_RELEASE_DATA_ROOT and NEE_OUTPUT_ROOT.
function FigS4_maps_final_v01()
%FIGS4_MAPS_FINAL_V01 A4 portrait map-only evidence-screen figure.
%
% SCIENCE LOCK / PROVENANCE
%   Frozen source 1 (agreement maps):
%     NEE_RELEASE_DATA_ROOT/figure_inputs/...
%     FIGS5_current_agreement_maps.csv
%   Frozen source 2 (evidence-status map):
%     NEE_RELEASE_DATA_ROOT/figure_inputs/...
%     FIGS6_current_evidence_maps.csv
%
%   A = slow recovery; B = incomplete before the next drought;
%   C = high recurrence. Recovery-risk agreement is the archived
%   max(A,B) agreement count across three SPEI scales. Recurrence-
%   monitoring agreement is the archived C agreement count across the
%   same three scales. Evidence status retains the archived conservative
%   LIMITED / CONDITIONAL / SUPPORTED definition. This script changes
%   display only: no threshold, class, aggregation or conclusion is changed.

close all force;

sourceRoot = fullfile(getenv('NEE_RELEASE_DATA_ROOT'),'figure_inputs');
agreementFile = fullfile(sourceRoot,'FIGS5_SOURCE_PACK_20260818', ...
    '03_source_data','matlab_ready','FIGS5_current_agreement_maps.csv');
statusFile = fullfile(sourceRoot,'FIGS6_SOURCE_PACK_20260818', ...
    '03_source_data','matlab_ready','FIGS6_current_evidence_maps.csv');
outDir = fileparts(mfilename('fullpath'));

pngPath = fullfile(outDir,'FigS4_maps_final_v01.png');
pdfPath = fullfile(outDir,'FigS4_maps_final_v01.pdf');
svgPath = fullfile(outDir,'FigS4_maps_final_v01.svg');
figPath = fullfile(outDir,'FigS4_maps_final_v01.fig');

must_exist({agreementFile,statusFile});
A = readtable(agreementFile,'VariableNamingRule','preserve','TextType','string');
E = readtable(statusFile,'VariableNamingRule','preserve','TextType','string');

assert(all(ismember({'lon','lat','risk','monitoring'},A.Properties.VariableNames)), ...
    'Agreement-map source schema is incomplete.');
assert(all(ismember({'lon','lat','application_status','status_code'},E.Properties.VariableNames)), ...
    'Evidence-status source schema is incomplete.');

lon = numeric_column(A.lon);
lat = numeric_column(A.lat);
risk = numeric_column(A.risk);
monitoring = numeric_column(A.monitoring);
statusLon = numeric_column(E.lon);
statusLat = numeric_column(E.lat);
statusCode = numeric_column(E.status_code);
statusName = string(E.application_status);

% Science-lock checks against the frozen archived tables.
assert(height(A)==16616 && height(E)==16616,'Unexpected archived map row count.');
assert(isequal(arrayfun(@(k)sum(risk==k),0:3),[14869 1379 307 61]), ...
    'Recovery-risk agreement values differ from the frozen source.');
assert(isequal(arrayfun(@(k)sum(monitoring==k),0:3),[10599 3060 1970 987]), ...
    'Recurrence-monitoring values differ from the frozen source.');
assert(isequal(arrayfun(@(k)sum(statusCode==k),1:3),[2783 13833 0]), ...
    'Evidence-status values differ from the frozen source.');
assert(all((statusCode==1 & statusName=="LIMITED") | ...
           (statusCode==2 & statusName=="CONDITIONAL") | ...
           (statusCode==3 & statusName=="SUPPORTED")), ...
    'Evidence-status labels and codes are inconsistent.');

% Color definitions: discrete, clean and consistent with the S2 redraw.
PURPLE = [248 247 251; 218 218 235; 158 154 200; 84 39 143] / 255;
BLUE = [247 251 255; 198 219 239; 107 174 214; 8 81 156] / 255;
STATUS = [166 166 166; 230 137 0; 18 153 130] / 255;
STATUS_LABELS = {'LIMITED','CONDITIONAL','SUPPORTED'};

FS.panel = 15;
FS.title = 12.5;
FS.note = 9.2;
FS.legend = 9.3;
FS.legendLabel = 10.4;
FS.strip = 8.6;

% A4-portrait layout parameters. Each map occupies a complete row.
POS.A = [0.045 0.720 0.91 0.215];
POS.ALEG = [0.18 0.680 0.64 0.030];
POS.B = [0.045 0.401 0.91 0.215];
POS.BLEG = [0.18 0.361 0.64 0.030];
POS.C = [0.045 0.082 0.91 0.215];
POS.CLEG = [0.225 0.042 0.55 0.030];
POS.STRIP = [0.055 0.003 0.89 0.033];

fig = figure('Color','w','Units','centimeters','Position',[1 1 18.5 25.5], ...
    'Renderer','painters','Name','S4 map products v01','NumberTitle','off', ...
    'Toolbar','none','MenuBar','none','Visible','off');
set(fig,'PaperUnits','centimeters','PaperPosition',[0 0 18.5 25.5], ...
    'PaperSize',[18.5 25.5],'InvertHardcopy','off');

% (a) Recovery-risk agreement: archived max(A,B) count, 0--3.
axA = axes(fig,'Position',POS.A,'Color','w');
draw_agreement_map(axA,lon,lat,risk,PURPLE,12.5);
panel_title_fig(fig,0.959,'(a)','Recovery-risk agreement', ...
    sprintf('max(A, B) across three SPEI scales  |  n = %s cells',format_integer(height(A))),FS);
axAL = axes(fig,'Position',POS.ALEG,'Color','w');
draw_discrete_strip(axAL,PURPLE,{'0','1','2','3'},FS.legend);

% (b) Recurrence-monitoring agreement: archived C count, 0--3.
axB = axes(fig,'Position',POS.B,'Color','w');
draw_agreement_map(axB,lon,lat,monitoring,BLUE,12.5);
panel_title_fig(fig,0.640,'(b)','Recurrence-monitoring agreement', ...
    sprintf('C across three SPEI scales  |  n = %s cells',format_integer(height(A))),FS);
axBL = axes(fig,'Position',POS.BLEG,'Color','w');
draw_discrete_strip(axBL,BLUE,{'0','1','2','3'},FS.legend);

% (c) Conservative archived evidence status. The Amazon audit constraint is
% marked in the main map; a competing inset is intentionally not used.
axC = axes(fig,'Position',POS.C,'Color','w');
draw_status_map(axC,statusLon,statusLat,statusCode,STATUS,13.0);
draw_amazon_window(axC);
panel_title_fig(fig,0.321,'(c)','Conservative evidence status', ...
    sprintf('archived support / ER / AUC rule  |  n = %s cells',format_integer(height(E))),FS);
axCL = axes(fig,'Position',POS.CLEG,'Color','w');
draw_status_legend(axCL,STATUS,STATUS_LABELS,FS.legend);

% Compact interpretation strip replaces the former stand-alone logic panel.
stripText = { ...
    'A = slow recovery; B = incomplete before next drought; C = high recurrence.', ...
    'Recovery risk = max(A, B); recurrence monitoring = C across three scales. Evidence summaries - not management maps.'};
annotation(fig,'textbox',POS.STRIP,'String',stripText,'LineStyle','-', ...
    'EdgeColor',[0.86 0.87 0.88],'BackgroundColor',[0.965 0.968 0.972], ...
    'Margin',3,'FontName','Arial','FontSize',7.7,'Color',[0.22 0.23 0.25], ...
    'HorizontalAlignment','left','VerticalAlignment','middle');

drawnow;
allAxes = findall(fig,'Type','axes');
for i = 1:numel(allAxes)
    disable_toolbar(allAxes(i));
end
drawnow;

set(fig,'Visible','on','WindowStyle','normal');
set(fig,'MenuBar','figure','ToolBar','figure');
drawnow;
savefig(fig,figPath);

print(fig,pdfPath,'-dpdf','-painters');
print(fig,svgPath,'-dsvg','-painters');
print(fig,pngPath,'-dpng','-r600');

fprintf('Created map figure outputs:\n%s\n%s\n%s\n%s\n',figPath,pngPath,pdfPath,svgPath);
end

function draw_agreement_map(ax,lon,lat,value,colors,markerSize)
setup_world_map(ax);
for k = 0:3
    idx = isfinite(lon) & isfinite(lat) & value==k;
    [xp,yp] = equal_earth(lon(idx),lat(idx));
    scatter(ax,xp,yp,markerSize,colors(k+1,:),'filled', ...
        'MarkerEdgeColor','none');
end
draw_map_overlay(ax);
end

function draw_status_map(ax,lon,lat,status,colors,markerSize)
setup_world_map(ax);
for k = 1:3
    idx = isfinite(lon) & isfinite(lat) & status==k;
    [xp,yp] = equal_earth(lon(idx),lat(idx));
    scatter(ax,xp,yp,markerSize,colors(k,:),'filled','MarkerEdgeColor','none');
end
draw_map_overlay(ax);
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

function draw_amazon_window(ax)
bottomLon = linspace(-75,-50,100);
rightLat = linspace(-15,5,80);
topLon = linspace(-50,-75,100);
leftLat = linspace(5,-15,80);
boxLon = [bottomLon, -50*ones(size(rightLat)), topLon, -75*ones(size(leftLat))];
boxLat = [-15*ones(size(bottomLon)), rightLat, 5*ones(size(topLon)), leftLat];
[xb,yb] = equal_earth(boxLon,boxLat);
accent = [0.72 0.18 0.18];
plot(ax,xb,yb,'--','Color',accent,'LineWidth',1.15);
[xt,yt] = equal_earth(-62.5,7.5);
text(ax,xt,yt,'Amazon audit window','FontName','Arial','FontSize',7.8, ...
    'FontWeight','bold','Color',accent,'HorizontalAlignment','center', ...
    'VerticalAlignment','bottom');
end

function draw_discrete_strip(ax,colors,labels,fontSize)
n = size(colors,1);
hold(ax,'on');
axis(ax,[0 n 0 1]);
axis(ax,'off');
for k = 1:n
    rectangle(ax,'Position',[k-1 0.54 1 0.40],'FaceColor',colors(k,:), ...
        'EdgeColor','w','LineWidth',0.9);
    text(ax,k-0.5,0.39,labels{k},'FontName','Arial','FontSize',fontSize, ...
        'Color',[0.12 0.13 0.15],'HorizontalAlignment','center', ...
        'VerticalAlignment','middle');
end
text(ax,n/2,0.08,'Number of SPEI scales','FontName','Arial', ...
    'FontSize',fontSize+0.8,'Color',[0.12 0.13 0.15], ...
    'HorizontalAlignment','center','VerticalAlignment','middle');
end

function draw_status_legend(ax,colors,labels,fontSize)
axis(ax,[0 1 0 1]);
axis(ax,'off');
hold(ax,'on');
x = [0.08 0.39 0.72];
for k = 1:3
    scatter(ax,x(k),0.53,72,colors(k,:),'filled','MarkerEdgeColor','none');
    text(ax,x(k)+0.035,0.53,labels{k},'FontName','Arial','FontSize',fontSize, ...
        'Color',[0.12 0.13 0.15],'HorizontalAlignment','left', ...
        'VerticalAlignment','middle');
end
end

function panel_title_fig(fig,mainY,label,titleText,noteText,FS)
annotation(fig,'textbox',[0.045 mainY 0.055 0.025],'String',label, ...
    'LineStyle','none','Margin',0,'FontName','Arial','FontSize',FS.panel, ...
    'FontWeight','bold','Color',[0.12 0.13 0.15], ...
    'HorizontalAlignment','left','VerticalAlignment','middle');
annotation(fig,'textbox',[0.098 mainY 0.82 0.025],'String',titleText, ...
    'LineStyle','none','Margin',0,'FontName','Arial','FontSize',FS.title, ...
    'FontWeight','bold','Color',[0.12 0.13 0.15], ...
    'HorizontalAlignment','left','VerticalAlignment','middle');
annotation(fig,'textbox',[0.098 mainY-0.017 0.82 0.016],'String',noteText, ...
    'LineStyle','none','Margin',0,'FontName','Arial','FontSize',FS.note, ...
    'Color',[0.38 0.40 0.43],'HorizontalAlignment','left', ...
    'VerticalAlignment','middle');
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

function v = numeric_column(v)
if isnumeric(v)
    v = double(v);
else
    v = str2double(string(v));
end
end

function must_exist(paths)
for i = 1:numel(paths)
    assert(isfile(paths{i}),'Missing frozen source: %s',paths{i});
end
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
