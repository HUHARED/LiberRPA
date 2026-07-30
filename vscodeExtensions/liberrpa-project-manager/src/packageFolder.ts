// FileName: packageFolder.ts
import * as vscode from "vscode";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { finished } from "node:stream/promises";

import { log } from "./output";
import { isRecord } from "./typeCheck";
import { getErrorMessage, stringifyJson, printUserCanceled } from "./utils";

interface LegacyProjectJson extends Record<string, unknown> {
  executorPackage: false;
  executorPackageName: string;
  executorPackageVersion: string;
  executorPackageDescription?: string;
}

export async function packageProject(): Promise<void> {
  let tempFolderPath: string | undefined;

  try {
    // This flow intentionally keeps using project.json until the new package
    // manifest design is implemented.
    const originalProjectJson = readProjectJson();

    const projectVersion = await vscode.window.showInputBox({
      prompt: "Enter the version for the package",
      value: originalProjectJson.executorPackageVersion,
      validateInput: (input) => {
        if (input.length === 0) {
          return "Package version cannot be empty.";
        }

        if (/[<>:"/\\|?*]/.test(input)) {
          return `Package version cannot contain these characters: ${'<>:"/\\|?*'}`;
        }

        if (input.length > 255) {
          return "Package version cannot be longer than 255 characters.";
        }

        return undefined;
      },
    });

    if (projectVersion === undefined) {
      printUserCanceled();
      return;
    }

    const description = await vscode.window.showInputBox({
      prompt: "Enter the description for the package",
      value: originalProjectJson.executorPackageDescription ?? "",
    });

    if (description === undefined) {
      printUserCanceled();
      return;
    }

    const containGit = await vscode.window.showQuickPick(["Yes", "No"] as const, {
      placeHolder: "Contain the .git folder? (If it exists)",
    });

    if (containGit === undefined) {
      printUserCanceled();
      return;
    }

    const folderUris = await vscode.window.showOpenDialog({
      canSelectFolders: true,
      canSelectFiles: false,
      canSelectMany: false,
      openLabel: "Select Folder for saving the package file",
    });

    const targetFolder = folderUris?.[0]?.fsPath;
    if (targetFolder === undefined) {
      printUserCanceled();
      return;
    }

    tempFolderPath = fs.mkdtempSync(path.join(os.tmpdir(), "LiberRPA-package-"));

    const workspaceFolderPath = getWorkspaceFolder().uri.fsPath;
    await copyFolderToTemp(
      workspaceFolderPath,
      tempFolderPath,
      containGit === "Yes",
      workspaceFolderPath,
    );

    const packagedProjectJson: Record<string, unknown> = {
      ...originalProjectJson,
      executorPackage: true,
      executorPackageVersion: projectVersion,
      executorPackageDescription: description,
    };

    fs.writeFileSync(
      path.join(tempFolderPath, "project.json"),
      stringifyJson(packagedProjectJson, 4),
      { encoding: "utf-8" },
    );

    const zipFilePath = await compressFolder(
      tempFolderPath,
      targetFolder,
      originalProjectJson.executorPackageName,
      projectVersion,
    );

    const updatedOriginalProjectJson: LegacyProjectJson = {
      ...originalProjectJson,
      executorPackageVersion: projectVersion,
      executorPackageDescription: description,
    };
    writeOriginalProjectJson(updatedOriginalProjectJson);

    log.info(`Reveal the package file: ${zipFilePath}`);
    await vscode.commands.executeCommand("revealFileInOS", vscode.Uri.file(zipFilePath));
  } catch (e: unknown) {
    const strErrorMessage = getErrorMessage(e);
    log.error(`Error packaging Project: ${strErrorMessage}`);
    void vscode.window.showErrorMessage(`Error packaging Project: ${strErrorMessage}`);
  } finally {
    if (tempFolderPath !== undefined) {
      try {
        fs.rmSync(tempFolderPath, { recursive: true, force: true });
      } catch (e: unknown) {
        log.error(
          `Failed to remove temporary package folder "${tempFolderPath}": ${getErrorMessage(e)}`,
        );
      }
    }
  }
}

function readProjectJson(): LegacyProjectJson {
  log.info("Read project.json in current workspace folder.");

  const projectJsonPath = getProjectJsonPath();
  const content = fs.readFileSync(projectJsonPath, { encoding: "utf-8" });
  const value = JSON.parse(content) as unknown;

  if (isLegacyProjectJson(value)) {
    return value;
  }

  throw new Error(
    "project.json must contain executorPackage=false, executorPackageName, and executorPackageVersion.",
  );
}

function isLegacyProjectJson(value: unknown): value is LegacyProjectJson {
  return (
    isRecord(value) &&
    value["executorPackage"] === false &&
    typeof value["executorPackageName"] === "string" &&
    value["executorPackageName"].length > 0 &&
    typeof value["executorPackageVersion"] === "string" &&
    value["executorPackageVersion"].length > 0 &&
    (value["executorPackageDescription"] === undefined ||
      typeof value["executorPackageDescription"] === "string")
  );
}

function writeOriginalProjectJson(projectJson: LegacyProjectJson): void {
  try {
    log.info(`Update project.json version to ${projectJson.executorPackageVersion}.`);

    fs.writeFileSync(getProjectJsonPath(), stringifyJson(projectJson, 4), {
      encoding: "utf-8",
    });
  } catch (e: unknown) {
    throw new Error(`Failed to update project.json: ${getErrorMessage(e)}`, {
      cause: e,
    });
  }
}

function getWorkspaceFolder(): vscode.WorkspaceFolder {
  const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
  if (workspaceFolder === undefined) {
    throw new Error("No workspace folder is open.");
  }

  return workspaceFolder;
}

function getProjectJsonPath(): string {
  return path.join(getWorkspaceFolder().uri.fsPath, "project.json");
}

async function copyFolderToTemp(
  source: string,
  destination: string,
  containGit: boolean,
  workspaceFolderPath: string,
): Promise<void> {
  try {
    const entries = await fs.promises.readdir(source, { withFileTypes: true });

    await Promise.all(
      entries.map(async (entry) => {
        if (source === workspaceFolderPath && entry.name === ".git" && !containGit) {
          return;
        }

        const sourcePath = path.join(source, entry.name);
        const destinationPath = path.join(destination, entry.name);

        if (entry.isDirectory()) {
          await fs.promises.mkdir(destinationPath, { recursive: true });
          await copyFolderToTemp(
            sourcePath,
            destinationPath,
            containGit,
            workspaceFolderPath,
          );
          return;
        }

        await fs.promises.copyFile(sourcePath, destinationPath);
      }),
    );
  } catch (e: unknown) {
    const strErrorMessage = getErrorMessage(e);
    log.error(`Error copying folder from ${source} to ${destination}: ${strErrorMessage}`);
    throw new Error(`Failed to copy Project files: ${strErrorMessage}`, { cause: e });
  }
}

async function compressFolder(
  sourceFolder: string,
  targetFolder: string,
  packageName: string,
  packageVersion: string,
): Promise<string> {
  const zipFileName = `${packageName}_${packageVersion}.rpa.zip`;
  const zipFilePath = path.join(targetFolder, zipFileName);
  const output = fs.createWriteStream(zipFilePath);
  const { ZipArchive } = await import("archiver");
  const archive = new ZipArchive({ zlib: { level: 9 } });

  try {
    archive.pipe(output);
    archive.directory(sourceFolder, false);
    await archive.finalize();
    await finished(output);
  } catch (e: unknown) {
    output.destroy();
    throw new Error(`Failed to create package archive: ${getErrorMessage(e)}`, {
      cause: e,
    });
  }

  log.info(`Create zip file with ${archive.pointer()} bytes.`);
  return zipFilePath;
}
