// FileName: createFolder.ts
import * as vscode from "vscode";
import * as fs from "node:fs";
import * as path from "node:path";
import { execFileSync } from "node:child_process";

import { log } from "./output";
import type { Str_ProjectType } from "./componentManagement/protocol";
import {
  getProjectFolderNameError,
  getVersionInputError,
  getComponentPackageNameError,
  getDisplayNameError,
} from "./projectValidation";
import type { DictCreateProjectInput, DictProjectTemplateInfo } from "./webviewMessages";
import {
  getProjectManifestDefaults,
  initializeFlowProject,
  initializeComponentProject,
} from "./projectManifest";
import { getErrorMessage } from "./utils";

interface DictCreateProjectResult {
  projectPath: string;
  warnings: string[];
}

function validateCreateProjectInput(input: DictCreateProjectInput): void {
  if (!path.isAbsolute(input.targetFolder)) {
    throw new Error("Target folder must be an absolute path.");
  }

  if (!fs.existsSync(input.targetFolder)) {
    throw new Error(`Target folder not found: ${input.targetFolder}`);
  }

  if (!fs.statSync(input.targetFolder).isDirectory()) {
    throw new Error(`Target path is not a folder: ${input.targetFolder}`);
  }

  const projectFolderNameError = getProjectFolderNameError(input.projectFolderName);
  if (projectFolderNameError !== undefined) {
    throw new Error(projectFolderNameError);
  }

  const versionError = getVersionInputError(input.version);
  if (versionError !== undefined) {
    throw new Error(versionError);
  }

  if (input.projectType === "component") {
    const packageNameError = getComponentPackageNameError(input.packageName);
    if (packageNameError !== undefined) {
      throw new Error(packageNameError);
    }

    const displayNameError = getDisplayNameError(input.displayName);
    if (displayNameError !== undefined) {
      throw new Error(displayNameError);
    }
  }
}

function getTemplateFolder(): string {
  const strLiberRPAEnvPath = process.env.LiberRPA;
  if (strLiberRPAEnvPath === undefined || strLiberRPAEnvPath.length === 0) {
    throw new Error(
      'The "LiberRPA" User Environment Variable is missing. Run InitLiberRPA.exe first.',
    );
  }

  const templateFolder = path.join(strLiberRPAEnvPath, "configFiles", "ProjectTemplate");

  if (!fs.existsSync(templateFolder) || !fs.statSync(templateFolder).isDirectory()) {
    throw new Error(`Template directory not found: ${templateFolder}`);
  }

  return templateFolder;
}

function getProjectType(templateName: string): Str_ProjectType | undefined {
  if (templateName.startsWith("FlowProject-")) {
    return "flow";
  }

  if (templateName.startsWith("ComponentProject-")) {
    return "component";
  }

  return undefined;
}

export function getProjectTemplates(): DictProjectTemplateInfo[] {
  const strTemplateFolder = getTemplateFolder();

  const arrTemplates = fs
    .readdirSync(strTemplateFolder, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .flatMap<DictProjectTemplateInfo>((entry) => {
      const strProjectType = getProjectType(entry.name);
      if (strProjectType === undefined) {
        log.warn(`Ignore unrecognized Project template folder: ${entry.name}`);
        return [];
      }

      const strTemplatePath = path.join(strTemplateFolder, entry.name);
      const dictDefaultInfo = getProjectManifestDefaults(strTemplatePath, strProjectType);

      return [
        {
          templateName: entry.name,
          projectType: strProjectType,
          defaultVersion: dictDefaultInfo.defaultVersion,
          defaultDescription: dictDefaultInfo.defaultDescription,
        },
      ];
    })
    .sort((left, right) => left.templateName.localeCompare(right.templateName));

  if (arrTemplates.length === 0) {
    throw new Error(`No valid Project templates found in: ${strTemplateFolder}`);
  }

  return arrTemplates;
}

export async function selectTargetFolder(): Promise<string | undefined> {
  const folderUris = await vscode.window.showOpenDialog({
    canSelectFolders: true,
    canSelectFiles: false,
    canSelectMany: false,
    openLabel: "Select Folder for New Project",
  });

  return folderUris?.[0]?.fsPath;
}

async function copyFolder(source: string, destination: string): Promise<void> {
  try {
    const arrEntries = await fs.promises.readdir(source, { withFileTypes: true });

    await Promise.all(
      arrEntries.map(async (entry) => {
        if (entry.name === ".gitkeep") {
          log.debug(`Ignore template placeholder file: ${path.join(source, entry.name)}`);
          return;
        }

        const strSrcPath = path.join(source, entry.name);
        const strDstPath = path.join(destination, entry.name);

        if (entry.isDirectory()) {
          await fs.promises.mkdir(strDstPath, { recursive: true });
          await copyFolder(strSrcPath, strDstPath);
          return;
        }

        await fs.promises.copyFile(strSrcPath, strDstPath);
      }),
    );
  } catch (e: unknown) {
    const strErrorMessage = getErrorMessage(e);
    log.error(`Error copying folder from ${source} to ${destination}: ${strErrorMessage}`);
    throw new Error(`Failed to copy template files: ${strErrorMessage}`, {
      cause: e,
    });
  }
}

function initGit(projectPath: string): string | undefined {
  try {
    execFileSync("git", ["init"], {
      cwd: projectPath,
      stdio: "ignore",
    });
    log.info("Git repository initialized.");
    return undefined;
  } catch (e: unknown) {
    const strWarning =
      `Failed to initialize Git repository: ${getErrorMessage(e)}. ` +
      "Make sure Git is installed and available in PATH.";
    log.warn(strWarning);
    return strWarning;
  }
}

function removeIncompleteProject(projectPath: string): void {
  try {
    fs.rmSync(projectPath, { recursive: true, force: true });
    log.info(`Removed incomplete Project folder: ${projectPath}`);
  } catch (e: unknown) {
    log.error(
      `Failed to remove incomplete Project folder "${projectPath}": ${getErrorMessage(e)}`,
    );
  }
}

export async function createProject(
  input: DictCreateProjectInput,
): Promise<DictCreateProjectResult> {
  validateCreateProjectInput(input);

  const strTemplateFolder = getTemplateFolder();
  const dictTemplate = getProjectTemplates().find(
    (item) => item.templateName === input.templateName,
  );

  if (dictTemplate === undefined) {
    throw new Error(`Project template not found: ${input.templateName}`);
  }

  if (dictTemplate.projectType !== input.projectType) {
    throw new Error(
      `Project template "${input.templateName}" does not match Project type "${input.projectType}".`,
    );
  }

  const strProjectPath = path.join(input.targetFolder, input.projectFolderName);
  if (fs.existsSync(strProjectPath)) {
    throw new Error(`The target Project folder already exists: ${strProjectPath}`);
  }

  const strStagingPath = fs.mkdtempSync(path.join(input.targetFolder, ".liberrpa-create-"));
  const arrWarning: string[] = [];
  let boolCommitted = false;

  try {
    const strTemplatePath = path.join(strTemplateFolder, input.templateName);
    await copyFolder(strTemplatePath, strStagingPath);

    switch (input.projectType) {
      case "flow":
        initializeFlowProject(
          strStagingPath,
          input.projectFolderName,
          input.version,
          input.description,
        );
        break;

      case "component":
        initializeComponentProject(
          strStagingPath,
          input.packageName,
          input.displayName,
          input.version,
          input.description,
        );
        break;
    }

    if (fs.existsSync(path.join(strStagingPath, ".gitignore"))) {
      const strWarning = initGit(strStagingPath);
      if (strWarning !== undefined) {
        arrWarning.push(strWarning);
      }
    }

    if (fs.existsSync(strProjectPath)) {
      throw new Error(`The target Project folder already exists: ${strProjectPath}`);
    }

    // Atomically create the target folder.
    fs.renameSync(strStagingPath, strProjectPath);
    boolCommitted = true;
  } finally {
    if (!boolCommitted && fs.existsSync(strStagingPath)) {
      removeIncompleteProject(strStagingPath);
    }
  }

  log.info(`Project "${input.projectFolderName}" created successfully.`);

  return {
    projectPath: strProjectPath,
    warnings: arrWarning,
  };
}
