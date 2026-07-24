// FileName: projectManagerPanel.ts
import * as vscode from "vscode";
import * as fs from "node:fs";

import { log } from "./output";
import { getProjectTemplates, selectTargetFolder, createProject } from "./createFolder";
import { getErrorMessage } from "./utils";
import type {
  Theme,
  DictCreateProjectInput,
  DictMessage_ExtensionToWebview,
  ProjectManagerOperation,
} from "./webviewMessages";
import { isMessage_WebviewToExtension } from "./webviewMessages";

function getTheme(theme: vscode.ColorTheme): Theme {
  return theme.kind === vscode.ColorThemeKind.Dark ||
    theme.kind === vscode.ColorThemeKind.HighContrast
    ? "dark"
    : "light";
}

export class ProjectManagerPanel {
  private static currentPanel: ProjectManagerPanel | undefined;

  private readonly panel: vscode.WebviewPanel;
  private readonly disposables: vscode.Disposable[] = [];
  private currentOperation: ProjectManagerOperation;
  private webviewReady = false;
  private busy = false;

  private getWebviewContent(webview: vscode.Webview): string {
    const indexHtmlUri = vscode.Uri.joinPath(
      this.context.extensionUri,
      "webview-ui",
      "dist",
      "index.html",
    );

    if (!fs.existsSync(indexHtmlUri.fsPath)) {
      throw new Error(
        "Project Manager Webview has not been built. Run npm run build in webview-ui first.",
      );
    }

    let html = fs.readFileSync(indexHtmlUri.fsPath, { encoding: "utf-8" });

    const assetsUri = vscode.Uri.joinPath(
      this.context.extensionUri,
      "webview-ui",
      "dist",
      "assets",
    );
    const webviewAssetsUri = webview.asWebviewUri(assetsUri).toString();

    html = html.replaceAll('"/assets/', `"${webviewAssetsUri}/`);
    html = html.replaceAll("'/assets/", `'${webviewAssetsUri}/`);
    html = html.replaceAll('"./assets/', `"${webviewAssetsUri}/`);
    html = html.replaceAll("'./assets/", `'${webviewAssetsUri}/`);
    html = html.replace(/\scrossorigin\b/g, "");
    html = html.replaceAll("{{WEBVIEW_CSP_SOURCE}}", webview.cspSource);

    return html;
  }

  private async postMessage(message: DictMessage_ExtensionToWebview): Promise<void> {
    const boolPosted = await this.panel.webview.postMessage(message);

    if (!boolPosted) {
      throw new Error("Project Manager Webview is not available.");
    }
  }

  private async loadCurrentOperation(): Promise<void> {
    if (!this.webviewReady) {
      return;
    }

    try {
      switch (this.currentOperation) {
        case "createProject": {
          await this.postMessage({
            command: "loadCreateProject",
            initialData: {
              templates: getProjectTemplates(),
              theme: getTheme(vscode.window.activeColorTheme),
            },
          });
          break;
        }
      }
    } catch (e: unknown) {
      log.error(`Failed to load Project Manager operation: ${getErrorMessage(e)}`);
      await this.sendError(e);
    }
  }

  private async handleCreateProject(input: DictCreateProjectInput): Promise<void> {
    if (this.busy) {
      return;
    }

    this.busy = true;

    try {
      await this.postMessage({ command: "setBusy", busy: true });

      const dictResult = await createProject(input);

      log.info(`Project created successfully: ${dictResult.projectPath}`);

      if (dictResult.warnings.length > 0) {
        void vscode.window.showWarningMessage(dictResult.warnings.join("\n"));
      }

      try {
        await vscode.commands.executeCommand(
          "vscode.openFolder",
          vscode.Uri.file(dictResult.projectPath),
          {
            forceNewWindow: true,
          },
        );
      } catch (e: unknown) {
        const strErrorMessage = getErrorMessage(e);
        log.error(`Project was created, but failed to open it: ${strErrorMessage}`);
        void vscode.window.showErrorMessage(
          `The Project was created successfully, but VS Code failed to open it: ${strErrorMessage}`,
        );
      }

      // Project creation has completed even if opening it failed. Close the tab.
      this.panel.dispose();
    } catch (e: unknown) {
      try {
        await this.postMessage({
          command: "setBusy",
          busy: false,
        });
      } catch (postError: unknown) {
        log.error(
          `Failed to restore Project Manager Webview busy state: ${getErrorMessage(postError)}`,
        );
      }

      throw e;
    } finally {
      this.busy = false;
    }
  }

  private async handleMessage(message: unknown): Promise<void> {
    try {
      if (!isMessage_WebviewToExtension(message)) {
        log.warn("Ignored invalid Project Manager Webview message.");
        return;
      }

      if (this.busy && message.command !== "ready") {
        log.debug(`Ignored Project Manager Webview message while busy: ${message.command}`);
        return;
      }

      switch (message.command) {
        case "ready": {
          if (this.webviewReady) {
            log.debug("Ignored repeated Project Manager Webview ready message.");
            return;
          }

          this.webviewReady = true;
          await this.loadCurrentOperation();
          break;
        }
        case "selectTargetFolder": {
          const strTargetFolder = await selectTargetFolder();
          if (strTargetFolder !== undefined) {
            await this.postMessage({
              command: "targetFolderSelected",
              path: strTargetFolder,
            });
          }
          break;
        }

        case "confirmCreateProject": {
          await this.handleCreateProject(message.input);
          break;
        }

        case "cancel": {
          this.panel.dispose();
          break;
        }
      }
    } catch (e) {
      const strErrorMessage = getErrorMessage(e);
      log.error(`Failed to handle Webview message: ${strErrorMessage}`);
      await this.sendError(e);
    }
  }

  private constructor(
    private readonly context: vscode.ExtensionContext,
    operation: ProjectManagerOperation,
  ) {
    this.currentOperation = operation;

    const webviewDistUri = vscode.Uri.joinPath(context.extensionUri, "webview-ui", "dist");

    this.panel = vscode.window.createWebviewPanel(
      "liberrpa-project-manager",
      "Project Manager - LiberRPA",
      vscode.ViewColumn.Active,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [webviewDistUri],
      },
    );

    try {
      this.panel.webview.html = this.getWebviewContent(this.panel.webview);
    } catch (e: unknown) {
      this.panel.dispose();
      throw e;
    }

    this.panel.onDidDispose(
      () => {
        this.disposeResources();
      },
      undefined,
      this.disposables,
    );

    this.panel.webview.onDidReceiveMessage(
      (message: unknown) => {
        void this.handleMessage(message);
      },
      undefined,
      this.disposables,
    );

    vscode.window.onDidChangeActiveColorTheme(
      (theme) => {
        if (this.webviewReady) {
          void this.postMessage({
            command: "themeChanged",
            theme: getTheme(theme),
          }).catch((e: unknown) => {
            log.warn(`Failed to update Project Manager theme: ${getErrorMessage(e)}`);
          });
        }
      },
      undefined,
      this.disposables,
    );
  }

  public static show(
    context: vscode.ExtensionContext,
    operation: ProjectManagerOperation,
  ): void {
    try {
      const currentPanel = ProjectManagerPanel.currentPanel;

      if (currentPanel !== undefined) {
        currentPanel.panel.reveal(vscode.ViewColumn.Active);

        if (currentPanel.currentOperation === operation) {
          return;
        }

        if (currentPanel.busy) {
          void vscode.window.showInformationMessage(
            "Project Manager cannot switch operations while the current operation is running.",
          );
          return;
        }

        currentPanel.currentOperation = operation;
        void currentPanel.loadCurrentOperation();
        return;
      }

      ProjectManagerPanel.currentPanel = new ProjectManagerPanel(context, operation);
    } catch (e: unknown) {
      const strErrorMessage = `Failed to open Project Manager: ${getErrorMessage(e)}`;
      log.error(strErrorMessage);
      void vscode.window.showErrorMessage(strErrorMessage);
    }
  }

  private async sendError(error: unknown): Promise<void> {
    const strErrorMessage = getErrorMessage(error);
    try {
      await this.postMessage({
        command: "error",
        message: strErrorMessage,
      });
    } catch (e: unknown) {
      log.error(`Failed to send error to Project Manager Webview: ${getErrorMessage(e)}`);
    }
  }

  private disposeResources(): void {
    if (ProjectManagerPanel.currentPanel === this) {
      ProjectManagerPanel.currentPanel = undefined;
    }

    while (this.disposables.length > 0) {
      this.disposables.pop()?.dispose();
    }
  }
}
