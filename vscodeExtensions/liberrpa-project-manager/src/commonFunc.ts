// FileName: commonFunc.ts

import { log } from "./output";

export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }

  if (typeof error === "string") {
    return error;
  }

  return "Unknown error.";
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function stringifyJson(value: unknown, indentation: number): string {
  const content = JSON.stringify(value, null, indentation);
  if (content === undefined) {
    throw new Error("Failed to serialize JSON value.");
  }

  return `${content}\n`;
}

export function printUserCanceled(): void {
  log.info("User canceled.");
}
