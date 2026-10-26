// FileName: packageRepository.ts

import { getDatabase } from "../Database/connection";

export function dbSelectConsolePackageId(folderName: string): string | undefined {
  const row = getDatabase()
    .prepare<[string], { package_id: string }>(
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
  return row?.package_id;
}

export function dbSaveConsolePackage(folderName: string, packageId: string): void {
  getDatabase()
    .prepare(
      `
      INSERT INTO
          console_package (
              folder_name,
              package_id
          )
      VALUES
          (?, ?)
      ON CONFLICT (package_id) DO UPDATE
      SET
          folder_name = excluded.folder_name
      `,
    )
    .run(folderName, packageId);
}
