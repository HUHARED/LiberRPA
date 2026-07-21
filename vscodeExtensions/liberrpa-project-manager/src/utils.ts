// FileName: utils.ts
import * as fs from "node:fs";

import { log } from "./output";

export const SET_RESERVED_WINDOWS_NAMES = new Set([
  "CON",
  "PRN",
  "AUX",
  "NUL",
  "COM1",
  "COM2",
  "COM3",
  "COM4",
  "COM5",
  "COM6",
  "COM7",
  "COM8",
  "COM9",
  "LPT1",
  "LPT2",
  "LPT3",
  "LPT4",
  "LPT5",
  "LPT6",
  "LPT7",
  "LPT8",
  "LPT9",
]);

export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }

  if (typeof error === "string") {
    return error;
  }

  return "Unknown error.";
}

export function readJsonFile(filePath: string): unknown {
  const content = fs.readFileSync(filePath, { encoding: "utf-8" });
  return JSON.parse(content) as unknown;
}

export function stringifyJson(value: unknown, indentation: number): string {
  const content = JSON.stringify(value, null, indentation);
  if (content === undefined) {
    throw new Error("Failed to serialize JSON value.");
  }

  return `${content}\n`;
}

export function writeJsonFile(filePath: string, value: object): void {
  fs.writeFileSync(filePath, stringifyJson(value, 2), { encoding: "utf-8" });
}

export function printUserCanceled(): void {
  log.info("User canceled.");
}
