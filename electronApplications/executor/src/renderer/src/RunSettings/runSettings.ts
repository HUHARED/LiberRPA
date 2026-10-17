// FileName: runSettings.ts

import { useInformationStore } from "../Store/informationStore";
import { LogLevel } from "../../../shared/runSettings";
import type { CustomProjectArgs } from "../../../shared/runSettings";

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
    customProjectArgumentArr[index][1] = JSON.parse(
      value,
      (_key, argumentValue: unknown) => {
        if (typeof argumentValue === "number") {
          if (!Number.isFinite(argumentValue)) {
            throw new Error("Numbers must be finite.");
          }
          if (Number.isInteger(argumentValue) && !Number.isSafeInteger(argumentValue)) {
            throw new Error(
              "Integers must be between -9007199254740991 and 9007199254740991.",
            );
          }
        }
        return argumentValue;
      },
    );
  } catch (e: unknown) {
    const informationStore = useInformationStore();
    informationStore.showAlertMessage(
      e instanceof Error && !(e instanceof SyntaxError)
        ? e.message
        : "Enter a valid JSON value.",
    );
    valueCacheArr[index] = JSON.stringify(customProjectArgumentArr[index][1]);
  }
}
