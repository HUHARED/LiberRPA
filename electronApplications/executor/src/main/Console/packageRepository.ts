// FileName: packageRepository.ts

import { ensureExactRecord, ensureNonEmptyString } from "../Common/validation";
import { getDatabase } from "../Database/connection";
import { ensureSingleRowAffected } from "../Database/rowConversion";

export function dbSelectConsolePackageId(folderName: string): string | undefined {
  const value = getDatabase()
    .prepare(
      `
      SELECT
          package_id
      FROM
          console_package
      WHERE
          folder_name = ?
      `,
    )
    .get(folderName);
  if (value === undefined) return undefined;
  const row = ensureExactRecord(value, ["package_id"], "Console Package registration");
  return ensureNonEmptyString(row.package_id, "Console Package registration.package_id");
}

export function dbSaveConsolePackage(folderName: string, packageId: string): void {
  const result = getDatabase()
    .prepare(
      `
      INSERT INTO
          console_package (
              folder_name,
              package_id
          )
      VALUES
          (?, ?)
      ON CONFLICT (folder_name) DO UPDATE
      SET
          package_id = excluded.package_id
      `,
    )
    .run(folderName, packageId);
  ensureSingleRowAffected(result, `Register Console Package ${packageId}`);
}
