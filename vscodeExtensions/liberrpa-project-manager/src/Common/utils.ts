// FileName: utils.ts

import * as fs from "node:fs";

export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    if (error.cause === undefined) {
      return error.message;
    }
    return `${error.message}\nCaused by: ${getErrorMessage(error.cause)}`;
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
