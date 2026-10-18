// FileName: packageRepository.ts

import type {
  PackageCreateData,
  PackageDetails,
  PackageSettings,
} from "../../shared/package";
import { loggerMain } from "../Logging/logger";
import { getDatabase } from "./connection";
import {
  ensureSingleRowAffected,
  parseNameRows,
  parseNonEmptyColumnRows,
  parsePackageDetailsRow,
} from "./rowValidation";

export function dbSelectProjectNames(): string[] {
  loggerMain.debug("--dbSelectProjectNames--");
  const rows = getDatabase()
    .prepare(
      `
      SELECT
          project_name
      FROM
          local_package
      GROUP BY
          project_name
      ORDER BY
          MAX(created_at_ms) DESC,
          project_name COLLATE NOCASE ASC;
      `,
    )
    .all();
  return parseNonEmptyColumnRows(rows, "project_name", "Project name query result");
}

export function dbSelectProjectVersions(projectName: string): string[] {
  loggerMain.debug("--dbSelectProjectVersions--");
  const rows = getDatabase()
    .prepare(
      `
      SELECT
          project_version
      FROM
          local_package
      WHERE
          project_name = ?
      ORDER BY
          created_at_ms DESC,
          project_version COLLATE NOCASE ASC;
      `,
    )
    .all(projectName);
  return parseNonEmptyColumnRows(rows, "project_version", "Project version query result");
}

export function dbSelectPackageBoundSchedules(id: number): { name: string }[] {
  loggerMain.debug("--dbSelectPackageBoundSchedules--");
  const rows = getDatabase()
    .prepare(
      `
      SELECT
          name
      FROM
          schedule
      WHERE
          local_package_id = ?
      ORDER BY
          name ASC;
      `,
    )
    .all(id);
  return parseNameRows(rows, "Bound Schedule query result");
}

export function dbSelectPackageDetails(
  projectName: string,
  projectVersion: string,
): PackageDetails | undefined {
  loggerMain.debug("--dbSelectPackageDetails--");
  const row = getDatabase()
    .prepare(
      `
      SELECT
          id,
          project_name,
          project_version,
          description,
          version_summary,
          python_environment_name,
          max_retry_count,
          timeout_min,
          builtin_log_level,
          builtin_record_video,
          builtin_stop_shortcut,
          builtin_highlight_ui,
          custom_prj_args,
          created_at_ms,
          updated_at_ms
      FROM
          local_package
      WHERE
          project_name = ?
          AND project_version = ?;
      `,
    )
    .get(projectName, projectVersion);
  return row === undefined
    ? undefined
    : parsePackageDetailsRow(row, "Package details query result");
}

export function dbSelectPackageDetailsById(id: number): PackageDetails | undefined {
  loggerMain.debug("--dbSelectPackageDetailsById--");
  const row = getDatabase()
    .prepare(
      `
      SELECT
          id,
          project_name,
          project_version,
          description,
          version_summary,
          python_environment_name,
          max_retry_count,
          timeout_min,
          builtin_log_level,
          builtin_record_video,
          builtin_stop_shortcut,
          builtin_highlight_ui,
          custom_prj_args,
          created_at_ms,
          updated_at_ms
      FROM
          local_package
      WHERE
          id = ?;
      `,
    )
    .get(id);
  return row === undefined
    ? undefined
    : parsePackageDetailsRow(row, "Package details by ID query result");
}

export function dbInsertPackageDetails(dictDetail: PackageCreateData): void {
  loggerMain.debug("--dbInsertPackageDetails--");
  const intNowMs = Date.now();
  const result = getDatabase()
    .prepare(
      `
      INSERT INTO
          local_package (
              project_name,
              project_version,
              description,
              version_summary,
              python_environment_name,
              max_retry_count,
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
          (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
      `,
    )
    .run(
      dictDetail.project_name,
      dictDetail.project_version,
      dictDetail.description,
      dictDetail.version_summary ?? "",
      dictDetail.python_environment_name,
      dictDetail.max_retry_count,
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
    `Insert Package ${dictDetail.project_name}-${dictDetail.project_version}`,
  );
}

export function dbUpdatePackageSettings(dictDetail: PackageSettings): void {
  loggerMain.debug("--dbUpdatePackageSettings--");
  const result = getDatabase()
    .prepare(
      `
      UPDATE local_package
      SET
          python_environment_name = ?,
          max_retry_count = ?,
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
      dictDetail.max_retry_count,
      dictDetail.timeout_min,
      dictDetail.builtin_log_level,
      dictDetail.builtin_record_video ? 1 : 0,
      dictDetail.builtin_stop_shortcut ? 1 : 0,
      dictDetail.builtin_highlight_ui ? 1 : 0,
      JSON.stringify(dictDetail.custom_prj_args),
      Date.now(),
      dictDetail.id,
    );
  ensureSingleRowAffected(result, `Update Package settings for ID ${dictDetail.id}`);
}

export function dbDeletePackage(id: number): void {
  loggerMain.debug("--dbDeletePackage--");

  const result = getDatabase()
    .prepare(
      `
      DELETE FROM
          local_package
      WHERE
          id = ?;
      `,
    )
    .run(id);
  ensureSingleRowAffected(result, `Delete Package ID ${id}`);
}

export function dbSelectMostRecentlyInstalledPackage(
  projectName: string,
): PackageDetails | undefined {
  loggerMain.debug("--dbSelectMostRecentlyInstalledPackage--");
  const row = getDatabase()
    .prepare(
      `
      SELECT
          id,
          project_name,
          project_version,
          description,
          version_summary,
          python_environment_name,
          max_retry_count,
          timeout_min,
          builtin_log_level,
          builtin_record_video,
          builtin_stop_shortcut,
          builtin_highlight_ui,
          custom_prj_args,
          created_at_ms,
          updated_at_ms
      FROM
          local_package
      WHERE
          project_name = ?
      ORDER BY
          created_at_ms DESC
      LIMIT
          1;
      `,
    )
    .get(projectName);
  return row === undefined
    ? undefined
    : parsePackageDetailsRow(row, "Most recently installed Package query result");
}
