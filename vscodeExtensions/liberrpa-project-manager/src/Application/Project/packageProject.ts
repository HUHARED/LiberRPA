// FileName: packageProject.ts

import * as vscode from "vscode";
import { randomUUID } from "node:crypto";
import * as fs from "node:fs";
import * as path from "node:path";
import { finished } from "node:stream/promises";

import { log } from "../../Adapter/VsCode/output";
import { getProjectDependencyState } from "../../Adapter/Python/componentManagementClient";
import {
  getWorkspaceProjectType,
  updateProjectTypeContext,
} from "../../Adapter/VsCode/projectTypeContext";
import { stringifyJson } from "../../Common/utils";
import type {
  DictComponentManagementWarning,
  DictProtocolResult_ProjectDependencyState,
} from "../../Domain/ComponentManagement/componentManagementTypes";
import {
  getProjectPackageFileNameError,
  getProjectPackageFileName,
  getProjectPackageDependencyBlockingReasons,
  shouldExcludeProjectFolder,
  shouldExcludeProjectFile,
} from "../../Domain/Project/projectPackage";
import {
  buildProjectPackageManifest,
  STR_PROJECT_PACKAGE_MANIFEST_FILE_NAME,
} from "../../Domain/Project/projectPackageManifest";
import { getOptionalSingleLineTextError } from "../../Domain/Project/projectValidation";
import type {
  DictProjectManifest_Flow,
  DictPackageProjectInput,
  DictProjectPackageResult,
} from "../../Domain/Project/projectTypes";

const PROJECT_PACKAGE_MANIFEST_ENTRY_DATE = new Date(1984, 4, 4);

interface Info_ProjectPackageEntry {
  type: "file" | "folder";
  sourceEntryPath: string;
  archivePath: string;
  modifiedAt: Date;
  size: number;
}

interface Info_PackageProjectData {
  projectPath: string;
  manifest: DictProjectManifest_Flow;
  projectDependencyState: DictProtocolResult_ProjectDependencyState;

  input: DictPackageProjectInput;
  packageFileName: string | null;
  packageFileExists: boolean;
  blockingReasons: string[];
  warnings: DictComponentManagementWarning[];
}

interface Info_PackageProjectOperationResult {
  result: DictProjectPackageResult;
  warnings: DictComponentManagementWarning[];
}

async function pathExists(fileSystemPath: string): Promise<boolean> {
  try {
    await fs.promises.lstat(fileSystemPath);
    return true;
  } catch (e: unknown) {
    if ((e as NodeJS.ErrnoException).code === "ENOENT") {
      return false;
    }
    throw e;
  }
}

function comparePath(left: string, right: string): number {
  const strLeft = left.toLowerCase();
  const strRight = right.toLowerCase();
  if (strLeft < strRight) {
    return -1;
  }
  if (strLeft > strRight) {
    return 1;
  }
  return left < right ? -1 : left > right ? 1 : 0;
}

function isSameOrChildPath(parentFolderPath: string, targetPath: string): boolean {
  const strRelativePath = path.relative(
    path.resolve(parentFolderPath),
    path.resolve(targetPath),
  );
  return (
    strRelativePath === "" ||
    (!strRelativePath.startsWith(`..${path.sep}`) &&
      strRelativePath !== ".." &&
      !path.isAbsolute(strRelativePath))
  );
}

async function ensureFlowProject(workspaceFolder: vscode.WorkspaceFolder): Promise<void> {
  if ((await getWorkspaceProjectType(workspaceFolder)) === "flow") {
    return;
  }

  await updateProjectTypeContext();
  throw new Error("Package Project is only available for a Flow Project.");
}

export function getDefaultPackageProjectInput(
  workspaceFolder: vscode.WorkspaceFolder,
): DictPackageProjectInput {
  return {
    outputFolderPath: path.dirname(workspaceFolder.uri.fsPath),
    versionSummary: "",
    includeVscodeSettings: false,
    includeProjectTests: false,
    includeGitRepository: false,
  };
}

async function getUnusedDependencyArtifactBlockingReasons(
  projectPath: string,
  projectState: DictProtocolResult_ProjectDependencyState,
): Promise<string[]> {
  if (Object.keys(projectState.manifest.componentDependencies).length > 0) {
    return [];
  }

  const arrReason: string[] = [];
  const strComponentsLockFilePath = path.join(projectPath, "components.lock.json");
  const strComponentsFolderPath = path.join(projectPath, "_Components");

  if (await pathExists(strComponentsLockFilePath)) {
    arrReason.push(
      "The Project does not require Components, but components.lock.json still exists.",
    );
  }
  if (await pathExists(strComponentsFolderPath)) {
    arrReason.push(
      "The Project does not require Components, but _Components still exists.",
    );
  }

  return arrReason;
}

async function getOutputFolderError(
  projectPath: string,
  outputFolderPath: string,
): Promise<string | undefined> {
  if (!path.isAbsolute(outputFolderPath)) {
    return "Package output folder must be an absolute path.";
  }

  let outputFolderStat: fs.Stats;
  try {
    outputFolderStat = await fs.promises.stat(outputFolderPath);
  } catch {
    return `Package output folder does not exist or cannot be accessed: ${outputFolderPath}`;
  }

  if (!outputFolderStat.isDirectory()) {
    return `Package output path is not a folder: ${outputFolderPath}`;
  }

  let strRealProjectPath: string;
  let strRealOutputFolderPath: string;
  try {
    [strRealProjectPath, strRealOutputFolderPath] = await Promise.all([
      fs.promises.realpath(projectPath),
      fs.promises.realpath(outputFolderPath),
    ]);
  } catch (e: unknown) {
    return (
      "Failed to resolve the Project or Package output folder: " +
      (e instanceof Error ? e.message : String(e))
    );
  }

  if (isSameOrChildPath(strRealProjectPath, strRealOutputFolderPath)) {
    return "Package output folder cannot be the Project folder or one of its subfolders.";
  }

  return undefined;
}

async function getPackageBlockingReasons(
  projectPath: string,
  manifest: DictProjectManifest_Flow,
  projectState: DictProtocolResult_ProjectDependencyState,
  input: DictPackageProjectInput,
): Promise<string[]> {
  const arrReason = getProjectPackageDependencyBlockingReasons(projectState);
  const strFileNameError = getProjectPackageFileNameError(manifest);
  if (strFileNameError !== undefined) {
    arrReason.unshift(strFileNameError);
  }

  const strVersionSummaryError = getOptionalSingleLineTextError(
    input.versionSummary,
    "Version summary",
  );
  if (strVersionSummaryError !== undefined) {
    arrReason.push(strVersionSummaryError);
  }

  const strOutputFolderError = await getOutputFolderError(
    projectPath,
    input.outputFolderPath,
  );
  if (strOutputFolderError !== undefined) {
    arrReason.push(strOutputFolderError);
  }

  arrReason.push(
    ...(await getUnusedDependencyArtifactBlockingReasons(projectPath, projectState)),
  );
  return arrReason;
}

export async function loadPackageProjectData(
  workspaceFolder: vscode.WorkspaceFolder,
  input: DictPackageProjectInput,
): Promise<Info_PackageProjectData> {
  await ensureFlowProject(workspaceFolder);

  const projectPath = workspaceFolder.uri.fsPath;
  const operationResult = await getProjectDependencyState(projectPath);
  const projectDependencyState = operationResult.result;
  if (
    projectDependencyState.projectType !== "flow" ||
    !("name" in projectDependencyState.manifest)
  ) {
    throw new Error("Component Management returned an invalid Flow Project manifest.");
  }
  const manifest = projectDependencyState.manifest;
  const packageFileName =
    getProjectPackageFileNameError(manifest) === undefined
      ? getProjectPackageFileName(manifest)
      : null;
  const packageFilePath =
    packageFileName === null ? null : path.join(input.outputFolderPath, packageFileName);

  return {
    projectPath,
    manifest,
    projectDependencyState,
    input,
    packageFileName,
    packageFileExists: packageFilePath === null ? false : await pathExists(packageFilePath),
    blockingReasons: await getPackageBlockingReasons(
      projectPath,
      manifest,
      projectDependencyState,
      input,
    ),
    warnings: operationResult.warnings,
  };
}

export async function selectPackageOutputFolder(
  currentOutputFolderPath: string,
): Promise<string | undefined> {
  let boolCurrentFolderAvailable = false;
  if (path.isAbsolute(currentOutputFolderPath)) {
    try {
      const currentFolderStat = await fs.promises.stat(currentOutputFolderPath);
      boolCurrentFolderAvailable = currentFolderStat.isDirectory();
    } catch {
      boolCurrentFolderAvailable = false;
    }
  }
  const arrFolderUri = await vscode.window.showOpenDialog({
    canSelectFolders: true,
    canSelectFiles: false,
    canSelectMany: false,
    openLabel: "Select Package Output Folder",
    ...(boolCurrentFolderAvailable
      ? { defaultUri: vscode.Uri.file(currentOutputFolderPath) }
      : {}),
  });
  return arrFolderUri?.[0]?.fsPath;
}

async function collectProjectPackageEntries(
  projectPath: string,
  input: DictPackageProjectInput,
): Promise<Info_ProjectPackageEntry[]> {
  const projectStat = await fs.promises.lstat(projectPath);
  if (!projectStat.isDirectory() || projectStat.isSymbolicLink()) {
    throw new Error(`Project path is not a normal folder: ${projectPath}`);
  }

  const arrEntry: Info_ProjectPackageEntry[] = [];
  const mapArchivePath = new Map<
    string,
    { archivePath: string; type: "file" | "folder" }
  >();

  function registerArchivePath(archivePath: string, type: "file" | "folder"): void {
    const strArchivePathKey = archivePath.toLowerCase();
    const existingEntry = mapArchivePath.get(strArchivePathKey);
    if (existingEntry !== undefined) {
      throw new Error(
        "Project Package paths conflict case-insensitively: " +
          `${existingEntry.archivePath} (${existingEntry.type}) and ` +
          `${archivePath} (${type}).`,
      );
    }
    mapArchivePath.set(strArchivePathKey, { archivePath, type });
  }

  async function scanFolder(
    folderPath: string,
    arrRelativePathPart: string[],
  ): Promise<void> {
    const arrFolderEntry = await fs.promises.readdir(folderPath, {
      withFileTypes: true,
    });
    arrFolderEntry.sort((left, right) => comparePath(left.name, right.name));

    for (const entryObj of arrFolderEntry) {
      const sourceEntryPath = path.join(folderPath, entryObj.name);
      const entryStat = await fs.promises.lstat(sourceEntryPath);
      if (entryStat.isSymbolicLink()) {
        throw new Error(
          `Project Package does not support symbolic links: ${sourceEntryPath}`,
        );
      }

      const arrEntryRelativePart = [...arrRelativePathPart, entryObj.name];
      const archivePath = arrEntryRelativePart.join("/");

      if (entryStat.isDirectory()) {
        if (
          shouldExcludeProjectFolder(entryObj.name, arrRelativePathPart.length === 0, input)
        ) {
          continue;
        }
        registerArchivePath(archivePath, "folder");
        arrEntry.push({
          type: "folder",
          sourceEntryPath,
          archivePath,
          modifiedAt: entryStat.mtime,
          size: 0,
        });
        await scanFolder(sourceEntryPath, arrEntryRelativePart);
        continue;
      }

      if (entryStat.isFile()) {
        if (
          shouldExcludeProjectFile(entryObj.name, arrRelativePathPart.length === 0, input)
        ) {
          continue;
        }
        registerArchivePath(archivePath, "file");
        arrEntry.push({
          type: "file",
          sourceEntryPath,
          archivePath,
          modifiedAt: entryStat.mtime,
          size: entryStat.size,
        });
        continue;
      }

      throw new Error(
        "Project Package does not support this file-system entry: " + sourceEntryPath,
      );
    }
  }

  registerArchivePath(STR_PROJECT_PACKAGE_MANIFEST_FILE_NAME, "file");
  await scanFolder(projectPath, []);
  arrEntry.sort((left, right) => comparePath(left.archivePath, right.archivePath));
  return arrEntry;
}

async function createPackageArchive(
  tempPackageFilePath: string,
  arrEntry: Info_ProjectPackageEntry[],
  packageManifestContent: string,
): Promise<void> {
  const { ZipArchive } = await import(/* webpackMode: "eager" */ "archiver");
  const outputFileObj = fs.createWriteStream(tempPackageFilePath, {
    flags: "wx",
  });
  const archiveObj = new ZipArchive({ zlib: { level: 9 } });
  const archiveFailurePromise = new Promise<never>((_, reject) => {
    archiveObj.once("warning", reject);
    archiveObj.once("error", reject);
    outputFileObj.once("error", reject);
  });

  try {
    archiveObj.pipe(outputFileObj);
    archiveObj.append(packageManifestContent, {
      name: STR_PROJECT_PACKAGE_MANIFEST_FILE_NAME,
      date: PROJECT_PACKAGE_MANIFEST_ENTRY_DATE,
    });
    for (const entryObj of arrEntry) {
      if (entryObj.type === "folder") {
        archiveObj.append(Buffer.alloc(0), {
          name: `${entryObj.archivePath}/`,
          date: entryObj.modifiedAt,
        });
      } else {
        archiveObj.file(entryObj.sourceEntryPath, {
          name: entryObj.archivePath,
          date: entryObj.modifiedAt,
        });
      }
    }

    await Promise.race([
      Promise.all([archiveObj.finalize(), finished(outputFileObj)]),
      archiveFailurePromise,
    ]);

    const tempPackageFileObj = await fs.promises.open(tempPackageFilePath, "r+");
    try {
      await tempPackageFileObj.sync();
    } finally {
      await tempPackageFileObj.close();
    }
  } catch (e: unknown) {
    try {
      archiveObj.abort();
    } catch {
      // The original archive error remains the primary failure.
    }
    outputFileObj.destroy();
    if (!outputFileObj.closed) {
      await new Promise<void>((resolve) => {
        outputFileObj.once("close", resolve);
      });
    }
    throw new Error("Failed to create the Project Package archive.", {
      cause: e,
    });
  }
}

export async function packageFlowProject(
  workspaceFolder: vscode.WorkspaceFolder,
  input: DictPackageProjectInput,
): Promise<Info_PackageProjectOperationResult> {
  await ensureFlowProject(workspaceFolder);

  const data = await loadPackageProjectData(workspaceFolder, input);
  if (data.blockingReasons.length > 0) {
    throw new Error(
      "The Flow Project cannot be packaged:\n" +
        data.blockingReasons.map((reason) => `- ${reason}`).join("\n"),
    );
  }

  const packageFileName = getProjectPackageFileName(data.manifest);
  const packageFilePath = path.join(input.outputFolderPath, packageFileName);
  if (data.packageFileExists || (await pathExists(packageFilePath))) {
    throw new Error(`Package file already exists: ${packageFilePath}`);
  }

  const arrEntry = await collectProjectPackageEntries(data.projectPath, input);
  const packageManifestContent = stringifyJson(
    buildProjectPackageManifest(input.versionSummary),
    2,
  );

  // Keep the temporary name independent of the final name so the UUID suffix cannot make a valid Windows filename exceed the entry name limit.
  const tempPackageFilePath = path.join(
    input.outputFolderPath,
    `.liberrpa-package-${randomUUID()}.tmp`,
  );

  try {
    await createPackageArchive(tempPackageFilePath, arrEntry, packageManifestContent);
    if (await pathExists(packageFilePath)) {
      throw new Error(`Package file already exists: ${packageFilePath}`);
    }
    await fs.promises.rename(tempPackageFilePath, packageFilePath);
  } catch (e: unknown) {
    await fs.promises.rm(tempPackageFilePath, { force: true }).catch(() => {});
    throw e;
  }

  const packageFileStat = await fs.promises.stat(packageFilePath);
  const intProjectFileCount = arrEntry.filter(
    (entryObj) => entryObj.type === "file",
  ).length;
  const intFileCount = intProjectFileCount + 1;
  const intFolderCount = arrEntry.length - intProjectFileCount;
  const intUncompressedSize =
    arrEntry.reduce((intTotal, entryObj) => intTotal + entryObj.size, 0) +
    Buffer.byteLength(packageManifestContent, "utf-8");
  log.info(`Created Project Package: ${packageFilePath}`);
  log.info(
    `Project Package contains ${String(intFileCount)} files and ` +
      `${String(intFolderCount)} folders.`,
  );

  return {
    result: {
      packageFilePath,
      packageFileName,
      fileCount: intFileCount,
      folderCount: intFolderCount,
      uncompressedSizeBytes: intUncompressedSize,
      packageSizeBytes: packageFileStat.size,
    },
    warnings: data.warnings,
  };
}

export async function openPackageProjectManifest(
  workspaceFolder: vscode.WorkspaceFolder,
): Promise<void> {
  await ensureFlowProject(workspaceFolder);
  const manifestFileUri = vscode.Uri.joinPath(workspaceFolder.uri, "flow.json");
  const documentObj = await vscode.workspace.openTextDocument(manifestFileUri);
  await vscode.window.showTextDocument(documentObj, {
    viewColumn: vscode.ViewColumn.Active,
    preview: false,
    preserveFocus: false,
  });
}

export async function revealProjectPackage(packageFilePath: string): Promise<void> {
  if (!(await pathExists(packageFilePath))) {
    throw new Error(`Project Package file does not exist: ${packageFilePath}`);
  }
  await vscode.commands.executeCommand("revealFileInOS", vscode.Uri.file(packageFilePath));
}
