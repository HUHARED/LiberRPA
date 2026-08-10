// FileName: projectManagerSession.ts

import * as vscode from "vscode";

import { log } from "../Adapter/VsCode/output";
import { getErrorMessage } from "../Common/utils";
import { ComponentManagementOperationError } from "../Adapter/Python/componentManagementClient";
import type {
  Theme,
  ProjectManagerOperation,
  Str_PublishComponentFile,
  DictProjectManagerNotification,
  DictPublishComponentInitialData,
  DictManageComponentsInitialData,
  DictMessage_WebviewToExtension,
  DictMessage_ExtensionToWebview,
} from "../Adapter/Webview/projectManagerMessages";
import type {
  DictProtocolDependencyOperation,
  DictProtocolResult_Publish,
} from "../Domain/ComponentManagement/componentManagementTypes";
import {
  logComponentManagementWarnings,
  getComponentManagementWarningMessages,
} from "./componentManagementOutput";
import {
  loadManageComponentsData,
  createProjectDependencyPlan,
  confirmProjectDependencyPlan,
  repairProjectComponentFolder,
} from "./Dependency/manageComponents";
import {
  getProjectTemplates,
  selectTargetFolder,
  createProject,
} from "./Project/createProject";
import {
  loadPublishComponentData,
  publishComponentProject,
  openPublishComponentFile,
} from "./Publish/publishComponent";
import {
  selectComponentWheelFilePaths,
  importComponentWheelFiles,
} from "./Repository/importComponentWheels";

export interface ProjectManagerSessionHost {
  postMessage(message: DictMessage_ExtensionToWebview): Promise<void>;
  dispose(): void;
}

function getTheme(theme: vscode.ColorTheme): Theme {
  return theme.kind === vscode.ColorThemeKind.Dark ||
    theme.kind === vscode.ColorThemeKind.HighContrast
    ? "dark"
    : "light";
}

export class ProjectManagerSession {
  private webviewReady = false;
  private busy = false;
  private operationLoadId = 0;
  private publishResult: DictProtocolResult_Publish | null = null;

  public constructor(
    private readonly host: ProjectManagerSessionHost,
    private operation: ProjectManagerOperation,
  ) {}

  public get currentOperation(): ProjectManagerOperation {
    return this.operation;
  }

  public get isBusy(): boolean {
    return this.busy;
  }

  private getSingleWorkspaceFolder(): vscode.WorkspaceFolder {
    const arrWorkspaceFolder = vscode.workspace.workspaceFolders;
    if (arrWorkspaceFolder === undefined || arrWorkspaceFolder.length !== 1) {
      throw new Error("Project Manager requires exactly one open workspace folder.");
    }
    return arrWorkspaceFolder[0];
  }

  private async saveAllProjectFiles(): Promise<void> {
    if (!(await vscode.workspace.saveAll())) {
      throw new Error("Could not save all Project files.");
    }
  }

  private async getPublishComponentInitialData(
    notification?: DictProjectManagerNotification,
    warningMessages: string[] = [],
  ): Promise<DictPublishComponentInitialData> {
    const workspaceFolder = this.getSingleWorkspaceFolder();
    const data = await loadPublishComponentData(workspaceFolder, this.publishResult);

    return {
      theme: getTheme(vscode.window.activeColorTheme),
      ...data,
      publishResult: this.publishResult,
      warningMessages,
      ...(notification === undefined ? {} : { notification }),
    };
  }

  private async getManageComponentsInitialData(
    notification?: DictProjectManagerNotification,
    additionalWarningMessages: string[] = [],
  ): Promise<DictManageComponentsInitialData> {
    const workspaceFolder = this.getSingleWorkspaceFolder();
    const data = await loadManageComponentsData(workspaceFolder.uri.fsPath);
    logComponentManagementWarnings(data.warnings);

    return {
      theme: getTheme(vscode.window.activeColorTheme),
      projectState: data.projectState,
      repositoryCatalog: data.repositoryCatalog,
      warningMessages: [
        ...additionalWarningMessages,
        ...getComponentManagementWarningMessages(data.warnings),
      ],
      ...(notification === undefined ? {} : { notification }),
    };
  }

  private async loadCurrentOperation(): Promise<void> {
    if (!this.webviewReady) {
      return;
    }

    const intLoadId = ++this.operationLoadId;
    switch (this.operation) {
      case "createProject": {
        const initialData = {
          templates: getProjectTemplates(),
          theme: getTheme(vscode.window.activeColorTheme),
        };
        if (intLoadId !== this.operationLoadId || this.operation !== "createProject") {
          return;
        }
        await this.host.postMessage({
          command: "loadCreateProject",
          initialData,
        });
        return;
      }

      case "publishComponent": {
        const initialData = await this.getPublishComponentInitialData();
        if (intLoadId !== this.operationLoadId || this.operation !== "publishComponent") {
          return;
        }
        await this.host.postMessage({
          command: "loadPublishComponent",
          initialData,
        });
        return;
      }

      case "manageComponents": {
        const initialData = await this.getManageComponentsInitialData();
        if (intLoadId !== this.operationLoadId || this.operation !== "manageComponents") {
          return;
        }
        await this.host.postMessage({
          command: "loadManageComponents",
          initialData,
        });
      }
    }
  }

  private async runBusyOperation(action: () => Promise<void>): Promise<void> {
    if (this.busy) {
      return;
    }

    this.busy = true;
    try {
      if (this.webviewReady) {
        await this.host.postMessage({ command: "setBusy", busy: true });
      }
      await action();
    } finally {
      this.busy = false;
      try {
        if (this.webviewReady) {
          await this.host.postMessage({ command: "setBusy", busy: false });
        }
      } catch (e: unknown) {
        log.warn(`Failed to restore Project Manager busy state: ${getErrorMessage(e)}`);
      }
    }
  }

  public async switchOperation(operation: ProjectManagerOperation): Promise<void> {
    if (this.busy || operation === this.operation) {
      return;
    }

    const previousOperation = this.operation;
    const previousPublishResult = this.publishResult;
    this.operation = operation;
    if (operation === "publishComponent") {
      this.publishResult = null;
    }
    try {
      await this.runBusyOperation(async () => {
        await this.loadCurrentOperation();
      });
    } catch (e: unknown) {
      this.operation = previousOperation;
      this.publishResult = previousPublishResult;
      throw e;
    }
  }

  private async runPublishComponent(): Promise<void> {
    await this.runBusyOperation(async () => {
      await this.saveAllProjectFiles();
      const workspaceFolder = this.getSingleWorkspaceFolder();
      const operationResult = await publishComponentProject(workspaceFolder);
      logComponentManagementWarnings(operationResult.warnings);
      this.publishResult = operationResult.result;

      if (operationResult.result.status !== "preparationCreated") {
        log.info(`Published Component Wheel: ${operationResult.result.wheelFileName}`);
        log.info(`Component Wheel SHA-256: ${operationResult.result.sha256}`);
      }

      const boolHasWarning = operationResult.warnings.length > 0;
      let strMessage: string;
      switch (operationResult.result.status) {
        case "preparationCreated":
          strMessage =
            "Component publish preparation was created. Review the Snippet files before running Publish Component again.";
          break;
        case "published":
          strMessage = "The Component was published successfully.";
          break;
        case "alreadyPublished":
          strMessage =
            "An identical Component version is already present in the ComponentRepository.";
      }

      await this.host.postMessage({
        command: "loadPublishComponent",
        initialData: await this.getPublishComponentInitialData(
          {
            type: boolHasWarning ? "warning" : "info",
            message: strMessage,
          },
          getComponentManagementWarningMessages(operationResult.warnings),
        ),
      });
    });
  }

  private async refreshPublishComponent(): Promise<void> {
    await this.runBusyOperation(async () => {
      this.publishResult = null;
      await this.host.postMessage({
        command: "loadPublishComponent",
        initialData: await this.getPublishComponentInitialData(),
      });
    });
  }

  private async openPublishFile(file: Str_PublishComponentFile): Promise<void> {
    await this.runBusyOperation(async () => {
      const workspaceFolder = this.getSingleWorkspaceFolder();
      await openPublishComponentFile(workspaceFolder, file, this.publishResult);
    });
  }

  private async buildDependencyPlan(
    dependencyOperation: DictProtocolDependencyOperation,
  ): Promise<void> {
    await this.runBusyOperation(async () => {
      await this.saveAllProjectFiles();
      const workspaceFolder = this.getSingleWorkspaceFolder();
      const operationResult = await createProjectDependencyPlan(
        workspaceFolder.uri.fsPath,
        dependencyOperation,
      );
      logComponentManagementWarnings(operationResult.warnings);

      await this.host.postMessage({
        command: "projectDependencyPlanBuilt",
        dependencyOperation,
        plan: operationResult.result,
        warningMessages: getComponentManagementWarningMessages(operationResult.warnings),
      });
    });
  }

  private async applyDependencyPlan(
    dependencyOperation: DictProtocolDependencyOperation,
    confirmedPlanSha256: string,
  ): Promise<void> {
    await this.runBusyOperation(async () => {
      await this.saveAllProjectFiles();
      const workspaceFolder = this.getSingleWorkspaceFolder();
      const operationResult = await confirmProjectDependencyPlan(
        workspaceFolder.uri.fsPath,
        dependencyOperation,
        confirmedPlanSha256,
      );
      logComponentManagementWarnings(operationResult.warnings);

      const boolHasWarning = operationResult.warnings.length > 0;
      await this.host.postMessage({
        command: "loadManageComponents",
        initialData: await this.getManageComponentsInitialData(
          {
            type: boolHasWarning ? "warning" : "info",
            message: boolHasWarning
              ? "Component dependency changes were applied with warnings."
              : "Component dependency changes were applied successfully.",
          },
          getComponentManagementWarningMessages(operationResult.warnings),
        ),
      });
    });
  }

  private async repairComponents(): Promise<void> {
    await this.runBusyOperation(async () => {
      await this.saveAllProjectFiles();
      const workspaceFolder = this.getSingleWorkspaceFolder();
      const operationResult = await repairProjectComponentFolder(
        workspaceFolder.uri.fsPath,
      );
      logComponentManagementWarnings(operationResult.warnings);

      const boolHasWarning = operationResult.warnings.length > 0;
      await this.host.postMessage({
        command: "loadManageComponents",
        initialData: await this.getManageComponentsInitialData(
          {
            type: boolHasWarning ? "warning" : "info",
            message: boolHasWarning
              ? "Project Components were repaired with warnings."
              : "Project Components were repaired successfully.",
          },
          getComponentManagementWarningMessages(operationResult.warnings),
        ),
      });
    });
  }

  private async importWheels(): Promise<void> {
    await this.runBusyOperation(async () => {
      const arrWheelFilePath = await selectComponentWheelFilePaths();
      if (arrWheelFilePath === undefined) {
        return;
      }

      const operationResult = await importComponentWheelFiles(arrWheelFilePath);

      await this.host.postMessage({
        command: "loadManageComponents",
        initialData: await this.getManageComponentsInitialData(
          {
            type: operationResult.warnings.length > 0 ? "warning" : "info",
            message:
              operationResult.warnings.length > 0
                ? "Component Wheels were imported with warnings."
                : "Component Wheels were imported into ComponentRepository. " +
                  "Select a Component below to add it to the Project.",
          },
          getComponentManagementWarningMessages(operationResult.warnings),
        ),
      });
    });
  }

  private async refreshManageComponents(): Promise<void> {
    await this.runBusyOperation(async () => {
      await this.host.postMessage({
        command: "loadManageComponents",
        initialData: await this.getManageComponentsInitialData(),
      });
    });
  }

  private async createNewProject(
    input: Extract<
      DictMessage_WebviewToExtension,
      { command: "confirmCreateProject" }
    >["input"],
  ): Promise<void> {
    await this.runBusyOperation(async () => {
      const result = await createProject(input);
      if (result.warnings.length > 0) {
        void vscode.window.showWarningMessage(result.warnings.join("\n"));
      }

      try {
        await vscode.commands.executeCommand(
          "vscode.openFolder",
          vscode.Uri.file(result.projectPath),
          true,
        );
      } catch (e: unknown) {
        const strMessage = getErrorMessage(e);
        log.error(`Project was created, but failed to open it: ${strMessage}`);
        void vscode.window.showErrorMessage(
          "The Project was created successfully, but VS Code failed to open it: " +
            strMessage,
        );
      }

      this.host.dispose();
    });
  }

  public async handleMessage(message: DictMessage_WebviewToExtension): Promise<void> {
    if (this.busy && message.command !== "ready") {
      log.debug(`Ignored Project Manager Webview message while busy: ${message.command}`);
      return;
    }

    switch (message.command) {
      case "ready":
        if (!this.webviewReady) {
          this.webviewReady = true;
          await this.loadCurrentOperation();
        }
        return;

      case "selectTargetFolder":
        if (this.operation !== "createProject") {
          return;
        }
        await this.runBusyOperation(async () => {
          const strTargetFolderPath = await selectTargetFolder();
          if (strTargetFolderPath !== undefined) {
            await this.host.postMessage({
              command: "targetFolderSelected",
              targetFolderPath: strTargetFolderPath,
            });
          }
        });
        return;

      case "confirmCreateProject":
        if (this.operation === "createProject") {
          await this.createNewProject(message.input);
        }
        return;

      case "runPublishComponent":
        if (this.operation === "publishComponent") {
          await this.runPublishComponent();
        }
        return;

      case "refreshPublishComponent":
        if (this.operation === "publishComponent") {
          await this.refreshPublishComponent();
        }
        return;

      case "openPublishComponentFile":
        if (this.operation === "publishComponent") {
          await this.openPublishFile(message.file);
        }
        return;

      case "buildProjectDependencyPlan":
        if (this.operation === "manageComponents") {
          await this.buildDependencyPlan(message.dependencyOperation);
        }
        return;

      case "applyProjectDependencyPlan":
        if (this.operation === "manageComponents") {
          await this.applyDependencyPlan(
            message.dependencyOperation,
            message.confirmedPlanSha256,
          );
        }
        return;

      case "repairProjectComponents":
        if (this.operation === "manageComponents") {
          await this.repairComponents();
        }
        return;

      case "importComponentWheels":
        if (this.operation === "manageComponents") {
          await this.importWheels();
        }
        return;

      case "refreshManageComponents":
        if (this.operation === "manageComponents") {
          await this.refreshManageComponents();
        }
        return;

      case "cancel":
        this.host.dispose();
    }
  }

  public async handleThemeChanged(theme: vscode.ColorTheme): Promise<void> {
    if (this.webviewReady) {
      await this.host.postMessage({
        command: "themeChanged",
        theme: getTheme(theme),
      });
    }
  }

  public async sendError(error: unknown): Promise<void> {
    if (error instanceof ComponentManagementOperationError) {
      log.error(`${error.operationName} failed [${error.code}]: ${error.message}`);
      if (Object.keys(error.details).length > 0) {
        log.debug(`Error details: ${JSON.stringify(error.details)}`);
      }

      await this.host.postMessage({
        command: "componentManagementError",
        code: error.code,
        message: error.message,
        details: error.details,
      });
      return;
    }

    const strMessage = getErrorMessage(error);
    log.error(`Project Manager operation failed: ${strMessage}`);
    await this.host.postMessage({
      command: "error",
      message: strMessage,
    });
  }
}
