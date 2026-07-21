// FileName: createFolder.ts
import * as vscode from "vscode";
import * as fs from "node:fs";
import * as path from "node:path";
import { execFileSync } from "node:child_process";

import { log } from "./output";
import type { CreateProjectResult } from "./interface";
import {
  getComponentPackageNameError,
  getDisplayNameError,
  getProjectFolderNameError,
  getVersionInputError,
} from "./projectValidation";
import type {
  CreateProjectInput,
  ProjectTemplateInfo,
  ProjectType,
} from "./webviewMessages";
import {
  getProjectManifestDefaults,
  initializeComponentProject,
  initializeFlowProject,
} from "./projectManifest";
import { getErrorMessage } from "./utils";

export async function selectTargetFolder(): Promise<string | undefined> {
  const folderUris = await vscode.window.showOpenDialog({
    canSelectFolders: true,
    canSelectFiles: false,
    canSelectMany: false,
    openLabel: "Select Folder for New Project",
  });

  return folderUris?.[0]?.fsPath;
}

export function getProjectTemplates(): ProjectTemplateInfo[] {
  const templateFolder = getTemplateFolder();

  const templates = fs
    .readdirSync(templateFolder, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .flatMap<ProjectTemplateInfo>((entry) => {
      const projectType = getProjectType(entry.name);
      if (projectType === undefined) {
        log.warn(`Ignore unrecognized Project template folder: ${entry.name}`);
        return [];
      }

      const templatePath = path.join(templateFolder, entry.name);
      const defaults = getProjectManifestDefaults(templatePath, projectType);

      return [
        {
          templateName: entry.name,
          projectType,
          version: defaults.version,
          description: defaults.description,
        },
      ];
    })
    .sort((left, right) => left.templateName.localeCompare(right.templateName));

  if (templates.length === 0) {
    throw new Error(`No valid Project templates found in: ${templateFolder}`);
  }

  return templates;
}

export async function createProject(
  input: CreateProjectInput,
): Promise<CreateProjectResult> {
  validateCreateProjectInput(input);

  const templateFolder = getTemplateFolder();
  const template = getProjectTemplates().find(
    (item) => item.templateName === input.templateName,
  );

  if (template === undefined) {
    throw new Error(`Project template not found: ${input.templateName}`);
  }

  if (template.projectType !== input.projectType) {
    throw new Error(
      `Project template "${input.templateName}" does not match Project type "${input.projectType}".`,
    );
  }

  const projectPath = path.join(input.targetFolder, input.projectFolderName);
  if (fs.existsSync(projectPath)) {
    throw new Error(`The target Project folder already exists: ${projectPath}`);
  }

  const stagingPath = fs.mkdtempSync(path.join(input.targetFolder, ".liberrpa-create-"));
  const warnings: string[] = [];
  let committed = false;

  try {
    const templatePath = path.join(templateFolder, input.templateName);
    await copyFolder(templatePath, stagingPath);

    switch (input.projectType) {
      case "flow":
        initializeFlowProject(
          stagingPath,
          input.projectFolderName,
          input.version,
          input.description,
        );
        break;

      case "component":
        initializeComponentProject(
          stagingPath,
          input.packageName,
          input.displayName,
          input.version,
          input.description,
        );
        break;
    }

    if (fs.existsSync(path.join(stagingPath, ".gitignore"))) {
      const warning = initGit(stagingPath);
      if (warning !== undefined) {
        warnings.push(warning);
      }
    }

    if (fs.existsSync(projectPath)) {
      throw new Error(`The target Project folder already exists: ${projectPath}`);
    }

    fs.renameSync(stagingPath, projectPath);
    committed = true;
  } finally {
    if (!committed && fs.existsSync(stagingPath)) {
      removeIncompleteProject(stagingPath);
    }
  }

  log.info(`Project "${input.projectFolderName}" created successfully.`);

  return {
    projectPath,
    warnings,
  };
}

function getTemplateFolder(): string {
  const liberRpaFolder = process.env.LiberRPA;
  if (liberRpaFolder === undefined || liberRpaFolder.length === 0) {
    throw new Error(
      'The "LiberRPA" User Environment Variable is missing. Run InitLiberRPA.exe first.',
    );
  }

  const templateFolder = path.join(liberRpaFolder, "configFiles", "ProjectTemplate");

  if (!fs.existsSync(templateFolder) || !fs.statSync(templateFolder).isDirectory()) {
    throw new Error(`Template directory not found: ${templateFolder}`);
  }

  return templateFolder;
}

function getProjectType(templateName: string): ProjectType | undefined {
  if (templateName.startsWith("FlowProject-")) {
    return "flow";
  }

  if (templateName.startsWith("ComponentProject-")) {
    return "component";
  }

  return undefined;
}

function validateCreateProjectInput(input: CreateProjectInput): void {
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

async function copyFolder(source: string, destination: string): Promise<void> {
  try {
    const entries = await fs.promises.readdir(source, { withFileTypes: true });

    await Promise.all(
      entries.map(async (entry) => {
        const sourcePath = path.join(source, entry.name);
        const destinationPath = path.join(destination, entry.name);

        if (entry.isDirectory()) {
          await fs.promises.mkdir(destinationPath, { recursive: true });
          await copyFolder(sourcePath, destinationPath);
          return;
        }

        await fs.promises.copyFile(sourcePath, destinationPath);
      }),
    );
  } catch (e: unknown) {
    const errorMessage = getErrorMessage(e);
    log.error(`Error copying folder from ${source} to ${destination}: ${errorMessage}`);
    throw new Error(`Failed to copy template files: ${errorMessage}`, {
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
    const warning =
      `Failed to initialize Git repository: ${getErrorMessage(e)}. ` +
      "Make sure Git is installed and available in PATH.";
    log.warn(warning);
    return warning;
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
