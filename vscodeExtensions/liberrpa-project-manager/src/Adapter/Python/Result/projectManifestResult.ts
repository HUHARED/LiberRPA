// FileName: projectManifestResult.ts

import { ensureExactRecord, ensureNonEmptyString } from "../../../Common/typeCheck";
import type { DictProtocolResult_ProjectManifestDefaults } from "../../../Domain/ComponentManagement/componentManagementTypes";

const SET_KEYS_PROJECT_MANIFEST_DEFAULTS = new Set([
  "status",
  "installedLiberrpaVersion",
  "requiresLiberrpa",
]);

export function parseProjectManifestDefaultsResult(
  value: unknown,
): DictProtocolResult_ProjectManifestDefaults {
  const dictValue = ensureExactRecord(
    value,
    SET_KEYS_PROJECT_MANIFEST_DEFAULTS,
    "Project Manifest defaults result",
  );
  if (dictValue["status"] !== "projectManifestDefaults") {
    throw new Error(
      "Component Management returned an unsupported Project Manifest defaults status.",
    );
  }

  return {
    status: "projectManifestDefaults",
    installedLiberrpaVersion: ensureNonEmptyString(
      dictValue["installedLiberrpaVersion"],
      "Project Manifest defaults result.installedLiberrpaVersion",
    ),
    requiresLiberrpa: ensureNonEmptyString(
      dictValue["requiresLiberrpa"],
      "Project Manifest defaults result.requiresLiberrpa",
    ),
  };
}
