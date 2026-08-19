// FileName: projectPackageManifest.ts

export const STR_PROJECT_PACKAGE_MANIFEST_FILE_NAME = ".liberrpa-package.json";

export interface DictProjectPackageManifest {
  schemaVersion: 1;
  versionSummary: string;
}

export function buildProjectPackageManifest(
  versionSummary: string,
): DictProjectPackageManifest {
  return {
    schemaVersion: 1,
    versionSummary,
  };
}
