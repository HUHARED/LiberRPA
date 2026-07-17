// FileName: extension.ts
import * as vscode from "vscode";
import * as path from "path";
import * as fs from "fs";
import type { DictProjectForWebview, WebviewToExtensionMessage } from "./interface";
import {
  outputChannel,
  isWebviewMessage,
  resolveWorkspacePythonFile,
  validatePythonImportSafety,
  validateProjectBlockPythonFiles,
} from "./utils";
import { parseFlowProjectFromText } from "./checkFlowchart";

export function activate(context: vscode.ExtensionContext): void {
  outputChannel.appendLine('"liberrpa-flowchart" is now active.');

  context.subscriptions.push(FlowchartEditorProvider.register(context));
}

export function deactivate(): void {
  outputChannel.appendLine('"liberrpa-flowchart" is now deactivated.');
}

class FlowchartEditorProvider implements vscode.CustomTextEditorProvider {
  constructor(private readonly context: vscode.ExtensionContext) {}

  // Register the custom editor for `.flow` files
  public static register(context: vscode.ExtensionContext): vscode.Disposable {
    const providerRegistration = vscode.window.registerCustomEditorProvider(
      "liberrpa-flowchart.editor",
      new FlowchartEditorProvider(context),
      {
        webviewOptions: {
          retainContextWhenHidden: true,
        },
      }
    );
    return providerRegistration;
  }

  // Called when the custom editor is opened.
  public resolveCustomTextEditor(
    document: vscode.TextDocument,
    webviewPanel: vscode.WebviewPanel,
    _token: vscode.CancellationToken
  ): void {
    // Control the local resources that Webview can load.
    const webviewDistUri = vscode.Uri.joinPath(
      this.context.extensionUri,
      "webview-ui",
      "dist"
    );
    webviewPanel.webview.options = {
      enableScripts: true,
      localResourceRoots: [webviewDistUri],
    };

    webviewPanel.webview.html = this.getWebviewContent(webviewPanel.webview);

    let strExpectedWebviewDocumentText: string | undefined;
    let promiseMessageQueue = Promise.resolve();

    const reportError = (e: unknown): void => {
      const messageText = e instanceof Error ? e.message : String(e);
      outputChannel.appendLine(messageText);
      void vscode.window.showErrorMessage(messageText);
    };

    // Keep messages and document reloads ordered. Catch each task so one failure does not
    // leave the queue rejected and prevent later user actions from being processed.
    const enqueueTask = (task: () => Promise<void>): void => {
      promiseMessageQueue = promiseMessageQueue.then(task).catch(reportError);
    };

    // Receive message from webview.
    const messageSubscription = webviewPanel.webview.onDidReceiveMessage(
      (message: unknown) => {
        if (!isWebviewMessage(message)) {
          outputChannel.appendLine(`Ignored invalid webview message.`);
          return;
        }

        enqueueTask(async () => {
          const boolIsUpdate = message.command === "update";
          if (boolIsUpdate) {
            strExpectedWebviewDocumentText = message.data;
          }

          try {
            await this.handleWebviewMessage(document, webviewPanel.webview, message);
          } catch (e) {
            // If an update was rejected, restore the GUI from the actual document instead of leaving it showing data that was never applied.
            if (boolIsUpdate) {
              strExpectedWebviewDocumentText = undefined;
              await this.loadWebviewData(document, webviewPanel.webview);
            }
            throw e;
          }
        });
      }
    );

    // Undo/redo and edits made outside this webview must also be reflected in the GUI.
    // applyEdit() fires the same event, so ignore only the event caused by our own update.
    const changeDocumentsSubscription = vscode.workspace.onDidChangeTextDocument(
      (event) => {
        if (event.document.uri.toString() !== document.uri.toString()) {
          return;
        }

        if (
          strExpectedWebviewDocumentText !== undefined &&
          event.document.getText() === strExpectedWebviewDocumentText
        ) {
          strExpectedWebviewDocumentText = undefined;
          return;
        }

        strExpectedWebviewDocumentText = undefined;
        enqueueTask(() => this.loadWebviewData(document, webviewPanel.webview));
      }
    );

    webviewPanel.onDidDispose(() => {
      messageSubscription.dispose();
      changeDocumentsSubscription.dispose();
    });
  }

  // Get the static html used for the editor webviews.
  private getWebviewContent(webview: vscode.Webview): string {
    const uriHtml = vscode.Uri.joinPath(
      this.context.extensionUri,
      "webview-ui",
      "dist",
      "index.html"
    );

    let html = fs.readFileSync(uriHtml.fsPath, "utf-8");

    const uriAssets = vscode.Uri.joinPath(
      this.context.extensionUri,
      "webview-ui",
      "dist",
      "assets"
    );

    const uriAssetsWebview = webview.asWebviewUri(uriAssets).toString();

    html = html.replaceAll('"/assets/', `"${uriAssetsWebview}/`);
    html = html.replaceAll("'/assets/", `'${uriAssetsWebview}/`);

    html = html.replaceAll('"./assets/', `"${uriAssetsWebview}/`);
    html = html.replaceAll("'./assets/", `'${uriAssetsWebview}/`);

    html = html.replace(/\scrossorigin\b/g, "");

    html = html.replaceAll("{{WEBVIEW_CSP_SOURCE}}", webview.cspSource);

    return html;
  }

  // Send the file content to webview.
  private async loadWebviewData(
    document: vscode.TextDocument,
    webview: vscode.Webview
  ): Promise<void> {
    const dictProject = parseFlowProjectFromText(document.getText());

    // Init color theme of flowchart. "Light" for Light and HighContrast.
    const strTheme: DictProjectForWebview["theme"] =
      vscode.ColorThemeKind[vscode.window.activeColorTheme.kind] === "Dark"
        ? "dark"
        : "light";

    const dictData: DictProjectForWebview = {
      ...dictProject,
      theme: strTheme,
    };
    await webview.postMessage({ command: "load", data: dictData });
  }

  // Write out the json to a given document.
  private async updateDocument(document: vscode.TextDocument, data: string): Promise<void> {
    parseFlowProjectFromText(data);

    const edit = new vscode.WorkspaceEdit();
    // Replace the entire document every time.
    edit.replace(document.uri, new vscode.Range(0, 0, document.lineCount, 0), data);
    // update it in editor but not automatically saved to disk.
    const boolApplied = await vscode.workspace.applyEdit(edit);
    if (!boolApplied) {
      throw new Error("Failed to update .flow document.");
    }
  }

  private async handleWebviewMessage(
    document: vscode.TextDocument,
    webview: vscode.Webview,

    message: WebviewToExtensionMessage
  ): Promise<void> {
    // Find the related workspace.
    const workspaceFolder = vscode.workspace.getWorkspaceFolder(document.uri);

    switch (message.command) {
      case "ready": {
        outputChannel.appendLine("Webview is ready. Loading flow data.");
        await this.loadWebviewData(document, webview);
        break;
      }

      case "update": {
        await this.updateDocument(document, message.data);
        break;
      }

      case "open": {
        outputChannel.appendLine(`Open ${message.path}`);

        if (!workspaceFolder) {
          throw new Error("No workspace folder is open.");
        }

        const uriPythonFile = resolveWorkspacePythonFile(workspaceFolder, message.path);
        validatePythonImportSafety(message.path);
        const strFileSystemPath = uriPythonFile.fsPath;

        // If the path doesn't exist, create it and write the default script.
        if (!fs.existsSync(strFileSystemPath) || !fs.statSync(strFileSystemPath).isFile()) {
          const strFolderPath = path.dirname(strFileSystemPath);
          if (!fs.existsSync(strFolderPath)) {
            fs.mkdirSync(strFolderPath, { recursive: true });
          }

          // Follow liberrpa-snippets-tree, add modules in _Utils and _Selectors.
          function getPythonModules(folderPath: string): string[] {
            if (!fs.existsSync(folderPath)) {
              return [];
            }

            return fs
              .readdirSync(folderPath)
              .filter((file) => {
                if (!file.endsWith(".py")) {
                  return false;
                }

                if (file === "__init__.py") {
                  return false;
                }

                const moduleName = path.parse(file).name;
                return /^[A-Za-z_][A-Za-z0-9_]*$/.test(moduleName);
              })
              .map((file) => path.parse(file).name)
              .sort();
          }

          const utilsPath = path.join(workspaceFolder.uri.fsPath, "_Utils");
          const selectorsPath = path.join(workspaceFolder.uri.fsPath, "_Selectors");

          const utilsModules = getPythonModules(utilsPath);
          const selectorsModules = getPythonModules(selectorsPath);
          const modulesText = [
            ...utilsModules.map(
              (mod) =>
                `from _Utils.${mod} import *  # noqa: F403 - Import project selector variables.\n`
            ),
            ...selectorsModules.map(
              (mod) =>
                `from _Selectors.${mod} import *  # noqa: F403 - Import project selector variables.\n`
            ),
          ];

          const strNewPython = `# FileName: ${path.basename(strFileSystemPath)}
# <LiberRPA imports: managed>
# This block is managed by LiberRPA. Do not edit it manually.
# </LiberRPA imports: managed>
${modulesText.join("")}

def main() -> None:
  raise NotImplementedError()


if __name__ == "__main__":
  main()
`;

          fs.writeFileSync(strFileSystemPath, strNewPython, { encoding: "utf-8" });
        }

        try {
          const pythonDocument = await vscode.workspace.openTextDocument(uriPythonFile);

          // Open it in a new tab.
          await vscode.window.showTextDocument(pythonDocument, {
            viewColumn: vscode.ViewColumn.Active,
            preview: false,
            preserveFocus: false,
          });
        } catch (e) {
          const strMessageText = e instanceof Error ? e.message : String(e);

          throw new Error(
            `Could not open or create file: ${strFileSystemPath}\n${strMessageText}`,
            { cause: e }
          );
        }

        break;
      }

      case "execute": {
        outputChannel.appendLine(
          `Execute "${message.data.pyFile}" in ${message.data.executeMode} mode.`
        );
        if (!workspaceFolder) {
          throw new Error("No workspace folder is open.");
        }

        const uriPythonFile = resolveWorkspacePythonFile(
          workspaceFolder,
          message.data.pyFile
        );
        validatePythonImportSafety(message.data.pyFile);
        const strFileSystemPath = uriPythonFile.fsPath;

        if (!fs.existsSync(strFileSystemPath) || !fs.statSync(strFileSystemPath).isFile()) {
          throw new Error(
            `File does not exist: ${strFileSystemPath}. Create it manually or click the "open" button in the Block node.`
          );
        }

        // Save files before running.
        const saved = await vscode.workspace.saveAll();

        if (!saved) {
          throw new Error("Could not save all files before running the block.");
        }

        const config: vscode.DebugConfiguration = {
          type: "debugpy",
          request: "launch",
          name: "Python Debugger: block file",
          program: strFileSystemPath,
          console: "integratedTerminal",
          cwd: workspaceFolder.uri.fsPath,
          env: {
            PYTHONPATH: workspaceFolder.uri.fsPath,
          },
        };

        const started = await vscode.debug.startDebugging(workspaceFolder, config, {
          noDebug: message.data.executeMode === "Run",
        });

        if (!started) {
          throw new Error(
            `Failed to start Python ${message.data.executeMode}: ${strFileSystemPath}`
          );
        }

        break;
      }

      case "executeProject": {
        outputChannel.appendLine(
          `Execute the project in ${message.data.executeMode} mode.`
        );
        if (!workspaceFolder) {
          throw new Error("No workspace folder is open.");
        }

        validateProjectBlockPythonFiles(workspaceFolder, document);

        // Save files before running.
        const saved = await vscode.workspace.saveAll();

        if (!saved) {
          throw new Error("Could not save all files before running the project.");
        }

        const strLiberRPAEnvPath = process.env.LiberRPA;

        if (!strLiberRPAEnvPath) {
          throw new Error("Not found 'LiberRPA' in User Environment Variables.");
        }

        const strProgramTemp = path.join(
          strLiberRPAEnvPath,
          "envs/pyenv/Lib/site-packages/liberrpa/FlowControl/Run.py"
        );

        if (!fs.existsSync(strProgramTemp) || !fs.statSync(strProgramTemp).isFile()) {
          throw new Error(
            `The Python module 'liberrpa' was not installed correctly. Run.py was not found: ${strProgramTemp}`
          );
        }

        const config: vscode.DebugConfiguration = {
          type: "debugpy",
          request: "launch",
          name: "Python Debugger: project",
          program: strProgramTemp,
          console: "integratedTerminal",
          cwd: workspaceFolder.uri.fsPath,
          env: {
            PYTHONPATH: workspaceFolder.uri.fsPath,
          },
        };

        const started = await vscode.debug.startDebugging(workspaceFolder, config, {
          noDebug: message.data.executeMode === "Run",
        });

        if (!started) {
          throw new Error(
            `Failed to start Python ${message.data.executeMode}: ${strProgramTemp}`
          );
        }

        break;
      }

      default:
        break;
    }
  }
}
