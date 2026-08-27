% Release copy: paths are supplied through NEE_RELEASE_DATA_ROOT and NEE_OUTPUT_ROOT.
%% Fig1_Nature_final_v03.m
% Figure 1 redesign (v03, enlarged typography + final layout cleanup)
%
% Scientific content is unchanged from v02:
%   (a) Conceptual recovery clocks: OLD / R1 / R2
%   (b) Frozen representative event (data-driven)
%   (c) Persistence and endpoint logic (schematic)
%
% v03 changes:
%   1) Substantially larger typography throughout.
%   2) Panel labels use "(a)", "(b)", "(c)".
%   3) Panel c is widened and wording shortened to avoid clipping.
%   4) Panel b annotations are repositioned for less crowding.
%   5) Footer / END overlap in panel c is removed.
%   6) Figure width is slightly increased while keeping journal-ready proportions.
%
% Input:
%   FIG1_matlab_input.mat
%
% Outputs:
%   Fig1_Nature_final_v03.fig
%   Fig1_Nature_final_v03.pdf
%   Fig1_Nature_final_v03.png (600 dpi)

clear; clc; close all;

%% ========================= USER-EDITABLE PATHS ==========================
DATAFILE = fullfile(getenv('NEE_RELEASE_DATA_ROOT'),'figure_inputs','Fig1','FIG1_matlab_input.mat');
OUTDIR = getenv('NEE_OUTPUT_ROOT');

if ~exist(DATAFILE,'file')
    here = fileparts(mfilename('fullpath'));
    candidates = { ...
        fullfile(here,'FIG1_matlab_input.mat'), ...
        fullfile(here,'03_source_data','FIG1_matlab_input.mat'), ...
        fullfile(here,'FIG1_SOURCE_PACK_20260818','03_source_data','FIG1_matlab_input.mat') ...
        };
    found = '';
    for ii = 1:numel(candidates)
        if exist(candidates{ii},'file')
            found = candidates{ii};
            break
        end
    end
    if isempty(found)
        error('Cannot find FIG1_matlab_input.mat. Edit DATAFILE at the top of the script.');
    end
    DATAFILE = found;
end

if ~exist(OUTDIR,'dir')
    mkdir(OUTDIR);
end

%% ============================= LOAD DATA ================================
D = load(DATAFILE);

x    = double(D.relative_month(:));
spei = double(D.spei(:));
k    = double(D.kndvi_anomaly(:));
thr  = double(D.recovery_threshold);

% MATLAB 1-based indices
iOnset = double(D.drought_start_index);
iEnd   = double(D.drought_end_index);
iMin   = double(D.full_drought_min_index);
iP1    = double(D.p1_crossing_index);
iP2a   = double(D.p2_first_index);
iP2b   = double(D.p2_second_index);

xOnset = x(iOnset);
xEnd   = x(iEnd);
xMin   = x(iMin);
xP1    = x(iP1);
xP2a   = x(iP2a);
xP2b   = x(iP2b);

%% ============================== PALETTE ================================
C.ink        = [0.10 0.10 0.10];
C.darkgray   = [0.34 0.34 0.34];
C.gray       = [0.58 0.58 0.58];
C.drought    = [0.95 0.92 0.85];
C.old        = [0.46 0.46 0.46];
C.r1         = [0.00 0.56 0.43];
C.r2         = [0.69 0.35 0.60];
C.p1         = [0.00 0.43 0.72];
C.p2         = [0.90 0.53 0.00];
C.threshold  = [0.73 0.17 0.21];
C.spei       = [0.33 0.33 0.33];

FONT = 'Arial';

%% =========================== TYPOGRAPHY ================================
% v03: significantly larger fonts
T.panelLabel = 14.0;
T.panelTitle = 11.8;
T.axisLabel  = 10.3;
T.tick       = 9.2;
T.annoSmall  = 8.0;
T.anno       = 8.5;
T.annoLarge  = 9.2;
T.footer     = 7.5;

LW.mainCurve = 2.8;
LW.axis      = 0.90;
LW.line      = 1.25;
LW.light     = 0.95;
LW.dash      = 1.05;

MS.node      = 4.8;
MS.emph      = 8.0;

%% ============================= FIGURE =================================
% Slightly wider than v02 for larger typography and panel-c breathing room
fig = figure('Color','w', ...
    'Units','centimeters', ...
    'Position',[2 2 18.5 13.3], ...
    'PaperPositionMode','auto', ...
    'Renderer','painters');

% Layout tuned for larger fonts:
% a: compact full width
% b: still the main data panel
% c: widened; right-side text no longer clips
axA  = axes(fig,'Position',[0.060 0.635 0.915 0.285]);
axB1 = axes(fig,'Position',[0.075 0.365 0.535 0.140]);
axB2 = axes(fig,'Position',[0.075 0.115 0.535 0.195]);
axC  = axes(fig,'Position',[0.640 0.115 0.335 0.390]);

%% ================= PANEL (a): CONCEPTUAL RECOVERY CLOCKS ===============
hold(axA,'on');
axis(axA,'off');
xlim(axA,[0 10.8]);
ylim(axA,[-1.82 0.84]);

% Conceptual curve (not quantitative)
xa = [0.25 1.45 2.18 3.22 4.05 5.30 6.35 7.18 8.85 10.18];
ya = [0.48 0.48 0.36 -0.72 -0.28 -1.20 -0.76 -0.34 0.16 0.38];
xd = linspace(min(xa),max(xa),500);
yd = pchip(xa,ya,xd);

aOnset    = 2.18;
aLocalMin = 3.22;
aOldCross = 4.05;
aFullMin  = 5.30;
aEnd      = 6.35;
aRecovery = 7.18;
aThr      = -0.50;

% Drought phase
patch(axA,[aOnset aEnd aEnd aOnset],[-1.34 -1.34 0.70 0.70], ...
    C.drought,'EdgeColor','none','FaceAlpha',0.82);

% Recovery threshold
plot(axA,[0.18 10.42],[aThr aThr],'--','Color',C.threshold,'LineWidth',LW.dash);
text(axA,10.40,aThr+0.07,'recovery threshold', ...
    'HorizontalAlignment','right','VerticalAlignment','bottom', ...
    'FontName',FONT,'FontSize',T.annoSmall,'Color',C.threshold);

% Conceptual trajectory
plot(axA,xd,yd,'Color',C.ink,'LineWidth',LW.mainCurve);
plot(axA,xa,ya,'o','MarkerSize',MS.node,'MarkerFaceColor','w', ...
    'MarkerEdgeColor',C.ink,'LineWidth',0.85);

% Timing landmarks
plot(axA,[aOnset aOnset],[-1.34 0.69],':','Color',C.gray,'LineWidth',LW.light);
plot(axA,[aEnd aEnd],[-1.34 0.69],'--','Color',C.ink,'LineWidth',LW.line);

text(axA,aOnset,0.65,'drought onset','HorizontalAlignment','center', ...
    'VerticalAlignment','bottom','FontName',FONT,'FontSize',T.anno, ...
    'Color',C.darkgray);
text(axA,aEnd,0.65,'drought end','HorizontalAlignment','center', ...
    'VerticalAlignment','bottom','FontName',FONT,'FontSize',T.anno, ...
    'FontWeight','bold','Color',C.ink);
text(axA,(aOnset+aEnd)/2,0.43,'meteorological drought', ...
    'HorizontalAlignment','center','FontName',FONT,'FontSize',T.anno, ...
    'Color',C.darkgray);

% Local/full minima
plot(axA,aLocalMin,interp1(xd,yd,aLocalMin),'o','MarkerSize',5.7, ...
    'MarkerFaceColor',C.old,'MarkerEdgeColor','w','LineWidth',0.75);
text(axA,aLocalMin-0.12,-0.91,'truncated local minimum', ...
    'HorizontalAlignment','right','VerticalAlignment','top', ...
    'FontName',FONT,'FontSize',T.annoSmall,'Color',C.old);

plot(axA,aFullMin,interp1(xd,yd,aFullMin),'o','MarkerSize',6.0, ...
    'MarkerFaceColor',C.r1,'MarkerEdgeColor','w','LineWidth',0.75);
text(axA,aFullMin,-1.26,'full-drought minimum', ...
    'HorizontalAlignment','center','VerticalAlignment','top', ...
    'FontName',FONT,'FontSize',T.annoSmall,'Color',C.r1);

% Recovery clocks
yOLD = -1.42;
yR1  = -1.60;
yR2  = -1.78;

text(axA,0.20,yOLD,'OLD','FontName',FONT,'FontSize',T.annoLarge, ...
    'FontWeight','bold','Color',C.old);
text(axA,0.86,yOLD,'local minimum \rightarrow first crossing', ...
    'FontName',FONT,'FontSize',T.anno,'Color',C.old);
drawHorizontalArrow(axA,aLocalMin,aOldCross,yOLD,C.old,1.65,0.14,0.055);

text(axA,0.20,yR1,'R1','FontName',FONT,'FontSize',T.annoLarge, ...
    'FontWeight','bold','Color',C.r1);
text(axA,0.86,yR1,'full-drought minimum \rightarrow crossing', ...
    'FontName',FONT,'FontSize',T.anno,'Color',C.r1);
drawHorizontalArrow(axA,aFullMin,aRecovery,yR1,C.r1,1.65,0.14,0.055);

text(axA,0.20,yR2,'R2','FontName',FONT,'FontSize',T.annoLarge, ...
    'FontWeight','bold','Color',C.r2);
text(axA,0.86,yR2,'drought end \rightarrow post-drought crossing', ...
    'FontName',FONT,'FontSize',T.anno,'Color',C.r2);
drawHorizontalArrow(axA,aEnd,aRecovery,yR2,C.r2,1.65,0.14,0.055);

panelHeading(axA,'(a)','Recovery clocks use different time origins',FONT,C.ink,T);
text(axA,10.45,0.77,'conceptual; not to scale', ...
    'HorizontalAlignment','right','VerticalAlignment','top', ...
    'FontName',FONT,'FontSize',T.anno,'FontAngle','italic','Color',C.gray);

%% ================= PANEL (b): REPRESENTATIVE EVENT =====================
% ---- SPEI ----
hold(axB1,'on');
styleAxes(axB1,FONT,C.ink,T,LW);

yl = [-1.35 0.95];
ylim(axB1,yl);
xlim(axB1,[min(x)-0.45 max(x)+0.45]);
shadeX(axB1,xOnset-0.50,xEnd+0.50,yl,C.drought,0.80);

yline(axB1,-1,'--','Color',C.gray,'LineWidth',LW.light);
plot(axB1,x,spei,'-s','Color',C.spei,'LineWidth',1.35, ...
    'MarkerSize',4.5,'MarkerFaceColor',C.spei,'MarkerEdgeColor',C.spei);

xline(axB1,xOnset,':','Color',C.gray,'LineWidth',LW.light);
xline(axB1,xEnd,'--','Color',C.ink,'LineWidth',LW.line);

text(axB1,(xOnset+xEnd)/2,0.80,'merged drought span', ...
    'HorizontalAlignment','center','VerticalAlignment','top', ...
    'FontName',FONT,'FontSize',T.annoSmall,'Color',C.darkgray);
text(axB1,max(x)+0.34,-0.96,'SPEI = -1', ...
    'HorizontalAlignment','right','VerticalAlignment','bottom', ...
    'FontName',FONT,'FontSize',T.annoSmall,'Color',C.gray);

ylabel(axB1,'SPEI','FontName',FONT,'FontSize',T.axisLabel);
set(axB1,'XTick',-5:1:4,'XTickLabel',[]);
set(axB1,'YTick',[-1 -0.5 0 0.5]);

panelHeading(axB1,'(b)','Representative observed event',FONT,C.ink,T);

% ---- kNDVI anomaly ----
hold(axB2,'on');
styleAxes(axB2,FONT,C.ink,T,LW);

yl2 = [-3.35 1.90];
ylim(axB2,yl2);
xlim(axB2,[min(x)-0.45 max(x)+0.45]);
shadeX(axB2,xOnset-0.50,xEnd+0.50,yl2,C.drought,0.80);

yline(axB2,thr,'--','Color',C.threshold,'LineWidth',LW.dash);
xline(axB2,xOnset,':','Color',C.gray,'LineWidth',LW.light);
xline(axB2,xEnd,'--','Color',C.ink,'LineWidth',LW.line);

plot(axB2,x,k,'-o','Color',C.r2,'LineWidth',1.45, ...
    'MarkerSize',4.7,'MarkerFaceColor',C.r2,'MarkerEdgeColor',C.r2);

% Full-drought minimum
plot(axB2,xMin,k(iMin),'v','MarkerSize',MS.emph, ...
    'MarkerFaceColor',C.r1,'MarkerEdgeColor','w','LineWidth',0.85);
text(axB2,xMin-0.10,k(iMin)-0.16,'full-drought minimum', ...
    'HorizontalAlignment','right','VerticalAlignment','top', ...
    'FontName',FONT,'FontSize',T.annoSmall,'Color',C.r1);

% Drought end / R2 origin
text(axB2,xEnd+0.07,1.72,'drought end', ...
    'HorizontalAlignment','left','VerticalAlignment','top', ...
    'FontName',FONT,'FontSize',T.annoSmall,'FontWeight','bold','Color',C.ink);
text(axB2,xEnd+0.07,1.38,'R2 origin', ...
    'HorizontalAlignment','left','VerticalAlignment','top', ...
    'FontName',FONT,'FontSize',T.annoSmall,'Color',C.r2);

% P1 / P2
plot(axB2,xP1,k(iP1),'o','MarkerSize',MS.emph, ...
    'MarkerFaceColor',C.p1,'MarkerEdgeColor','w','LineWidth',0.85);
text(axB2,xP1+0.12,k(iP1)+0.27,'P1 crossing', ...
    'HorizontalAlignment','left','VerticalAlignment','bottom', ...
    'FontName',FONT,'FontSize',T.annoSmall,'FontWeight','bold','Color',C.p1);

text(axB2,xP2a+0.15,k(iP2a)-0.34,'P2 assigned here', ...
    'HorizontalAlignment','left','VerticalAlignment','top', ...
    'FontName',FONT,'FontSize',T.annoSmall,'Color',C.p2);

plot(axB2,xP2b,k(iP2b),'o','MarkerSize',MS.emph, ...
    'MarkerFaceColor',C.p2,'MarkerEdgeColor','w','LineWidth',0.85);
text(axB2,xP2b-0.05,k(iP2b)+0.29,'P2 confirmation', ...
    'HorizontalAlignment','center','VerticalAlignment','bottom', ...
    'FontName',FONT,'FontSize',T.annoSmall,'Color',C.p2);

text(axB2,max(x)+0.34,thr+0.08,'-0.5 SD', ...
    'HorizontalAlignment','right','VerticalAlignment','bottom', ...
    'FontName',FONT,'FontSize',T.annoSmall,'Color',C.threshold);

xlabel(axB2,'Months relative to drought end','FontName',FONT,'FontSize',T.axisLabel);
ylabel(axB2,'kNDVI anomaly (SD)','FontName',FONT,'FontSize',T.axisLabel);
set(axB2,'XTick',-5:1:4,'YTick',[-3 -2 -1 0 1]);

%% ================= PANEL (c): PERSISTENCE / ENDPOINT LOGIC =============
hold(axC,'on');
axis(axC,'off');
xlim(axC,[0 10.4]);
ylim(axC,[0 3.55]);

panelHeading(axC,'(c)','Persistence and endpoint logic',FONT,C.ink,T);

% Larger fonts + shorter wording
rowY = [2.80 1.84 0.78];
labX = 0.20;
xObs = [2.75 4.70 6.40];

% ---- P1 ----
text(axC,labX,rowY(1)+0.14,'P1','FontName',FONT,'FontSize',9.5, ...
    'FontWeight','bold','Color',C.p1);
text(axC,labX,rowY(1)-0.20,'one finite qualifying month', ...
    'FontName',FONT,'FontSize',T.annoSmall,'Color',C.darkgray);

th1 = rowY(1);
plot(axC,[2.05 7.65],[th1 th1],'--','Color',C.threshold,'LineWidth',LW.light);
v1 = [th1-0.30 th1+0.32 th1+0.10];
plot(axC,xObs,v1,'-','Color',C.ink,'LineWidth',LW.line);
plot(axC,xObs,v1,'o','MarkerSize',4.7,'MarkerFaceColor',C.ink,'MarkerEdgeColor',C.ink);
plot(axC,xObs(2),v1(2),'o','MarkerSize',8.8,'MarkerFaceColor',C.p1, ...
    'MarkerEdgeColor','w','LineWidth',0.85);
text(axC,7.85,rowY(1)+0.12,'complete at first crossing', ...
    'FontName',FONT,'FontSize',T.annoSmall,'Color',C.p1,'VerticalAlignment','middle');

% ---- P2 ----
text(axC,labX,rowY(2)+0.14,'P2','FontName',FONT,'FontSize',9.5, ...
    'FontWeight','bold','Color',C.p2);
text(axC,labX,rowY(2)-0.20,'two adjacent qualifying months', ...
    'FontName',FONT,'FontSize',T.annoSmall,'Color',C.darkgray);

th2 = rowY(2);
plot(axC,[2.05 7.65],[th2 th2],'--','Color',C.threshold,'LineWidth',LW.light);
v2 = [th2-0.31 th2+0.23 th2+0.34];
plot(axC,xObs,v2,'-','Color',C.ink,'LineWidth',LW.line);
plot(axC,xObs,v2,'o','MarkerSize',4.7,'MarkerFaceColor',C.ink,'MarkerEdgeColor',C.ink);
plot(axC,xObs(2:3),v2(2:3),'o','MarkerSize',8.8,'MarkerFaceColor',C.p2, ...
    'MarkerEdgeColor','w','LineWidth',0.85);
drawHorizontalBracket(axC,xObs(2),xObs(3),rowY(2)+0.55,C.p2,T);
text(axC,7.85,rowY(2)+0.12,'month 2 confirms; assign month 1', ...
    'FontName',FONT,'FontSize',T.annoSmall,'Color',C.p2,'VerticalAlignment','middle');

% ---- Endpoint ----
text(axC,labX,rowY(3)+0.14,'Endpoint','FontName',FONT,'FontSize',8.8, ...
    'FontWeight','bold','Color',C.ink);
text(axC,labX,rowY(3)-0.20,'final observed month crosses threshold', ...
    'FontName',FONT,'FontSize',T.annoSmall,'Color',C.darkgray);

th3 = rowY(3);
plot(axC,[2.05 6.00],[th3 th3],'--','Color',C.threshold,'LineWidth',LW.light);

x3 = [2.75 4.85];
v3 = [th3-0.31 th3+0.30];
plot(axC,x3,v3,'-','Color',C.ink,'LineWidth',LW.line);
plot(axC,x3(1),v3(1),'o','MarkerSize',4.7,'MarkerFaceColor',C.ink,'MarkerEdgeColor',C.ink);
plot(axC,x3(2),v3(2),'o','MarkerSize',8.8,'MarkerFaceColor',C.p1, ...
    'MarkerEdgeColor','w','LineWidth',0.85);

xEndpoint = 5.92;
plot(axC,[xEndpoint xEndpoint],[rowY(3)-0.48 rowY(3)+0.56], ...
    '-','Color',C.darkgray,'LineWidth',1.20);
text(axC,xEndpoint,rowY(3)-0.54,'END', ...
    'HorizontalAlignment','center','VerticalAlignment','top', ...
    'FontName',FONT,'FontSize',T.annoSmall,'FontWeight','bold','Color',C.darkgray);

% Outcome labels shifted right and separated
text(axC,6.72,rowY(3)+0.22,'P1: complete', ...
    'FontName',FONT,'FontSize',T.anno,'FontWeight','bold','Color',C.p1);
text(axC,6.72,rowY(3)-0.07,'P2: right-censored', ...
    'FontName',FONT,'FontSize',T.anno,'FontWeight','bold','Color',C.p2);

% No fake second point; only a cue after the endpoint
plot(axC,[xEndpoint+0.12 6.50],[rowY(3)+0.31 rowY(3)+0.31], ...
    ':','Color',C.gray,'LineWidth',LW.light);
text(axC,6.54,rowY(3)+0.31,'no second finite observation', ...
    'FontName',FONT,'FontSize',7.2,'Color',C.gray,'VerticalAlignment','middle');

% Threshold key (left) and footer (right), now separated vertically
plot(axC,[0.28 1.32],[0.12 0.12],'--','Color',C.threshold,'LineWidth',LW.light);
text(axC,1.45,0.12,'qualifying threshold', ...
    'FontName',FONT,'FontSize',7.1,'Color',C.threshold,'VerticalAlignment','middle');

text(axC,10.15,-0.03,'Only finite observations qualify; no interpolation.', ...
    'HorizontalAlignment','right','VerticalAlignment','top', ...
    'FontName',FONT,'FontSize',T.footer,'FontAngle','italic','Color',C.darkgray);

%% ============================= EXPORT ==================================
base = fullfile(OUTDIR,'Fig1_Nature_final_v03');

savefig(fig,[base '.fig']);
exportgraphics(fig,[base '.pdf'], ...
    'ContentType','vector','BackgroundColor','white');
exportgraphics(fig,[base '.png'], ...
    'Resolution',600,'BackgroundColor','white');

fprintf('\nFigure 1 v03 exported successfully:\n');
fprintf('  %s.fig\n',base);
fprintf('  %s.pdf\n',base);
fprintf('  %s.png\n\n',base);

%% ========================== LOCAL FUNCTIONS =============================
function styleAxes(ax,fontName,ink,T,LW)
    set(ax, ...
        'FontName',fontName, ...
        'FontSize',T.tick, ...
        'LineWidth',LW.axis, ...
        'TickDir','out', ...
        'TickLength',[0.016 0.016], ...
        'Box','off', ...
        'XColor',ink, ...
        'YColor',ink, ...
        'Layer','top');
end

function shadeX(ax,x1,x2,yl,c,alphaVal)
    patch(ax,[x1 x2 x2 x1],[yl(1) yl(1) yl(2) yl(2)],c, ...
        'EdgeColor','none','FaceAlpha',alphaVal,'HandleVisibility','off');
end

function panelHeading(ax,labelText,titleText,fontName,ink,T)
    % Explicit parenthesized panel labels: (a), (b), (c)
    text(ax,-0.062,1.040,labelText, ...
        'Units','normalized', ...
        'FontName',fontName,'FontSize',T.panelLabel,'FontWeight','bold', ...
        'Color',ink,'VerticalAlignment','bottom','Clipping','off');
    text(ax,0.020,1.040,titleText, ...
        'Units','normalized', ...
        'FontName',fontName,'FontSize',T.panelTitle,'FontWeight','bold', ...
        'Color',ink,'VerticalAlignment','bottom','Clipping','off');
end

function drawHorizontalArrow(ax,x0,x1,y,c,lw,headX,headY)
    if x1 <= x0
        return
    end
    plot(ax,[x0 x1-headX],[y y],'-','Color',c,'LineWidth',lw);
    patch(ax,[x1-headX x1-headX x1],[y-headY y+headY y],c, ...
        'EdgeColor',c,'FaceColor',c);
    plot(ax,x0,y,'o','MarkerSize',5.3,'MarkerFaceColor',c, ...
        'MarkerEdgeColor','w','LineWidth',0.75);
end

function drawHorizontalBracket(ax,x0,x1,y,c,T)
    plot(ax,[x0 x1],[y y],'-','Color',c,'LineWidth',1.1);
    plot(ax,[x0 x0],[y-0.07 y+0.02],'-','Color',c,'LineWidth',1.1);
    plot(ax,[x1 x1],[y-0.07 y+0.02],'-','Color',c,'LineWidth',1.1);
    text(ax,(x0+x1)/2,y+0.055,'two adjacent months', ...
        'HorizontalAlignment','center','VerticalAlignment','bottom', ...
        'FontName','Arial','FontSize',T.annoSmall-0.3,'Color',c);
end
