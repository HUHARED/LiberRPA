// FileName: projectManagerSession.ts

import * as vscode from "vscode";
import { randomUUID } from "node:crypto";
import * as path from "node:path";

import {
  log,
  showLogs,
  showErrorMessageWithLogs,
  showWarningMessageWithLogs,
} from "../Adapter/VsCode/output";
import { getErrorMessage } from "../Common/utils";
import {
  ComponentManagementOperationError,
  buildProjectDependencyPlan,
  applyProjectDependencyPlan,
  repairProjectComponents,
} from "../Adapter/Python/componentManagementClient";
import type {
  Theme,
  ProjectManagerOperation,
  Str_PublishComponentFile,
  DictProjectManagerNotification,
  DictPackageProjectInitialData,
  DictPublishComponentInitialData,
  DictManageComponentsInitialData,
  DictMessage_WebviewToExtension,
  DictMessage_ExtensionToWebview,
} from "../Adapter/Webview/projectManagerMessages";
import type {
  DictProtocolDependencyOperation,
  DictProtocolResult_Publish,
} from "../Domain/ComponentManagement/componentManagementTypes";
import type {
  DictPackageProjectInput,
  DictProjectPackageResult,
} from "../Domain/Project/projectTypes";
import {
  logComponentManagementOperationError,
  logComponentManagementWarnings,
  getComponentManagementWarningMessages,
} from "./componentManagementOutput";
import { loadManageComponentsData } from "./Dependency/manageComponents";
import {
  getProjectTemplates,
  selectTargetFolder,
  createProject,
} from "./Project/createProject";
import {
  type PackageProjectData,
  getDefaultPackageProjectInput,
  loadPackageProjectData,
  selectPackageOutputFolder,
  packageFlowProject,
  openPackageProjectManifest,
  revealProjectPackage,
} from "./Project/packageProject";
import {
  loadPublishComponentData,
  publishComponentProject,
  openPublishComponentFile,
} from "./Publish/publishComponent";
import {
  selectComponentWheelFilePaths,
  importComponentWheelFiles,
} from "./Repository/importComponentWheels";
import type { ConsoleAccount } from "./Console/consoleAccount";
import {
  ConsoleAction,
  type ConsolePublishDepartment,
  ConsolePublishStatus,
  type ConsolePublishResult,
  type ConsoleAccountState,
} from "../Domain/Console/consoleTypes";

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
  private packageProjectInput: DictPackageProjectInput | null = null;
  private packageResult: DictProjectPackageResult | null = null;
  private publishResult: DictProtocolResult_Publish | null = null;
  private consolePublishRequestId = "";
  private consoleDepartments: ConsolePublishDepartment[] = [];
  private consolePublishingMessage = "";
  private consolePublishResult: ConsolePublishResult = {
    status: ConsolePublishStatus.NotRequested,
    message: "",
    packageId: null,
  };

  public constructor(
    private readonly host: ProjectManagerSessionHost,
    private operation: ProjectManagerOperation,
    private readonly consoleAccount: ConsoleAccount,
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

  private async loadConsolePublishingDepartments(): Promise<void> {
    this.consoleDepartments = [];
    this.consolePublishingMessage = "";
    try {
      this.consoleDepartments = await this.consoleAccount.getPackageDepartments();
      if (this.consoleDepartments.length === 0) {
        this.consolePublishingMessage =
          "Your account has no department where it can publish Packages.";
      }
    } catch (e: unknown) {
      this.consolePublishingMessage = getErrorMessage(e);
    }
  }

  private async getPackageProjectInitialData(
    notification?: DictProjectManagerNotification,
    additionalWarningMessages: string[] = [],
    checkedData?: PackageProjectData,
  ): Promise<DictPackageProjectInitialData> {
    const workspaceFolder = this.getSingleWorkspaceFolder();
    const input =
      this.packageProjectInput ?? getDefaultPackageProjectInput(workspaceFolder);
    const data = checkedData ?? (await loadPackageProjectData(workspaceFolder, input));
    logComponentManagementWarnings(data.warnings);
    this.packageProjectInput = data.input;
    if (
      this.packageResult !== null &&
      (!data.packageFileExists ||
        data.packageFileName === null ||
        path.join(input.outputFolderPath, data.packageFileName) !==
          this.packageResult.packageFilePath)
    ) {
      this.packageResult = null;
      this.consolePublishRequestId = "";
      this.consolePublishResult = {
        status: ConsolePublishStatus.NotRequested,
        message: "",
        packageId: null,
      };
    }
    if (checkedData === undefined && input.publishToConsole) {
      await this.loadConsolePublishingDepartments();
    }

    return {
      theme: getTheme(vscode.window.activeColorTheme),
      projectPath: data.projectPath,
      manifest: data.manifest,
      projectDependencyState: data.projectDependencyState,
      input: data.input,
      packageFileName: data.packageFileName,
      packageFileExists: data.packageFileExists,
      blockingReasons: data.blockingReasons,
      warningMessages: [
        ...new Set([
          ...additionalWarningMessages,
          ...getComponentManagementWarningMessages(data.warnings),
        ]),
      ],
      packageResult: this.packageResult,
      consoleDepartments: this.consoleDepartments,
      consolePublishingMessage: this.consolePublishingMessage,
      consolePublishResult: this.consolePublishResult,
      ...(notification === undefined ? {} : { notification }),
    };
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
    if (data.repositoryCatalogError !== null) {
      logComponentManagementOperationError(data.repositoryCatalogError);
    }

    return {
      theme: getTheme(vscode.window.activeColorTheme),
      projectState: data.projectState,
      repositoryCatalog: data.repositoryCatalog,
      repositoryCatalogError:
        data.repositoryCatalogError === null
          ? null
          : {
              code: data.repositoryCatalogError.code,
              message: data.repositoryCatalogError.message,
            },
      warningMessages: [
        ...new Set([
          ...additionalWarningMessages,
          ...getComponentManagementWarningMessages(data.warnings),
        ]),
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

      case "packageProject": {
        const initialData = await this.getPackageProjectInitialData();
        if (intLoadId !== this.operationLoadId || this.operation !== "packageProject") {
          return;
        }
        await this.host.postMessage({
          command: "loadPackageProject",
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
        return;
      }

      case "console": {
        const state = await this.consoleAccount.getState();
        if (intLoadId !== this.operationLoadId || this.operation !== "console") {
          return;
        }

        await this.host.postMessage({
          command: "loadConsole",
          theme: getTheme(vscode.window.activeColorTheme),
          state,
        });
        return;
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
    const previousPackageProjectInput = this.packageProjectInput;
    const previousPackageResult = this.packageResult;
    const previousPublishResult = this.publishResult;
    const previousConsolePublishResult = this.consolePublishResult;
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
      this.packageProjectInput = previousPackageProjectInput;
      this.packageResult = previousPackageResult;
      this.publishResult = previousPublishResult;
      this.consolePublishResult = previousConsolePublishResult;
      throw e;
    }
  }

  private async selectPackageFolder(input: DictPackageProjectInput): Promise<void> {
    await this.runBusyOperation(async () => {
      const strOutputFolderPath = await selectPackageOutputFolder(input.outputFolderPath);
      if (strOutputFolderPath === undefined) {
        return;
      }

      this.packageProjectInput = {
        ...input,
        outputFolderPath: strOutputFolderPath,
      };
      this.packageResult = null;
      this.consolePublishResult = {
        status: ConsolePublishStatus.NotRequested,
        message: "",
        packageId: null,
      };
      await this.host.postMessage({
        command: "loadPackageProject",
        initialData: await this.getPackageProjectInitialData(),
      });
    });
  }

  private async publishCreatedPackage(): Promise<void> {
    const packageResult = this.packageResult;
    const input = this.packageProjectInput;
    if (packageResult === null || input === null || input.consoleDepartmentId === "") {
      throw new Error("Create a local Package and select a publishing department first.");
    }
    this.consolePublishResult = {
      status: ConsolePublishStatus.Publishing,
      message: "The local Package was created. Uploading it to Console...",
      packageId: null,
    };
    await this.host.postMessage({
      command: "consolePublishChanged",
      result: this.consolePublishResult,
    });
    try {
      const strPackageId = await this.consoleAccount.publishPackage(
        packageResult.packageFilePath,
        input.consoleDepartmentId,
        this.consolePublishRequestId,
      );
      this.consolePublishResult = {
        status: ConsolePublishStatus.Completed,
        message: "The Package was published to Console successfully.",
        packageId: strPackageId,
      };
    } catch (e: unknown) {
      this.consolePublishResult = {
        status: ConsolePublishStatus.Failed,
        message: `The local Package is ready, but Console publishing failed: ${getErrorMessage(e)}`,
        packageId: null,
      };
    }
    await this.host.postMessage({
      command: "consolePublishChanged",
      result: this.consolePublishResult,
    });
  }

  private async retryConsolePublish(): Promise<void> {
    if (this.consolePublishResult.status !== ConsolePublishStatus.Failed) {
      throw new Error("There is no failed Console upload to retry.");
    }
    await this.runBusyOperation(async () => {
      await this.publishCreatedPackage();
    });
  }

  private async runPackageProject(input: DictPackageProjectInput): Promise<void> {
    await this.runBusyOperation(async () => {
      await this.saveAllProjectFiles();
      const workspaceFolder = this.getSingleWorkspaceFolder();
      this.packageProjectInput = input;
      this.packageResult = null;
      this.consolePublishRequestId = randomUUID();
      this.consolePublishResult = {
        status: ConsolePublishStatus.NotRequested,
        message: "",
        packageId: null,
      };
      if (input.publishToConsole && input.consoleDepartmentId === "") {
        throw new Error("Select a department for Console publishing.");
      }

      const operationResult = await packageFlowProject(workspaceFolder, input);
      logComponentManagementWarnings(operationResult.warnings);
      this.packageResult = operationResult.result;
      await this.host.postMessage({
        command: "loadPackageProject",
        initialData: await this.getPackageProjectInitialData(
          {
            type: operationResult.warnings.length > 0 ? "warning" : "info",
            message:
              operationResult.warnings.length > 0
                ? "The Flow Project was packaged with warnings."
                : "The Flow Project was packaged successfully.",
          },
          getComponentManagementWarningMessages(operationResult.warnings),
          operationResult.data,
        ),
      });
      if (input.publishToConsole) {
        await this.publishCreatedPackage();
      }
    });
  }

  private async refreshPackageProject(input: DictPackageProjectInput): Promise<void> {
    await this.runBusyOperation(async () => {
      await this.saveAllProjectFiles();
      this.packageProjectInput = input;
      await this.host.postMessage({
        command: "loadPackageProject",
        initialData: await this.getPackageProjectInitialData(),
      });
    });
  }

  private async refreshConsolePublishing(input: DictPackageProjectInput): Promise<void> {
    await this.runBusyOperation(async () => {
      this.packageProjectInput = input;
      await this.host.postMessage({
        command: "loadPackageProject",
        initialData: await this.getPackageProjectInitialData(),
      });
    });
  }

  private async openPackageManifest(): Promise<void> {
    await this.runBusyOperation(async () => {
      await openPackageProjectManifest(this.getSingleWorkspaceFolder());
    });
  }

  private async revealPackageResult(): Promise<void> {
    const packageResult = this.packageResult;
    if (packageResult === null) {
      throw new Error("No Project Package is available to reveal.");
    }
    await this.runBusyOperation(async () => {
      await revealProjectPackage(packageResult.packageFilePath);
    });
  }

  private async runPublishComponent(): Promise<void> {
    await this.runBusyOperation(async () => {
      await this.saveAllProjectFiles();
      const workspaceFolder = this.getSingleWorkspaceFolder();
      const operationResult = await publishComponentProject(workspaceFolder);
      logComponentManagementWarnings(operationResult.warnings);
      this.publishResult = operationResult.result;

      if (operationResult.result.status === "published") {
        log.info(`Published Component Wheel: ${operationResult.result.wheelFileName}`);
        log.info(`Component Wheel SHA-256: ${operationResult.result.sha256}`);
      } else if (operationResult.result.status === "alreadyPublished") {
        log.info(
          `Component Wheel is already published: ${operationResult.result.wheelFileName}`,
        );
        log.info(`Component Wheel SHA-256: ${operationResult.result.sha256}`);
      }

      const boolShowWarningNotification =
        operationResult.warnings.length > 0 ||
        operationResult.result.status === "alreadyPublished";
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
            type: boolShowWarningNotification ? "warning" : "info",
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
      const operationResult = await buildProjectDependencyPlan(
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
      const operationResult = await applyProjectDependencyPlan(
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
      const operationResult = await repairProjectComponents(workspaceFolder.uri.fsPath);
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
        void showWarningMessageWithLogs(result.warnings.join("\n"));
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
        void showErrorMessageWithLogs(
          "The Project was created successfully, but VS Code failed to open it: " +
            strMessage,
        );
      }

      this.host.dispose();
    });
  }

  public async handleConsoleStateChanged(state: ConsoleAccountState): Promise<void> {
    if (this.webviewReady && this.operation === "console") {
      await this.host.postMessage({ command: "consoleStateChanged", state });
    }
  }

  private async runConsoleAction(
    action: ConsoleAction,
    callback: () => Promise<void>,
  ): Promise<void> {
    if (this.operation !== "console") {
      return;
    }

    await this.runBusyOperation(async () => {
      let strError: string | null = null;
      try {
        await callback();
      } catch (e: unknown) {
        strError = getErrorMessage(e);
      }
      await this.host.postMessage({
        command: "consoleActionFinished",
        action,
        error: strError,
      });
    });
  }

  public async handleMessage(message: DictMessage_WebviewToExtension): Promise<void> {
    if (message.command === "showLogs") {
      showLogs();
      return;
    }

    if (this.busy && message.command !== "ready") {
      log.debug(`Ignored Project Manager Webview message while busy: ${message.command}`);
      return;
    }

    switch (message.command) {
      // Shared commands.
      case "ready":
        if (!this.webviewReady) {
          this.webviewReady = true;
          await this.loadCurrentOperation();
        }
        return;

      // Create Project.
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

      // Package Project.
      case "selectPackageOutputFolder":
        if (this.operation === "packageProject") {
          await this.selectPackageFolder(message.input);
        }
        return;

      case "runPackageProject":
        if (this.operation === "packageProject") {
          await this.runPackageProject(message.input);
        }
        return;

      case "refreshPackageProject":
        if (this.operation === "packageProject") {
          await this.refreshPackageProject(message.input);
        }
        return;

      case "refreshConsolePublishing":
        if (this.operation === "packageProject") {
          await this.refreshConsolePublishing(message.input);
        }
        return;

      case "openPackageProjectManifest":
        if (this.operation === "packageProject") {
          await this.openPackageManifest();
        }
        return;

      case "revealProjectPackage":
        if (this.operation === "packageProject") {
          await this.revealPackageResult();
        }
        return;

      case "retryConsolePublish":
        if (this.operation === "packageProject") {
          await this.retryConsolePublish();
        }
        return;

      case "openManageComponents":
        if (this.operation === "packageProject") {
          await this.switchOperation("manageComponents");
        }
        return;

      // Publish Component.
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

      // Manage Components.
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

      // Console account.
      case "changeConsoleAddress":
        await this.runConsoleAction(ConsoleAction.ChangeAddress, () =>
          this.consoleAccount.changeAddress(message.url),
        );
        return;

      case "signInConsole":
        await this.runConsoleAction(ConsoleAction.SignIn, () =>
          this.consoleAccount.signIn(message.email, message.password),
        );
        return;

      case "signOutConsole":
        await this.runConsoleAction(ConsoleAction.SignOut, () =>
          this.consoleAccount.signOut(),
        );
        return;

      case "checkConsoleConnection":
        await this.runConsoleAction(ConsoleAction.CheckConnection, () =>
          this.consoleAccount.checkConnection(),
        );
        return;

      // Close the panel.
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
      logComponentManagementOperationError(error);

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
