% Release copy: paths are supplied through NEE_RELEASE_DATA_ROOT and NEE_OUTPUT_ROOT.
%% FigS3_Nature_final_v02
% Final visual refinement of Supplementary Figure S3.
% Layout, text, and style only: no science, data, or model changes.

clearvars;
clc;

scriptPath = mfilename('fullpath');
matlabDir = fileparts(scriptPath);
taskRoot = fileparts(matlabDir);

dataRoot = fullfile(getenv('NEE_RELEASE_DATA_ROOT'),'figure_inputs','ExtendedDataFig3');
sourceS4 = fullfile(dataRoot,'FIGS4_functional_legacy_contrasts.csv');
sourceS7 = fullfile(dataRoot,'FIGS7_fire_overlap_contrasts.csv');
derivedPath = fullfile(dataRoot,'S3_FUNCTIONAL_ROBUSTNESS_DERIVED.csv');
summaryPath = fullfile(dataRoot,'S3_CROSS_METRIC_SUMMARY.csv');

figPath = fullfile(matlabDir, 'FigS3_Nature_final_v02.fig');
pdfPath = fullfile(matlabDir, 'FigS3_Nature_final_v02.pdf');
pngPath = fullfile(matlabDir, 'FigS3_Nature_final_v02.png');

assert(isfile(sourceS4) && isfile(sourceS7), 'Frozen source table is missing.');
assert(isfile(derivedPath) && isfile(summaryPath), 'Required S3 derived table is missing.');

S4 = readtable(sourceS4, 'TextType', 'string', 'VariableNamingRule', 'preserve');
S7 = readtable(sourceS7, 'TextType', 'string', 'VariableNamingRule', 'preserve');
D = readtable(derivedPath, 'TextType', 'string', 'VariableNamingRule', 'preserve');
X = readtable(summaryPath, 'TextType', 'string', 'VariableNamingRule', 'preserve');

%% Frozen-data and duplicate checks
assert(height(S4) == 8, 'Expected exactly eight frozen FIGS4 rows.');
assert(height(S7) == 2, 'Expected exactly two frozen FIGS7 rows.');
assert(height(D) == 8 && height(X) == 4, 'Unexpected S3 derived-table dimensions.');
keys = S4.metric + "|" + S4.comparison;
assert(numel(unique(keys)) == 8, 'FIGS4 metric-comparison rows must be unique.');
assert(sum(D.metric == "gpp_legacy") == 4 && sum(D.metric == "npp_legacy") == 4, ...
    'Expected four GPP and four NPP rows.');

numericVars = ["difference_a_minus_b", "ci_low", "ci_high", "mean_a", "mean_b", "n_a", "n_b"];
for i = 1:height(D)
    idx = find(S4.metric == D.metric(i) & S4.comparison == D.comparison(i));
    assert(isscalar(idx), 'Derived row does not map uniquely to FIGS4.');
    for v = numericVars
        delta = abs(double(D{i, v}) - double(S4{idx, v}));
        assert(delta < 1e-12, 'Derived numeric field differs from frozen FIGS4 source.');
    end
    expectedWidth = double(D.ci_high(i)) - double(D.ci_low(i));
    assert(abs(double(D.ci_width(i)) - expectedWidth) < 1e-12, 'CI-width derivation failed.');
    if double(D.ci_high(i)) < 0
        expectedStatus = "decrease_supported";
    elseif double(D.ci_low(i)) > 0
        expectedStatus = "increase_supported";
    else
        expectedStatus = "uncertain_crosses_zero";
    end
    assert(D.interval_support(i) == expectedStatus, 'Frozen interval classification changed.');
end
assert(sum(D.interval_support == "decrease_supported") == 4, ...
    'Expected four archived intervals below zero.');
assert(sum(D.interval_support == "uncertain_crosses_zero") == 4, ...
    'Expected four archived intervals including zero.');

sharedVars = intersect(string(S7.Properties.VariableNames), string(S4.Properties.VariableNames), 'stable');
for i = 1:height(S7)
    idx = find(S4.metric == S7.metric(i) & S4.comparison == S7.comparison(i));
    assert(isscalar(idx), 'FIGS7 row does not map uniquely to FIGS4.');
    for v = sharedVars
        assert(isequaln(S7{i, v}, S4{idx, v}), 'FIGS7 is not an exact FIGS4 duplicate.');
    end
end

%% Figure constants
blue = [46, 103, 148] / 255;
orange = [207, 111, 45] / 255;
deepBlue = [37, 91, 124] / 255;
warmGrey = [189, 184, 174] / 255;
lightBlue = [222, 234, 241] / 255;
lightGrey = [247, 247, 247] / 255;
dark = [42, 45, 47] / 255;
mid = [92, 96, 99] / 255;
gridGrey = [226, 227, 227] / 255;
zeroGrey = [0.40, 0.40, 0.40];

comparisonIDs = [ ...
    "consensus_risk_ge2_vs_no_risk_consensus"; ...
    "incomplete_vs_recovered_before_next"; ...
    "fire_overlap_vs_none"; ...
    "intact_vs_nonintact"];
comparisonLabels = { ...
    'Consensus risk \geq2 vs none'; ...
    'Incomplete vs recovered'; ...
    'Fire overlap vs none'; ...
    'Intact vs non-intact'};
shortLabels = {'Consensus', 'Incomplete', 'Fire overlap', 'Intact'};

fig = figure('Color', 'w', ...
    'Units', 'centimeters', ...
    'Position', [2, 1, 21, 29.7], ...
    'PaperUnits', 'centimeters', ...
    'PaperPositionMode', 'manual', ...
    'PaperPosition', [0, 0, 21, 29.7], ...
    'PaperSize', [21, 29.7], ...
    'InvertHardcopy', 'off', ...
    'Renderer', 'painters', ...
    'Visible', 'off', ...
    'MenuBar', 'none', ...
    'ToolBar', 'none', ...
    'Name', 'FigS3 Nature final v02', ...
    'NumberTitle', 'off');

%% Panel (a): paired archived forest plot
panel_title_fig(fig, 0.958, 0.055, 0.102, '(a)', 'Functional-legacy contrasts', 0.84, dark);

axA = axes(fig, 'Position', [0.265, 0.575, 0.675, 0.340], ...
    'FontName', 'Arial', 'FontSize', 9.2, 'Color', 'w', ...
    'Box', 'off', 'Layer', 'top', 'TickDir', 'out', 'LineWidth', 0.8);
hold(axA, 'on');
xMin = -0.034;
xMax = 0.019;
sampleDivider = 0.0125;
yBase = [4, 3, 2, 1];
yOffset = 0.13;
for i = 1:4
    if mod(i, 2) == 1
        patch(axA, [xMin, xMax, xMax, xMin], ...
            [yBase(i)-0.43, yBase(i)-0.43, yBase(i)+0.43, yBase(i)+0.43], ...
            lightGrey, 'EdgeColor', 'none', 'FaceAlpha', 1.0);
    end
end
plot(axA, [sampleDivider, sampleDivider], [0.50, 4.48], '-', ...
    'Color', [0.86, 0.87, 0.87], 'LineWidth', 0.75);
xline(axA, 0, '-', 'Color', zeroGrey, 'LineWidth', 1.0);

hG = gobjects(1);
hN = gobjects(1);
for i = 1:4
    comp = comparisonIDs(i);
    iG = find(D.comparison == comp & D.metric == "gpp_legacy");
    iN = find(D.comparison == comp & D.metric == "npp_legacy");
    assert(isscalar(iG) && isscalar(iN), 'Missing paired metric row.');

    yG = yBase(i) + yOffset;
    yN = yBase(i) - yOffset;
    hG = draw_interval(axA, double(D.ci_low(iG)), double(D.ci_high(iG)), ...
        double(D.difference_a_minus_b(iG)), yG, blue, 'o');
    hN = draw_interval(axA, double(D.ci_low(iN)), double(D.ci_high(iN)), ...
        double(D.difference_a_minus_b(iN)), yN, orange, 's');

    nText = sprintf('%s / %s', format_integer(double(D.n_a(iG))), format_integer(double(D.n_b(iG))));
    text(axA, xMax - 0.00035, yBase(i), nText, 'FontName', 'Arial', ...
        'FontSize', 8.25, 'Color', mid, 'HorizontalAlignment', 'right', ...
        'VerticalAlignment', 'middle');
end
text(axA, xMax - 0.00035, 4.57, 'n_A / n_B', 'Interpreter', 'tex', ...
    'FontName', 'Arial', 'FontSize', 8.25, 'FontWeight', 'bold', 'Color', mid, ...
    'HorizontalAlignment', 'right', 'VerticalAlignment', 'middle');

xlim(axA, [xMin, xMax]);
ylim(axA, [0.42, 4.65]);
set(axA, 'YTick', [1, 2, 3, 4], 'YTickLabel', flip(comparisonLabels), ...
    'XTick', -0.03:0.01:0.01, 'XGrid', 'on', 'YGrid', 'off', ...
    'GridColor', gridGrey, 'GridAlpha', 0.70, 'TickLabelInterpreter', 'tex');
minusSign = char(8722);
xlabel(axA, sprintf('Mean difference (A %c B), kg C m^{-2} yr^{-1}', minusSign), ...
    'Interpreter', 'tex', 'FontName', 'Arial', 'FontSize', 9.8, 'Color', dark);
legA = legend(axA, [hG, hN], {'GPP', 'NPP'}, 'FontName', 'Arial', 'FontSize', 9, ...
    'Orientation', 'horizontal', 'Box', 'off', 'Location', 'southwest');
legA.ItemTokenSize = [13, 9];

%% Panel (b): cross-metric direction concordance
panel_title_fig(fig, 0.493, 0.055, 0.102, '(b)', 'Cross-metric concordance', 0.42, dark);

axB = axes(fig, 'Position', [0.095, 0.090, 0.430, 0.350], ...
    'FontName', 'Arial', 'FontSize', 8.8, 'Color', 'w', ...
    'Box', 'off', 'Layer', 'top', 'TickDir', 'out', 'LineWidth', 0.8);
hold(axB, 'on');
bx = [-0.026, 0.006];
by = [-0.015, 0.006];
patch(axB, [bx(1), 0, 0, bx(1)], [by(1), by(1), 0, 0], ...
    lightBlue, 'EdgeColor', 'none', 'FaceAlpha', 0.24);
commonRange = [max(bx(1), by(1)), min(bx(2), by(2))];
plot(axB, commonRange, commonRange, '--', ...
    'Color', [0.74, 0.74, 0.74], 'LineWidth', 0.75);
xline(axB, 0, '-', 'Color', zeroGrey, 'LineWidth', 0.95);
yline(axB, 0, '-', 'Color', zeroGrey, 'LineWidth', 0.95);

labelOffsets = [0.00065, 0.00058; 0.00070, -0.00088; 0.00065, 0.00072; 0.00070, -0.00100];
for i = 1:4
    iG = find(D.comparison == comparisonIDs(i) & D.metric == "gpp_legacy");
    iN = find(D.comparison == comparisonIDs(i) & D.metric == "npp_legacy");
    xVal = double(D.difference_a_minus_b(iG));
    yVal = double(D.difference_a_minus_b(iN));
    supported = D.interval_support(iG) == "decrease_supported" && ...
        D.interval_support(iN) == "decrease_supported";
    if supported
        fillColor = deepBlue;
        edgeColor = deepBlue;
    else
        fillColor = warmGrey;
        edgeColor = [0.42, 0.42, 0.40];
    end
    scatter(axB, xVal, yVal, 56, fillColor, 'filled', ...
        'MarkerEdgeColor', edgeColor, 'LineWidth', 0.8);
    text(axB, xVal + labelOffsets(i,1), yVal + labelOffsets(i,2), shortLabels{i}, ...
        'FontName', 'Arial', 'FontSize', 8.35, 'Color', dark, ...
        'VerticalAlignment', 'middle');
end
xlim(axB, bx);
ylim(axB, by);
xTicksB = -0.025:0.005:0.005;
yTicksB = -0.015:0.005:0.005;
set(axB, 'XTick', xTicksB, 'YTick', yTicksB, ...
    'XTickLabel', cellstr(compose('%.3f', xTicksB)), ...
    'YTickLabel', cellstr(compose('%.3f', yTicksB)), ...
    'XGrid', 'on', 'YGrid', 'on', 'GridColor', gridGrey, 'GridAlpha', 0.70);
axB.XAxis.Exponent = 0;
axB.YAxis.Exponent = 0;
xlabel(axB, 'GPP difference', 'FontName', 'Arial', 'FontSize', 9.4, 'Color', dark);
ylabel(axB, 'NPP difference', 'FontName', 'Arial', 'FontSize', 9.4, 'Color', dark);
text(axB, bx(1)+0.0008, by(1)+0.0007, 'concordant decrease', ...
    'FontName', 'Arial', 'FontSize', 7.7, 'Color', deepBlue, ...
    'VerticalAlignment', 'bottom');

%% Panel (c): interval-based robustness matrix
panel_title_fig(fig, 0.493, 0.555, 0.602, '(c)', 'Archived-interval status', 0.343, dark);

axC = axes(fig, 'Position', [0.650, 0.090, 0.295, 0.350], ...
    'FontName', 'Arial', 'FontSize', 8.55, 'Color', 'w', ...
    'Box', 'off', 'TickDir', 'out', 'LineWidth', 0.8);
hold(axC, 'on');
for i = 1:4
    iG = find(D.comparison == comparisonIDs(i) & D.metric == "gpp_legacy");
    iN = find(D.comparison == comparisonIDs(i) & D.metric == "npp_legacy");
    rowY = 5 - i;
    cellState = [D.interval_support(iG) == "decrease_supported", ...
        D.interval_support(iN) == "decrease_supported"];
    bothSupported = all(cellState);
    for j = 1:2
        if cellState(j)
            face = lightBlue;
            label = 'CI < 0';
            tColor = deepBlue;
        else
            face = lightGrey;
            label = 'CI includes 0';
            tColor = mid;
        end
        rectangle(axC, 'Position', [j-0.46, rowY-0.39, 0.92, 0.78], ...
            'FaceColor', face, 'EdgeColor', 'w', 'LineWidth', 2);
        text(axC, j, rowY, label, 'Interpreter', 'tex', 'FontName', 'Arial', ...
            'FontSize', 7.75, 'Color', tColor, 'HorizontalAlignment', 'center', ...
            'VerticalAlignment', 'middle');
    end
    if bothSupported
        face = deepBlue;
        label = 'shared \downarrow';
        tColor = 'w';
    else
        face = warmGrey;
        label = 'not shared';
        tColor = dark;
    end
    rectangle(axC, 'Position', [2.54, rowY-0.39, 0.92, 0.78], ...
        'FaceColor', face, 'EdgeColor', 'w', 'LineWidth', 2);
    text(axC, 3, rowY, label, 'Interpreter', 'tex', 'FontName', 'Arial', ...
        'FontSize', 7.75, 'FontWeight', 'bold', 'Color', tColor, ...
        'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle');
end
xlim(axC, [0.5, 3.5]);
ylim(axC, [0.5, 4.5]);
set(axC, 'XTick', 1:3, 'XTickLabel', {'GPP', 'NPP', 'Across metrics'}, ...
    'XAxisLocation', 'top', 'YTick', 1:4, 'YTickLabel', flip(shortLabels), ...
    'TickLength', [0, 0], 'TickLabelInterpreter', 'none', ...
    'XTickLabelRotation', 0);

%% Editable FIG first, then clean A4 export
drawnow;
set(fig,'Visible','on', ...
    'WindowStyle','normal', ...
    'MenuBar','figure', ...
    'ToolBar','figure');
drawnow;
savefig(fig, figPath);

allAxes = findall(fig, 'Type', 'axes');
for i = 1:numel(allAxes)
    try
        allAxes(i).Toolbar.Visible = 'off';
    catch
    end
end
set(fig, 'MenuBar', 'none', 'ToolBar', 'none');
drawnow;
print(fig, pdfPath, '-dpdf', '-painters');
print(fig, pngPath, '-dpng', '-r600');

set(fig, 'Visible', 'on', 'WindowStyle', 'normal', ...
    'MenuBar', 'figure', 'ToolBar', 'figure');
for i = 1:numel(allAxes)
    try
        allAxes(i).Toolbar.Visible = 'on';
    catch
    end
end
drawnow;

fprintf('S3_V02_FIG=%s\n', figPath);
fprintf('S3_V02_PDF=%s\n', pdfPath);
fprintf('S3_V02_PNG=%s\n', pngPath);
fprintf('SCIENCE_CHANGED=NO DATA_CHANGED=NO NEW_ANALYSIS=NO NEW_MODEL_FIT=NO\n');

%% Local helpers
function panel_title_fig(fig, y, labelX, titleX, labelText, titleText, titleWidth, color)
    annotation(fig, 'textbox', [labelX, y, 0.050, 0.028], ...
        'String', labelText, 'LineStyle', 'none', 'Margin', 0, ...
        'FontName', 'Arial', 'FontSize', 13.0, 'FontWeight', 'bold', ...
        'Color', color, 'HorizontalAlignment', 'left', ...
        'VerticalAlignment', 'middle');
    annotation(fig, 'textbox', [titleX, y, titleWidth, 0.028], ...
        'String', titleText, 'LineStyle', 'none', 'Margin', 0, ...
        'FontName', 'Arial', 'FontSize', 12.5, 'FontWeight', 'bold', ...
        'Color', color, 'HorizontalAlignment', 'left', ...
        'VerticalAlignment', 'middle');
end

function h = draw_interval(ax, low, high, estimate, y, color, marker)
    plot(ax, [low, high], [y, y], '-', 'Color', color, 'LineWidth', 1.8);
    plot(ax, [low, low], [y-0.045, y+0.045], '-', 'Color', color, 'LineWidth', 1.1);
    plot(ax, [high, high], [y-0.045, y+0.045], '-', 'Color', color, 'LineWidth', 1.1);
    h = plot(ax, estimate, y, marker, 'MarkerSize', 6.2, ...
        'MarkerFaceColor', color, 'MarkerEdgeColor', 'w', 'LineWidth', 0.8);
end

function out = format_integer(value)
    out = sprintf('%.0f', value);
end
