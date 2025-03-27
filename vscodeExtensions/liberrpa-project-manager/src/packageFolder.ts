// FileName: packageFolder.ts
import * as vscode from "vscode";
import * as os from "os";
import * as fs from "fs";
import * as path from "path";
import archiver from "archiver";

import { outputChannel } from "./commonValue";
import { printUserCanceled } from "./commonFunc";

export async function packageProject(): Promise<void> {
  try {
    // 1. Check executor item in project.json
    const dictProject = await readProjectJson();

    // 2. Ask for the project version
    const strProjectVersion = await vscode.window.showInputBox({
      prompt: "Enter the version for the package",
      value: dictProject["executorPackageVersion"] as string,
      validateInput: (input) => {
        const regexInvalidChars = /[<>:"/\\|?*]/;
        if (regexInvalidChars.test(input)) {
          return `Package version can't contain these characters: ${'<>:"/\\|?*'}`;
        }
        if (input.length > 255) {
          return `Package version length can't longer than 255.`;
        }
        return null;
      },
    });

    if (!strProjectVersion) {
      printUserCanceled();
      return;
    } else {
      dictProject["executorPackageVersion"] = strProjectVersion;
      await writeOriginalProjectJson(dictProject);
    }

    // 3. Ask for the project description.

    const strDescription = await vscode.window.showInputBox({
      prompt: "Enter the description for the package",
    });

    if (strDescription === undefined) {
      printUserCanceled();
      return;
    } else {
      dictProject["executorPackageDescription"] = strDescription;
    }

    // 4. Ask for whether package .git folder.
    const strContainGit = await vscode.window.showQuickPick(["Yes", "No"], {
      placeHolder: "Contain the .git folder? (If it exists)",
    });

    if (!strContainGit) {
      printUserCanceled();
      return;
    }

    // 5. Create copy.

    // Clean temp folder to paste new files later.
    const strTempFolderPath = path.join(os.homedir(), "Documents", "LiberRPA", "Temp");
    fs.rmSync(strTempFolderPath, { recursive: true, force: true });
    // Recreate the Temp folder to avoid the error ignore copy .git folder.
    fs.mkdirSync(strTempFolderPath, { recursive: true });

    // Copy the workspace folder to temp folder.
    await copyFolderToTemp(
      getWorkspaceFolder().uri.fsPath,
      strTempFolderPath,
      strContainGit === "Yes"
    );

    // Update executorPackage and executorPackageDescription values in Temp folder.
    dictProject["executorPackage"] = true;

    fs.writeFileSync(
      path.join(strTempFolderPath, "project.json"),
      JSON.stringify(dictProject, null, 4),
      {
        encoding: "utf-8",
      }
    );

    // 6. Ask for compress file store path.
    const folderUri = await vscode.window.showOpenDialog({
      canSelectFolders: true,
      canSelectFiles: false,
      canSelectMany: false,
      openLabel: "Select Folder for saving the package file",
    });
    if (!folderUri) {
      printUserCanceled();
      return;
    }
    const strTargetFolder = folderUri[0].fsPath;

    // 7. Compress all files in strTempFolderPath to strTargetFolder, named the file as "dictProject["executorPackageName"]_dictProject["executorPackageVersion"].rpa.zip"

    const strZipFilePath = await compressFolder(
      strTempFolderPath,
      strTargetFolder,
      dictProject["executorPackageName"] as string,
      dictProject["executorPackageVersion"]
    );

    // 8. Clean Temp folder.
    fs.rmSync(strTempFolderPath, { recursive: true, force: true });

    // 9. Reveal the compressed file.
    outputChannel.appendLine(`Reveal the package file: ${strZipFilePath}`);
    vscode.commands.executeCommand("revealFileInOS", vscode.Uri.file(strZipFilePath));
  } catch (e) {
    vscode.window.showErrorMessage(`Error packaging project: ${e}`);
  }
}

async function readProjectJson(): Promise<{ [key: string]: string | boolean }> {
  outputChannel.appendLine("Read project.json in current workspaceFolder.");

  const projectJsonPath = getProjectJsonPath();
  const strContent = fs.readFileSync(projectJsonPath, "utf-8");
  const dictProject: { [key: string]: string | boolean } = JSON.parse(strContent);

  if (
    !(dictProject["executorPackage"] === false) ||
    !dictProject["executorPackageName"] ||
    !dictProject["executorPackageVersion"]
  ) {
    throw Error(
      "'executorPackage': false, executorPackageName and executorPackageVersion should in project.json"
    );
  }

  return dictProject;
}

async function writeOriginalProjectJson(dictProject: {
  [key: string]: string | boolean;
}): Promise<void> {
  try {
    outputChannel.appendLine(
      `Update project.json's version to ${dictProject["executorPackageVersion"]}`
    );

    const projectJsonPath = getProjectJsonPath();

    fs.writeFileSync(projectJsonPath, JSON.stringify(dictProject, null, 4), {
      encoding: "utf-8",
    });
  } catch (e) {
    throw new Error(`Failed to update project.json: ${e}`);
  }
}

function getWorkspaceFolder(): vscode.WorkspaceFolder {
  const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
  if (!workspaceFolder) {
    throw Error("No workspace folder is open.");
  }
  return workspaceFolder;
}

function getProjectJsonPath(): string {
  const projectJsonPath = path.join(getWorkspaceFolder().uri.fsPath, "project.json");
  return projectJsonPath;
}

async function copyFolderToTemp(
  src: string,
  dest: string,
  containGit: boolean
): Promise<void> {
  try {
    const entries = await fs.promises.readdir(src, { withFileTypes: true });
    await Promise.all(
      entries.map(async (entry) => {
        // If we are at the root level and the entry is ".git" and user does NOT want it, skip it.
        if (
          src === getWorkspaceFolder().uri.fsPath &&
          entry.name === ".git" &&
          !containGit
        ) {
          return;
        }

        const srcPath = path.join(src, entry.name);
        const destPath = path.join(dest, entry.name);
        if (entry.isDirectory()) {
          fs.mkdirSync(destPath, { recursive: true });
          await copyFolderToTemp(srcPath, destPath, containGit);
        } else {
          fs.copyFileSync(srcPath, destPath);
        }
      })
    );
  } catch (e) {
    outputChannel.appendLine(`Error copying folder from ${src} to ${dest}: ${e}`);
    throw new Error(`Failed to copy files: ${e}`);
  }
}

async function compressFolder(
  sourceFolder: string,
  targetFolder: string,
  packageName: string,
  packageVersion: string
): Promise<string> {
  const strZipFileName = `${packageName}_${packageVersion}.rpa.zip`;
  const strZipFilePath = path.join(targetFolder, strZipFileName);

  return new Promise((resolve, reject) => {
    const output = fs.createWriteStream(strZipFilePath);
    const archive = archiver("zip", { zlib: { level: 9 } });

    output.on("close", () => {
      outputChannel.appendLine(`Create zip file with ${archive.pointer()} bytes.`);
      resolve(strZipFilePath);
    });

    output.on("error", (err) => {
      reject(err);
    });

    archive.on("error", (err) => {
      reject(err);
    });

    archive.pipe(output);
    archive.directory(sourceFolder, false);
    archive.finalize();
  });
}
