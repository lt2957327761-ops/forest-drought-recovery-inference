% Release copy: paths are supplied through NEE_RELEASE_DATA_ROOT and NEE_OUTPUT_ROOT.
function Fig4_Nature_final_v09e_final()
% FIG4_NATURE_FINAL_V09E_FINAL
% -------------------------------------------------------------------------
% A4-style Nature redraw of Figure 4.
% Requested refinements relative to v03:
%   1) restore a SINGLE-HUE sequential palette for the map,
%   2) make the whole page feel like an A4 figure plate,
%   3) map occupies the upper half,
%   4) panels (b)-(e) occupy the lower half as four visually balanced panels,
%   5) panel (e) no longer uses square aspect, so its size matches the other
%      three quantitative panels.
%
% Frozen inputs only. No scientific values are recomputed.
% v09-final change: ONLY the display-class legend was moved out of the map axes.
% -------------------------------------------------------------------------

close all; clc;

%% PATHS
DATA_DIR = fullfile(getenv('NEE_RELEASE_DATA_ROOT'),'figure_inputs','Fig4');
OUT_DIR = getenv('NEE_OUTPUT_ROOT');
if ~exist(OUT_DIR,'dir'); mkdir(OUT_DIR); end

F_MAP   = fullfile(DATA_DIR,'FIG4_panel_a_geometry.csv');
F_FOLD  = fullfile(DATA_DIR,'FIG4_panel_b_fold_metrics.csv');
F_TIME  = fullfile(DATA_DIR,'FIG4_panel_c_temporal_metrics.csv');
F_HOLD  = fullfile(DATA_DIR,'FIG4_panel_d_forest_holdouts.csv');
F_CAL   = fullfile(DATA_DIR,'FIG4_panel_e_calibration_bins.csv');
F_CALS  = fullfile(DATA_DIR,'FIG4_panel_e_calibration_summary.csv');

assert(isfile(F_MAP),'Missing %s',F_MAP);
assert(isfile(F_FOLD),'Missing %s',F_FOLD);
assert(isfile(F_TIME),'Missing %s',F_TIME);
assert(isfile(F_HOLD),'Missing %s',F_HOLD);
assert(isfile(F_CAL),'Missing %s',F_CAL);
assert(isfile(F_CALS),'Missing %s',F_CALS);

%% READ TABLES
Tmap  = readtable(F_MAP, 'TextType','string');
Tfold = readtable(F_FOLD,'TextType','string');
Ttime = readtable(F_TIME,'TextType','string');
Thold = readtable(F_HOLD,'TextType','string');
Tcal  = readtable(F_CAL, 'TextType','string');
Tcals = readtable(F_CALS,'TextType','string');

Tfold.spei_timescale = strtrim(string(Tfold.spei_timescale));
Ttime.spei_timescale = strtrim(string(Ttime.spei_timescale));
Ttime.persistence_rule = strtrim(string(Ttime.persistence_rule));
Thold.spei_timescale = strtrim(string(Thold.spei_timescale));
Thold.held_group = strtrim(string(Thold.held_group));
Thold.display_support_range = strtrim(string(Thold.display_support_range));
Tcal.spei_timescale = strtrim(string(Tcal.spei_timescale));
Tcal.persistence_rule = strtrim(string(Tcal.persistence_rule));
Tcals.spei_timescale = strtrim(string(Tcals.spei_timescale));
Tcals.persistence_rule = strtrim(string(Tcals.persistence_rule));

scienceLockCheck(Tmap,Tfold,Ttime,Thold,Tcal,Tcals);

%% STYLE
C.ink    = [0.12 0.12 0.12];
C.mid    = [0.45 0.47 0.49];
C.light  = [0.82 0.84 0.86];
C.grid   = [0.90 0.91 0.92];
C.coast  = [0.42 0.44 0.46];
C.outln  = [0.68 0.70 0.72];
C.blue   = [0.09 0.40 0.67];
C.orange = [0.86 0.51 0.08];

% Sequential blue palette inspired by common top-journal map palettes
% (clearer and more elegant than multi-hue categorical colouring).
MAPCOL = [ ...
    0.84 0.92 0.97
    0.47 0.73 0.88
    0.08 0.42 0.70];

SCALECOL = [ ...
    0.71 0.84 0.92
    0.35 0.63 0.82
    0.09 0.40 0.67];

FS.panel  = 14.0;
FS.title  = 11.7;
FS.axis   = 10.0;
FS.tick   = 9.1;
FS.note   = 8.6;
FS.value  = 8.4;
FS.legend = 8.6;

MS.fold = 42;
MS.hold = 38;
MS.cal  = 26;
MS.map  = 12;

%% FIGURE + POSITIONS (A4-LIKE TOP-DOWN PLATE)
fig = figure('Color','w','Units','pixels','Position',[40 10 1400 1500],'Renderer','painters');
set(fig,'PaperUnits','centimeters','PaperPosition',[0 0 18.5 26.0], ...
    'PaperSize',[18.5 26.0],'InvertHardcopy','off');

% Refined A4-like layout:
% - map fills the full upper plate and matches the total width of panels below,
% - four lower quantitative panels are balanced in size and spacing.
POS.A   = [0.085 0.560 0.83 0.390];
POS.ALG = [0.260 0.515 0.48 0.045];   % moved upward; directly beneath the globe
POS.B   = [0.085 0.315 0.36 0.145];
POS.C   = [0.555 0.315 0.36 0.145];
POS.D   = [0.115 0.075 0.33 0.165];
POS.E   = [0.555 0.075 0.36 0.165];

axA   = axes(fig,'Position',POS.A);
axALG = axes(fig,'Position',POS.ALG);   % separate legend axes: NOT part of map axes
axB   = axes(fig,'Position',POS.B);
axC   = axes(fig,'Position',POS.C);
axD   = axes(fig,'Position',POS.D);
axE   = axes(fig,'Position',POS.E);

%% PANEL (a): MAP
makeMapPanel(axA,Tmap,MAPCOL,C,FS,MS);
panelHeader(axA,'(a)','Five-degree geographic grouping geometry',FS,C);

% IMPORTANT: draw display-class legend on a completely separate axes.
% This guarantees that the legend is physically below the map rather than
% being constrained by the map's Equal Earth coordinate system.
makeMapLegend(axALG,MAPCOL,C,FS);

%% PANEL (b): FOLD-LEVEL RMSE
makeFoldPanel(axB,Tfold,SCALECOL,C,FS,MS);
panelHeader(axB,'(b)','Fold-level duration RMSE',FS,C);

%% PANEL (c): FIXED 2021-2023 TRANSFER
makeTransferPanel(axC,Ttime,C,FS);
panelHeader(axC,'(c)','Fixed 2021–2023 duration transfer',FS,C);

%% PANEL (d): HELD-OUT FOREST TYPES
makeForestPanel(axD,Thold,SCALECOL,C,FS,MS);
panelHeader(axD,'(d)','Held-out forest types',FS,C);

%% PANEL (e): TEMPORAL HAZARD CALIBRATION
makeCalibrationPanel(axE,Tcal,Tcals,C,FS,MS);
panelHeader(axE,'(e)','Temporal hazard calibration',FS,C);

%% EXPORT
stem = fullfile(OUT_DIR,'Fig4_Nature_final_v09e_final');
savefig(fig,[stem '.fig']);
try
    exportgraphics(fig,[stem '.pdf'],'ContentType','vector','BackgroundColor','white');
catch
    print(fig,[stem '.pdf'],'-dpdf','-painters');
end
try
    exportgraphics(fig,[stem '.png'],'Resolution',600,'BackgroundColor','white');
catch
    print(fig,[stem '.png'],'-dpng','-r600');
end
fprintf('Saved %s.[fig|pdf|png]\n',stem);
end

%% ========================================================================
function makeMapPanel(ax,Tmap,MAPCOL,C,FS,MS)
cla(ax); hold(ax,'on');
lon = double(Tmap.lon);
lat = double(Tmap.lat);
cls = double(Tmap.renderer_display_class);

good = isfinite(lon) & isfinite(lat) & isfinite(cls);
lon = lon(good); lat = lat(good); cls = cls(good);

set(ax,'Color',[0.99 0.99 0.995]);

% Graticule
for phi = [-60 -30 0 30 60]
    glon = linspace(-180,180,361);
    glat = phi*ones(size(glon));
    [gx,gy] = equalEarth(glon,glat);
    plot(ax,gx,gy,'-','Color',C.grid,'LineWidth',0.38);
end
for lam = [-120 -60 0 60 120]
    glat = linspace(-89.5,89.5,260);
    glon = lam*ones(size(glat));
    [gx,gy] = equalEarth(glon,glat);
    plot(ax,gx,gy,'-','Color',C.grid,'LineWidth',0.38);
end

% Outline
olat = linspace(-90,90,361);
[xl,yl] = equalEarth(-180*ones(size(olat)),olat);
[xr,yr] = equalEarth( 180*ones(size(olat)),olat);
plot(ax,[xl xr(end:-1:1) xl(1)],[yl yr(end:-1:1) yl(1)],'-','Color',C.outln,'LineWidth',0.78);

% Class rendering in one hue, darker = more prominent class.
for k = 0:2
    idx = cls==k;
    if any(idx)
        [x,y] = equalEarth(lon(idx),lat(idx));
        scatter(ax,x,y,MS.map,'s','filled', ...
            'MarkerFaceColor',MAPCOL(k+1,:), ...
            'MarkerEdgeColor','none', ...
            'MarkerFaceAlpha',0.92);
    end
end

% Coastline
try
    S = load('coastlines');
    [cx,cy] = equalEarth(S.coastlon,S.coastlat);
    plot(ax,cx,cy,'-','Color',C.coast,'LineWidth',0.43);
catch
end

xlim(ax,[-2.78 2.78]); ylim(ax,[-1.39 1.39]);
axis(ax,'equal'); axis(ax,'off');

% No legend is drawn inside this map axes.
% The display-class legend is rendered by makeMapLegend() on axALG below.
end

%% ========================================================================
function makeMapLegend(ax,MAPCOL,C,FS)
% Dedicated Fig.2-style legend strip below the map.
% This axes uses simple 0-1 coordinates and is completely independent of
% the map projection, so it can never appear inside the geographic panel.

cla(ax); hold(ax,'on');
axis(ax,[0 1 0 1]);
axis(ax,'off');

labels = {'display class 1','display class 2','display class 3'};

% Three large colour swatches with labels underneath, centred as a group.
boxW = 0.145;
boxH = 0.33;
gap  = 0.055;
totalW = 3*boxW + 2*gap;
startX = (1-totalW)/2;
yBox = 0.48;

for i = 1:3
    x0 = startX + (i-1)*(boxW+gap);

    patch(ax, ...
        [x0 x0+boxW x0+boxW x0], ...
        [yBox yBox yBox+boxH yBox+boxH], ...
        MAPCOL(i,:), ...
        'EdgeColor','none');

    text(ax, x0+boxW/2, yBox-0.12, labels{i}, ...
        'FontName','Arial', ...
        'FontSize',FS.note+1.2, ...
        'FontWeight','normal', ...
        'Color',C.mid, ...
        'HorizontalAlignment','center', ...
        'VerticalAlignment','top');
end

end

%% ========================================================================
function makeFoldPanel(ax,Tfold,SCALECOL,C,FS,MS)
cla(ax); hold(ax,'on'); styleAxis(ax,FS,C);
SCALES_D = ["D1","D3","D6"];
SCALE_LABELS = {'SPEI-1','SPEI-3','SPEI-6'};
x = 1:3;

for i = 1:3
    Ti = Tfold(Tfold.spei_timescale==SCALES_D(i),:);
    y = Ti.rmse;
    jit = linspace(-0.10,0.10,height(Ti))';
    plot(ax,[x(i) x(i)],[min(y) max(y)],'-','Color',C.grid,'LineWidth',0.95);
    scatter(ax,x(i)+jit,y,MS.fold,'o','filled', ...
        'MarkerFaceColor',SCALECOL(i,:), 'MarkerEdgeColor',C.blue,'LineWidth',0.8);
    med = unique(Ti.renderer_scale_median_rmse); med = med(1);
    plot(ax,[x(i)-0.18 x(i)+0.18],[med med],'-','Color',C.ink,'LineWidth',2.0);
    text(ax,x(i),med+0.020,sprintf('%.2f',med),'FontName','Arial','FontSize',FS.value, ...
        'FontWeight','bold','Color',C.ink,'HorizontalAlignment','center','VerticalAlignment','bottom');
end
xlim(ax,[0.6 3.4]);
ylim(ax,[min(Tfold.rmse)-0.05 max(Tfold.rmse)+0.06]);
set(ax,'XTick',x,'XTickLabel',SCALE_LABELS,'YGrid','on','GridColor',C.grid);
ylabel(ax,'RMSE (months)','FontSize',FS.axis);
end

%% ========================================================================
function makeTransferPanel(ax,Ttime,C,FS)
cla(ax); hold(ax,'on'); styleAxis(ax,FS,C);
SCALES_D = ["D1","D3","D6"];
SCALE_LABELS = {'SPEI-1','SPEI-3','SPEI-6'};
x = 1:3; W = 0.28;

p1 = nan(1,3); p2 = nan(1,3);
for i = 1:3
    p1(i) = Ttime.r2(Ttime.spei_timescale==SCALES_D(i) & Ttime.persistence_rule=="P1");
    p2(i) = Ttime.r2(Ttime.spei_timescale==SCALES_D(i) & Ttime.persistence_rule=="P2");
end

b1 = bar(ax,x-W/2,p1,W,'FaceColor',C.blue,'EdgeColor','none');
b2 = bar(ax,x+W/2,p2,W,'FaceColor',C.orange,'EdgeColor','none');
plot(ax,[0.5 3.5],[0 0],'-','Color',C.mid,'LineWidth',0.9);
for i = 1:3
    addSignedValue(ax,x(i)-W/2,p1(i),FS.value,C.blue);
    addSignedValue(ax,x(i)+W/2,p2(i),FS.value,C.orange);
end
xlim(ax,[0.5 3.5]);
ylim(ax,[-0.030 0.028]);
set(ax,'XTick',x,'XTickLabel',SCALE_LABELS,'YGrid','on','GridColor',C.grid);
ylabel(ax,'R^2','FontSize',FS.axis);
legend(ax,[b1 b2],{'P1','P2'},'Location','northeast','Orientation','horizontal','Box','off','FontSize',FS.legend);
end

%% ========================================================================
function makeForestPanel(ax,Thold,SCALECOL,C,FS,MS)
cla(ax); hold(ax,'on'); styleAxis(ax,FS,C);
SCALES_D = ["D1","D3","D6"];
SCALE_LABELS = {'SPEI-1','SPEI-3','SPEI-6'};
FOREST_NAMES = ["Mixed forest";"Evergreen needleleaf forest";"Evergreen broadleaf forest"; ...
    "Deciduous needleleaf forest";"Deciduous broadleaf forest"];
FOREST_ABBR = {'MF','ENF','EBF','DNF','DBF'};
ypos = 1:5;

% Build TRUE y-axis tick labels so forest labels sit outside the axes.
forestTickLabels = cell(1,5);

for j = 1:5
    Tg = Thold(Thold.held_group==FOREST_NAMES(j),:);
    vals = nan(1,3);
    for i = 1:3
        vals(i) = Tg.rmse(Tg.spei_timescale==SCALES_D(i));
    end

    plot(ax,[min(vals) max(vals)],[ypos(j) ypos(j)],'-','Color',C.light,'LineWidth',2.0);

    for i = 1:3
        scatter(ax,vals(i),ypos(j),MS.hold,'o','filled', ...
            'MarkerFaceColor',SCALECOL(i,:), ...
            'MarkerEdgeColor','none');
    end

    med = Tg.renderer_group_median_rmse(1);
    plot(ax,[med med],[ypos(j)-0.22 ypos(j)+0.22],'-','Color',C.ink,'LineWidth',1.8);

    support = char(string(Tg.display_support_range(1)));
    forestTickLabels{j} = sprintf('%s  (%s)',FOREST_ABBR{j},support);
end

% Key fix: use actual y tick labels, not text() placed inside data coordinates.
set(ax, ...
    'YTick',ypos, ...
    'YTickLabel',forestTickLabels, ...
    'YDir','reverse', ...
    'XGrid','on', ...
    'GridColor',C.grid);

% Leave only the data area inside the axes; labels now sit outside automatically.
xlim(ax,[0 2.02]);
ylim(ax,[0.5 5.5]);
xlabel(ax,'RMSE (months)','FontSize',FS.axis);

% Move scale legend to the UPPER-RIGHT with wider spacing.
% Because YDir='reverse', small y values are visually at the top.
legendY = 0.72;
legendX = [1.13 1.48 1.83];

for i = 1:3
    scatter(ax,legendX(i),legendY,MS.hold,'o','filled', ...
        'MarkerFaceColor',SCALECOL(i,:), ...
        'MarkerEdgeColor','none');

    text(ax,legendX(i)+0.065,legendY,SCALE_LABELS{i}, ...
        'FontName','Arial', ...
        'FontSize',FS.note, ...
        'VerticalAlignment','middle', ...
        'HorizontalAlignment','left', ...
        'Color',C.ink);
end
end

%% ========================================================================
function makeCalibrationPanel(ax,Tcal,Tcals,C,FS,MS)
cla(ax); hold(ax,'on'); styleAxis(ax,FS,C);
plot(ax,[0 1],[0 1],'--','Color',C.mid,'LineWidth',0.95);
SCALES_D = ["D1","D3","D6"];
SCALE_LABELS = {'SPEI-1','SPEI-3','SPEI-6'};
BLUE_SHADE = [0.72 0.84 0.92; 0.39 0.66 0.82; 0.09 0.40 0.67];
ORANGE_SHADE = [0.97 0.86 0.66; 0.93 0.71 0.33; 0.86 0.51 0.08];

for i = 1:3
    P1 = sortrows(Tcal(Tcal.spei_timescale==SCALES_D(i) & Tcal.persistence_rule=="P1",:),'bin');
    P2 = sortrows(Tcal(Tcal.spei_timescale==SCALES_D(i) & Tcal.persistence_rule=="P2",:),'bin');
    plot(ax,P1.mean_predicted_probability,P1.observed_recovery_fraction,'-','Color',BLUE_SHADE(i,:),'LineWidth',1.4);
    scatter(ax,P1.mean_predicted_probability,P1.observed_recovery_fraction,MS.cal,'o','filled','MarkerFaceColor',BLUE_SHADE(i,:), 'MarkerEdgeColor',C.blue,'LineWidth',0.45);
    plot(ax,P2.mean_predicted_probability,P2.observed_recovery_fraction,'-','Color',ORANGE_SHADE(i,:),'LineWidth',1.4);
    scatter(ax,P2.mean_predicted_probability,P2.observed_recovery_fraction,MS.cal,'s','filled','MarkerFaceColor',ORANGE_SHADE(i,:), 'MarkerEdgeColor',C.orange,'LineWidth',0.45);
end

xlim(ax,[0 0.80]); ylim(ax,[0 0.80]);
set(ax,'XGrid','on','YGrid','on','GridColor',C.grid);
xlabel(ax,'mean predicted probability','FontSize',FS.axis);
ylabel(ax,'observed recovery fraction','FontSize',FS.axis);

h1 = scatter(ax,nan,nan,40,'o','filled','MarkerFaceColor',C.blue,'MarkerEdgeColor',C.blue);
h2 = scatter(ax,nan,nan,40,'s','filled','MarkerFaceColor',C.orange,'MarkerEdgeColor',C.orange);
legend(ax,[h1 h2],{'P1','P2'},'Location','northwest','Orientation','horizontal','Box','off','FontSize',FS.legend);

% compact gap note placed at upper-right, but not dominating the panel
for i = 1:3
    s1 = Tcals(Tcals.spei_timescale==SCALES_D(i) & Tcals.persistence_rule=="P1",:);
    s2 = Tcals(Tcals.spei_timescale==SCALES_D(i) & Tcals.persistence_rule=="P2",:);
    text(ax,0.98,0.95-0.08*(i-1),sprintf('%s  |gap| %.3f / %.3f',SCALE_LABELS{i},s1.absolute_calibration_gap,s2.absolute_calibration_gap), ...
        'Units','normalized','FontName','Arial','FontSize',FS.note,'Color',C.mid,'HorizontalAlignment','right','VerticalAlignment','top');
end
end

%% ========================================================================
function [x,y] = equalEarth(lonDeg,latDeg)
lon = deg2rad(double(lonDeg));
lat = deg2rad(double(latDeg));
A1 = 1.340264; A2 = -0.081106; A3 = 0.000893; A4 = 0.003796;
theta = asin(sqrt(3).*sin(lat)./2);
theta2 = theta.^2;
denom = 3.*(9.*A4.*theta2.^4 + 7.*A3.*theta2.^3 + 3.*A2.*theta2 + A1);
x = 2.*sqrt(3).*lon.*cos(theta)./denom;
y = A4.*theta.^9 + A3.*theta.^7 + A2.*theta.^3 + A1.*theta;
end

%% ========================================================================
function styleAxis(ax,FS,C)
set(ax,'FontName','Arial','FontSize',FS.tick,'LineWidth',0.85,'TickDir','out', ...
    'TickLength',[0.018 0.018],'Box','off','Color','w','XColor',C.ink,'YColor',C.ink);
ax.Layer = 'top';
end

%% ========================================================================
function panelHeader(ax,letter,titleText,FS,C)
text(ax,-0.08,1.055,letter,'Units','normalized','Clipping','off','FontName','Arial', ...
    'FontSize',FS.panel,'FontWeight','bold','Color',C.ink,'HorizontalAlignment','left','VerticalAlignment','bottom');
text(ax,0.045,1.055,titleText,'Units','normalized','Clipping','off','FontName','Arial', ...
    'FontSize',FS.title,'FontWeight','bold','Color',C.ink,'HorizontalAlignment','left','VerticalAlignment','bottom');
end

%% ========================================================================
function addSignedValue(ax,x,v,fontSize,color)
if v >= 0
    y = v + 0.0012; va = 'bottom';
else
    y = v - 0.0016; va = 'top';
end
text(ax,x,y,sprintf('%.3f',v),'FontName','Arial','FontSize',fontSize,'FontWeight','bold', ...
    'Color',color,'HorizontalAlignment','center','VerticalAlignment',va);
end

%% ========================================================================
function scienceLockCheck(Tmap,Tfold,Ttime,Thold,Tcal,Tcals)
assert(height(Tmap)==16616,'SCIENCE LOCK FAIL: expected 16,616 map geometry rows.');
assert(all(ismember(unique(double(Tmap.renderer_display_class)),[0 1 2])), ...
    'SCIENCE LOCK FAIL: unexpected geometry display class.');
assert(height(Tfold)==15,'SCIENCE LOCK FAIL: expected 15 spatial fold metric rows.');
assert(height(Ttime)==6,'SCIENCE LOCK FAIL: expected 6 temporal RF rows.');
assert(height(Thold)==15,'SCIENCE LOCK FAIL: expected 15 forest holdout rows.');
assert(height(Tcal)==60,'SCIENCE LOCK FAIL: expected 60 calibration-bin rows.');
assert(height(Tcals)==6,'SCIENCE LOCK FAIL: expected 6 calibration summary rows.');
fprintf('SCIENCE LOCK CHECK: PASS\n');
end
