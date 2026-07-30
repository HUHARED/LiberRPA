// FileName: projectManagerPanel.ts
import * as vscode from "vscode";
import * as fs from "node:fs";

import { log } from "./output";
import type {
  Theme,
  ProjectManagerOperation,
  DictCreateProjectInput,
  DictManageComponentsInitialData,
  DictMessage_ExtensionToWebview,
} from "./webviewMessages";
import { isMessage_WebviewToExtension } from "./webviewMessages";
import type {
  DictComponentManagementWarning,
  DictProtocolDependencyOperation,
} from "./componentManagement/protocol";
import {
  ComponentManagementOperationError,
  getComponentRepositoryCatalog,
  getProjectDependencyState,
  buildProjectDependencyPlan,
  applyProjectDependencyPlan,
  repairProjectComponents,
} from "./componentManagement/operations";
import { getProjectTemplates, selectTargetFolder, createProject } from "./createFolder";
import { importComponentWheels } from "./importComponentWheels";
import { getErrorMessage } from "./utils";

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
  private operationLoadId = 0;

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

    const intLoadId = ++this.operationLoadId;

    switch (this.currentOperation) {
      case "createProject": {
        const initialData = {
          templates: getProjectTemplates(),
          theme: getTheme(vscode.window.activeColorTheme),
        };
        if (
          intLoadId !== this.operationLoadId ||
          this.currentOperation !== "createProject"
        ) {
          return;
        }

        await this.postMessage({
          command: "loadCreateProject",
          initialData,
        });
        break;
      }

      case "manageComponents": {
        const initialData = await this.getManageComponentsInitialData();
        if (
          intLoadId !== this.operationLoadId ||
          this.currentOperation !== "manageComponents"
        ) {
          return;
        }

        await this.postMessage({
          command: "loadManageComponents",
          initialData,
        });
        break;
      }
    }
  }

  private async switchOperation(operation: ProjectManagerOperation): Promise<void> {
    const previousOperation = this.currentOperation;
    this.currentOperation = operation;
    this.busy = true;

    try {
      await this.postMessage({ command: "setBusy", busy: true });
      await this.loadCurrentOperation();
    } catch (e: unknown) {
      this.currentOperation = previousOperation;
      throw e;
    } finally {
      this.busy = false;
      try {
        await this.postMessage({ command: "setBusy", busy: false });
      } catch (e: unknown) {
        log.warn(`Failed to restore Project Manager busy state: ${getErrorMessage(e)}`);
      }
    }
  }

  private getSingleWorkspaceFolder(): vscode.WorkspaceFolder {
    const arrWorkspaceFolder = vscode.workspace.workspaceFolders;
    if (arrWorkspaceFolder === undefined || arrWorkspaceFolder.length !== 1) {
      throw new Error("Manage Components requires exactly one open workspace folder.");
    }

    return arrWorkspaceFolder[0];
  }

  private getWarningMessages(warnings: DictComponentManagementWarning[]): string[] {
    return warnings.map((warning) => warning.message);
  }

  private async getManageComponentsInitialData(notification?: {
    type: "info" | "warning";
    message: string;
  }): Promise<DictManageComponentsInitialData> {
    const workspaceFolder = this.getSingleWorkspaceFolder();
    const projectStateResult = await getProjectDependencyState(workspaceFolder.uri.fsPath);
    const repositoryCatalogResult = await getComponentRepositoryCatalog();
    const arrWarning = [
      ...projectStateResult.warnings,
      ...repositoryCatalogResult.warnings,
    ];

    for (const warning of arrWarning) {
      log.warn(warning.message);
    }

    return {
      theme: getTheme(vscode.window.activeColorTheme),
      projectState: projectStateResult.result,
      repositoryCatalog: repositoryCatalogResult.result,
      warningMessages: this.getWarningMessages(arrWarning),
      ...(notification === undefined ? {} : { notification }),
    };
  }

  private async saveAllProjectFiles(): Promise<void> {
    const boolSaved = await vscode.workspace.saveAll();
    if (!boolSaved) {
      throw new Error("Could not save all files before managing Components.");
    }
  }

  private async runBusyOperation(action: () => Promise<void>): Promise<void> {
    if (this.busy) {
      return;
    }

    this.busy = true;
    try {
      await this.postMessage({ command: "setBusy", busy: true });
      await action();
    } finally {
      this.busy = false;
      try {
        await this.postMessage({ command: "setBusy", busy: false });
      } catch (e: unknown) {
        log.warn(`Failed to restore Project Manager busy state: ${getErrorMessage(e)}`);
      }
    }
  }

  private async handleBuildProjectDependencyPlan(
    dependencyOperation: DictProtocolDependencyOperation,
  ): Promise<void> {
    await this.runBusyOperation(async () => {
      await this.saveAllProjectFiles();
      const workspaceFolder = this.getSingleWorkspaceFolder();
      const planResult = await buildProjectDependencyPlan(
        workspaceFolder.uri.fsPath,
        dependencyOperation,
      );

      for (const warning of planResult.warnings) {
        log.warn(warning.message);
      }

      await this.postMessage({
        command: "projectDependencyPlanBuilt",
        dependencyOperation,
        plan: planResult.result,
        warningMessages: this.getWarningMessages(planResult.warnings),
      });
    });
  }

  private async handleApplyProjectDependencyPlan(
    dependencyOperation: DictProtocolDependencyOperation,
    confirmedPlanSha256: string,
  ): Promise<void> {
    await this.runBusyOperation(async () => {
      await this.saveAllProjectFiles();
      const workspaceFolder = this.getSingleWorkspaceFolder();
      const applyResult = await applyProjectDependencyPlan(
        workspaceFolder.uri.fsPath,
        dependencyOperation,
        confirmedPlanSha256,
      );

      for (const warning of applyResult.warnings) {
        log.warn(warning.message);
      }

      const initialData = await this.getManageComponentsInitialData({
        type: applyResult.warnings.length === 0 ? "info" : "warning",
        message:
          applyResult.warnings.length === 0
            ? "Component dependency changes were applied successfully."
            : "Component dependency changes were applied with warnings. See the warnings shown below.",
      });
      initialData.warningMessages.unshift(...this.getWarningMessages(applyResult.warnings));

      await this.postMessage({ command: "loadManageComponents", initialData });
    });
  }

  private async handleRepairProjectComponents(): Promise<void> {
    await this.runBusyOperation(async () => {
      await this.saveAllProjectFiles();
      const workspaceFolder = this.getSingleWorkspaceFolder();
      const repairResult = await repairProjectComponents(workspaceFolder.uri.fsPath);

      for (const warning of repairResult.warnings) {
        log.warn(warning.message);
      }

      const initialData = await this.getManageComponentsInitialData({
        type: repairResult.warnings.length === 0 ? "info" : "warning",
        message:
          repairResult.warnings.length === 0
            ? "Project Components were repaired successfully."
            : "Project Components were repaired with warnings. See the warnings shown below.",
      });
      initialData.warningMessages.unshift(
        ...this.getWarningMessages(repairResult.warnings),
      );

      await this.postMessage({ command: "loadManageComponents", initialData });
    });
  }

  private async handleImportComponentWheels(): Promise<void> {
    await this.runBusyOperation(async () => {
      const boolImported = await importComponentWheels();
      if (!boolImported) {
        return;
      }

      const initialData = await this.getManageComponentsInitialData({
        type: "info",
        message:
          "Component Wheels were imported into ComponentRepository. Select a Component below to add it to the Project.",
      });
      await this.postMessage({ command: "loadManageComponents", initialData });
    });
  }

  private async handleRefreshManageComponents(): Promise<void> {
    await this.runBusyOperation(async () => {
      const initialData = await this.getManageComponentsInitialData();
      await this.postMessage({ command: "loadManageComponents", initialData });
    });
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
          if (this.currentOperation !== "createProject") {
            log.warn("Ignored selectTargetFolder outside Create Project.");
            return;
          }

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
          if (this.currentOperation !== "createProject") {
            log.warn("Ignored confirmCreateProject outside Create Project.");
            return;
          }

          await this.handleCreateProject(message.input);
          break;
        }

        case "buildProjectDependencyPlan": {
          if (this.currentOperation !== "manageComponents") {
            log.warn("Ignored buildProjectDependencyPlan outside Manage Components.");
            return;
          }

          await this.handleBuildProjectDependencyPlan(message.dependencyOperation);
          break;
        }

        case "applyProjectDependencyPlan": {
          if (this.currentOperation !== "manageComponents") {
            log.warn("Ignored applyProjectDependencyPlan outside Manage Components.");
            return;
          }

          await this.handleApplyProjectDependencyPlan(
            message.dependencyOperation,
            message.confirmedPlanSha256,
          );
          break;
        }

        case "repairProjectComponents": {
          if (this.currentOperation !== "manageComponents") {
            log.warn("Ignored repairProjectComponents outside Manage Components.");
            return;
          }

          await this.handleRepairProjectComponents();
          break;
        }

        case "importComponentWheels": {
          if (this.currentOperation !== "manageComponents") {
            log.warn("Ignored importComponentWheels outside Manage Components.");
            return;
          }

          await this.handleImportComponentWheels();
          break;
        }

        case "refreshManageComponents": {
          if (this.currentOperation !== "manageComponents") {
            log.warn("Ignored refreshManageComponents outside Manage Components.");
            return;
          }

          await this.handleRefreshManageComponents();
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
      (theme: vscode.ColorTheme) => {
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

        void currentPanel.switchOperation(operation).catch(async (e: unknown) => {
          const strErrorMessage = getErrorMessage(e);
          log.error(`Failed to switch Project Manager operation: ${strErrorMessage}`);
          await currentPanel.sendError(e);
        });
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
    try {
      if (error instanceof ComponentManagementOperationError) {
        await this.postMessage({
          command: "componentManagementError",
          code: error.code,
          message: error.message,
        });
        return;
      }

      const strErrorMessage = getErrorMessage(error);
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
