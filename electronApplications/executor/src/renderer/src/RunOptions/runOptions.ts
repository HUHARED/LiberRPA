import { computed, ref } from "vue";
import type { Ref, WritableComputedRef } from "vue";

import { useInformationStore } from "../Store/informationStore";
import type {
  TypeColumns_LogLevel,
  TypeCustomProjectArgs,
  DictColumns_Project_Detail,
  DictColumns_Schedule_Detail,
  DictColumns_Schedule_Detail_BeforeInsert,
} from "../../../shared/interface";

export const ARR_LOG_LEVEL: TypeColumns_LogLevel[] = [
  "VERBOSE",
  "DEBUG",
  "INFO",
  "WARNING",
  "ERROR",
  "CRITICAL",
];

type TypeRunOptionsDetail =
  | DictColumns_Project_Detail
  | DictColumns_Schedule_Detail
  | DictColumns_Schedule_Detail_BeforeInsert;

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

export function createCustomProjectArgumentValueCache(
  dictDetail: TypeRunOptionsDetail | undefined,
): Ref<string[]> {
  return ref(
    dictDetail?.custom_prj_args.map((item) => JSON.stringify(item[1], null, 0)) ?? [],
  );
}

export function getCustomProjectArgumentValueCache(
  dictDetail: TypeRunOptionsDetail,
): string[] {
  return dictDetail.custom_prj_args.map((item) => JSON.stringify(item[1], null, 0));
}

export function createTimeoutMinModel(
  dictDetail: TypeRunOptionsDetail | undefined,
): WritableComputedRef<number, number> {
  return computed<number>({
    get() {
      return dictDetail?.timeout_min ?? 0;
    },
    set(newValue: number | null) {
      if (newValue === null) {
        const informationStore = useInformationStore();
        informationStore.showAlertMessage(`It's not an integer >= 0. (${newValue})`);
        return;
      }

      if (newValue >= 0 && dictDetail !== undefined) {
        dictDetail.timeout_min = newValue;
      }
    },
  });
}
