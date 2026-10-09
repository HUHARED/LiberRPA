// FileName: runOptions.ts

import { useInformationStore } from "../Store/informationStore";
import { LogLevel } from "../../../shared/runOptions";
import type { CustomProjectArgs } from "../../../shared/runOptions";

export const ARR_LOG_LEVEL: LogLevel[] = Object.values(LogLevel);

export function getArgumentValueNote(value: unknown): string {
  const strValue = JSON.stringify(value, null, 0) ?? "undefined";
  const arrLine = [
    "Original value:",
    strValue,
    "The value must be valid JSON.",
    "Press Enter or leave the input box to update.",
  ];
  if (typeof value === "object" && value !== null && !Array.isArray(value)) {
    arrLine.push("Object keys may be reordered.");
  }
  return arrLine.join("\n");
}

export function updateCustomProjectArgumentValue(
  customProjectArgumentArr: CustomProjectArgs,
  valueCacheArr: string[],
  index: number,
  value: string,
): void {
  try {
    customProjectArgumentArr[index][1] = JSON.parse(value);
  } catch {
    const informationStore = useInformationStore();
    informationStore.showAlertMessage(`It can't be deserialized: ${value}`);
    valueCacheArr[index] = JSON.stringify(customProjectArgumentArr[index][1]);
  }
}
