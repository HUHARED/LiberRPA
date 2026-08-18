// FileName: extension.ts
import * as vscode from "vscode";
import * as path from "path";
import * as fs from "fs";
import type {
  DictProjectForWebview,
  ExtensionToWebviewMessage,
  Theme,
  WebviewToExtensionMessage,
} from "./interface";
import { log } from "./output";
import {
  isWebviewMessage,
  resolveWorkspacePythonFile,
  validatePythonImportSafety,
  validateProjectBlockPythonFiles,
} from "./utils";
import { parseFlowProjectFromText } from "./checkFlowchart";

function getFlowchartTheme(theme: vscode.ColorTheme): Theme {
  return theme.kind === vscode.ColorThemeKind.Dark ||
    theme.kind === vscode.ColorThemeKind.HighContrast
    ? "dark"
    : "light";
}

function getProjectPythonPath(workspaceFolder: vscode.WorkspaceFolder): string {
  const arrPythonPath = [
    workspaceFolder.uri.fsPath,
    path.join(workspaceFolder.uri.fsPath, "_Components"),
  ];

  if (process.env.PYTHONPATH) {
    arrPythonPath.push(process.env.PYTHONPATH);
  }

  return arrPythonPath.join(path.delimiter);
}

export function activate(context: vscode.ExtensionContext): void {
  // Let vscode manage log's lifecycle.
  context.subscriptions.push(log);

  log.info('"liberrpa-flowchart" is now active.');

  context.subscriptions.push(FlowchartEditorProvider.register(context));
}

export function deactivate(): void {
  log.info('"liberrpa-flowchart" is now deactivated.');
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
      },
    );
    return providerRegistration;
  }

  // Called when the custom editor is opened.
  public resolveCustomTextEditor(
    document: vscode.TextDocument,
    webviewPanel: vscode.WebviewPanel,
    _token: vscode.CancellationToken,
  ): void {
    // Control the local resources that Webview can load.
    const webviewDistUri = vscode.Uri.joinPath(
      this.context.extensionUri,
      "webview-ui",
      "dist",
    );
    webviewPanel.webview.options = {
      enableScripts: true,
      localResourceRoots: [webviewDistUri],
    };

    webviewPanel.webview.html = this.getWebviewContent(webviewPanel.webview);

    let boolWebviewReady = false;
    let strExpectedWebviewDocumentText: string | undefined;
    let promiseMessageQueue = Promise.resolve();

    const reportError = (e: unknown): void => {
      const messageText = e instanceof Error ? e.message : String(e);
      log.error(messageText);
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
          log.warn(`Ignored invalid webview message.`);
          return;
        }

        enqueueTask(async () => {
          const boolIsReady = message.command === "ready";
          const boolIsUpdate = message.command === "update";

          if (boolIsReady) {
            // The Webview can receive messages as soon as it sends "ready". Mark it ready before loading so theme changes can be queued behind the initial load.
            boolWebviewReady = true;
          }
          if (boolIsUpdate) {
            strExpectedWebviewDocumentText = message.data;
          }

          try {
            await this.handleWebviewMessage(document, webviewPanel.webview, message);
          } catch (e) {
            if (boolIsReady) {
              boolWebviewReady = false;
            }

            // If an update was rejected, restore the GUI from the actual document instead of leaving it showing data that was never applied.
            if (boolIsUpdate) {
              strExpectedWebviewDocumentText = undefined;
              await this.loadWebviewData(document, webviewPanel.webview);
            }
            throw e;
          }
        });
      },
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
      },
    );

    const changeColorThemeSubscription = vscode.window.onDidChangeActiveColorTheme(
      (theme) => {
        if (!boolWebviewReady) {
          return;
        }

        enqueueTask(async () => {
          if (boolWebviewReady) {
            await this.postThemeChanged(webviewPanel.webview, theme);
          }
        });
      },
    );

    webviewPanel.onDidDispose(() => {
      boolWebviewReady = false;
      messageSubscription.dispose();
      changeDocumentsSubscription.dispose();
      changeColorThemeSubscription.dispose();
    });
  }

  // Get the static html used for the editor webviews.
  private getWebviewContent(webview: vscode.Webview): string {
    const uriHtml = vscode.Uri.joinPath(
      this.context.extensionUri,
      "webview-ui",
      "dist",
      "index.html",
    );

    let html = fs.readFileSync(uriHtml.fsPath, "utf-8");

    const uriAssets = vscode.Uri.joinPath(
      this.context.extensionUri,
      "webview-ui",
      "dist",
      "assets",
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
    webview: vscode.Webview,
  ): Promise<void> {
    const dictProject = parseFlowProjectFromText(document.getText());

    const dictData: DictProjectForWebview = {
      ...dictProject,
      theme: getFlowchartTheme(vscode.window.activeColorTheme),
    };
    const message: ExtensionToWebviewMessage = {
      command: "load",
      data: dictData,
    };

    await webview.postMessage(message);
  }

  private async postThemeChanged(
    webview: vscode.Webview,
    theme: vscode.ColorTheme,
  ): Promise<void> {
    const message: ExtensionToWebviewMessage = {
      command: "themeChanged",
      theme: getFlowchartTheme(theme),
    };

    try {
      const boolPosted = await webview.postMessage(message);
      if (!boolPosted) {
        log.warn("Flowchart Webview is not available for theme update.");
      }
    } catch (e) {
      const strMessage = e instanceof Error ? e.message : String(e);
      log.warn(`Failed to update Flowchart theme: ${strMessage}`);
    }
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

    message: WebviewToExtensionMessage,
  ): Promise<void> {
    // Find the related workspace.
    const workspaceFolder = vscode.workspace.getWorkspaceFolder(document.uri);

    switch (message.command) {
      case "ready": {
        log.debug("Webview is ready. Loading flow data.");
        await this.loadWebviewData(document, webview);
        break;
      }

      case "update": {
        await this.updateDocument(document, message.data);
        break;
      }

      case "open": {
        log.debug(`Open ${message.path}`);

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

          const strNewPython = `# FileName: ${path.basename(strFileSystemPath)}
# <LiberRPA imports: managed>
# This block is managed by LiberRPA. Do not edit it manually.
# ruff: isort: off
# ruff: isort: on
# </LiberRPA imports: managed>

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
            { cause: e },
          );
        }

        break;
      }

      case "execute": {
        log.debug(`Execute "${message.data.pyFile}" in ${message.data.executeMode} mode.`);
        if (!workspaceFolder) {
          throw new Error("No workspace folder is open.");
        }

        const uriPythonFile = resolveWorkspacePythonFile(
          workspaceFolder,
          message.data.pyFile,
        );
        validatePythonImportSafety(message.data.pyFile);
        const strFileSystemPath = uriPythonFile.fsPath;

        if (!fs.existsSync(strFileSystemPath) || !fs.statSync(strFileSystemPath).isFile()) {
          throw new Error(
            `File does not exist: ${strFileSystemPath}. Create it manually or click the "open" button in the Block node.`,
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
            PYTHONPATH: getProjectPythonPath(workspaceFolder),
          },
        };

        const started = await vscode.debug.startDebugging(workspaceFolder, config, {
          noDebug: message.data.executeMode === "Run",
        });

        if (!started) {
          throw new Error(
            `Failed to start Python ${message.data.executeMode}: ${strFileSystemPath}`,
          );
        }

        break;
      }

      case "executeProject": {
        log.debug(`Execute the project in ${message.data.executeMode} mode.`);
        if (!workspaceFolder) {
          throw new Error("No workspace folder is open.");
        }

        validateProjectBlockPythonFiles(workspaceFolder, document);

        // Save files before running.
        const boolSaved = await vscode.workspace.saveAll();

        if (!boolSaved) {
          throw new Error("Could not save all files before running the project.");
        }

        const config: vscode.DebugConfiguration = {
          type: "debugpy",
          request: "launch",
          name:
            message.data.executeMode === "Debug"
              ? "LiberRPA: Debug Flow Project"
              : "LiberRPA: Run Flow Project",
          module: "liberrpa.FlowControl.Run",
          console: "integratedTerminal",
          cwd: workspaceFolder.uri.fsPath,
          env: {
            PYTHONPATH: getProjectPythonPath(workspaceFolder),
          },
        };

        const boolStarted = await vscode.debug.startDebugging(workspaceFolder, config, {
          noDebug: message.data.executeMode === "Run",
        });

        if (!boolStarted) {
          throw new Error(
            `Failed to start the Flow Project in ${message.data.executeMode} mode.`,
          );
        }

        break;
      }

      default:
        break;
    }
  }
}
