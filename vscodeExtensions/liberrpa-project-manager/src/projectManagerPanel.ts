// FileName: projectManagerPanel.ts

import * as vscode from "vscode";
import * as fs from "node:fs";

import { createProject, getProjectTemplates, selectTargetFolder } from "./createFolder";
import { log } from "./output";
import { getErrorMessage } from "./utils";
import {
  isWebviewToExtensionMessage,
  type CreateProjectInput,
  type ExtensionToWebviewMessage,
  type ProjectManagerOperation,
  type ProjectManagerTheme,
} from "./webviewMessages";

export class ProjectManagerPanel {
  private static currentPanel: ProjectManagerPanel | undefined;

  private readonly panel: vscode.WebviewPanel;
  private readonly disposables: vscode.Disposable[] = [];
  private currentOperation: ProjectManagerOperation;
  private webviewReady = false;
  private busy = false;

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
            theme: getProjectManagerTheme(theme),
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
      if (ProjectManagerPanel.currentPanel !== undefined) {
        ProjectManagerPanel.currentPanel.currentOperation = operation;
        ProjectManagerPanel.currentPanel.panel.reveal(vscode.ViewColumn.Active);
        void ProjectManagerPanel.currentPanel.loadCurrentOperation();
        return;
      }

      ProjectManagerPanel.currentPanel = new ProjectManagerPanel(context, operation);
    } catch (e: unknown) {
      const message = `Failed to open Project Manager: ${getErrorMessage(e)}`;
      log.error(message);
      void vscode.window.showErrorMessage(message);
    }
  }

  private async handleMessage(message: unknown): Promise<void> {
    if (!isWebviewToExtensionMessage(message)) {
      log.warn("Ignored invalid Project Manager Webview message.");
      return;
    }

    switch (message.command) {
      case "ready":
        this.webviewReady = true;
        await this.loadCurrentOperation();
        break;

      case "selectTargetFolder": {
        const targetFolder = await selectTargetFolder();
        if (targetFolder !== undefined) {
          await this.postMessage({
            command: "targetFolderSelected",
            path: targetFolder,
          });
        }
        break;
      }

      case "confirmCreateProject":
        await this.handleCreateProject(message.input);
        break;

      case "cancel":
        this.panel.dispose();
        break;
    }
  }

  private async loadCurrentOperation(): Promise<void> {
    if (!this.webviewReady) {
      return;
    }

    try {
      switch (this.currentOperation) {
        case "createProject":
          await this.postMessage({
            command: "load",
            operation: "createProject",
            context: {
              templates: getProjectTemplates(),
              theme: getProjectManagerTheme(vscode.window.activeColorTheme),
            },
          });
          break;
      }
    } catch (e: unknown) {
      await this.sendError(e);
    }
  }

  private async handleCreateProject(input: CreateProjectInput): Promise<void> {
    if (this.busy) {
      return;
    }

    this.busy = true;
    await this.postMessage({ command: "setBusy", busy: true });

    try {
      const result = await createProject(input);
      const warnings = [...result.warnings];

      try {
        await vscode.commands.executeCommand(
          "vscode.openFolder",
          vscode.Uri.file(result.projectPath),
          { forceNewWindow: true },
        );
      } catch (e: unknown) {
        const warning = `Project was created, but VS Code could not open it: ${getErrorMessage(e)}`;
        log.warn(warning);
        warnings.push(warning);
      }

      await this.postMessage({ command: "setBusy", busy: false });

      await this.postMessage({
        command: "completed",
        message: `Project "${input.projectFolderName}" was created successfully.`,
        projectPath: result.projectPath,
        warnings,
      });
      this.panel.dispose();
    } catch (e: unknown) {
      await this.postMessage({ command: "setBusy", busy: false });
      await this.sendError(e);
    } finally {
      this.busy = false;
    }
  }

  private async sendError(error: unknown): Promise<void> {
    const message = getErrorMessage(error);
    log.error(message);
    await this.postMessage({ command: "error", message });
  }

  private async postMessage(message: ExtensionToWebviewMessage): Promise<void> {
    await this.panel.webview.postMessage(message);
  }

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

  private disposeResources(): void {
    ProjectManagerPanel.currentPanel = undefined;

    while (this.disposables.length > 0) {
      this.disposables.pop()?.dispose();
    }
  }
}

function getProjectManagerTheme(theme: vscode.ColorTheme): ProjectManagerTheme {
  return theme.kind === vscode.ColorThemeKind.Dark ||
    theme.kind === vscode.ColorThemeKind.HighContrast
    ? "dark"
    : "light";
}
