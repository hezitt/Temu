import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [payloadPath, outputPath] = process.argv.slice(2);
if (!payloadPath || !outputPath) {
  throw new Error("Usage: node render_listing_validation.mjs PAYLOAD_JSON OUTPUT_XLSX");
}

const payload = JSON.parse(await fs.readFile(payloadPath, "utf8"));
const workbook = Workbook.create();
const summary = workbook.worksheets.add("summary");
const products = workbook.worksheets.add("products");
const skus = workbook.worksheets.add("skus");
const issues = workbook.worksheets.add("issues");
const headerFill = "#1F4E78";
const titleFill = "#D9EAF7";
const font = "Arial";

for (const sheet of [summary, products, skus, issues]) sheet.showGridLines = false;

summary.getRange("A2:B2").values = [["Temu Listing Pre-flight Validation", null]];
summary.getRange("A2:B2").format = {
  fill: titleFill,
  font: { name: font, size: 14, bold: true, color: "#1F1F1F" },
};
const summaryRows = Object.entries(payload.summary);
summary.getRange("A4").write([["metric", "value"], ...summaryRows]);
styleTable(summary, `A4:B${summaryRows.length + 4}`, "ListingValidationSummary");
summary.getRange("A1:A40").format.columnWidth = 30;
summary.getRange("B1:B40").format.columnWidth = 55;

writeSheet(
  products,
  ["design_id", "factory_design_code", "title", "valid", "sku_count", "valid_sku_count", "main_image"],
  payload.products,
  "ListingProducts",
);
writeSheet(
  skus,
  [
    "design_id",
    "sku",
    "size",
    "colors_count",
    "framed",
    "factory_cost_cny",
    "shipping_cost_usd",
    "exchange_rate",
    "unit_variable_cost_cny",
    "valid",
  ],
  payload.skus,
  "ListingSkus",
);
writeSheet(
  issues,
  ["severity", "code", "design_id", "sku", "message"],
  payload.issues,
  "ListingIssues",
);

setWidths(products, [24, 22, 52, 12, 12, 16, 56]);
setWidths(skus, [24, 32, 12, 14, 12, 18, 18, 16, 22, 12]);
setWidths(issues, [12, 28, 24, 36, 82]);
issues.getRange(`E2:E${Math.max(2, payload.issues.length + 1)}`).format.wrapText = true;
issues.getRange(`A2:E${Math.max(2, payload.issues.length + 1)}`).format.autofitRows();
summary.tabColor = "#1F4E78";
products.tabColor = "#70AD47";
skus.tabColor = "#5B9BD5";
issues.tabColor = "#C65911";

workbook.recalculate();
await fs.mkdir(path.dirname(outputPath), { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

function writeSheet(sheet, headers, records, tableName) {
  const rows = records.map((record) => headers.map((header) => record[header] ?? null));
  sheet.getRange("A1").write([headers, ...rows]);
  const lastColumn = columnName(headers.length);
  const lastRow = rows.length + 1;
  if (rows.length > 0) styleTable(sheet, `A1:${lastColumn}${lastRow}`, tableName);
  else styleHeader(sheet, `A1:${lastColumn}1`);
  sheet.getRange(`A1:${lastColumn}${lastRow}`).format.font = { name: font, size: 10 };
  sheet.getRange(`A1:${lastColumn}${lastRow}`).format.autofitColumns();
  sheet.getRange(`A1:${lastColumn}${lastRow}`).format.autofitRows();
  sheet.freezePanes.freezeRows(1);
}

function styleTable(sheet, range, name) {
  sheet.tables.add(range, true, name).style = "TableStyleMedium2";
  const header = range.split(":")[0].replace(/\d+$/, "") + "1";
  void header;
  const match = range.match(/^([A-Z]+)(\d+):([A-Z]+)(\d+)$/);
  if (match) styleHeader(sheet, `${match[1]}${match[2]}:${match[3]}${match[2]}`);
}

function styleHeader(sheet, range) {
  sheet.getRange(range).format = {
    fill: headerFill,
    font: { name: font, size: 10, bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center",
    verticalAlignment: "center",
  };
}

function columnName(number) {
  let result = "";
  let value = number;
  while (value > 0) {
    value -= 1;
    result = String.fromCharCode(65 + (value % 26)) + result;
    value = Math.floor(value / 26);
  }
  return result;
}

function setWidths(sheet, widths) {
  widths.forEach((width, index) => {
    const column = columnName(index + 1);
    sheet.getRange(`${column}1:${column}2000`).format.columnWidth = width;
  });
}
