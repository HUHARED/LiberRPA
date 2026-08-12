// FileName: componentManagementOutput.ts

import { log } from "../Adapter/VsCode/output";
import type { ComponentManagementOperationError } from "../Adapter/Python/componentManagementClient";
import type { DictComponentManagementWarning } from "../Domain/ComponentManagement/componentManagementTypes";

function getFormattedDetails(details: Record<string, unknown>): string {
  return JSON.stringify(details, null, 2);
}

export function logComponentManagementOperationError(
  error: ComponentManagementOperationError,
): void {
  log.error(`${error.operationName} failed [${error.code}]: ${error.message}`);
  if (Object.keys(error.details).length > 0) {
    log.error(`Error details:\n${getFormattedDetails(error.details)}`);
  }
}

export function logComponentManagementWarnings(
  warnings: DictComponentManagementWarning[],
): void {
  for (const warning of warnings) {
    log.warn(`[${warning.code}] ${warning.message}`);
    if ("details" in warning && warning.details !== undefined) {
      log.warn(`Warning details:\n${getFormattedDetails(warning.details)}`);
    }
  }
}

export function getComponentManagementWarningMessages(
  warnings: DictComponentManagementWarning[],
): string[] {
  return warnings.map((warning) => warning.message);
}
