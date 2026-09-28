// FileName: queueImport.ts

import {
  read,
  utils,
  type WorkBook,
  type WorkSheet,
  type CellObject,
  type Range,
} from "xlsx";

import type { JsonValueInput as JsonValue } from "../api/generated/browserApi";

import { validateJsonValue } from "./validators";

export interface QueueImportSource {
  kind: "table" | "txt" | "json" | "jsonl";
  workbook?: WorkBook;
  text?: string;
  excel: boolean;
}
export interface QueueImportRow {
  source: string;
  value: JsonValue;
}
export interface QueueImportOptions {
  worksheet: string;
  column: number | null;
  header: boolean;
  format: "text" | "json";
}
const MAX_BYTES = 2 * 1024 * 1024;
const MAX_ROWS = 10000;

export async function readQueueFile(file: File): Promise<QueueImportSource> {
  if (file.size > MAX_BYTES) throw new Error("The source file exceeds 2 MiB.");
  const extension = file.name.split(".").at(-1)?.toLowerCase();
  const bytes = await file.arrayBuffer();
  if (["xlsx", "xls"].includes(extension ?? "")) {
    return {
      kind: "table",
      excel: true,
      workbook: read(bytes, {
        type: "array",
        sheetRows: MAX_ROWS + 1,
        cellFormula: true,
        cellText: true,
        cellNF: true,
      }),
    };
  }
  const text = new TextDecoder("utf-8", { fatal: true })
    .decode(bytes)
    .replace(/^\uFEFF/, "");
  if (extension === "csv" || extension === "tsv") {
    return {
      kind: "table",
      excel: false,
      workbook: read(text, {
        type: "string",
        raw: true,
        FS: extension === "tsv" ? "\t" : ",",
        sheetRows: MAX_ROWS + 1,
      }),
    };
  }
  if (extension === "txt" || extension === "json" || extension === "jsonl")
    return { kind: extension, text, excel: false };
  throw new Error("Choose an XLSX, XLS, CSV, TSV, TXT, JSON, or JSONL file.");
}

function sheetRange(sheet: WorkSheet): Range {
  const fullRange: unknown = sheet["!fullref"];
  const range = utils.decode_range(
    typeof fullRange === "string" ? fullRange : (sheet["!ref"] ?? "A1"),
  );
  if (range.e.r >= MAX_ROWS || range.e.c >= 256)
    throw new Error("Use a worksheet with at most 10,000 rows and 256 columns.");
  return range;
}

export function getQueueColumns(
  source: QueueImportSource,
  worksheet: string,
  header: boolean,
): { title: string; value: number }[] {
  const sheet = source.workbook?.Sheets[worksheet];
  if (!sheet) return [];
  const range = sheetRange(sheet);
  return Array.from({ length: range.e.c - range.s.c + 1 }, (_, offset) => {
    const column = range.s.c + offset;
    const cell = sheet[utils.encode_cell({ r: range.s.r, c: column })] as
      CellObject | undefined;
    const title = header && cell ? utils.format_cell(cell).slice(0, 100) : "";
    return {
      value: column,
      title: `${utils.encode_col(column)}${title ? ` — ${title}` : ""}`,
    };
  });
}

export function convertQueueFile(
  source: QueueImportSource,
  options: QueueImportOptions,
): { rows: QueueImportRow[]; skipped: number } {
  const rows: QueueImportRow[] = [];
  let skipped = 0;
  function add(value: JsonValue, location: string): void {
    try {
      validateJsonValue(value);
      if (new TextEncoder().encode(JSON.stringify(value)).length > 1024 * 1024)
        throw new Error("The item exceeds 1 MiB.");
      if (rows.length >= 100) throw new Error("A batch can contain at most 100 items.");
      rows.push({ source: location, value });
    } catch (e) {
      throw new Error(`${location}: ${e instanceof Error ? e.message : "Invalid value."}`, {
        cause: e,
      });
    }
  }
  function parse(text: string, location: string): JsonValue {
    try {
      return JSON.parse(text) as JsonValue;
    } catch {
      throw new Error(`${location}: Enter one complete JSON value.`);
    }
  }
  if (source.kind === "json") {
    const value = parse(source.text ?? "", "JSON");
    if (!Array.isArray(value))
      throw new Error("JSON files must contain a top-level array.");
    value.forEach((entry, index) => add(entry, `Element ${index + 1}`));
  } else if (source.kind === "txt" || source.kind === "jsonl") {
    (source.text ?? "").split(/\r\n|\n|\r/).forEach((line, index) => {
      if (!line.trim()) {
        skipped += 1;
        return;
      }
      const location = `Line ${index + 1}`;
      add(
        source.kind === "jsonl" || options.format === "json" ? parse(line, location) : line,
        location,
      );
    });
  } else {
    const sheet = source.workbook?.Sheets[options.worksheet];
    if (!sheet) throw new Error("Select a worksheet and column.");
    const range = sheetRange(sheet);
    if (options.column === null) throw new Error("Select a worksheet and column.");
    for (let row = range.s.r + (options.header ? 1 : 0); row <= range.e.r; row += 1) {
      const address = utils.encode_cell({ r: row, c: options.column });
      const cell = sheet[address] as CellObject | undefined;
      const location = `${options.worksheet}!${address}`;
      if (cell?.t === "e" || (cell?.f && cell.v === undefined))
        throw new Error(`${location}: No readable saved cell result.`);
      if (
        !cell ||
        cell.v === undefined ||
        cell.v === null ||
        String(cell.v).trim() === ""
      ) {
        skipped += 1;
        continue;
      }
      const text = utils.format_cell(cell);
      const value =
        options.format === "text"
          ? text
          : typeof cell.v === "boolean"
            ? cell.v
            : parse(text, location);
      add(value, location);
    }
  }
  if (!rows.length) throw new Error("No nonempty items were found.");
  if (
    new TextEncoder().encode(
      JSON.stringify({
        items: rows.map((row) => row.value),
        request_id: "00000000-0000-4000-8000-000000000000",
      }),
    ).length > MAX_BYTES
  )
    throw new Error("The complete JSON request exceeds 2 MiB. Reduce this batch.");
  return { rows, skipped };
}
