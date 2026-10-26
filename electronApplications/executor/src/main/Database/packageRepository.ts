// FileName: packageRepository.ts

import type {
  PackageCreateData,
  PackageDetails,
  PackageSettings,
} from "../../shared/package";
import type { RunSettings } from "../../shared/runSettings";
import { loggerMain } from "../Logging/logger";
import { getDatabase } from "./connection";
import {
  type RunSettingsRow,
  convertRunSettingsRow,
  ensureSingleRowAffected,
} from "./rowConversion";

type PackageDetailsRow = Omit<PackageDetails, keyof RunSettings> & RunSettingsRow;

function convertPackageDetailsRow(row: PackageDetailsRow): PackageDetails {
  return { ...row, ...convertRunSettingsRow(row) };
}

export function dbSelectProjectNames(): string[] {
  loggerMain.debug("--dbSelectProjectNames--");
  const rows = getDatabase()
    .prepare<[], { project_name: string }>(
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
  return rows.map((row) => row.project_name);
}

export function dbSelectProjectVersions(projectName: string): string[] {
  loggerMain.debug("--dbSelectProjectVersions--");
  const rows = getDatabase()
    .prepare<[string], { project_version: string }>(
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
  return rows.map((row) => row.project_version);
}

export function dbSelectPackageBoundSchedules(id: number): { name: string }[] {
  loggerMain.debug("--dbSelectPackageBoundSchedules--");
  return getDatabase()
    .prepare<[number], { name: string }>(
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
}

export function dbSelectPackageDetails(
  projectName: string,
  projectVersion: string,
): PackageDetails | undefined {
  loggerMain.debug("--dbSelectPackageDetails--");
  const row = getDatabase()
    .prepare<[string, string], PackageDetailsRow>(
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
  return row === undefined ? undefined : convertPackageDetailsRow(row);
}

export function dbSelectPackageDetailsById(id: number): PackageDetails | undefined {
  loggerMain.debug("--dbSelectPackageDetailsById--");
  const row = getDatabase()
    .prepare<[number], PackageDetailsRow>(
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
  return row === undefined ? undefined : convertPackageDetailsRow(row);
}

export function dbInsertPackageDetails(dictDetail: PackageCreateData): void {
  loggerMain.debug("--dbInsertPackageDetails--");
  const intNowMs = Date.now();
  getDatabase()
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
    .prepare<[string], PackageDetailsRow>(
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
  return row === undefined ? undefined : convertPackageDetailsRow(row);
}
