// FileName: manualRun.ts

import type { PackageDetails, PackageSettings } from "../../shared/package";

import type { RunConfig } from "../../shared/run";
import {
  dbSelectPackageDetailsById,
  dbSelectMostRecentlyInstalledPackage,
} from "../Database/packageRepository";
import { dbSelectFinishedLocalRunProjectName } from "../Database/runHistoryRepository";
import { startRun } from "./packageRunner";

function buildManualRunConfig(dictPackage: PackageDetails): RunConfig {
  return {
    schedule_name: null,

    local_package_id: dictPackage.id,
    project_name: dictPackage.project_name,
    project_version: dictPackage.project_version,

    python_environment_name: dictPackage.python_environment_name,

    max_retry_count: dictPackage.max_retry_count,
    timeout_min: dictPackage.timeout_min,

    builtin_log_level: dictPackage.builtin_log_level,
    builtin_record_video: dictPackage.builtin_record_video,
    builtin_stop_shortcut: dictPackage.builtin_stop_shortcut,
    builtin_highlight_ui: dictPackage.builtin_highlight_ui,
    custom_prj_args: dictPackage.custom_prj_args,
  };
}

export async function runInstalledPackage(settings: PackageSettings): Promise<void> {
  const dictPackage = dbSelectPackageDetailsById(settings.id);
  if (dictPackage === undefined) {
    throw new Error(`Package not found: ${settings.id}`);
  }

  await startRun(buildManualRunConfig({ ...dictPackage, ...settings }));
}

export function getLocalRerunPackage(runHistoryId: number): PackageDetails {
  const strProjectName = dbSelectFinishedLocalRunProjectName(runHistoryId);
  if (strProjectName === undefined) {
    throw new Error("Only a local Run with a confirmed end can be rerun.");
  }
  const dictPackage = dbSelectMostRecentlyInstalledPackage(strProjectName);
  if (dictPackage === undefined) {
    throw new Error(`No installed Project version found: ${strProjectName}`);
  }

  return dictPackage;
}
