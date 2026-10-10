// FileName: manualRun.ts

import type { Dict_ProjectDetail, Dict_ProjectSettingsUpdate } from "../../shared/project";
import {
  dbSelectProjectDetailById,
  dbSelectProjectMostRecentlyInstalledDetail,
} from "../Database/projectRepository";
import { dbSelectFinishedLocalRunProjectName } from "../Database/runHistoryRepository";
import { pythonRun } from "./projectRunner";
import type { ProjectRunDetails } from "./types";

function createManualRunDetail(dictProject: Dict_ProjectDetail): ProjectRunDetails {
  return {
    schedule_name: null,

    id: dictProject.id,
    name: dictProject.name,
    version: dictProject.version,

    python_environment_name: dictProject.python_environment_name,

    retry_count: dictProject.retry_count,
    timeout_min: dictProject.timeout_min,

    builtin_log_level: dictProject.builtin_log_level,
    builtin_record_video: dictProject.builtin_record_video,
    builtin_stop_shortcut: dictProject.builtin_stop_shortcut,
    builtin_highlight_ui: dictProject.builtin_highlight_ui,
    custom_prj_args: dictProject.custom_prj_args,
  };
}

export async function runInstalledProject(
  settings: Dict_ProjectSettingsUpdate,
): Promise<void> {
  const dictProject = dbSelectProjectDetailById(settings.id);
  if (dictProject === undefined) {
    throw new Error(`Project not found: ${settings.id}`);
  }

  await pythonRun(createManualRunDetail({ ...dictProject, ...settings }));
}

export async function rerunLocalRun(runHistoryId: number): Promise<void> {
  const strProjectName = dbSelectFinishedLocalRunProjectName(runHistoryId);
  if (strProjectName === undefined) {
    throw new Error("Only a local Run with a confirmed end can be rerun.");
  }
  const dictProject = dbSelectProjectMostRecentlyInstalledDetail(strProjectName);
  if (dictProject === undefined) {
    throw new Error(`No installed Project version found: ${strProjectName}`);
  }

  await pythonRun(createManualRunDetail(dictProject));
}
