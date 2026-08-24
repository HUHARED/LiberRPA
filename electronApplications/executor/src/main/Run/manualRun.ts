import type { DictProjectDetail } from "../../shared/project";
import {
  dbSelectProjectDetailById,
  dbSelectProjectMostRecentlyImportedDetail,
} from "../Database/projectRepository";
import { pythonRun } from "./projectRunner";
import type { DictProjectRunDetail } from "./types";

function createManualRunDetail(dictProject: DictProjectDetail): DictProjectRunDetail {
  return {
    schedule_name: null,
    project_source: "local",
    id: dictProject.id,
    name: dictProject.name,
    version: dictProject.version,
    python_environment_name: dictProject.python_environment_name,
    timeout_min: dictProject.timeout_min,
    builtin_log_level: dictProject.builtin_log_level,
    builtin_record_video: dictProject.builtin_record_video,
    builtin_stop_shortcut: dictProject.builtin_stop_shortcut,
    builtin_highlight_ui: dictProject.builtin_highlight_ui,
    custom_prj_args: dictProject.custom_prj_args,
  };
}

export async function runInstalledProject(projectId: number): Promise<void> {
  const dictProject = dbSelectProjectDetailById(projectId);
  if (dictProject === undefined) {
    throw new Error(`Project not found: ${projectId}`);
  }

  await pythonRun(createManualRunDetail(dictProject));
}

export async function runMostRecentlyImportedProjectVersion(
  projectName: string,
): Promise<void> {
  const dictProject = dbSelectProjectMostRecentlyImportedDetail(projectName);
  if (dictProject === undefined) {
    throw new Error(`No installed Project version found: ${projectName}`);
  }

  await pythonRun(createManualRunDetail(dictProject));
}
