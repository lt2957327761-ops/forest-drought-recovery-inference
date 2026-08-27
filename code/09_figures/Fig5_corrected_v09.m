% Release copy: paths are supplied through NEE_RELEASE_DATA_ROOT and NEE_OUTPUT_ROOT.
function Fig5_corrected_v09()
% FIG5_CORRECTED_V09
% -------------------------------------------------------------------------
% Cleaner vertical layout for merged Fig. 5.
% Main quantitative evidence remains dominant in panel (a).
% The explanatory part is split into two lighter panels to avoid crowding:
%   (b) target population key
%   (c) interpretation guide
% -------------------------------------------------------------------------

close all; clc;

%% 1) PATHS
BASE = fullfile(getenv('NEE_RELEASE_DATA_ROOT'),'figure_inputs','Fig5');
DATA_DIR = BASE;
OUT_DIR = getenv('NEE_OUTPUT_ROOT');

if ~exist(OUT_DIR,'dir')
    mkdir(OUT_DIR);
end

F_POOL   = fullfile(DATA_DIR,'FIG5_panel_a_pooled_estimands.csv');
F_SCALE  = fullfile(DATA_DIR,'FIG5_panel_b_scale_specific.csv');
F_TARGET = fullfile(DATA_DIR,'FIG5_panel_c_target_definitions.csv');

assert(isfile(F_POOL),  'Missing: %s',F_POOL);
assert(isfile(F_SCALE), 'Missing: %s',F_SCALE);
assert(isfile(F_TARGET),'Missing: %s',F_TARGET);

%% 2) READ TABLES
Tpool   = readtable(F_POOL,'TextType','string');
Tscale  = readtable(F_SCALE,'TextType','string');
Ttarget = readtable(F_TARGET,'TextType','string');

Tpool.persistence_rule = strtrim(string(Tpool.persistence_rule));
Tpool.estimand         = strtrim(string(Tpool.estimand));
Tscale.persistence_rule = strtrim(string(Tscale.persistence_rule));
Tscale.spei_timescale   = strtrim(string(Tscale.spei_timescale));
Ttarget.target     = strtrim(string(Ttarget.target));
Ttarget.definition = strtrim(string(Ttarget.definition));
Ttarget.weight     = strtrim(string(Ttarget.weight));

scienceLockCheck(Tpool,Tscale,Ttarget);

%% 3) STYLE
C.ink        = [0.10 0.10 0.10];
C.mid        = [0.46 0.48 0.50];
C.light      = [0.82 0.84 0.87];
C.grid       = [0.92 0.93 0.94];
C.blue       = [0.10 0.44 0.72];
C.orange     = [0.88 0.54 0.08];
C.green      = [0.10 0.62 0.46];
C.purple     = [0.69 0.41 0.66];
C.panelBlue  = [0.96 0.98 0.995];
C.panelGray  = [0.985 0.985 0.985];
C.keyBG      = [0.985 0.987 0.990];
C.areaFill   = [1.00 0.985 0.955];

FS.panel = 15.0;
FS.title = 12.0;
FS.axis  = 10.8;
FS.tick  = 9.6;
FS.note  = 8.5;
FS.value = 8.6;
FS.group = 9.7;
FS.key   = 9.2;
FS.body  = 8.7;

MS.point = 58;
LW.axis  = 0.90;
LW.ci    = 1.9;
LW.null  = 1.0;

%% 4) FIGURE LAYOUT
% Match the square canvas stored in the finalized editable artwork.
fig = figure('Color','w', ...
    'Units','pixels', ...
    'Position',[40 24 878 876], ...
    'Renderer','painters');

set(fig,'PaperUnits','centimeters', ...
    'PaperPosition',[0 0 18.5 18.5], ...
    'PaperSize',[18.5 18.5], ...
    'InvertHardcopy','off');

% Vertical layout: one dominant top panel + two clean lower rows
% Preserve the finalized editable artwork's manually adjusted forest-plot
% position so long row labels remain fully visible.
POS.A = [0.198 0.41 0.783 0.50];
POS.B = [0.085 0.20 0.85 0.13];
POS.C = [0.085 0.055 0.85 0.10];

axA = axes(fig,'Position',POS.A);
axB = axes(fig,'Position',POS.B);
axC = axes(fig,'Position',POS.C);

%% 5) PANELS
makeIntegratedForest(axA,Tpool,Tscale,C,FS,MS,LW);
panelHeader(axA,'(a)','Integrated enrichment evidence',FS,C);

makeTargetPopulationKey(axB,Ttarget,C,FS);
panelHeader(axB,'(b)','Target population key',FS,C);

makeInterpretationGuide(axC,C,FS);
panelHeader(axC,'(c)','Interpretation guide',FS,C);

%% 6) EXPORT
stem = fullfile(OUT_DIR,'Fig5_corrected_v09');
savefig(fig,[stem '.fig']);

% Use the same auto paper geometry that reproduces the finalized editable
% artwork without clipping long row labels or crowding its legend.
set(fig,'PaperPositionMode','auto');
print(fig,[stem '.pdf'],'-dpdf','-painters');
print(fig,[stem '.png'],'-dpng','-r300');

fprintf('\nGenerated: %s\n',stem);
end

%% =========================================================================
function makeIntegratedForest(ax,Tpool,Tscale,C,FS,MS,LW)
cla(ax); hold(ax,'on');
styleAxis(ax,FS,C);

% Row coordinates (increasing for MATLAB YTick compatibility)
yScale = [1 2 3];
% The estimands below are ordered Event, Cell, Forest-cell area. Assign
% their coordinates top-to-bottom in the same order so labels and values
% remain keyed correctly in the rendered forest plot.
yPool  = [7 6 5];
off = 0.13;

poolEstimands = [ ...
    "POOLED_EVENT_WEIGHTED"
    "PIXEL_WEIGHTED_EQUAL_SCALE_WITHIN_PIXEL"
    "FOREST_CELL_AREA_WEIGHTED_EQUAL_SCALE_WITHIN_PIXEL"];

scaleNames = ["D6","D3","D1"];

% Background group bands
patch(ax,[0.47 3.28 3.28 0.47],[4.45 4.45 7.52 7.52], ...
    C.panelBlue,'EdgeColor','none');
patch(ax,[0.47 3.28 3.28 0.47],[0.48 0.48 3.52 3.52], ...
    C.panelGray,'EdgeColor','none');

% Guide grid and null
plot(ax,[1 1],[0.5 7.5],'--','Color',C.mid,'LineWidth',LW.null);
for xv = [0.5 0.75 1 1.5 2 3]
    plot(ax,[xv xv],[0.5 7.5],':','Color',C.grid,'LineWidth',0.7);
end

% --- pooled rows
for i = 1:3
    p1 = Tpool(Tpool.estimand==poolEstimands(i) & Tpool.persistence_rule=="P1",:);
    p2 = Tpool(Tpool.estimand==poolEstimands(i) & Tpool.persistence_rule=="P2",:);

    drawEstimate(ax,p1,yPool(i)+off,C.blue,'o',MS,LW);
    drawEstimate(ax,p2,yPool(i)-off,C.orange,'s',MS,LW);

    addValueText(ax,2.58,yPool(i)+off,p1,C.blue,FS);
    addValueText(ax,2.58,yPool(i)-off,p2,C.orange,FS);
end

% --- scale-specific rows
for i = 1:3
    p1 = Tscale(Tscale.spei_timescale==scaleNames(i) & Tscale.persistence_rule=="P1",:);
    p2 = Tscale(Tscale.spei_timescale==scaleNames(i) & Tscale.persistence_rule=="P2",:);

    drawEstimate(ax,p1,yScale(i)+off,C.blue,'o',MS,LW);
    drawEstimate(ax,p2,yScale(i)-off,C.orange,'s',MS,LW);

    addValueText(ax,2.58,yScale(i)+off,p1,C.blue,FS);
    addValueText(ax,2.58,yScale(i)-off,p2,C.orange,FS);
end

set(ax,'YTick',[1 2 3 5 6 7], ...
    'YTickLabel',{'SPEI-6','SPEI-3','SPEI-1', ...
                  'Forest-cell-area-weighted', ...
                  'Pixel-weighted', ...
                  'Event-weighted'}, ...
    'XScale','log', ...
    'XTick',[0.5 0.75 1 1.5 2 3], ...
    'XTickLabel',{'0.5','0.75','1','1.5','2','3'});

xlim(ax,[0.48 3.28]);
ylim(ax,[0.48 7.55]);
xlabel(ax,'enrichment ratio (log2 scale)','FontSize',FS.axis);

text(ax,0.52,7.35,'POOLED EVIDENCE', ...
    'FontName','Arial','FontSize',FS.group,'FontWeight','bold','Color',C.ink);
text(ax,0.52,3.35,'SCALE-SPECIFIC EVENT-WEIGHTED', ...
    'FontName','Arial','FontSize',FS.group,'FontWeight','bold','Color',C.ink);
text(ax,2.58,7.35,'ER [95% CI]', ...
    'FontName','Arial','FontSize',FS.group,'FontWeight','bold','Color',C.ink);
text(ax,1.02,7.00,'ER = 1', ...
    'FontName','Arial','FontSize',FS.note,'Color',C.mid);
text(ax,2.98,0.62,'500-repeat spatial-block bootstrap', ...
    'FontName','Arial','FontSize',FS.note,'Color',C.mid,'HorizontalAlignment','right');

addTargetGlyph(ax,0.56,7.0,'event',C,FS);
addTargetGlyph(ax,0.56,6.0,'cell',C,FS);
addTargetGlyph(ax,0.56,5.0,'area',C,FS);

h1 = scatter(ax,nan,nan,MS.point,'o','filled', ...
    'MarkerFaceColor',C.blue,'MarkerEdgeColor',C.blue);
h2 = scatter(ax,nan,nan,MS.point,'s','filled', ...
    'MarkerFaceColor',C.orange,'MarkerEdgeColor',C.orange);
lgd = legend(ax,[h1 h2],{'P1','P2'}, ...
    'Location','northeast', ...
    'Orientation','horizontal', ...
    'Box','off', ...
    'FontSize',FS.value);
% Preserve the manually positioned legend in the finalized editable file.
set(lgd,'Units','normalized','Position',[0.7350 0.8739 0.0812 0.0198]);
end

%% =========================================================================
function makeTargetPopulationKey(ax,T,C,FS)
cla(ax); hold(ax,'on'); axis(ax,[0 1 0 1]); axis(ax,'off');

rectangle(ax,'Position',[0.01 0.08 0.98 0.82], ...
    'Curvature',[0.010 0.030], ...
    'FaceColor',C.keyBG, ...
    'EdgeColor',[0.86 0.87 0.89], ...
    'LineWidth',0.9);

xName = 0.04; xGlyph = 0.16; xText = 0.34;

% Event
text(ax,xName,0.68,'Event', ...
    'FontName','Arial','FontSize',FS.key,'FontWeight','bold','Color',C.blue);
for i = 1:5
    scatter(ax,xGlyph+0.032*(i-1),0.70,22,'o','filled', ...
        'MarkerFaceColor',C.blue,'MarkerEdgeColor','none');
end
text(ax,xText,0.70,'each recovery event contributes equally', ...
    'FontName','Arial','FontSize',FS.body,'Color',C.mid,'VerticalAlignment','middle');

% Cell
text(ax,xName,0.42,'Cell', ...
    'FontName','Arial','FontSize',FS.key,'FontWeight','bold','Color',C.green);
for j = 1:3
    xx = xGlyph + 0.085*(j-1);
    rectangle(ax,'Position',[xx 0.365 0.052 0.11], ...
        'FaceColor','white','EdgeColor',C.green,'LineWidth',1.0);
    scatter(ax,xx+0.026,0.42,18,'o','filled', ...
        'MarkerFaceColor',C.blue,'MarkerEdgeColor','none');
end
text(ax,xText,0.42,'events are summarized within cells; cells contribute equally', ...
    'FontName','Arial','FontSize',FS.body,'Color',C.mid,'VerticalAlignment','middle');

% Forest-cell-area
text(ax,xName,0.18,'Forest-cell-area', ...
    'FontName','Arial','FontSize',FS.key,'FontWeight','bold','Color',C.orange);
widths = [0.050 0.075 0.105]; xs = [xGlyph xGlyph+0.095 xGlyph+0.205];
for j = 1:3
    rectangle(ax,'Position',[xs(j) 0.125 widths(j) 0.10], ...
        'FaceColor',C.areaFill,'EdgeColor',C.orange,'LineWidth',1.0);
end
text(ax,xText,0.18,'cell weights are proportional to grid-cell surface area only', ...
    'FontName','Arial','FontSize',FS.body,'Color',C.mid,'VerticalAlignment','middle');

% explicit boundary from source table
rowArea = T(T.target=="forest-cell-area",:);
if height(rowArea)==1
    txt = lower(string(rowArea.definition));
    if contains(txt,'forest fraction is not an area weight')
        text(ax,0.98,0.08,'Forest fraction is not an area weight.', ...
            'FontName','Arial','FontSize',FS.note,'Color',C.mid, ...
            'HorizontalAlignment','right','VerticalAlignment','middle');
    end
end
end

%% =========================================================================
function makeInterpretationGuide(ax,C,FS)
cla(ax); hold(ax,'on'); axis(ax,[0 1 0 1]); axis(ax,'off');

rectangle(ax,'Position',[0.01 0.12 0.98 0.76], ...
    'Curvature',[0.010 0.030], ...
    'FaceColor','white', ...
    'EdgeColor',[0.86 0.87 0.89], ...
    'LineWidth',0.9);

chips = { ...
    'Time origin', C.purple, 'OLD / R1 / R2'; ...
    'Persistence / censoring', C.orange, 'P1 / P2 / censoring rule'; ...
    'Information boundary', C.blue, 'forecast vs diagnostic'; ...
    'Target / uncertainty', C.green, 'estimand / weights / bootstrap'};

xList = [0.04 0.29 0.54 0.79];
for i = 1:4
    xx = xList(i);
    col = chips{i,2};
    rectangle(ax,'Position',[xx 0.37 0.18 0.27], ...
        'Curvature',[0.018 0.04], ...
        'FaceColor',[1 1 1], ...
        'EdgeColor',col, ...
        'LineWidth',1.1);
    text(ax,xx+0.012,0.56,chips{i,1}, ...
        'FontName','Arial','FontSize',FS.note+0.3,'FontWeight','bold', ...
        'Color',col,'HorizontalAlignment','left','VerticalAlignment','middle');
    text(ax,xx+0.012,0.44,chips{i,3}, ...
        'FontName','Arial','FontSize',FS.note,'Color',C.mid, ...
        'HorizontalAlignment','left','VerticalAlignment','middle');
end

text(ax,0.98,0.20, ...
    'These four design choices set how enrichment ratios should be interpreted; full details remain in the Methods and Table S8.', ...
    'FontName','Arial','FontSize',FS.note,'Color',C.mid, ...
    'HorizontalAlignment','right','VerticalAlignment','middle');
end

%% =========================================================================
function addTargetGlyph(ax,x,y,kind,C,FS)
switch lower(kind)
    case 'event'
        scatter(ax,[x x+0.04 x+0.08],[y y y],12,'o','filled', ...
            'MarkerFaceColor',C.blue,'MarkerEdgeColor','none');
    case 'cell'
        rectangle(ax,'Position',[x-0.01 y-0.12 0.06 0.24], ...
            'Curvature',0.02,'FaceColor','white','EdgeColor',C.green,'LineWidth',0.9);
        scatter(ax,x+0.02,y,12,'o','filled','MarkerFaceColor',C.blue,'MarkerEdgeColor','none');
    case 'area'
        rectangle(ax,'Position',[x-0.01 y-0.10 0.05 0.20], ...
            'Curvature',0.02,'FaceColor',C.areaFill,'EdgeColor',C.orange,'LineWidth',0.9);
        text(ax,x+0.015,y,'A','FontName','Arial','FontSize',FS.note-0.5, ...
            'Color',C.orange,'HorizontalAlignment','center','VerticalAlignment','middle');
end
end

%% =========================================================================
function addValueText(ax,x,y,row,color,FS)
text(ax,x,y,sprintf('%.2f [%.2f, %.2f]',row.point_estimate,row.ci_low,row.ci_high), ...
    'FontName','Arial','FontSize',FS.value,'Color',color, ...
    'HorizontalAlignment','left','VerticalAlignment','middle');
end

%% =========================================================================
function drawEstimate(ax,row,y,color,marker,MS,LW)
cap = 0.045;
plot(ax,[row.ci_low row.ci_high],[y y],'-','Color',color,'LineWidth',LW.ci);
plot(ax,[row.ci_low row.ci_low],[y-cap y+cap],'-','Color',color,'LineWidth',LW.ci);
plot(ax,[row.ci_high row.ci_high],[y-cap y+cap],'-','Color',color,'LineWidth',LW.ci);
scatter(ax,row.point_estimate,y,MS.point,marker,'filled', ...
    'MarkerFaceColor',color,'MarkerEdgeColor',color);
end

%% =========================================================================
function styleAxis(ax,FS,C)
set(ax,'FontName','Arial', ...
    'FontSize',FS.tick, ...
    'LineWidth',0.85, ...
    'TickDir','out', ...
    'TickLength',[0.018 0.018], ...
    'Box','off', ...
    'Color','w', ...
    'XColor',C.ink, ...
    'YColor',C.ink);
ax.Layer = 'top';
end

%% =========================================================================
function panelHeader(ax,letter,titleText,FS,C)
text(ax,-0.070,1.030,letter, ...
    'Units','normalized','Clipping','off', ...
    'FontName','Arial','FontSize',FS.panel,'FontWeight','bold', ...
    'Color',C.ink,'HorizontalAlignment','left','VerticalAlignment','bottom');
text(ax,0.028,1.030,titleText, ...
    'Units','normalized','Clipping','off', ...
    'FontName','Arial','FontSize',FS.title,'FontWeight','bold', ...
    'Color',C.ink,'HorizontalAlignment','left','VerticalAlignment','bottom');
end

%% =========================================================================
function scienceLockCheck(Tpool,Tscale,Ttarget)
assert(height(Tpool)==6,'SCIENCE LOCK FAIL: expected 6 pooled rows.');
assert(height(Tscale)==6,'SCIENCE LOCK FAIL: expected 6 scale-specific rows.');
assert(height(Ttarget)==3,'SCIENCE LOCK FAIL: expected 3 target definitions.');

estimands = [ ...
    "POOLED_EVENT_WEIGHTED"
    "PIXEL_WEIGHTED_EQUAL_SCALE_WITHIN_PIXEL"
    "FOREST_CELL_AREA_WEIGHTED_EQUAL_SCALE_WITHIN_PIXEL"];

refP1 = [1.551862 1.324476 1.230417];
refP2 = [1.414611 1.354169 1.287988];

for i = 1:3
    p1 = Tpool(Tpool.estimand==estimands(i) & Tpool.persistence_rule=="P1",:);
    p2 = Tpool(Tpool.estimand==estimands(i) & Tpool.persistence_rule=="P2",:);
    assert(height(p1)==1 && height(p2)==1,'SCIENCE LOCK FAIL: pooled row missing.');
    assert(abs(p1.point_estimate-refP1(i))<1e-5,'SCIENCE LOCK FAIL: P1 pooled ER mismatch.');
    assert(abs(p2.point_estimate-refP2(i))<1e-5,'SCIENCE LOCK FAIL: P2 pooled ER mismatch.');
end

scaleNames = ["D1","D3","D6"];
refSP1 = [1.354601 1.818212 1.315626];
refSP2 = [1.480411 1.382488 1.103631];

for i = 1:3
    p1 = Tscale(Tscale.spei_timescale==scaleNames(i) & Tscale.persistence_rule=="P1",:);
    p2 = Tscale(Tscale.spei_timescale==scaleNames(i) & Tscale.persistence_rule=="P2",:);
    assert(abs(p1.point_estimate-refSP1(i))<1e-5,'SCIENCE LOCK FAIL: P1 scale-specific ER mismatch.');
    assert(abs(p2.point_estimate-refSP2(i))<1e-5,'SCIENCE LOCK FAIL: P2 scale-specific ER mismatch.');
end

areaRow = Ttarget(Ttarget.target=="forest-cell-area",:);
assert(height(areaRow)==1,'SCIENCE LOCK FAIL: forest-cell-area target missing.');
assert(contains(lower(areaRow.definition),'grid-cell surface area'), ...
    'SCIENCE LOCK FAIL: area weighting definition mismatch.');
assert(contains(lower(areaRow.definition),'forest fraction is not an area weight'), ...
    'SCIENCE LOCK FAIL: forest-fraction boundary missing.');

fprintf('SCIENCE LOCK CHECK: PASS\n');
end
