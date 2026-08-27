% Release copy: paths are supplied through NEE_RELEASE_DATA_ROOT and NEE_OUTPUT_ROOT.
function Fig2_Nature_final_v03()
% FIG2_NATURE_FINAL_V03
% Figure 2 redesign for:
% "Global satellite estimates of forest drought recovery are design-dependent"
%
% V03 major layout change
% -------------------------------------------------------------------------
% 1) All six world maps are moved to the LEFT MAJOR COLUMN so they dominate
%    the full figure.
% 2) The four statistical panels (b)-(e) are moved to the RIGHT COLUMN as a
%    compact 2 x 2 block.
% 3) Maps are further enlarged and remain the visual focus.
% 4) Panel (a) still fixes the V07 science issue by enforcing:
%       recovery_definition == "R2"
% 5) Map colours remain discrete duration classes for stronger visual
%    separation.
%
% OUTPUT
% -------------------------------------------------------------------------
% Fig2_Nature_final_v03.fig
% Fig2_Nature_final_v03.pdf
% Fig2_Nature_final_v03.png
%
% -------------------------------------------------------------------------

close all; clc;

%% ========================================================================
%  1. USER PATHS
%  ========================================================================

DATA_DIR = fullfile(getenv('NEE_RELEASE_DATA_ROOT'),'figure_inputs','Fig2');
OUT_DIR = getenv('NEE_OUTPUT_ROOT');

if ~exist(OUT_DIR,'dir')
    mkdir(OUT_DIR);
end

%% ========================================================================
%  2. VISUAL SYSTEM
%  ========================================================================

COL.P1      = [0.000, 0.447, 0.698];
COL.P2      = [0.902, 0.624, 0.000];
COL.INK     = [0.10, 0.10, 0.10];
COL.MID     = [0.46, 0.48, 0.50];
COL.LIGHT   = [0.76, 0.79, 0.81];
COL.GRID    = [0.89, 0.90, 0.91];
COL.OUTLINE = [0.55, 0.57, 0.59];
COL.COAST   = [0.28, 0.29, 0.30];
COL.WHITE   = [1, 1, 1];

% Stronger discrete classes for maps
MAP_COLORS = [ ...
    255 255 204
    199 233 180
    127 205 187
     65 182 196
     44 127 184
     37  52 148] ./ 255;
MAP_LABELS = {'\leq1','1-2','2-3','3-4','4-5','>5'};

FS.panel      = 14.0;
FS.panelTitle = 11.2;
FS.colHeader  = 11.0;
FS.rowHeader  = 10.2;
FS.axis       = 9.8;
FS.tick       = 9.0;
FS.note       = 8.2;
FS.value      = 8.4;
FS.legend     = 8.7;

LW.main    = 1.35;
LW.connect = 1.10;
LW.grid    = 0.30;
LW.outline = 0.60;
LW.coast   = 0.43;

MS.P1  = 42;
MS.P2  = 44;
MS.map = 10.0;

FIG_W_CM = 18.0;
FIG_H_CM = 24.5;

%% ========================================================================
%  3. LOAD FROZEN DATA
%  ========================================================================

mapT = readtable(fullfile(DATA_DIR,'FIG2_panel_a_current_map_rows.csv'), ...
    'TextType','string');
sumT = readtable(fullfile(DATA_DIR,'FIG2_panel_b_median_upper_tail.csv'), ...
    'TextType','string');
tailT = readtable(fullfile(DATA_DIR,'FIG2_panel_c_tail_probabilities.csv'), ...
    'TextType','string');
countT = readtable(fullfile(DATA_DIR,'FIG2_panel_d_completion_counts.csv'), ...
    'TextType','string');
censorT = readtable(fullfile(DATA_DIR,'FIG2_panel_e_right_censor_rates.csv'), ...
    'TextType','string');

% Science repair: only R2 rows are valid for Panel (a)
mapT = mapT(strcmpi(strtrim(mapT.recovery_definition),"R2"),:);

scienceLockCheck(mapT,sumT,tailT,countT,censorT);

SCALES = ["D1","D3","D6"];
SCALE_LABEL = ["SPEI-1","SPEI-3","SPEI-6"];

%% ========================================================================
%  4. FIGURE CANVAS
%  ========================================================================

fig = figure( ...
    'Color','w', ...
    'Units','centimeters', ...
    'Position',[1 1 FIG_W_CM FIG_H_CM], ...
    'PaperUnits','centimeters', ...
    'PaperPosition',[0 0 FIG_W_CM FIG_H_CM], ...
    'PaperSize',[FIG_W_CM FIG_H_CM], ...
    'Renderer','painters');

set(fig,'InvertHardcopy','off');

%% ========================================================================
%  5. GLOBAL LAYOUT
%  ========================================================================

% Left major map column
L.left   = 0.060;
L.width  = 0.585;
L.right  = L.left + L.width;

% Right statistics column
R.left   = 0.705;
R.width  = 0.255;

% Top heading
figText(fig,[0.040 0.962 0.045 0.024],'(a)',FS.panel,COL.INK,'bold','left');
figText(fig,[0.082 0.961 0.54 0.026], ...
    'Persistence changes the spatial post-drought recovery record', ...
    FS.panelTitle,COL.INK,'bold','left');

%% ========================================================================
%  6. PANEL (a): SIX LARGE MAPS IN LEFT COLUMN
%  ========================================================================

% Two map columns within left major block
mapColGap = 0.034;
mapW = (L.width - 0.070 - mapColGap)/2;
mapH = 0.162;

x1 = L.left + 0.055;
x2 = x1 + mapW + mapColGap;
rowY = [0.770 0.575 0.380];

% Column headers
figText(fig,[x1 0.925 mapW 0.022],'P1',FS.colHeader,COL.P1,'bold','center');
figText(fig,[x2 0.925 mapW 0.022],'P2',FS.colHeader,COL.P2,'bold','center');
annotation(fig,'line',[x1+0.05 x1+mapW-0.05],[0.919 0.919], ...
    'Color',COL.P1,'LineWidth',1.15);
annotation(fig,'line',[x2+0.05 x2+mapW-0.05],[0.919 0.919], ...
    'Color',COL.P2,'LineWidth',1.15);

for i = 1:3
    % Row label
    figText(fig,[L.left rowY(i)+0.060 0.050 0.025], ...
        SCALE_LABEL(i),FS.rowHeader,COL.INK,'bold','right');

    sub = mapT(strcmpi(strtrim(mapT.spei_timescale),SCALES(i)),:);

    % P1 map
    ax1 = axes(fig,'Position',[x1 rowY(i) mapW mapH]);
    drawEqualEarthMapDiscrete(ax1,sub.lon,sub.lat, ...
        sub.P1_median_recovery_months,MAP_COLORS,COL,LW,MS.map);

    % P2 map
    ax2 = axes(fig,'Position',[x2 rowY(i) mapW mapH]);
    drawEqualEarthMapDiscrete(ax2,sub.lon,sub.lat, ...
        sub.P2_median_recovery_months,MAP_COLORS,COL,LW,MS.map);
end

% Discrete legend under the map block
drawDiscreteMapLegend(fig,[x1+0.020 0.310 0.450 0.026], ...
    MAP_COLORS,MAP_LABELS,FS,COL);
figText(fig,[x1+0.020 0.284 0.450 0.021], ...
    'pixel median R2 duration (months from drought end)', ...
    FS.axis,COL.INK,'normal','center');
figText(fig,[x1+0.025 0.262 0.475 0.018], ...
    'R2 only; >5-month class includes values above the display threshold', ...
    FS.note,COL.MID,'normal','left');

%% ========================================================================
%  7. RIGHT COLUMN: 2 x 2 STATISTICS BLOCK
%  ========================================================================

% Shared P1/P2 key at the top of the right column
keyAx = axes(fig,'Position',[R.left 0.938 R.width 0.020],'Visible','off');
hold(keyAx,'on');
scatter(keyAx,0.18,0.5,MS.P1,'o','filled', ...
    'MarkerFaceColor',COL.P1,'MarkerEdgeColor',COL.P1);
text(keyAx,0.27,0.5,'P1','FontName','Arial','FontSize',FS.legend, ...
    'Color',COL.INK,'VerticalAlignment','middle');
scatter(keyAx,0.58,0.5,MS.P2,'s','filled', ...
    'MarkerFaceColor',COL.P2,'MarkerEdgeColor',COL.P2);
text(keyAx,0.67,0.5,'P2','FontName','Arial','FontSize',FS.legend, ...
    'Color',COL.INK,'VerticalAlignment','middle');
xlim(keyAx,[0 1]); ylim(keyAx,[0 1]);

% Right column panels: 2 rows x 2 columns
cGapX = 0.030;
cGapY = 0.100;
boxW  = (R.width - cGapX)/2;
boxH  = 0.265;

topY  = 0.565;
botY  = 0.180;

posB = [R.left,               topY, boxW, boxH];
posC = [R.left+boxW+cGapX,    topY, boxW, boxH];
posD = [R.left,               botY, boxW, boxH];
posE = [R.left+boxW+cGapX,    botY, boxW, boxH];

%% ========================================================================
%  8. PANEL (b): MEDIAN + 95TH PERCENTILE
%  ========================================================================

axB = axes(fig,'Position',posB);
styleAxis(axB,FS,COL);
panelHeader(fig,posB,'(b)','Upper tail shifts more than the median',FS,COL);
hold(axB,'on');

yBase = [3 2 1];
yOff  = 0.105;

for i = 1:3
    p1 = getRuleRow(sumT,SCALES(i),"P1");
    p2 = getRuleRow(sumT,SCALES(i),"P2");

    y1 = yBase(i)+yOff;
    plot(axB,[p1.median_recovery_months p1.p95_recovery_months],[y1 y1], ...
        '-','Color',COL.P1,'LineWidth',LW.connect);
    scatter(axB,p1.median_recovery_months,y1,MS.P1,'o','filled', ...
        'MarkerFaceColor',COL.P1,'MarkerEdgeColor',COL.P1);
    scatter(axB,p1.p95_recovery_months,y1,MS.P1*0.88,'o', ...
        'MarkerFaceColor','w','MarkerEdgeColor',COL.P1,'LineWidth',1.10);

    y2 = yBase(i)-yOff;
    plot(axB,[p2.median_recovery_months p2.p95_recovery_months],[y2 y2], ...
        '-','Color',COL.P2,'LineWidth',LW.connect);
    scatter(axB,p2.median_recovery_months,y2,MS.P2,'s','filled', ...
        'MarkerFaceColor',COL.P2,'MarkerEdgeColor',COL.P2);
    scatter(axB,p2.p95_recovery_months,y2,MS.P2*0.88,'s', ...
        'MarkerFaceColor','w','MarkerEdgeColor',COL.P2,'LineWidth',1.10);
end

xlim(axB,[0 9]);
ylim(axB,[0.55 3.45]);
xticks(axB,0:2:8);
yticks(axB,[1 2 3]);
yticklabels(axB,{'SPEI-6','SPEI-3','SPEI-1'});
xlabel(axB,'duration (months)','FontSize',FS.axis);

text(axB,0.98,0.98,'filled = median   open = 95th percentile', ...
    'Units','normalized','FontName','Arial','FontSize',FS.note, ...
    'Color',COL.MID,'HorizontalAlignment','right','VerticalAlignment','top');

%% ========================================================================
%  9. PANEL (c): TAIL PROBABILITIES
%  ========================================================================

axC = axes(fig,'Position',posC);
styleAxis(axC,FS,COL);
panelHeader(fig,posC,'(c)','Long-duration events become more frequent under P2',FS,COL);
hold(axC,'on');

% Stack three threshold bands vertically for compact use of space
THR = {'fraction_gt3_months','fraction_gt6_months','fraction_gt12_months'};
THR_LABEL = {'>3 months','>6 months','>12 months'};
THR_XLIM = [0 26; 0 9; 0 1.6];
THR_XTICK = {0:5:25, 0:2:8, 0:0.4:1.6};

% Create three inset axes inside panel C
innerGapY = 0.040;
innerH = (posC(4)-0.065-2*innerGapY)/3;
innerY = [posC(2)+2*(innerH+innerGapY), posC(2)+(innerH+innerGapY), posC(2)];

for k = 1:3
    ax = axes(fig,'Position',[posC(1)+0.010, innerY(k)+0.010, posC(3)-0.015, innerH]);
    styleAxis(ax,FS,COL);
    hold(ax,'on');

    for i = 1:3
        p1 = getRuleRow(tailT,SCALES(i),"P1");
        p2 = getRuleRow(tailT,SCALES(i),"P2");

        v1 = 100*p1.(THR{k});
        v2 = 100*p2.(THR{k});
        y  = 4-i;

        plot(ax,[v1 v2],[y y],'-','Color',COL.LIGHT,'LineWidth',LW.connect);
        scatter(ax,v1,y,MS.P1,'o','filled', ...
            'MarkerFaceColor',COL.P1,'MarkerEdgeColor',COL.P1);
        scatter(ax,v2,y,MS.P2,'s','filled', ...
            'MarkerFaceColor',COL.P2,'MarkerEdgeColor',COL.P2);
    end

    xlim(ax,THR_XLIM(k,:));
    xticks(ax,THR_XTICK{k});
    ylim(ax,[0.55 3.45]);
    yticks(ax,[1 2 3]);

    if k == 1
        yticklabels(ax,{'SPEI-6','SPEI-3','SPEI-1'});
    else
        yticklabels(ax,{});
    end

    title(ax,THR_LABEL{k},'FontName','Arial','FontSize',FS.rowHeader, ...
        'FontWeight','bold','Color',COL.INK);

    if k < 3
        xlabel(ax,'');
    else
        xlabel(ax,'complete events (%)','FontSize',FS.axis);
    end
end

%% ========================================================================
% 10. PANEL (d): COMPLETE EVENT COUNTS
%  ========================================================================

axD = axes(fig,'Position',posD);
styleAxis(axD,FS,COL);
panelHeader(fig,posD,'(d)','P2 reduces confirmed complete recoveries',FS,COL);
hold(axD,'on');

for i = 1:3
    p1 = getRuleRow(countT,SCALES(i),"P1");
    p2 = getRuleRow(countT,SCALES(i),"P2");

    y = 4-i;
    x1 = p1.complete_recovery_count;
    x2 = p2.complete_recovery_count;

    plot(axD,[x2 x1],[y y],'-','Color',COL.LIGHT,'LineWidth',2.4);
    scatter(axD,x1,y,MS.P1,'o','filled', ...
        'MarkerFaceColor',COL.P1,'MarkerEdgeColor',COL.P1);
    scatter(axD,x2,y,MS.P2,'s','filled', ...
        'MarkerFaceColor',COL.P2,'MarkerEdgeColor',COL.P2);

    delta = round(x1-x2);
    text(axD,(x1+x2)/2,y+0.18,['-' commaNumber(delta)], ...
        'FontName','Arial','FontSize',FS.value,'Color',COL.P2, ...
        'HorizontalAlignment','center','VerticalAlignment','bottom', ...
        'FontWeight','bold');
end

xlim(axD,[83500 101500]);
xticks(axD,[84000 90000 96000 100000]);
xticklabels(axD,{'84k','90k','96k','100k'});
ylim(axD,[0.55 3.45]);
yticks(axD,[1 2 3]);
yticklabels(axD,{'SPEI-6','SPEI-3','SPEI-1'});
xlabel(axD,'complete events','FontSize',FS.axis);

%% ========================================================================
% 11. PANEL (e): RIGHT CENSORING
%  ========================================================================

axE = axes(fig,'Position',posE);
styleAxis(axE,FS,COL);
panelHeader(fig,posE,'(e)','Right censoring increases',FS,COL);
hold(axE,'on');

for i = 1:3
    p1 = getRuleRow(censorT,SCALES(i),"P1");
    p2 = getRuleRow(censorT,SCALES(i),"P2");

    y = 4-i;
    v1 = p1.right_censor_percent;
    v2 = p2.right_censor_percent;

    plot(axE,[v1 v2],[y y],'-','Color',COL.LIGHT,'LineWidth',2.4);
    scatter(axE,v1,y,MS.P1,'o','filled', ...
        'MarkerFaceColor',COL.P1,'MarkerEdgeColor',COL.P1);
    scatter(axE,v2,y,MS.P2,'s','filled', ...
        'MarkerFaceColor',COL.P2,'MarkerEdgeColor',COL.P2);

    text(axE,(v1+v2)/2,y+0.18,sprintf('+%.2f pp',v2-v1), ...
        'FontName','Arial','FontSize',FS.value,'Color',COL.P2, ...
        'HorizontalAlignment','center','VerticalAlignment','bottom');
end

xlim(axE,[1.0 4.7]);
xticks(axE,1:1:4);
ylim(axE,[0.55 3.45]);
yticks(axE,[1 2 3]);
yticklabels(axE,{'SPEI-6','SPEI-3','SPEI-1'});
xlabel(axE,'right-censored (%)','FontSize',FS.axis);

%% ========================================================================
% 12. EXPORT
%  ========================================================================

drawnow;

stem = fullfile(OUT_DIR,'Fig2_Nature_final_v03');

savefig(fig,[stem '.fig']);

try
    exportgraphics(fig,[stem '.pdf'], ...
        'ContentType','vector','BackgroundColor','white');
catch
    print(fig,[stem '.pdf'],'-dpdf','-painters');
end

try
    exportgraphics(fig,[stem '.png'], ...
        'Resolution',600,'BackgroundColor','white');
catch
    print(fig,[stem '.png'],'-dpng','-r600');
end

fprintf('\n============================================================\n');
fprintf('Fig2_Nature_final_v03 generated.\n');
fprintf('Layout: maps in left major column; panels (b)-(e) in right 2x2 block.\n');
fprintf('Panel (a): R2-only, enlarged maps, discrete duration classes.\n');
fprintf('Outputs: %s\n',OUT_DIR);
fprintf('============================================================\n\n');

end


%% =========================================================================
% SCIENCE LOCK CHECK
% =========================================================================
function scienceLockCheck(mapT,sumT,tailT,countT,censorT)

scales = ["D1","D3","D6"];

defs = unique(strtrim(string(mapT.recovery_definition)));
assert(numel(defs)==1 && strcmpi(defs,"R2"), ...
    'SCIENCE LOCK FAIL: Panel (a) contains non-R2 rows.');

for i=1:3
    s = scales(i);
    sub = mapT(strcmpi(strtrim(mapT.spei_timescale),s),:);
    assert(~isempty(sub),'SCIENCE LOCK FAIL: missing map rows.');
    assert(numel(unique(string(sub.pixel_id)))==height(sub), ...
        'SCIENCE LOCK FAIL: duplicate R2 map rows.');
end

p1Med = [1 1 1];
p2Med = [2 1 1];
p1P95 = [5 4 4];
p2P95 = [8 7 7];

p1Cnt = [89621 99757 84446];
p2Cnt = [88224 98262 83531];

p1Cen = [1.483989 2.157772 3.181573];
p2Cen = [3.019644 3.624077 4.230633];

for i=1:3
    a = getRuleRow(sumT,scales(i),"P1");
    b = getRuleRow(sumT,scales(i),"P2");

    assert(abs(a.median_recovery_months-p1Med(i))<1e-10);
    assert(abs(b.median_recovery_months-p2Med(i))<1e-10);
    assert(abs(a.p95_recovery_months-p1P95(i))<1e-10);
    assert(abs(b.p95_recovery_months-p2P95(i))<1e-10);

    a = getRuleRow(countT,scales(i),"P1");
    b = getRuleRow(countT,scales(i),"P2");
    assert(round(a.complete_recovery_count)==p1Cnt(i));
    assert(round(b.complete_recovery_count)==p2Cnt(i));

    a = getRuleRow(censorT,scales(i),"P1");
    b = getRuleRow(censorT,scales(i),"P2");
    assert(abs(a.right_censor_percent-p1Cen(i))<1e-5);
    assert(abs(b.right_censor_percent-p2Cen(i))<1e-5);

    getRuleRow(tailT,scales(i),"P1");
    getRuleRow(tailT,scales(i),"P2");
end

fprintf('SCIENCE LOCK CHECK: PASS\n');
fprintf('  Panel (a) contains R2 only.\n');
fprintf('  P1/P2 medians, p95, counts and censor rates match frozen V07.\n');

end


%% =========================================================================
% GET UNIQUE SCALE/RULE ROW
% =========================================================================
function row = getRuleRow(T,scaleName,ruleName)

m = strcmpi(strtrim(string(T.spei_timescale)),scaleName) & ...
    strcmpi(strtrim(string(T.persistence_rule)),ruleName);

sub = T(m,:);

if height(sub)~=1
    error('Expected one row for %s / %s; found %d.', ...
        scaleName,ruleName,height(sub));
end

row = sub(1,:);

end


%% =========================================================================
% AXIS STYLE
% =========================================================================
function styleAxis(ax,FS,COL)

set(ax, ...
    'FontName','Arial', ...
    'FontSize',FS.tick, ...
    'LineWidth',0.75, ...
    'TickDir','out', ...
    'TickLength',[0.018 0.018], ...
    'Box','off', ...
    'Color','w', ...
    'XColor',COL.INK, ...
    'YColor',COL.INK);

ax.Layer='top';

end


%% =========================================================================
% PANEL HEADER
% =========================================================================
function panelHeader(fig,pos,letter,titleText,FS,COL)

figText(fig,[pos(1)-0.020 pos(2)+pos(4)+0.014 0.040 0.024], ...
    letter,FS.panel,COL.INK,'bold','left');

figText(fig,[pos(1)+0.010 pos(2)+pos(4)+0.013 pos(3)-0.008 0.026], ...
    titleText,FS.panelTitle,COL.INK,'bold','left');

end


%% =========================================================================
% FIGURE-LEVEL TEXT
% =========================================================================
function figText(fig,pos,str,fontSize,color,weight,align)

annotation(fig,'textbox',pos, ...
    'String',str, ...
    'LineStyle','none', ...
    'Margin',0, ...
    'FontName','Arial', ...
    'FontSize',fontSize, ...
    'FontWeight',weight, ...
    'Color',color, ...
    'HorizontalAlignment',align, ...
    'VerticalAlignment','middle', ...
    'Interpreter','tex');

end


%% =========================================================================
% DISCRETE EQUAL EARTH MAP
% =========================================================================
function drawEqualEarthMapDiscrete(ax,lon,lat,val,MAP_COLORS,COL,LW,markerSize)

lon = double(lon);
lat = double(lat);
val = double(val);

good = isfinite(lon) & isfinite(lat) & isfinite(val);
lon = lon(good);
lat = lat(good);
val = val(good);

hold(ax,'on');

for phi=[-60 -30 0 30 60]
    glon=linspace(-180,180,361);
    glat=phi.*ones(size(glon));
    [gx,gy]=equalEarth(glon,glat);
    plot(ax,gx,gy,'-','Color',COL.GRID,'LineWidth',LW.grid);
end

for lam=[-120 -60 0 60 120]
    glat=linspace(-89.5,89.5,260);
    glon=lam.*ones(size(glat));
    [gx,gy]=equalEarth(glon,glat);
    plot(ax,gx,gy,'-','Color',COL.GRID,'LineWidth',LW.grid);
end

olat=linspace(-90,90,361);
[xl,yl]=equalEarth(-180.*ones(size(olat)),olat);
[xr,yr]=equalEarth( 180.*ones(size(olat)),olat);
plot(ax,[xl xr(end:-1:1) xl(1)], ...
        [yl yr(end:-1:1) yl(1)], ...
    '-','Color',COL.OUTLINE,'LineWidth',LW.outline);

classID = discretize(val,[-Inf 1 2 3 4 5 Inf], ...
    'IncludedEdge','right');

[x,y]=equalEarth(lon,lat);

for k=1:6
    m=classID==k;
    if any(m)
        scatter(ax,x(m),y(m),markerSize,'s','filled', ...
            'MarkerFaceColor',MAP_COLORS(k,:), ...
            'MarkerEdgeColor','none');
    end
end

drawProjectedCoastlines(ax,COL.COAST,LW.coast);

xlim(ax,[-2.78 2.78]);
ylim(ax,[-1.35 1.35]);
axis(ax,'equal');
axis(ax,'off');

end


%% =========================================================================
% OPTIONAL MATLAB COASTLINE OVERLAY
% =========================================================================
function drawProjectedCoastlines(ax,color,lw)

persistent coastLon coastLat coastAvailable

if isempty(coastAvailable)
    try
        S = load('coastlines');
        coastLon = S.coastlon;
        coastLat = S.coastlat;
        coastAvailable = true;
    catch
        coastAvailable = false;
    end
end

if coastAvailable
    [cx,cy] = equalEarth(coastLon,coastLat);
    plot(ax,cx,cy,'-','Color',color,'LineWidth',lw);
end

end


%% =========================================================================
% DISCRETE MAP LEGEND
% =========================================================================
function drawDiscreteMapLegend(fig,pos,colors,labels,FS,COL)

ax = axes(fig,'Position',pos);
hold(ax,'on');

for k=1:6
    rectangle(ax,'Position',[k-1 0 1 1], ...
        'FaceColor',colors(k,:), ...
        'EdgeColor','w', ...
        'LineWidth',0.8);
end

xlim(ax,[0 6]);
ylim(ax,[0 1]);
yticks(ax,[]);
xticks(ax,0.5:1:5.5);
xticklabels(ax,labels);
set(ax, ...
    'FontName','Arial', ...
    'FontSize',FS.tick, ...
    'TickLength',[0 0], ...
    'Box','on', ...
    'LineWidth',0.55, ...
    'XColor',COL.INK, ...
    'YColor',COL.INK, ...
    'Color','w');

end


%% =========================================================================
% EQUAL EARTH FORWARD PROJECTION
% =========================================================================
function [x,y] = equalEarth(lonDeg,latDeg)

lon = deg2rad(double(lonDeg));
lat = deg2rad(double(latDeg));

A1 = 1.340264;
A2 = -0.081106;
A3 = 0.000893;
A4 = 0.003796;

theta = asin(sqrt(3).*sin(lat)./2);
theta2 = theta.^2;

denom = 3.*( ...
    9.*A4.*theta2.^4 + ...
    7.*A3.*theta2.^3 + ...
    3.*A2.*theta2 + ...
    A1);

x = 2.*sqrt(3).*lon.*cos(theta)./denom;
y = A4.*theta.^9 + A3.*theta.^7 + A2.*theta.^3 + A1.*theta;

end


%% =========================================================================
% COMMA FORMAT
% =========================================================================
function s = commaNumber(x)

s = sprintf('%d',round(x));
idx = length(s)-2;

while idx>1
    s = [s(1:idx-1) ',' s(idx:end)]; %#ok<AGROW>
    idx = idx-3;
end

end
