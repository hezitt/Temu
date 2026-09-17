import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const [templatePath, payloadPath, outputPath] = process.argv.slice(2);
if (!templatePath || !payloadPath || !outputPath) {
  throw new Error("Usage: node fill_temu_template.mjs TEMPLATE_XLSX PAYLOAD_JSON OUTPUT_XLSX");
}

const payload = JSON.parse(await fs.readFile(payloadPath, "utf8"));
const mapping = payload.mapping;
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(templatePath));
const sheet = workbook.worksheets.items.find((item) => item.name === mapping.sheet_name);
if (!sheet) {
  throw new Error(`Mapped worksheet not found: ${mapping.sheet_name}`);
}

const headerRow = Number(mapping.header_row);
const firstDataRow = Number(mapping.first_data_row);
if (!Number.isInteger(headerRow) || !Number.isInteger(firstDataRow) || firstDataRow <= headerRow) {
  throw new Error("Mapping requires valid header_row and first_data_row values");
}

for (const [canonicalField, column] of Object.entries(mapping.columns)) {
  if (!/^[A-Z]{1,3}$/.test(column)) {
    throw new Error(`Invalid Excel column for ${canonicalField}: ${column}`);
  }
  const expectedHeader = mapping.expected_headers?.[canonicalField];
  if (expectedHeader !== undefined) {
    const actual = sheet.getRange(`${column}${headerRow}`).values?.[0]?.[0];
    if (actual !== expectedHeader) {
      throw new Error(
        `Template header mismatch at ${column}${headerRow}: expected ${expectedHeader}, got ${actual}`,
      );
    }
  }
}

for (let index = 0; index < payload.rows.length; index += 1) {
  const rowNumber = firstDataRow + index;
  const record = payload.rows[index];
  for (const [canonicalField, column] of Object.entries(mapping.columns)) {
    let value = record[canonicalField];
    if (typeof value === "boolean") value = value ? "YES" : "NO";
    sheet.getRange(`${column}${rowNumber}`).values = [[value ?? null]];
  }
}

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
