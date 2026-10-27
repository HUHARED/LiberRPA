// FileName: projectPackage.ts

import type { DictProtocolResult_ProjectDependencyState } from "../ComponentManagement/componentManagementTypes";
import type { DictProjectManifest_Flow, DictPackageProjectInput } from "./projectTypes";
import { getWindowsFileOrFolderNameError } from "./projectValidation";

export const STR_PROJECT_PACKAGE_MANIFEST_FILE_NAME = ".liberrpa-package.json";

// NOTE: Keep the Console Package name budget aligned with Console and Executor; reserve 37 units for "_" and the full UUID.
const INT_CONSOLE_PACKAGE_BASE_NAME_MAX_LENGTH = 255 - 37;

const SET_ALWAYS_EXCLUDED_FOLDER_NAME = new Set([
  ".liberrpa-project-manager",
  ".mypy_cache",
  ".pytest_cache",
  ".ruff_cache",
  "__pycache__",
]);
const STR_PROJECT_TEST_FOLDER_NAME_LOWERCASE = "_test";
const STR_PROJECT_OPERATION_LOCK_FILE_NAME = ".liberrpa-project-manager.lock";

export function getProjectPackageFileName(manifest: DictProjectManifest_Flow): string {
  return `${manifest.name}_${manifest.version}.rpa.zip`;
}

export function getProjectPackageNameError(
  manifest: DictProjectManifest_Flow,
  publishToConsole: boolean,
): string | undefined {
  if (manifest.name.length === 0) {
    return "flow.json name cannot be empty.";
  }
  if (manifest.name !== manifest.name.trim()) {
    return "flow.json name cannot start or end with whitespace.";
  }
  if (manifest.version.length === 0) {
    return "flow.json version cannot be empty.";
  }
  if (manifest.version !== manifest.version.trim()) {
    return "flow.json version cannot start or end with whitespace.";
  }

  const strFileNameError = getWindowsFileOrFolderNameError(
    getProjectPackageFileName(manifest),
    "Package filename",
  );
  if (strFileNameError !== undefined) {
    return strFileNameError;
  }
  if (
    publishToConsole &&
    `${manifest.name}_${manifest.version}`.length > INT_CONSOLE_PACKAGE_BASE_NAME_MAX_LENGTH
  ) {
    return `For Console publishing, the project name and version, including the separating underscore, cannot exceed ${String(INT_CONSOLE_PACKAGE_BASE_NAME_MAX_LENGTH)} UTF-16 code units.`;
  }
  return undefined;
}

export function getProjectPackageDependencyBlockingReasons(
  projectState: DictProtocolResult_ProjectDependencyState,
): string[] {
  const arrReason: string[] = [];
  const boolDependenciesRequired =
    Object.keys(projectState.manifest.componentDependencies).length > 0;

  if (projectState.projectType !== "flow") {
    arrReason.push("Only a Flow Project can be packaged.");
    return arrReason;
  }

  if (boolDependenciesRequired) {
    if (projectState.lockState !== "valid") {
      arrReason.push(`components.lock.json is not valid (${projectState.lockState}).`);
    }
    if (projectState.componentsState !== "valid") {
      arrReason.push(`_Components is not valid (${projectState.componentsState}).`);
    }
  } else {
    if (projectState.lockState !== "notRequired") {
      arrReason.push(
        `The Project does not require Components, but its dependency lock state is ${projectState.lockState}.`,
      );
    }
    if (projectState.componentsState !== "notRequired") {
      arrReason.push(
        `The Project does not require Components, but its _Components state is ${projectState.componentsState}.`,
      );
    }
  }

  if (projectState.environmentState !== "compatible") {
    arrReason.push(
      `The installed liberrpa environment is not compatible with all Project requirements (${projectState.environmentState}).`,
    );
  }

  return arrReason;
}

export function shouldExcludeProjectFolder(
  folderName: string,
  isProjectRootEntry: boolean,
  input: DictPackageProjectInput,
): boolean {
  const strFolderNameLowercase = folderName.toLowerCase();
  if (SET_ALWAYS_EXCLUDED_FOLDER_NAME.has(strFolderNameLowercase)) {
    return true;
  }
  if (!isProjectRootEntry) {
    return false;
  }
  if (strFolderNameLowercase === ".vscode") {
    return !input.includeVscodeSettings;
  }
  if (strFolderNameLowercase === STR_PROJECT_TEST_FOLDER_NAME_LOWERCASE) {
    return !input.includeProjectTests;
  }
  if (strFolderNameLowercase === ".git") {
    return !input.includeGitRepository;
  }
  return false;
}

export function shouldExcludeProjectFile(
  fileName: string,
  isProjectRootEntry: boolean,
  input: DictPackageProjectInput,
): boolean {
  const strFileNameLowercase = fileName.toLowerCase();
  if (
    strFileNameLowercase === STR_PROJECT_OPERATION_LOCK_FILE_NAME ||
    strFileNameLowercase.endsWith(".pyc") ||
    strFileNameLowercase.endsWith(".pyo") ||
    strFileNameLowercase.endsWith(".rpa.zip")
  ) {
    return true;
  }
  if (!isProjectRootEntry) {
    return false;
  }
  if (strFileNameLowercase === STR_PROJECT_PACKAGE_MANIFEST_FILE_NAME) {
    return true;
  }
  if (strFileNameLowercase === ".git") {
    return !input.includeGitRepository;
  }
  return false;
}
