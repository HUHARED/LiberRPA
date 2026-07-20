// FileName: createFolder.ts
import * as vscode from "vscode";
import * as fs from "node:fs";
import * as path from "node:path";
import { execFileSync } from "node:child_process";

import { log } from "./output";
import { getErrorMessage, printUserCanceled } from "./commonFunc";
import {
  COMPONENT_PACKAGE_NAME_PATTERN,
  getComponentPackageNameError,
  initializeComponentProject,
  initializeFlowProject,
} from "./projectManifest";

type ProjectType = "flow" | "component";

interface ProjectTemplateItem extends vscode.QuickPickItem {
  projectType: ProjectType;
  templateName: string;
}

interface ComponentProjectInput {
  packageName: string;
  displayName: string;
}

const SET_RESERVED_WINDOWS_NAMES = new Set([
  "CON",
  "PRN",
  "AUX",
  "NUL",
  "COM1",
  "COM2",
  "COM3",
  "COM4",
  "COM5",
  "COM6",
  "COM7",
  "COM8",
  "COM9",
  "LPT1",
  "LPT2",
  "LPT3",
  "LPT4",
  "LPT5",
  "LPT6",
  "LPT7",
  "LPT8",
  "LPT9",
]);

export async function createProject(): Promise<void> {
  let newProjectPath: string | undefined;
  let projectFolderCreated = false;

  try {
    const targetFolder = await selectTargetFolder();
    if (targetFolder === undefined) {
      printUserCanceled();
      return;
    }

    const templateFolder = getTemplateFolder();
    const selectedTemplate = await selectProjectTemplate(templateFolder);
    if (selectedTemplate === undefined) {
      printUserCanceled();
      return;
    }

    const projectName = await askProjectName(targetFolder);
    if (projectName === undefined) {
      printUserCanceled();
      return;
    }

    const componentInput =
      selectedTemplate.projectType === "component"
        ? await askComponentProjectInput(projectName)
        : undefined;

    if (selectedTemplate.projectType === "component" && componentInput === undefined) {
      printUserCanceled();
      return;
    }

    newProjectPath = path.join(targetFolder, projectName);
    fs.mkdirSync(newProjectPath);
    projectFolderCreated = true;

    const templatePath = path.join(templateFolder, selectedTemplate.templateName);
    await copyFolder(templatePath, newProjectPath);

    switch (selectedTemplate.projectType) {
      case "flow":
        initializeFlowProject(newProjectPath, projectName);
        break;

      case "component":
        if (componentInput === undefined) {
          throw new Error("Missing Component Project input.");
        }

        initializeComponentProject(
          newProjectPath,
          componentInput.packageName,
          componentInput.displayName,
        );
        break;
    }

    if (fs.existsSync(path.join(newProjectPath, ".gitignore"))) {
      initGit(newProjectPath);
    }

    log.info(`Project "${projectName}" created successfully.`);

    await vscode.commands.executeCommand(
      "vscode.openFolder",
      vscode.Uri.file(newProjectPath),
      { forceNewWindow: true },
    );
  } catch (error: unknown) {
    if (projectFolderCreated && newProjectPath !== undefined) {
      removeIncompleteProject(newProjectPath);
    }

    const errorMessage = getErrorMessage(error);
    log.error(`Error creating Project: ${errorMessage}`);
    void vscode.window.showErrorMessage(`Error creating Project: ${errorMessage}`);
  }
}

async function selectTargetFolder(): Promise<string | undefined> {
  const folderUris = await vscode.window.showOpenDialog({
    canSelectFolders: true,
    canSelectFiles: false,
    canSelectMany: false,
    openLabel: "Select Folder for New Project",
  });

  return folderUris?.[0]?.fsPath;
}

function getTemplateFolder(): string {
  const liberRpaFolder = process.env["LiberRPA"];
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

async function selectProjectTemplate(
  templateFolder: string,
): Promise<ProjectTemplateItem | undefined> {
  const templates = fs
    .readdirSync(templateFolder, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .flatMap<ProjectTemplateItem>((entry) => {
      const projectType = getProjectType(entry.name);
      if (projectType === undefined) {
        log.warn(`Ignore unrecognized Project template folder: ${entry.name}`);
        return [];
      }

      return [
        {
          label: entry.name,
          projectType,
          templateName: entry.name,
        },
      ];
    })
    .sort((left, right) => left.label.localeCompare(right.label));

  if (templates.length === 0) {
    throw new Error(`No valid Project templates found in: ${templateFolder}`);
  }

  return vscode.window.showQuickPick(templates, {
    placeHolder: "Select a Project template",
  });
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

async function askProjectName(targetFolder: string): Promise<string | undefined> {
  return vscode.window.showInputBox({
    prompt: "Enter the folder name for the new Project",
    validateInput: (input) => getProjectFolderNameError(targetFolder, input),
  });
}

function getProjectFolderNameError(
  targetFolder: string,
  projectName: string,
): string | undefined {
  if (projectName.length === 0) {
    return "Project folder name cannot be empty.";
  }

  if (projectName !== projectName.trim()) {
    return "Project folder name cannot start or end with whitespace.";
  }

  if (/[<>:"/\\|?*]/.test(projectName)) {
    return `Project folder name cannot contain Windows reserved characters: ${'<>:"/\\|?*'}`;
  }

  if ([...projectName].some((character) => character.charCodeAt(0) <= 0x1f)) {
    return "Project folder name cannot contain ASCII control characters.";
  }

  if (projectName.endsWith(".")) {
    return "Project folder name cannot end with a period.";
  }

  const nameBeforeFirstPeriod = projectName.split(".", 1)[0]?.toUpperCase();
  if (
    nameBeforeFirstPeriod !== undefined &&
    SET_RESERVED_WINDOWS_NAMES.has(nameBeforeFirstPeriod)
  ) {
    return `Project folder name "${projectName}" is reserved by Windows.`;
  }

  if (projectName.length > 255) {
    return "Project folder name cannot be longer than 255 characters.";
  }

  if (fs.existsSync(path.join(targetFolder, projectName))) {
    return "A folder with this name already exists.";
  }

  return undefined;
}

async function askComponentProjectInput(
  projectName: string,
): Promise<ComponentProjectInput | undefined> {
  const suggestedPackageName = COMPONENT_PACKAGE_NAME_PATTERN.test(projectName)
    ? projectName
    : "";

  const packageName = await vscode.window.showInputBox({
    prompt: "Enter the Component package name",
    placeHolder: "PascalCase, for example: ExcelTools",
    value: suggestedPackageName,
    validateInput: getComponentPackageNameError,
  });

  if (packageName === undefined) {
    return undefined;
  }

  const displayName = await vscode.window.showInputBox({
    prompt: "Enter the Component display name",
    placeHolder: "A readable name shown in user interfaces",
    value: projectName,
    validateInput: (input) => {
      if (input.trim().length === 0) {
        return "Display name cannot be empty.";
      }

      return undefined;
    },
  });

  if (displayName === undefined) {
    return undefined;
  }

  return {
    packageName,
    displayName: displayName.trim(),
  };
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
  } catch (error: unknown) {
    const errorMessage = getErrorMessage(error);
    log.error(`Error copying folder from ${source} to ${destination}: ${errorMessage}`);
    throw new Error(`Failed to copy template files: ${errorMessage}`, {
      cause: error,
    });
  }
}

function initGit(projectPath: string): void {
  try {
    execFileSync("git", ["init"], {
      cwd: projectPath,
      stdio: "ignore",
    });
    log.info("Git repository initialized.");
  } catch (error: unknown) {
    const errorMessage = getErrorMessage(error);
    const message =
      `Failed to initialize Git repository: ${errorMessage}. ` +
      "Make sure Git is installed and available in PATH.";
    log.error(message);
    void vscode.window.showErrorMessage(message);
  }
}

function removeIncompleteProject(projectPath: string): void {
  try {
    fs.rmSync(projectPath, { recursive: true, force: true });
    log.info(`Removed incomplete Project folder: ${projectPath}`);
  } catch (error: unknown) {
    log.error(
      `Failed to remove incomplete Project folder "${projectPath}": ${getErrorMessage(error)}`,
    );
  }
}
