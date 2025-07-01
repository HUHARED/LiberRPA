// FileName: commonFunc.ts
import { ref, computed, WritableComputedRef, Ref } from "vue";
import cronstrue from "cronstrue";

import { invokeMain } from "./ipcOfRenderer";
import { useInformationStore } from "./store";
import {
  DictColumns_Project_Detail,
  DictColumns_Scheduler_Detail,
  DictColumns_Scheduler_Detail_BeforeInsert,
} from "../../shared/interface";

export function generateValueNote(value: any): string {
  return (
    "Original value:<br/>" +
    JSON.stringify(value, null, 0) +
    "<br/>(The value must can be deserialized.<br/>Press Enter or leave the inputbox to update.)" +
    (typeof value === "object" && value !== null && !Array.isArray(value)
      ? "<br/>(It is a dictionary, the keys may be reordered.)"
      : "")
  );
}

export function updateCusPrjArgsValue(
  arrCusPrjArgs: string[][],
  arrValueCache: string[],
  index: number,
  value: string
): void {
  try {
    arrCusPrjArgs[index][1] = JSON.parse(value);
  } catch (e) {
    const informationStore = useInformationStore();
    informationStore.showAlertMessage(`It can't be deserialized: ${value}`);
    // Reset inputbox.
    arrValueCache[index] = JSON.stringify(arrCusPrjArgs[index][1]);
  }
}

export function initCusPrjArgsValueCache(
  dictDetail:
    | DictColumns_Project_Detail
    | DictColumns_Scheduler_Detail
    | DictColumns_Scheduler_Detail_BeforeInsert
    | undefined
): Ref<string[]> {
  // Initialize localValues as an array of stringified item values
  return ref(
    dictDetail?.custom_prj_args.map((item) => JSON.stringify(item[1], null, 0)) || []
  );
}

export function updateCusPrjArgsValueCache(
  dictDetail:
    | DictColumns_Project_Detail
    | DictColumns_Scheduler_Detail
    | DictColumns_Scheduler_Detail_BeforeInsert
): string[] {
  // console.log("--updateCusPrjArgsValueCache--", JSON.stringify(dictDetail.custom_prj_args));

  return dictDetail.custom_prj_args.map((item) => JSON.stringify(item[1], null, 0));
}

export function computedTimeoutMin(
  dictDetail:
    | DictColumns_Project_Detail
    | DictColumns_Scheduler_Detail
    | DictColumns_Scheduler_Detail_BeforeInsert
    | undefined
): WritableComputedRef<number, number> {
  return computed<number>({
    get() {
      // console.log(dictDetail);

      if (dictDetail) {
        // console.log("Init:", JSON.stringify(dictDetail));

        return dictDetail.timeout_min;
      } else {
        return 0;
      }
    },
    set(newValue: number | null) {
      if (newValue === null) {
        const informationStore = useInformationStore();
        informationStore.showAlertMessage(`It's not an integer >= 0. (${newValue})`);
        return;
      }

      if (newValue >= 0 && dictDetail) {
        dictDetail.timeout_min = newValue;
      }
    },
  });
}

export function checkCron(cron: string): boolean {
  const informationStore = useInformationStore();
  try {
    informationStore.information = cronstrue.toString(cron, {
      use24HourTimeFormat: true,
      throwExceptionOnParseError: true,
      verbose: true,
    });

    // refresh the current alert.
    informationStore.showAlert = false;
    return true;
  } catch (e) {
    informationStore.showAlertMessage(`Cron error: ${e}`);
    return false;
  }
}

export function getColor_Source(source: string): string {
  if (source === "local") return "info";
  else return "teal";
}

export async function fileOpenFolder(folderPath: string): Promise<void> {
  await invokeMain("invoke:fileOpenFolder", folderPath);
}

export function sanitizeJsonObj<T>(obj: T): T {
  // NOTE: I don't know why some non-cloneable properties may appear, so "sanitize" it.
  return JSON.parse(JSON.stringify(obj));
}
