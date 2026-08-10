// FileName: createProject.ts

import * as vscode from "vscode";
import * as fs from "node:fs";
import * as path from "node:path";
import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";

import { log } from "../../Adapter/VsCode/output";
import {
  readFlowManifest,
  readComponentManifest,
  writeFlowManifest,
  writeComponentManifest,
} from "../../Domain/Project/projectManifest";
import type {
  Str_ProjectType,
  DictCreateProjectInput,
  DictProjectTemplateInfo,
} from "../../Domain/Project/projectTypes";
import {
  getProjectFolderNameError,
  getVersionInputError,
  getComponentPackageNameError,
  getDisplayNameError,
} from "../../Domain/Project/projectValidation";
import { getErrorMessage } from "../../Common/utils";

export interface Info_CreateProjectResult {
  projectPath: string;
  warnings: string[];
}

function validateCreateProjectInput(input: DictCreateProjectInput): void {
  if (!path.isAbsolute(input.targetFolderPath)) {
    throw new Error("Target folder must be an absolute path.");
  }
  if (!fs.existsSync(input.targetFolderPath)) {
    throw new Error(`Target folder not found: ${input.targetFolderPath}`);
  }
  if (!fs.statSync(input.targetFolderPath).isDirectory()) {
    throw new Error(`Target path is not a folder: ${input.targetFolderPath}`);
  }

  const strProjectFolderNameError = getProjectFolderNameError(input.projectFolderName);
  if (strProjectFolderNameError !== undefined) {
    throw new Error(strProjectFolderNameError);
  }

  const strVersionError = getVersionInputError(input.version);
  if (strVersionError !== undefined) {
    throw new Error(strVersionError);
  }

  if (input.projectType === "component") {
    const strPackageNameError = getComponentPackageNameError(input.packageName);
    if (strPackageNameError !== undefined) {
      throw new Error(strPackageNameError);
    }

    const strDisplayNameError = getDisplayNameError(input.displayName);
    if (strDisplayNameError !== undefined) {
      throw new Error(strDisplayNameError);
    }
  }
}

function getTemplatesFolderPath(): string {
  const strLiberRPAPath = process.env.LiberRPA;
  if (strLiberRPAPath === undefined || strLiberRPAPath.trim().length === 0) {
    throw new Error(
      'The "LiberRPA" User Environment Variable is missing. Run InitLiberRPA.exe first.',
    );
  }

  const strTemplatesFolderPath = path.join(
    strLiberRPAPath,
    "configFiles",
    "ProjectTemplate",
  );
  if (
    !fs.existsSync(strTemplatesFolderPath) ||
    !fs.statSync(strTemplatesFolderPath).isDirectory()
  ) {
    throw new Error(`Template folder not found: ${strTemplatesFolderPath}`);
  }

  return strTemplatesFolderPath;
}

function getTemplateProjectType(templateName: string): Str_ProjectType | undefined {
  if (templateName.startsWith("FlowProject-")) {
    return "flow";
  }
  if (templateName.startsWith("ComponentProject-")) {
    return "component";
  }
  return undefined;
}

function getTemplateInfo(
  templateFolderPath: string,
  templateName: string,
  projectType: Str_ProjectType,
): DictProjectTemplateInfo {
  if (projectType === "flow") {
    const dictManifest = readFlowManifest(path.join(templateFolderPath, "flow.json"));
    return {
      templateName,
      projectType,
      defaultVersion: dictManifest.version,
      defaultDescription: dictManifest.description,
    };
  }

  const dictManifest = readComponentManifest(
    path.join(templateFolderPath, "component.json"),
  );
  return {
    templateName,
    projectType,
    defaultVersion: dictManifest.version,
    defaultDescription: dictManifest.description,
  };
}

export function getProjectTemplates(): DictProjectTemplateInfo[] {
  const strTemplatesFolderPath = getTemplatesFolderPath();
  const arrTemplate = fs
    .readdirSync(strTemplatesFolderPath, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .flatMap<DictProjectTemplateInfo>((entry) => {
      const projectType = getTemplateProjectType(entry.name);
      if (projectType === undefined) {
        log.warn(`Ignored unrecognized Project template folder: ${entry.name}`);
        return [];
      }

      return [
        getTemplateInfo(
          path.join(strTemplatesFolderPath, entry.name),
          entry.name,
          projectType,
        ),
      ];
    })
    .sort((left, right) => left.templateName.localeCompare(right.templateName));

  if (arrTemplate.length === 0) {
    throw new Error(`No valid Project templates found in: ${strTemplatesFolderPath}`);
  }

  return arrTemplate;
}

export async function selectTargetFolder(): Promise<string | undefined> {
  const arrFolderUri = await vscode.window.showOpenDialog({
    canSelectFolders: true,
    canSelectFiles: false,
    canSelectMany: false,
    openLabel: "Select Folder for New Project",
  });

  return arrFolderUri?.[0]?.fsPath;
}

async function copyTemplateFolder(
  sourceFolderPath: string,
  targetFolderPath: string,
): Promise<void> {
  const arrEntry = await fs.promises.readdir(sourceFolderPath, {
    withFileTypes: true,
  });

  for (const entry of arrEntry) {
    if (entry.name === ".gitkeep") {
      continue;
    }

    const strSourceEntryPath = path.join(sourceFolderPath, entry.name);
    const strTargetEntryPath = path.join(targetFolderPath, entry.name);

    if (entry.isDirectory()) {
      await fs.promises.mkdir(strTargetEntryPath, { recursive: true });
      await copyTemplateFolder(strSourceEntryPath, strTargetEntryPath);
      continue;
    }

    if (!entry.isFile()) {
      throw new Error(`Unsupported Project template entry: ${strSourceEntryPath}`);
    }

    await fs.promises.copyFile(strSourceEntryPath, strTargetEntryPath);
  }
}

function initializeFlowProject(projectPath: string, input: DictCreateProjectInput): void {
  const strManifestFilePath = path.join(projectPath, "flow.json");
  const dictManifest = readFlowManifest(strManifestFilePath);
  dictManifest.name = input.projectFolderName;
  dictManifest.version = input.version;
  dictManifest.description = input.description;
  writeFlowManifest(strManifestFilePath, dictManifest);
}

function initializeComponentProject(
  projectPath: string,
  input: DictCreateProjectInput,
): void {
  const strManifestFilePath = path.join(projectPath, "component.json");
  const dictManifest = readComponentManifest(strManifestFilePath);
  dictManifest.id = randomUUID();
  dictManifest.packageName = input.packageName;
  dictManifest.displayName = input.displayName;
  dictManifest.version = input.version;
  dictManifest.description = input.description;
  writeComponentManifest(strManifestFilePath, dictManifest);

  const strPackageFolderPath = path.join(projectPath, "src", input.packageName);
  fs.mkdirSync(strPackageFolderPath, { recursive: true });
  fs.writeFileSync(path.join(strPackageFolderPath, "__init__.py"), "", {
    encoding: "utf-8",
    flag: "wx",
  });
  fs.writeFileSync(path.join(strPackageFolderPath, "py.typed"), "", {
    encoding: "utf-8",
    flag: "wx",
  });
}

function initializeGit(projectPath: string): string | undefined {
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
  } catch (e: unknown) {
    log.error(
      `Failed to remove incomplete Project folder "${projectPath}": ` + getErrorMessage(e),
    );
  }
}

export async function createProject(
  input: DictCreateProjectInput,
): Promise<Info_CreateProjectResult> {
  validateCreateProjectInput(input);

  const arrTemplate = getProjectTemplates();
  const dictTemplate = arrTemplate.find((item) => item.templateName === input.templateName);
  if (dictTemplate === undefined) {
    throw new Error(`Project template not found: ${input.templateName}`);
  }
  if (dictTemplate.projectType !== input.projectType) {
    throw new Error(
      `Project template "${input.templateName}" does not match Project type ` +
        `"${input.projectType}".`,
    );
  }

  const strProjectPath = path.join(input.targetFolderPath, input.projectFolderName);
  if (fs.existsSync(strProjectPath)) {
    throw new Error(`The target Project folder already exists: ${strProjectPath}`);
  }

  const strTempProjectPath = fs.mkdtempSync(
    path.join(input.targetFolderPath, ".liberrpa-create-"),
  );
  const arrWarning: string[] = [];
  let boolCommitted = false;

  try {
    await copyTemplateFolder(
      path.join(getTemplatesFolderPath(), input.templateName),
      strTempProjectPath,
    );

    if (input.projectType === "flow") {
      initializeFlowProject(strTempProjectPath, input);
    } else {
      initializeComponentProject(strTempProjectPath, input);
    }

    if (fs.existsSync(path.join(strTempProjectPath, ".gitignore"))) {
      const strWarning = initializeGit(strTempProjectPath);
      if (strWarning !== undefined) {
        arrWarning.push(strWarning);
      }
    }

    if (fs.existsSync(strProjectPath)) {
      throw new Error(`The target Project folder already exists: ${strProjectPath}`);
    }

    fs.renameSync(strTempProjectPath, strProjectPath);
    boolCommitted = true;
  } catch (e: unknown) {
    throw new Error(`Failed to create Project: ${getErrorMessage(e)}`, {
      cause: e,
    });
  } finally {
    if (!boolCommitted && fs.existsSync(strTempProjectPath)) {
      removeIncompleteProject(strTempProjectPath);
    }
  }

  log.info(`Project "${input.projectFolderName}" created successfully.`);
  return { projectPath: strProjectPath, warnings: arrWarning };
}
