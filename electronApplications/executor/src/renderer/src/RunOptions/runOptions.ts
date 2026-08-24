import { useInformationStore } from "../Store/informationStore";
import type { TypeCustomProjectArgs, TypeLogLevel } from "../../../shared/runOptions";

export const ARR_LOG_LEVEL: TypeLogLevel[] = [
  "VERBOSE",
  "DEBUG",
  "INFO",
  "WARNING",
  "ERROR",
  "CRITICAL",
];

export function getArgumentValueNote(value: unknown): string {
  return (
    "Original value:<br/>" +
    JSON.stringify(value, null, 0) +
    "<br/>(The value must be deserializable.<br/>Press Enter or leave the input box to update.)" +
    (typeof value === "object" && value !== null && !Array.isArray(value)
      ? "<br/>(It is a dictionary, so the keys may be reordered.)"
      : "")
  );
}

export function updateCustomProjectArgumentValue(
  arrCustomProjectArgument: TypeCustomProjectArgs,
  arrValueCache: string[],
  index: number,
  value: string,
): void {
  try {
    arrCustomProjectArgument[index][1] = JSON.parse(value);
  } catch {
    const informationStore = useInformationStore();
    informationStore.showAlertMessage(`It can't be deserialized: ${value}`);
    arrValueCache[index] = JSON.stringify(arrCustomProjectArgument[index][1]);
  }
}
