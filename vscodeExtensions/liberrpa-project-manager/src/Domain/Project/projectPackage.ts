// FileName: projectPackage.ts

import type { DictProtocolResult_ProjectDependencyState } from "../ComponentManagement/componentManagementTypes";
import type { DictProjectManifest_Flow, DictPackageProjectInput } from "./projectTypes";
import { getWindowsFileOrFolderNameError } from "./projectValidation";

const SET_EXCLUDED_FOLDER_NAME = new Set([
  ".liberrpa-project-manager",
  ".mypy_cache",
  ".pytest_cache",
  ".ruff_cache",
  "__pycache__",
]);
const STR_PROJECT_OPERATION_LOCK_FILE_NAME = ".liberrpa-project-manager.lock";

export function getProjectPackageFileNameError(
  manifest: DictProjectManifest_Flow,
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

  const strPackageFileName = `${manifest.name}_${manifest.version}.rpa.zip`;
  return getWindowsFileOrFolderNameError(strPackageFileName, "Package filename");
}

export function getProjectPackageFileName(manifest: DictProjectManifest_Flow): string {
  const strError = getProjectPackageFileNameError(manifest);
  if (strError !== undefined) {
    throw new Error(strError);
  }
  return `${manifest.name}_${manifest.version}.rpa.zip`;
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
  input: DictPackageProjectInput,
): boolean {
  const strFolderName = folderName.toLowerCase();
  if (SET_EXCLUDED_FOLDER_NAME.has(strFolderName)) {
    return true;
  }
  if (strFolderName === ".vscode") {
    return !input.includeVscodeSettings;
  }
  if (strFolderName === ".git") {
    return !input.includeGitRepository;
  }
  return false;
}

export function shouldExcludeProjectFile(
  fileName: string,
  input: DictPackageProjectInput,
): boolean {
  const strFileName = fileName.toLowerCase();
  if (strFileName === ".vscode") {
    return !input.includeVscodeSettings;
  }
  if (strFileName === ".git") {
    return !input.includeGitRepository;
  }
  return (
    strFileName === STR_PROJECT_OPERATION_LOCK_FILE_NAME ||
    strFileName.endsWith(".pyc") ||
    strFileName.endsWith(".pyo") ||
    strFileName.endsWith(".rpa.zip")
  );
}
