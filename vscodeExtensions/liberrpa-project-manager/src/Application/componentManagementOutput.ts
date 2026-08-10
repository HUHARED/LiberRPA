// FileName: componentManagementOutput.ts

import { log } from "../Adapter/VsCode/output";
import type {
  DictComponentManagementWarning,
} from "../Domain/ComponentManagement/componentManagementTypes";

export function logComponentManagementWarnings(
  warnings: DictComponentManagementWarning[],
): void {
  for (const warning of warnings) {
    log.warn(warning.message);
    if ("details" in warning && warning.details !== undefined) {
      log.debug(JSON.stringify(warning.details, null, 2));
    }
  }
}

export function getComponentManagementWarningMessages(
  warnings: DictComponentManagementWarning[],
): string[] {
  return warnings.map((warning) => warning.message);
}
