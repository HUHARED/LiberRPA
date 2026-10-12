// FileName: manualRun.ts

import type { ProjectDetails, ProjectSettingsUpdate } from "../../shared/project";

import type { ProjectRunConfig } from "../../shared/run";
import {
  dbSelectProjectDetailById,
  dbSelectProjectMostRecentlyInstalledDetail,
} from "../Database/projectRepository";
import { dbSelectFinishedLocalRunProjectName } from "../Database/runHistoryRepository";
import { startProjectRun } from "./projectRunner";

function buildManualRunConfig(dictProject: ProjectDetails): ProjectRunConfig {
  return {
    schedule_name: null,

    local_project_id: dictProject.id,
    project_name: dictProject.name,
    project_version: dictProject.version,

    python_environment_name: dictProject.python_environment_name,

    max_retry_count: dictProject.max_retry_count,
    timeout_min: dictProject.timeout_min,

    builtin_log_level: dictProject.builtin_log_level,
    builtin_record_video: dictProject.builtin_record_video,
    builtin_stop_shortcut: dictProject.builtin_stop_shortcut,
    builtin_highlight_ui: dictProject.builtin_highlight_ui,
    custom_prj_args: dictProject.custom_prj_args,
  };
}

export async function runInstalledProject(settings: ProjectSettingsUpdate): Promise<void> {
  const dictProject = dbSelectProjectDetailById(settings.id);
  if (dictProject === undefined) {
    throw new Error(`Project not found: ${settings.id}`);
  }

  await startProjectRun(buildManualRunConfig({ ...dictProject, ...settings }));
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

  await startProjectRun(buildManualRunConfig(dictProject));
}
