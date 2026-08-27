import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";


const configPath = process.env.NEE_SOURCE_DATA_CONFIG;
if (!configPath) throw new Error("Set NEE_SOURCE_DATA_CONFIG to the generated JSON configuration.");
const previewRoot = process.env.NEE_SOURCE_DATA_PREVIEW_ROOT || path.join(path.dirname(configPath), "previews");
const config = JSON.parse(await fs.readFile(configPath, "utf8"));
await fs.mkdir(previewRoot, { recursive: true });

const BLUE = "#1F4E78";
const LIGHT = "#D9EAF7";
const MID = "#D5DCE2";
const INK = "#1F2933";

function safeName(name) {
  return name.replace(/[^A-Za-z0-9_.-]+/g, "_");
}

async function addCsvSheet(workbook, item) {
  const csvText = await fs.readFile(item.path, "utf8");
  // artifact-tool can only hydrate CSV into an empty collaborative document.
  // Parse each frozen CSV in an isolated workbook, then copy its values into
  // the final multi-sheet workbook without transforming scientific content.
  const imported = await Workbook.fromCSV(csvText, { sheetName: item.sheet_name });
  const importedSheet = imported.worksheets.getItem(item.sheet_name);
  const rows = item.n_rows + 1;
  const cols = item.columns.length;
  const importedValues = importedSheet.getRangeByIndexes(0, 0, rows, cols).values;
  const sheet = workbook.worksheets.add(item.sheet_name);
  sheet.getRangeByIndexes(0, 0, rows, cols).values = importedValues;
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);
  const used = sheet.getRangeByIndexes(0, 0, rows, cols);
  used.format = {
    font: { name: "Arial", size: 9, color: INK },
    verticalAlignment: "center",
  };
  const header = sheet.getRangeByIndexes(0, 0, 1, cols);
  header.format = {
    fill: BLUE,
    font: { name: "Arial", size: 9, bold: true, color: "#FFFFFF" },
    wrapText: true,
    verticalAlignment: "center",
    borders: { preset: "outside", style: "thin", color: BLUE },
  };
  header.format.rowHeight = 34;
  used.format.autofitColumns();
  for (let c = 0; c < cols; c += 1) {
    const headerText = String(item.columns[c] ?? "");
    const width = Math.max(11, Math.min(28, Math.ceil(headerText.length * 0.9) + 2));
    sheet.getRangeByIndexes(0, c, rows, 1).format.columnWidth = width;
  }
  if (rows > 1) {
    sheet.getRangeByIndexes(1, 0, rows - 1, cols).format.borders = {
      insideHorizontal: { style: "hair", color: "#E7EBEF" },
    };
  }
}

async function buildWorkbook(spec) {
  const workbook = Workbook.create();
  const readme = workbook.worksheets.add("README");
  readme.showGridLines = false;
  readme.getRange("A1:F1").merge();
  readme.getRange("A1").values = [[`${spec.display_item} source data`]];
  readme.getRange("A1:F1").format = {
    fill: BLUE,
    font: { name: "Arial", size: 15, bold: true, color: "#FFFFFF" },
    verticalAlignment: "center",
  };
  readme.getRange("A1:F1").format.rowHeight = 28;
  readme.getRange("A3").values = [["Scope note"]];
  readme.getRange("B3:F3").merge();
  readme.getRange("B3").values = [[spec.notes]];
  readme.getRange("A3:F3").format = {
    fill: LIGHT,
    font: { name: "Arial", size: 9, color: INK },
    wrapText: true,
    verticalAlignment: "top",
    borders: { preset: "outside", style: "thin", color: MID },
  };
  readme.getRange("A3").format.font = { name: "Arial", size: 9, bold: true, color: INK };
  readme.getRange("A3:F3").format.rowHeight = 54;
  const headings = [["Sheet / file", "Rows", "Columns", "Frozen source path", "Source SHA-256", "Role"]];
  const rows = [];
  for (const sheet of spec.sheets) {
    rows.push([sheet.sheet_name, sheet.n_rows, sheet.columns.length, sheet.path, sheet.sha256, "Workbook sheet"]);
  }
  for (const ext of spec.external_files ?? []) {
    rows.push([path.basename(ext.path), ext.n_rows, ext.columns.length, ext.path, ext.sha256, "External source-data CSV"]);
  }
  readme.getRange("A5:F5").values = headings;
  if (rows.length) {
    readme.getRangeByIndexes(5, 0, rows.length, 6).values = rows;
  }
  readme.getRange("A5:F5").format = {
    fill: BLUE,
    font: { name: "Arial", size: 9, bold: true, color: "#FFFFFF" },
    wrapText: true,
    borders: { preset: "outside", style: "thin", color: BLUE },
  };
  if (rows.length) {
    readme.getRangeByIndexes(5, 0, rows.length, 6).format = {
      font: { name: "Arial", size: 9, color: INK },
      wrapText: true,
      verticalAlignment: "top",
      borders: { insideHorizontal: { style: "hair", color: "#E7EBEF" } },
    };
  }
  readme.getRange("A1:F20").format.font = { name: "Arial", color: INK };
  readme.getRange("A1:F1").format.font = { name: "Arial", size: 15, bold: true, color: "#FFFFFF" };
  readme.getRange("A5:F5").format.font = { name: "Arial", size: 9, bold: true, color: "#FFFFFF" };
  readme.getRange("A:A").format.columnWidth = 24;
  readme.getRange("B:C").format.columnWidth = 10;
  readme.getRange("D:D").format.columnWidth = 48;
  readme.getRange("E:E").format.columnWidth = 48;
  readme.getRange("F:F").format.columnWidth = 22;
  readme.freezePanes.freezeRows(5);

  for (const sheet of spec.sheets) {
    await addCsvSheet(workbook, sheet);
  }

  const wbPreviewDir = path.join(previewRoot, safeName(path.parse(spec.filename).name));
  await fs.mkdir(wbPreviewDir, { recursive: true });
  const previewRows = Math.min(12, 6 + rows.length);
  const readmePreview = await workbook.render({ sheetName: "README", range: `A1:F${previewRows}`, scale: 1.3, format: "png" });
  await fs.writeFile(path.join(wbPreviewDir, "README.png"), new Uint8Array(await readmePreview.arrayBuffer()));
  for (const sheet of spec.sheets) {
    const lastRow = Math.min(sheet.n_rows + 1, 18);
    const lastCol = Math.min(sheet.columns.length, 10);
    const colLetter = String.fromCharCode(64 + lastCol);
    const preview = await workbook.render({ sheetName: sheet.sheet_name, range: `A1:${colLetter}${lastRow}`, scale: 1.15, format: "png" });
    await fs.writeFile(path.join(wbPreviewDir, `${safeName(sheet.sheet_name)}.png`), new Uint8Array(await preview.arrayBuffer()));
  }

  const errors = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
    options: { useRegex: true, maxResults: 100 },
    summary: `formula error scan ${spec.filename}`,
  });
  const key = await workbook.inspect({
    kind: "table",
    sheetId: "README",
    range: `A1:F${previewRows}`,
    include: "values,formulas",
    tableMaxRows: previewRows,
    tableMaxCols: 6,
    maxChars: 4000,
  });
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(spec.output);
  return {
    output: spec.output,
    sheets: ["README", ...spec.sheets.map((x) => x.sheet_name)],
    source_rows: spec.sheets.reduce((a, b) => a + b.n_rows, 0),
    formula_error_scan: errors.ndjson,
    key_inspection: key.ndjson,
  };
}

const results = [];
for (const spec of config) {
  results.push(await buildWorkbook(spec));
}
await fs.writeFile(path.join(root, "_work", "source_workbook_validation.json"), JSON.stringify(results, null, 2));
process.stdout.write(JSON.stringify({ workbooks: results.length, outputs: results.map((x) => x.output) }, null, 2));
