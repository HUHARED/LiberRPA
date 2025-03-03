// FileName: extension.ts
import * as vscode from "vscode";
import * as fs from "fs";
import * as path from "path";
import * as util from "util";
import { execSync } from "child_process";

const outputChannel = vscode.window.createOutputChannel("liberrpa-project-manager");
outputChannel.show(true);

export function activate(context: vscode.ExtensionContext) {
  outputChannel.appendLine('"liberrpa-project-manager" is now active.');

  const disposable = vscode.commands.registerCommand("LiberRPA.createProject", async () => {
    try {
      // 1. Ask for the target folder.
      const folderUri = await vscode.window.showOpenDialog({
        canSelectFolders: true,
        canSelectFiles: false,
        canSelectMany: false,
        openLabel: "Select Folder for New Project",
      });
      // User canceled.
      if (!folderUri) {
        outputChannel.appendLine("User canceled.");
        return;
      }
      const strTargetFolder = folderUri[0].fsPath;

      // 2. Ask for the project name
      const strProjectName = await vscode.window.showInputBox({
        prompt: "Enter the name for the new project",
        validateInput: (input) => {
          const regexInvalidChars = /[<>:"/\\|?*]/;
          if (regexInvalidChars.test(input)) {
            return `Project name can't contain these characters: ${'<>:"/\\|?*'}`;
          }
          if (input.length > 255) {
            return `Project name length can't longer than 255.`;
          }
          if (fs.existsSync(path.join(strTargetFolder, input))) {
            return "A folder with this name already exists.";
          }
          return null;
        },
      });

      // User canceled.
      if (!strProjectName) {
        outputChannel.appendLine("User canceled.");
        return;
      }

      // 3. Get project templates
      const strTemplateFolder = path.join(
        process.env["LiberRPA"] as string,
        "configFiles/ProjectTemplate"
      );
      if (
        !fs.existsSync(strTemplateFolder) ||
        !fs.statSync(strTemplateFolder).isDirectory()
      ) {
        vscode.window.showErrorMessage(
          `Template directory not found: ${strTemplateFolder}`
        );
        return;
      }

      const arrTemplates = fs.readdirSync(strTemplateFolder).filter((item) => {
        const strItemPath = path.join(strTemplateFolder, item);
        return fs.statSync(strItemPath).isDirectory();
      });

      if (arrTemplates.length === 0) {
        vscode.window.showErrorMessage(
          "No templates found in the 'LiberRPA/configFiles/ProjectTemplate'."
        );
        return;
      }

      const strSelectedTemplate = await vscode.window.showQuickPick(arrTemplates, {
        placeHolder: "Select a project template",
      });
      // User canceled.
      if (!strSelectedTemplate) {
        outputChannel.appendLine("User canceled.");
        return;
      }

      // 4. Create the project folder and copy template files
      const strNewProjectPath = path.join(strTargetFolder, strProjectName);
      fs.mkdirSync(strNewProjectPath, { recursive: true });
      const strTemplatePath = path.join(strTemplateFolder, strSelectedTemplate);
      await copyFolder(strTemplatePath, strNewProjectPath);
      // If a .gitignore exists, initialize Git.
      if (fs.existsSync(path.join(strNewProjectPath, "./.gitignore"))) {
        outputChannel.appendLine("Git init.");
        initGit(strNewProjectPath);
      }

      // 5. Open the project folder.
      await vscode.commands.executeCommand(
        "vscode.openFolder",
        vscode.Uri.file(strNewProjectPath),
        { forceNewWindow: true }
      );

      outputChannel.appendLine(`Project "${strProjectName}" created successfully.`);
    } catch (e) {
      vscode.window.showErrorMessage(`Error creating project: ${e}`);
    }
  });

  context.subscriptions.push(disposable);
}

export function deactivate() {
  outputChannel.appendLine('"liberrpa-project-manager" is now deactivated.');
}

async function copyFolder(src: string, dest: string) {
  try {
    const entries = await util.promisify(fs.readdir)(src, { withFileTypes: true });
    await Promise.all(
      entries.map(async (entry) => {
        const srcPath = path.join(src, entry.name);
        const destPath = path.join(dest, entry.name);
        if (entry.isDirectory()) {
          fs.mkdirSync(destPath, { recursive: true });
          await copyFolder(srcPath, destPath);
        } else {
          fs.copyFileSync(srcPath, destPath);
        }
      })
    );
  } catch (e) {
    console.error(`Error copying folder from ${src} to ${dest}:`, e);
    throw new Error(`Failed to copy files: ${e}`);
  }
}

function initGit(cwd: string): void {
  try {
    execSync("git init", { cwd: cwd });
    outputChannel.appendLine("Git repository initialized.");
  } catch (e) {
    const strErrorText = `Error initializing git repository: ${e}, make sure you installed Git in the computer.`;
    outputChannel.appendLine(strErrorText);
    vscode.window.showErrorMessage(strErrorText);
  }
}
