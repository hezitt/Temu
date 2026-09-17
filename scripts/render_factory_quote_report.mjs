import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [payloadPath, outputPath] = process.argv.slice(2);
if (!payloadPath || !outputPath) {
  throw new Error("Usage: node render_factory_quote_report.mjs PAYLOAD_JSON OUTPUT_XLSX");
}

const payload = JSON.parse(await fs.readFile(payloadPath, "utf8"));
const workbook = Workbook.create();
const summary = workbook.worksheets.add("summary");
const normalized = workbook.worksheets.add("normalized");
const issues = workbook.worksheets.add("issues");
const fontFamily = "Arial";
const headerFill = "#1F4E78";
const lightBlue = "#D9EAF7";
const warningFill = "#FFF2CC";
const errorFill = "#FCE4D6";
const infoFill = "#E2F0D9";

for (const sheet of [summary, normalized, issues]) {
  sheet.showGridLines = false;
}

summary.getRange("A2:B2").values = [["工厂报价导入校验", null]];
summary.getRange("A2:B2").format.font = { name: fontFamily, size: 14, bold: true, color: "#1F1F1F" };
summary.getRange("A3:B3").format.borders = { bottom: { style: "thin", color: headerFill } };

const summaryRows = [
  ["文件", path.basename(payload.source_file)],
  ["文件 SHA-256", payload.source_sha256],
  ["供应商", payload.supplier_code],
  ["工作表", payload.source_sheet],
  ["Import Batch", payload.batch_id],
  ["模式", payload.mode],
  ["生效日期", payload.effective_date],
  ["导入时间 (UTC)", payload.started_at],
  ["解析候选", payload.summary.parsed_count],
  ["有效", payload.summary.valid_count],
  ["WARNING", payload.summary.warning_count],
  ["ERROR", payload.summary.error_count],
  ["SKIPPED", payload.summary.skipped_count],
  ["问题数", payload.summary.issue_count],
  ["计划新增", payload.plan.insert_count],
  ["计划更新", payload.plan.update_count],
  ["数据库无变化", payload.plan.unchanged_count],
  ["已提交数据库", payload.committed ? "是" : "否"],
];
summary.getRange("A5").write([[
  "指标",
  "值",
], ...summaryRows]);
summary.tables.add(`A5:B${summaryRows.length + 5}`, true, "FactoryQuoteSummary").style = "TableStyleMedium2";
summary.getRange(`A5:B${summaryRows.length + 5}`).format.font = { name: fontFamily, size: 10 };
summary.getRange("A5:B5").format = {
  fill: headerFill,
  font: { name: fontFamily, size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
summary.getRange(`A6:A${summaryRows.length + 5}`).format.font = { name: fontFamily, bold: true };
summary.getRange("B13").format.numberFormat = "yyyy-mm-dd hh:mm:ss";
summary.getRange("A1:A30").format.columnWidth = 24;
summary.getRange("B1:B30").format.columnWidth = 72;
summary.getRange("A1:B30").format.verticalAlignment = "center";

const normalizedHeaders = [
  "source_row",
  "source_column",
  "colors_count",
  "size",
  "width_cm",
  "height_cm",
  "variant_type",
  "unit_cost",
  "currency",
  "shipping_included",
  "status",
  "issue_codes",
];
const normalizedRows = payload.records.map((record) => [
  record.source_row_number,
  record.source_column,
  record.colors_count,
  record.size_code ?? record.raw_size,
  record.width_cm === null ? null : Number(record.width_cm),
  record.height_cm === null ? null : Number(record.height_cm),
  record.variant_type,
  record.unit_cost === null ? null : Number(record.unit_cost),
  record.currency,
  record.shipping_included ? "是" : "否",
  rowStatus(record),
  record.issues.map((issue) => issue.issue_code).join(", "),
]);
normalized.getRange("A1").write([normalizedHeaders, ...normalizedRows]);
normalized.tables.add(`A1:L${normalizedRows.length + 1}`, true, "NormalizedFactoryQuotes").style = "TableStyleMedium2";
normalized.getRange(`A1:L${normalizedRows.length + 1}`).format.font = { name: fontFamily, size: 10 };
normalized.getRange("A1:L1").format = {
  fill: headerFill,
  font: { name: fontFamily, size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
normalized.getRange(`E2:F${normalizedRows.length + 1}`).format.numberFormat = "0.00";
normalized.getRange(`H2:H${normalizedRows.length + 1}`).format.numberFormat = "#,##0.00";
normalized.getRange(`K2:K${normalizedRows.length + 1}`).conditionalFormats.add("containsText", {
  text: "WARNING",
  format: { fill: warningFill, font: { color: "#9C6500", bold: true } },
});
normalized.getRange(`K2:K${normalizedRows.length + 1}`).conditionalFormats.add("containsText", {
  text: "ERROR",
  format: { fill: errorFill, font: { color: "#C00000", bold: true } },
});
normalized.getRange(`K2:K${normalizedRows.length + 1}`).conditionalFormats.add("containsText", {
  text: "SKIPPED",
  format: { fill: infoFill, font: { color: "#548235" } },
});
normalized.freezePanes.freezeRows(1);

const issueHeaders = [
  "source_row",
  "source_column",
  "colors_count",
  "size",
  "variant_type",
  "raw_cost",
  "normalized_cost",
  "severity",
  "issue_code",
  "message",
];
const issueRows = [];
for (const record of payload.records) {
  for (const issue of record.issues) {
    issueRows.push([
      record.source_row_number,
      record.source_column,
      record.colors_count,
      record.size_code ?? record.raw_size,
      record.variant_type,
      record.raw_cost,
      record.unit_cost === null ? null : Number(record.unit_cost),
      issue.severity,
      issue.issue_code,
      issue.message,
    ]);
  }
}
issues.getRange("A1").write([issueHeaders, ...issueRows]);
if (issueRows.length > 0) {
  issues.tables.add(`A1:J${issueRows.length + 1}`, true, "FactoryQuoteIssues").style = "TableStyleMedium2";
}
issues.getRange(`A1:J${issueRows.length + 1}`).format.font = { name: fontFamily, size: 10 };
issues.getRange("A1:J1").format = {
  fill: headerFill,
  font: { name: fontFamily, size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
if (issueRows.length > 0) {
  issues.getRange(`G2:G${issueRows.length + 1}`).format.numberFormat = "#,##0.00";
  issues.getRange(`H2:H${issueRows.length + 1}`).conditionalFormats.add("containsText", {
    text: "WARNING",
    format: { fill: warningFill, font: { color: "#9C6500", bold: true } },
  });
  issues.getRange(`H2:H${issueRows.length + 1}`).conditionalFormats.add("containsText", {
    text: "ERROR",
    format: { fill: errorFill, font: { color: "#C00000", bold: true } },
  });
  issues.getRange(`H2:H${issueRows.length + 1}`).conditionalFormats.add("containsText", {
    text: "INFO",
    format: { fill: infoFill, font: { color: "#548235" } },
  });
}
issues.freezePanes.freezeRows(1);

for (const [sheet, range] of [
  [normalized, `A1:L${normalizedRows.length + 1}`],
  [issues, `A1:J${issueRows.length + 1}`],
]) {
  sheet.getRange(range).format.verticalAlignment = "center";
  sheet.getRange(range).format.autofitColumns();
  sheet.getRange(range).format.autofitRows();
}
normalized.getRange(`A1:A${normalizedRows.length + 1}`).format.columnWidth = 12;
normalized.getRange(`B1:B${normalizedRows.length + 1}`).format.columnWidth = 14;
normalized.getRange(`D1:D${normalizedRows.length + 1}`).format.columnWidth = 22;
normalized.getRange(`G1:G${normalizedRows.length + 1}`).format.columnWidth = 16;
normalized.getRange(`K1:K${normalizedRows.length + 1}`).format.columnWidth = 14;
normalized.getRange(`L1:L${normalizedRows.length + 1}`).format.columnWidth = 42;
issues.getRange(`A1:B${issueRows.length + 1}`).format.columnWidth = 14;
issues.getRange(`D1:D${issueRows.length + 1}`).format.columnWidth = 22;
issues.getRange(`E1:E${issueRows.length + 1}`).format.columnWidth = 16;
issues.getRange(`H1:I${issueRows.length + 1}`).format.columnWidth = 24;
issues.getRange(`J1:J${issueRows.length + 1}`).format.columnWidth = 54;
if (issueRows.length > 0) {
  issues.getRange(`J2:J${issueRows.length + 1}`).format.wrapText = true;
}
summary.tabColor = "#1F4E78";
normalized.tabColor = lightBlue;
issues.tabColor = "#C65911";

workbook.recalculate();
await fs.mkdir(path.dirname(outputPath), { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

function rowStatus(record) {
  if (record.issues.some((issue) => issue.severity === "ERROR")) return "ERROR";
  if (record.issues.some((issue) => ["NO_QUOTE", "SEPARATOR_ROW"].includes(issue.issue_code))) return "SKIPPED";
  if (record.issues.some((issue) => issue.severity === "WARNING")) return "WARNING";
  return "VALID";
}
