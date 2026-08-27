% Release copy: paths are supplied through NEE_RELEASE_DATA_ROOT and NEE_OUTPUT_ROOT.
function FigS4_groups_final_v01()
%FIGS4_GROUPS_FINAL_V01 Group-level evidence landscape, split from S4.
%
% SCIENCE LOCK / PROVENANCE
%   Frozen source:
%     NEE_RELEASE_DATA_ROOT/figure_inputs/...
%     FIGS6_archived_group_evidence_components.csv
%
%   This script directly displays the archived equal-scale median
%   enrichment ratio, archived 95% 5-degree block-bootstrap interval,
%   archived prospective hazard AUC, archived event count and archived
%   conservative evidence status. It does not recompute a threshold,
%   interval, classification, aggregation or scientific conclusion.

close all force;

sourceRoot = fullfile(getenv('NEE_RELEASE_DATA_ROOT'),'figure_inputs');
groupFile = fullfile(sourceRoot,'FIGS6_SOURCE_PACK_20260818', ...
    '03_source_data','matlab_ready','FIGS6_archived_group_evidence_components.csv');
outDir = fileparts(mfilename('fullpath'));

pngPath = fullfile(outDir,'FigS4_groups_final_v01.png');
pdfPath = fullfile(outDir,'FigS4_groups_final_v01.pdf');
svgPath = fullfile(outDir,'FigS4_groups_final_v01.svg');
figPath = fullfile(outDir,'FigS4_groups_final_v01.fig');

assert(isfile(groupFile),'Missing frozen source: %s',groupFile);
G = readtable(groupFile,'VariableNamingRule','preserve','TextType','string');
required = {'application_evidence_status','equal_scale_median_enrichment_ratio', ...
    'equal_scale_median_prospective_hazard_auc','er_5deg_bootstrap_ci_high', ...
    'er_5deg_bootstrap_ci_low','group','group_dimension','sample_events_total'};
assert(all(ismember(required,G.Properties.VariableNames)), ...
    'Group-evidence source schema is incomplete.');

% Science-lock checks against the archived table.
assert(height(G)==20,'Unexpected archived group row count.');
dims = ["forest_type","climate_zone","large_region","pilot_constraint"];
dimCounts = arrayfun(@(i)sum(G.group_dimension==dims(i)),1:numel(dims));
assert(isequal(dimCounts,[6 6 7 1]),'Archived group dimensions changed.');
statusAll = string(G.application_evidence_status);
statusCounts = [sum(statusAll=="LIMITED"),sum(statusAll=="CONDITIONAL"),sum(statusAll=="SUPPORTED")];
assert(isequal(statusCounts,[4 15 1]),'Archived evidence-status assignments changed.');

% Color definitions shared with the map figure.
STATUS = [166 166 166; 230 137 0; 18 153 130] / 255;
STATUS_LABELS = {'LIMITED','CONDITIONAL','SUPPORTED'};
ink = [0.12 0.13 0.15];
darkGrey = [0.38 0.40 0.43];
midGrey = [0.62 0.64 0.66];
lightGrey = [0.92 0.93 0.94];

% Preserve archived within-dimension order and add visual section spacing.
sectionNames = ["FOREST","CLIMATE","REGION","PILOT"];
[idx,labels,yrow,headerY,separators,yLimits] = group_layout(G,dims);
er = numeric_column(G.equal_scale_median_enrichment_ratio(idx));
lo = numeric_column(G.er_5deg_bootstrap_ci_low(idx));
hi = numeric_column(G.er_5deg_bootstrap_ci_high(idx));
auc = numeric_column(G.equal_scale_median_prospective_hazard_auc(idx));
events = numeric_column(G.sample_events_total(idx));
status = string(G.application_evidence_status(idx));

% A4-portrait layout parameters: labels + ER forest plot + AUC + event count.
POS.LABELS = [0.045 0.105 0.235 0.775];
POS.ER = [0.295 0.105 0.355 0.775];
POS.AUC = [0.700 0.105 0.170 0.775];
POS.N = [0.895 0.105 0.080 0.775];
POS.LEGEND = [0.10 0.947 0.80 0.030];
POS.FOOT = [0.045 0.020 0.93 0.037];

FS.panel = 14.5;
FS.title = 11.8;
FS.group = 9.2;
FS.section = 9.3;
FS.axis = 8.5;
FS.legend = 8.9;
FS.foot = 8.4;

fig = figure('Color','w','Units','centimeters','Position',[1 1 18.5 25.5], ...
    'Renderer','painters','Name','S4 group evidence v01','NumberTitle','off', ...
    'Toolbar','none','MenuBar','none','Visible','off');
set(fig,'PaperUnits','centimeters','PaperPosition',[0 0 18.5 25.5], ...
    'PaperSize',[18.5 25.5],'InvertHardcopy','off');

axLabel = axes(fig,'Position',POS.LABELS,'Color','w');
axER = axes(fig,'Position',POS.ER,'Color','w');
axAUC = axes(fig,'Position',POS.AUC,'Color','w');
axN = axes(fig,'Position',POS.N,'Color','w');

configure_data_axis(axER,[-0.05 4.6],yLimits,FS.axis);
configure_data_axis(axAUC,[0.48 1.0],yLimits,FS.axis);
configure_text_axis(axLabel,yLimits);
configure_text_axis(axN,yLimits);

% Quiet row guides and stronger section separators align all three columns.
for yy = yrow(:)'
    plot(axER,[-0.05 4.6],[yy yy],'-','Color',[0.955 0.958 0.962],'LineWidth',0.45);
    plot(axAUC,[0.48 1.0],[yy yy],'-','Color',[0.955 0.958 0.962],'LineWidth',0.45);
    plot(axN,[0 1],[yy yy],'-','Color',[0.955 0.958 0.962],'LineWidth',0.45);
end
for yy = separators(:)'
    plot(axLabel,[0 1],[yy yy],'-','Color',lightGrey,'LineWidth',0.8);
    plot(axER,[-0.05 4.6],[yy yy],'-','Color',lightGrey,'LineWidth',0.8);
    plot(axAUC,[0.48 1.0],[yy yy],'-','Color',lightGrey,'LineWidth',0.8);
    plot(axN,[0 1],[yy yy],'-','Color',lightGrey,'LineWidth',0.8);
end

% Shared y labels grouped into Forest / Climate / Region / Pilot.
for d = 1:numel(sectionNames)
    text(axLabel,0,headerY(d),sectionNames(d),'FontName','Arial', ...
        'FontSize',FS.section,'FontWeight','bold','Color',darkGrey, ...
        'HorizontalAlignment','left','VerticalAlignment','middle');
end
for r = 1:numel(idx)
    text(axLabel,0.055,yrow(r),labels(r),'FontName','Arial','FontSize',FS.group, ...
        'Color',ink,'HorizontalAlignment','left','VerticalAlignment','middle');
end

% (a) Enrichment-ratio forest plot with archived intervals.
for r = 1:numel(idx)
    color = status_color(status(r),STATUS);
    if isfinite(er(r)) && isfinite(lo(r)) && isfinite(hi(r))
        plot(axER,[lo(r) hi(r)],[yrow(r) yrow(r)],'-','Color',darkGrey,'LineWidth',1.15);
        plot(axER,[lo(r) lo(r)],[yrow(r)-0.09 yrow(r)+0.09],'-','Color',darkGrey,'LineWidth',0.75);
        plot(axER,[hi(r) hi(r)],[yrow(r)-0.09 yrow(r)+0.09],'-','Color',darkGrey,'LineWidth',0.75);
        scatter(axER,er(r),yrow(r),38,color,'filled','MarkerEdgeColor','w','LineWidth',0.55);
    else
        text(axER,0.04,yrow(r),'NA','FontName','Arial','FontSize',FS.axis, ...
            'Color',midGrey,'HorizontalAlignment','left','VerticalAlignment','middle');
    end
end
plot(axER,[1 1],yLimits,'--','Color',darkGrey,'LineWidth',0.9);
text(axER,1.03,yLimits(2)-0.45,'null','FontName','Arial','FontSize',7.6, ...
    'Color',darkGrey,'HorizontalAlignment','left','VerticalAlignment','top');
set(axER,'XTick',[0 1 2 3 4],'YTick',[],'Box','off','Layer','top');
xlabel(axER,'Equal-scale median enrichment ratio','FontName','Arial','FontSize',9.6);

% (b) Prospective discrimination. Chance (0.5) and the archived status-rule
% threshold (0.60) are distinct and are shown with distinct line styles.
for r = 1:numel(idx)
    color = status_color(status(r),STATUS);
    if isfinite(auc(r))
        scatter(axAUC,auc(r),yrow(r),38,color,'filled','MarkerEdgeColor','w','LineWidth',0.55);
    else
        text(axAUC,0.49,yrow(r),'NA','FontName','Arial','FontSize',FS.axis, ...
            'Color',midGrey,'HorizontalAlignment','left','VerticalAlignment','middle');
    end
end
plot(axAUC,[0.5 0.5],yLimits,'--','Color',darkGrey,'LineWidth',0.9);
plot(axAUC,[0.6 0.6],yLimits,':','Color',midGrey,'LineWidth',1.0);
text(axAUC,0.505,yLimits(2)-0.35,'chance','FontName','Arial','FontSize',7.3, ...
    'Color',darkGrey,'HorizontalAlignment','left','VerticalAlignment','top');
text(axAUC,0.607,yLimits(2)-1.00,'status rule','FontName','Arial','FontSize',7.3, ...
    'Color',midGrey,'HorizontalAlignment','left','VerticalAlignment','top');
set(axAUC,'XTick',[0.5 0.6 0.8 1.0],'XTickLabelRotation',0, ...
    'YTick',[],'Box','off','Layer','top');
xlabel(axAUC,'Hazard AUC','FontName','Arial','FontSize',9.6);

% (c) Archived event counts remain explicit. The pilot row has no numeric n.
for r = 1:numel(idx)
    if isfinite(events(r))
        eventText = format_integer(round(events(r)));
        eventColor = ink;
    else
        eventText = 'NA';
        eventColor = midGrey;
    end
    text(axN,0.94,yrow(r),eventText,'FontName','Arial','FontSize',FS.group, ...
        'Color',eventColor,'HorizontalAlignment','right','VerticalAlignment','middle');
end

column_title(fig,[0.285 0.895 0.375 0.042],'(a)','Enrichment ratio',FS);
column_title(fig,[0.690 0.895 0.195 0.042],'(b)','Prospective discrimination',FS);
column_title(fig,[0.885 0.895 0.100 0.042],'(c)','Events',FS);

axLegend = axes(fig,'Position',POS.LEGEND,'Color','w');
draw_status_legend(axLegend,STATUS,STATUS_LABELS,FS.legend);

annotation(fig,'textbox',POS.FOOT,'String', ...
    'Points show archived group-level estimates; horizontal lines show archived 95% 5-degree block-bootstrap intervals.', ...
    'LineStyle','none','Margin',0,'FontName','Arial','FontSize',FS.foot, ...
    'FontAngle','italic','Color',darkGrey,'HorizontalAlignment','center', ...
    'VerticalAlignment','middle');

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

fprintf('Created group figure outputs:\n%s\n%s\n%s\n%s\n',figPath,pngPath,pdfPath,svgPath);
end

function [idx,labels,yrow,headerY,separators,yLimits] = group_layout(G,dims)
idx = zeros(0,1);
labels = strings(0,1);
yrow = zeros(0,1);
headerY = zeros(numel(dims),1);
separators = zeros(0,1);
cursor = 25;
for d = 1:numel(dims)
    q = find(G.group_dimension==dims(d));
    headerY(d) = cursor;
    cursor = cursor-0.75;
    for j = 1:numel(q)
        idx(end+1,1) = q(j); %#ok<AGROW>
        label = string(G.group(q(j)));
        if dims(d)=="forest_type"
            label = erase(label," forest");
        elseif dims(d)=="pilot_constraint"
            label = "Amazon audit window";
        end
        labels(end+1,1) = label; %#ok<AGROW>
        yrow(end+1,1) = cursor; %#ok<AGROW>
        cursor = cursor-1;
    end
    if d<numel(dims)
        separators(end+1,1) = cursor+0.30; %#ok<AGROW>
        cursor = cursor-0.55;
    end
end
yLimits = [max(0.25,cursor+0.05),25.55];
end

function configure_data_axis(ax,xLimits,yLimits,fontSize)
hold(ax,'on');
set(ax,'XLim',xLimits,'YLim',yLimits,'FontName','Arial','FontSize',fontSize, ...
    'TickDir','out','TickLength',[0.012 0.012],'LineWidth',0.65, ...
    'Color','w','Box','off','Layer','top');
end

function configure_text_axis(ax,yLimits)
hold(ax,'on');
axis(ax,[0 1 yLimits]);
axis(ax,'off');
end

function column_title(fig,pos,label,titleText,FS)
annotation(fig,'textbox',pos,'String',[label '  ' titleText], ...
    'LineStyle','none','Margin',0,'FontName','Arial','FontSize',FS.title, ...
    'FontWeight','bold','Color',[0.12 0.13 0.15], ...
    'HorizontalAlignment','left','VerticalAlignment','middle');
end

function draw_status_legend(ax,colors,labels,fontSize)
axis(ax,[0 1 0 1]);
axis(ax,'off');
hold(ax,'on');
text(ax,0,0.52,'Conservative evidence status','FontName','Arial', ...
    'FontSize',fontSize,'FontWeight','bold','Color',[0.20 0.21 0.23], ...
    'HorizontalAlignment','left','VerticalAlignment','middle');
x = [0.50 0.68 0.88];
for k = 1:3
    scatter(ax,x(k),0.52,54,colors(k,:),'filled','MarkerEdgeColor','none');
    text(ax,x(k)+0.025,0.52,labels{k},'FontName','Arial','FontSize',fontSize, ...
        'Color',[0.12 0.13 0.15],'HorizontalAlignment','left', ...
        'VerticalAlignment','middle');
end
end

function color = status_color(status,palette)
if status=="SUPPORTED"
    color = palette(3,:);
elseif status=="CONDITIONAL"
    color = palette(2,:);
else
    color = palette(1,:);
end
end

function v = numeric_column(v)
if isnumeric(v)
    v = double(v);
else
    v = str2double(string(v));
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
