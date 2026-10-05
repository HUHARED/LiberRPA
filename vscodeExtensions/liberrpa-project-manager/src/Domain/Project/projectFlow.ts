// FileName: projectFlow.ts

import { isRecord } from "../../Common/typeCheck";

const INT_MAX_CUSTOM_ARGUMENT_COUNT = 100;
const INT_MAX_CUSTOM_ARGUMENT_JSON_BYTES = 64 * 1024;
const INT_MAX_JSON_DEPTH = 64;

function validateJsonString(value: string, sourceName: string): void {
  if (/[\uD800-\uDFFF]/u.test(value)) {
    throw new Error(`${sourceName} must contain valid Unicode text.`);
  }
  if (value.includes("\0")) {
    throw new Error(`${sourceName} cannot contain a null character.`);
  }
}

function ensureJsonValue(
  value: unknown,
  sourceName: string,
  depth = 0,
  ancestorSet = new Set<object>(),
): void {
  if (depth > INT_MAX_JSON_DEPTH) {
    throw new Error(`${sourceName} cannot exceed ${INT_MAX_JSON_DEPTH} levels of nesting.`);
  }
  if (value === null || typeof value === "boolean") {
    return;
  }
  if (typeof value === "string") {
    validateJsonString(value, sourceName);
    return;
  }
  if (typeof value === "number") {
    if (
      !Number.isFinite(value) ||
      (Number.isInteger(value) && !Number.isSafeInteger(value))
    ) {
      throw new Error(`${sourceName} must contain finite numbers and safe integers.`);
    }
    return;
  }
  if (typeof value !== "object") {
    throw new Error(`${sourceName} must be JSON-compatible.`);
  }
  if (ancestorSet.has(value)) {
    throw new Error(`${sourceName} cannot contain circular references.`);
  }

  ancestorSet.add(value);
  try {
    if (Array.isArray(value)) {
      for (let intIndex = 0; intIndex < value.length; intIndex++) {
        ensureJsonValue(
          value[intIndex],
          `${sourceName}[${intIndex}]`,
          depth + 1,
          ancestorSet,
        );
      }
      return;
    }

    if (!isRecord(value)) {
      throw new Error(`${sourceName} must be JSON-compatible.`);
    }
    for (const [strKey, item] of Object.entries(value)) {
      validateJsonString(strKey, `${sourceName} object key`);
      ensureJsonValue(item, `${sourceName}.${strKey}`, depth + 1, ancestorSet);
    }
  } finally {
    ancestorSet.delete(value);
  }
}

export function validateProjectFlowCustomArguments(value: unknown): void {
  if (!isRecord(value)) {
    throw new Error("project.flow must be a JSON object.");
  }
  const arrArgument: unknown = value["customPrjArgs"];
  if (!Array.isArray(arrArgument)) {
    throw new Error("project.flow customPrjArgs must be an array.");
  }
  if (arrArgument.length > INT_MAX_CUSTOM_ARGUMENT_COUNT) {
    throw new Error(
      `project.flow customPrjArgs cannot exceed ${String(INT_MAX_CUSTOM_ARGUMENT_COUNT)} pairs.`,
    );
  }
  for (let intIndex = 0; intIndex < arrArgument.length; intIndex++) {
    const argument: unknown = arrArgument[intIndex];
    if (
      !Array.isArray(argument) ||
      argument.length !== 2 ||
      typeof argument[0] !== "string"
    ) {
      throw new Error(
        `project.flow customPrjArgs[${String(intIndex)}] must be a [string, value] pair.`,
      );
    }
  }
  // Count the complete ordered list at depth zero, including the pair arrays.
  ensureJsonValue(arrArgument, "project.flow customPrjArgs");
  if (
    Buffer.byteLength(JSON.stringify(arrArgument), "utf-8") >
    INT_MAX_CUSTOM_ARGUMENT_JSON_BYTES
  ) {
    throw new Error("project.flow customPrjArgs exceeds the 64 KiB JSON limit.");
  }
}
