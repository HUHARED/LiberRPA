// FileName: projectRepository.ts

import type {
  Dict_ProjectCreate,
  Dict_ProjectDetail,
  Dict_ProjectSettingsUpdate,
} from "../../shared/project";
import { loggerMain } from "../Logging/logger";
import { getDatabase } from "./connection";
import {
  ensureNameRows,
  ensureProjectDetailRow,
  ensureSingleRowAffected,
  ensureVersionRows,
} from "./rowValidation";

export function dbSelectProjectNames(): { name: string }[] {
  loggerMain.debug("--dbSelectProjectNames--");
  const rows = getDatabase()
    .prepare(
      `
      SELECT
          name
      FROM
          project
      GROUP BY
          name
      ORDER BY
          MAX(created_at_ms) DESC,
          name COLLATE NOCASE ASC;
      `,
    )
    .all();
  return ensureNameRows(rows, "Project name query result");
}

export function dbSelectProjectVersions(name: string): { version: string }[] {
  loggerMain.debug("--dbSelectProjectVersions--");
  const rows = getDatabase()
    .prepare(
      `
      SELECT
          version
      FROM
          project
      WHERE
          name = ?
      ORDER BY
          created_at_ms DESC,
          version COLLATE NOCASE ASC;
      `,
    )
    .all(name);
  return ensureVersionRows(rows, "Project version query result");
}

export function dbSelectProjectBoundSchedules(id: number): { name: string }[] {
  loggerMain.debug("--dbSelectProjectBoundSchedules--");
  const rows = getDatabase()
    .prepare(
      `
      SELECT
          name
      FROM
          schedule
      WHERE
          project_id = ?
      ORDER BY
          name ASC;
      `,
    )
    .all(id);
  return ensureNameRows(rows, "Bound Schedule query result");
}

export function dbSelectProjectDetail(
  name: string,
  version: string,
): Dict_ProjectDetail | undefined {
  loggerMain.debug("--dbSelectProjectDetail--");
  const row = getDatabase()
    .prepare(
      `
      SELECT
          id,
          name,
          version,
          description,
          version_summary,
          python_environment_name,
          timeout_min,
          builtin_log_level,
          builtin_record_video,
          builtin_stop_shortcut,
          builtin_highlight_ui,
          custom_prj_args,
          created_at_ms,
          updated_at_ms
      FROM
          project
      WHERE
          name = ?
          AND version = ?;
      `,
    )
    .get(name, version);
  return row === undefined
    ? undefined
    : ensureProjectDetailRow(row, "Project detail query result");
}

export function dbSelectProjectDetailById(id: number): Dict_ProjectDetail | undefined {
  loggerMain.debug("--dbSelectProjectDetailById--");
  const row = getDatabase()
    .prepare(
      `
      SELECT
          id,
          name,
          version,
          description,
          version_summary,
          python_environment_name,
          timeout_min,
          builtin_log_level,
          builtin_record_video,
          builtin_stop_shortcut,
          builtin_highlight_ui,
          custom_prj_args,
          created_at_ms,
          updated_at_ms
      FROM
          project
      WHERE
          id = ?;
      `,
    )
    .get(id);
  return row === undefined
    ? undefined
    : ensureProjectDetailRow(row, "Project detail by ID query result");
}

export function dbInsertProjectDetail(dictDetail: Dict_ProjectCreate): void {
  loggerMain.debug("--dbInsertProjectDetail--");
  const intNowMs = Date.now();
  const result = getDatabase()
    .prepare(
      `
      INSERT INTO
          project (
              name,
              version,
              description,
              version_summary,
              python_environment_name,
              timeout_min,
              builtin_log_level,
              builtin_record_video,
              builtin_stop_shortcut,
              builtin_highlight_ui,
              custom_prj_args,
              created_at_ms,
              updated_at_ms
          )
      VALUES
          (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
      `,
    )
    .run(
      dictDetail.name,
      dictDetail.version,
      dictDetail.description,
      dictDetail.version_summary ?? "",
      dictDetail.python_environment_name,
      dictDetail.timeout_min,
      dictDetail.builtin_log_level,
      dictDetail.builtin_record_video ? 1 : 0,
      dictDetail.builtin_stop_shortcut ? 1 : 0,
      dictDetail.builtin_highlight_ui ? 1 : 0,
      JSON.stringify(dictDetail.custom_prj_args),
      intNowMs,
      intNowMs,
    );
  ensureSingleRowAffected(
    result,
    `Insert Project ${dictDetail.name}-${dictDetail.version}`,
  );
}

export function dbUpdateProjectSettings(dictDetail: Dict_ProjectSettingsUpdate): void {
  loggerMain.debug("--dbUpdateProjectSettings--");
  const result = getDatabase()
    .prepare(
      `
      UPDATE project
      SET
          python_environment_name = ?,
          timeout_min = ?,
          builtin_log_level = ?,
          builtin_record_video = ?,
          builtin_stop_shortcut = ?,
          builtin_highlight_ui = ?,
          custom_prj_args = ?,
          updated_at_ms = ?
      WHERE
          id = ?;
      `,
    )
    .run(
      dictDetail.python_environment_name,
      dictDetail.timeout_min,
      dictDetail.builtin_log_level,
      dictDetail.builtin_record_video ? 1 : 0,
      dictDetail.builtin_stop_shortcut ? 1 : 0,
      dictDetail.builtin_highlight_ui ? 1 : 0,
      JSON.stringify(dictDetail.custom_prj_args),
      Date.now(),
      dictDetail.id,
    );
  ensureSingleRowAffected(result, `Update Project settings for ID ${dictDetail.id}`);
}

export function dbDeleteProject(id: number): void {
  loggerMain.debug("--dbDeleteProject--");

  const arrBoundSchedule = dbSelectProjectBoundSchedules(id);
  if (arrBoundSchedule.length !== 0) {
    throw new Error(
      `Cannot delete Project ${id} because it is used by Schedule: ${arrBoundSchedule
        .map((dictSchedule) => dictSchedule.name)
        .join(", ")}.`,
    );
  }

  const result = getDatabase().prepare("DELETE FROM project WHERE id = ?;").run(id);
  ensureSingleRowAffected(result, `Delete Project ID ${id}`);
}

export function dbSelectProjectMostRecentlyInstalledDetail(
  name: string,
): Dict_ProjectDetail | undefined {
  loggerMain.debug("--dbSelectProjectMostRecentlyInstalledDetail--");
  const row = getDatabase()
    .prepare(
      `
      SELECT
          id,
          name,
          version,
          description,
          version_summary,
          python_environment_name,
          timeout_min,
          builtin_log_level,
          builtin_record_video,
          builtin_stop_shortcut,
          builtin_highlight_ui,
          custom_prj_args,
          created_at_ms,
          updated_at_ms
      FROM
          project
      WHERE
          name = ?
      ORDER BY
          created_at_ms DESC
      LIMIT
          1;
      `,
    )
    .get(name);
  return row === undefined
    ? undefined
    : ensureProjectDetailRow(row, "Most recently installed Project version query result");
}
