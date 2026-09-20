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

if ((mapping.row_strategy ?? "flat") === "spu_with_sku_rows") {
  const groups = new Map();
  for (const record of payload.rows) {
    const key = record.spu_item_code;
    if (!key) throw new Error("spu_with_sku_rows requires spu_item_code on every row");
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(record);
  }
  let rowNumber = firstDataRow;
  for (const records of groups.values()) {
    const first = records[0];
    writeConfiguredRow(sheet, rowNumber, first, mapping.spu_columns ?? {});
    rowNumber += 1;
    for (const record of records) {
      writeConfiguredRow(sheet, rowNumber, record, mapping.sku_columns ?? {});
      rowNumber += 1;
    }
  }
} else {
  for (let index = 0; index < payload.rows.length; index += 1) {
    const rowNumber = firstDataRow + index;
    const record = payload.rows[index];
    for (const [canonicalField, column] of Object.entries(mapping.columns)) {
      let value = record[canonicalField];
      if (typeof value === "boolean") value = value ? "YES" : "NO";
      sheet.getRange(`${column}${rowNumber}`).values = [[value ?? null]];
    }
  }
}

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

function writeConfiguredRow(sheet, rowNumber, record, columnSpecs) {
  for (const [field, spec] of Object.entries(columnSpecs)) {
    if (!spec || typeof spec !== "object") {
      throw new Error(`Invalid column spec for ${field}`);
    }
    const column = spec.column;
    if (!/^[A-Z]{1,3}$/.test(column)) {
      throw new Error(`Invalid Excel column for ${field}: ${column}`);
    }
    const value = resolveValue(record, spec);
    sheet.getRange(`${column}${rowNumber}`).values = [[value ?? null]];
  }
}

function resolveValue(record, spec) {
  if (Object.hasOwn(spec, "value")) return spec.value;
  let value = record[spec.source];
  if (Number.isInteger(spec.index)) value = Array.isArray(value) ? value[spec.index] : null;
  switch (spec.transform) {
    case undefined:
      return value;
    case "frame_type":
      return value === true ? "有框" : value === false ? "无框" : null;
    case "spu_frame_type":
      if (typeof value === "string" && value.trim()) return value.trim();
      return record.framed === true ? "有框" : record.framed === false ? "无框" : null;
    case "frame_variant_label":
      return record.framed === true ? "with frame" : record.framed === false ? "no frame" : null;
    case "size_label":
      return `${record.width_cm}x${record.height_cm}cm`;
    case "paint_color_bucket":
      return [6, 12, 24, 36, 48, 72, 96].includes(Number(value)) ? Number(value) : "其他";
    case "other_paint_color_count":
      return [6, 12, 24, 36, 48, 72, 96].includes(Number(value)) ? null : value;
    case "other_paint_color_unit":
      return [6, 12, 24, 36, 48, 72, 96].includes(Number(record.colors_count))
        ? null
        : "个";
    case "package_dimension_desc": {
      const dimensions = [
        record.package_length_cm,
        record.package_width_cm,
        record.package_height_cm,
      ]
        .filter((item) => item !== null && item !== undefined)
        .map(Number)
        .sort((a, b) => b - a);
      return dimensions[spec.index] ?? null;
    }
    default:
      throw new Error(`Unknown transform: ${spec.transform}`);
  }
}
