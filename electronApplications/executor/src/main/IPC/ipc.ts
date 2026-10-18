// FileName: ipc.ts

import { ipcMain } from "electron";
import type { IpcMainEvent, IpcMainInvokeEvent, WebContents } from "electron";

import {
  getConsoleAccountState,
  saveConsoleAddress,
  signInConsole,
  getConsoleExecutorChoices,
  associateConsoleExecutor,
  signOutConsole,
} from "../Console/consoleAccount";
import { getErrorMessage } from "../../shared/error";
import {
  parseExecutorConfig,
  dictConfigExecutor,
  getEffectiveProjectLogFolderPath,
  saveExecutorConfigDict,
  chooseProjectLogFolder,
} from "../Config/executorConfig";
import { getPythonEnvironmentNames } from "../Config/environment";
import {
  dbSelectProjectNames,
  dbSelectProjectVersions,
  dbSelectPackageBoundSchedules,
  dbSelectPackageDetails,
  dbUpdatePackageSettings,
} from "../Database/packageRepository";
import {
  dbSelectRunHistoryLogLocation,
  dbSelectRunHistoryPage,
  dbSelectRunDetails,
} from "../Database/runHistoryRepository";
import {
  dbSelectScheduleList,
  dbSelectScheduleDetail,
  dbInsertSchedule,
  dbUpdateSchedule,
  dbDeleteSchedule,
  dbSetScheduleEnabled,
} from "../Database/scheduleRepository";
import { fileOpenFolder } from "../FileSystem/executorFiles";
import { loggerMain } from "../Logging/logger";
import { installPackage } from "../Package/packageInstallation";
import { deleteInstalledPackage } from "../Package/packageDeletion";
import { runInstalledPackage, getLocalRerunPackage } from "../Run/manualRun";
import { ensureExistingRunLogFolderPath } from "../Run/logPath";
import { stopRunByHistoryId } from "../Run/packageRunner";
import {
  cancelQueuedRun,
  getJobQueueItems,
  refreshSchedulerEngine,
} from "../Scheduler/schedulerEngine";
import { ensureString, ensurePositiveInteger } from "../Common/validation";
import {
  ensureRendererLogLevel,
  ensureNoData,
  ensurePackageRef,
  ensurePackageSettings,
  ensureScheduleCreate,
  ensureScheduleUpdate,
  ensureScheduleEnabled,
  ensureQueuedRunId,
  ensureRunHistoryOptions,
  ensureConsoleSignIn,
} from "./validation";
import { IPC_CHANNEL_RENDERER_LOG, IPC_CHANNEL_RENDERER_INVOKE } from "../../shared/ipc";
import type {
  InvokeResult,
  ExecutorInvokeCommand,
  ExecutorInvokeRequest,
  ExecutorInvokeResponse,
} from "../../shared/ipc";

function createSuccessResult<T>(data: T): InvokeResult<T> {
  return { success: true, data };
}

function createErrorResult(e: unknown): InvokeResult<never> {
  return { success: false, error: getErrorMessage(e) };
}

type ExecutorInvokeValidators = {
  [C in ExecutorInvokeCommand]: (rawData: unknown) => ExecutorInvokeRequest<C>;
};

type ExecutorInvokeHandlers = {
  [C in ExecutorInvokeCommand]: (
    data: ExecutorInvokeRequest<C>,
  ) => ExecutorInvokeResponse<C> | Promise<ExecutorInvokeResponse<C>>;
};

const INVOKE_VALIDATOR = {
  // Packages.
  getPythonEnvironmentNames: (rawData: unknown) =>
    ensureNoData(rawData, "getPythonEnvironmentNames"),
  getProjectNames: (rawData: unknown) => ensureNoData(rawData, "getProjectNames"),
  getProjectVersions: (rawData: unknown) => ensureString(rawData, "Project name"),
  getPackageDetails: ensurePackageRef,
  installPackage: (rawData: unknown) => ensureNoData(rawData, "installPackage"),
  savePackageSettings: (rawData: unknown) =>
    ensurePackageSettings(rawData, "Package settings update request"),
  runPackage: (rawData: unknown) => ensurePackageSettings(rawData, "Package run request"),
  getPackageBoundSchedules: (rawData: unknown) =>
    ensurePositiveInteger(rawData, "Package ID"),
  deletePackage: (rawData: unknown) => ensurePositiveInteger(rawData, "Package ID"),

  // Schedules.
  getScheduleList: (rawData: unknown) => ensureNoData(rawData, "getScheduleList"),
  getScheduleDetail: (rawData: unknown) => ensureString(rawData, "Schedule name"),
  createSchedule: ensureScheduleCreate,
  saveSchedule: ensureScheduleUpdate,
  setScheduleEnabled: ensureScheduleEnabled,
  deleteSchedule: (rawData: unknown) => ensurePositiveInteger(rawData, "Schedule ID"),

  // Job Queue.
  getJobQueue: (rawData: unknown) => ensureNoData(rawData, "getJobQueue"),
  cancelQueuedRun: ensureQueuedRunId,

  // Run History.
  getRunHistoryPage: ensureRunHistoryOptions,
  getRunDetails: (rawData: unknown) => ensurePositiveInteger(rawData, "Run History ID"),
  openRunLogFolder: (rawData: unknown) => ensurePositiveInteger(rawData, "Run History ID"),
  stopRun: (rawData: unknown) => ensurePositiveInteger(rawData, "Run History ID"),
  getLocalRerunPackage: (rawData: unknown) =>
    ensurePositiveInteger(rawData, "Run History ID"),

  // Settings.
  saveExecutorConfig: (rawData: unknown) => parseExecutorConfig(rawData),
  chooseProjectLogFolder: (rawData: unknown) =>
    ensureNoData(rawData, "chooseProjectLogFolder"),
  openProjectLogFolder: (rawData: unknown) => ensureNoData(rawData, "openProjectLogFolder"),

  // Console.
  getConsoleAccount: (rawData: unknown) => ensureNoData(rawData, "getConsoleAccount"),
  saveConsoleAddress: (rawData: unknown) => ensureString(rawData, "Console URL"),
  signInConsole: ensureConsoleSignIn,
  getConsoleExecutorChoices: (rawData: unknown) =>
    ensurePositiveInteger(rawData, "Executor choices page"),
  associateConsoleExecutor: (rawData: unknown) => ensureString(rawData, "Executor ID"),
  signOutConsole: (rawData: unknown) => ensureNoData(rawData, "signOutConsole"),
} satisfies ExecutorInvokeValidators;

function createInvokeHandlerMap(ensureExecutorRunning: () => void): ExecutorInvokeHandlers {
  return {
    // Packages.
    getPythonEnvironmentNames() {
      return getPythonEnvironmentNames();
    },

    getProjectNames() {
      return dbSelectProjectNames();
    },

    getProjectVersions(name) {
      return dbSelectProjectVersions(name);
    },

    getPackageDetails(packageRef) {
      return dbSelectPackageDetails(packageRef.project_name, packageRef.project_version);
    },

    async installPackage() {
      return await installPackage(ensureExecutorRunning);
    },

    savePackageSettings(detailDict) {
      dbUpdatePackageSettings(detailDict);
    },

    async runPackage(settings) {
      await runInstalledPackage(settings);
    },

    getPackageBoundSchedules(packageId) {
      return dbSelectPackageBoundSchedules(packageId);
    },

    async deletePackage(packageId) {
      await deleteInstalledPackage(packageId);
    },

    // Schedules.
    getScheduleList() {
      return dbSelectScheduleList();
    },

    getScheduleDetail(name) {
      return dbSelectScheduleDetail(name);
    },

    createSchedule(detailDict) {
      dbInsertSchedule(detailDict);
      refreshSchedulerEngine();
    },

    saveSchedule(detailDict) {
      dbUpdateSchedule(detailDict);
      refreshSchedulerEngine();
    },

    setScheduleEnabled({ id, enabled }) {
      dbSetScheduleEnabled(id, enabled);
      refreshSchedulerEngine();
    },

    deleteSchedule(scheduleId) {
      dbDeleteSchedule(scheduleId);
      refreshSchedulerEngine();
    },

    // Job Queue.
    getJobQueue() {
      return getJobQueueItems();
    },

    cancelQueuedRun(queueId) {
      cancelQueuedRun(queueId);
    },

    // Run History.
    getRunHistoryPage: dbSelectRunHistoryPage,

    getRunDetails: dbSelectRunDetails,

    async openRunLogFolder(runHistoryId) {
      const logLocation = dbSelectRunHistoryLogLocation(runHistoryId);
      if (logLocation === undefined) {
        throw new Error(`Run History record not found: ${runHistoryId}`);
      }
      await fileOpenFolder(ensureExistingRunLogFolderPath(logLocation.log_path));
    },

    stopRun(runHistoryId) {
      stopRunByHistoryId(runHistoryId);
    },

    getLocalRerunPackage,

    // Settings.
    saveExecutorConfig(dictConfig) {
      const boolTimezoneChanged = dictConfig.timezone !== dictConfigExecutor.timezone;
      saveExecutorConfigDict(dictConfig);
      // Other Main Process modules read this shared in-memory config.
      Object.assign(dictConfigExecutor, dictConfig);
      if (boolTimezoneChanged) {
        refreshSchedulerEngine();
      }
    },

    async chooseProjectLogFolder() {
      return await chooseProjectLogFolder();
    },

    async openProjectLogFolder() {
      await fileOpenFolder(getEffectiveProjectLogFolderPath());
    },

    // Console.
    getConsoleAccount: getConsoleAccountState,

    saveConsoleAddress,

    signInConsole,

    getConsoleExecutorChoices,

    associateConsoleExecutor,

    signOutConsole,
  };
}

async function executeInvoke<C extends ExecutorInvokeCommand>(
  command: C,
  rawData: unknown,
  validatorMap: ExecutorInvokeValidators,
  handlerMap: ExecutorInvokeHandlers,
): Promise<ExecutorInvokeResponse<C>> {
  const data = validatorMap[command](rawData);
  return await handlerMap[command](data);
}

export function registerExecutorIpc(
  getExpectedWebContents: () => WebContents | undefined,
  isExecutorShuttingDown: () => boolean,
): void {
  const ensureExecutorRunning = (): void => {
    if (isExecutorShuttingDown()) {
      throw new Error("Executor is shutting down and cannot accept new operations.");
    }
  };
  const invokeHandlerMap = createInvokeHandlerMap(ensureExecutorRunning);

  const isExpectedSender = (event: IpcMainEvent | IpcMainInvokeEvent): boolean =>
    event.sender === getExpectedWebContents();

  ipcMain.on(
    IPC_CHANNEL_RENDERER_LOG,
    (event: IpcMainEvent, rawLevel: unknown, rawMessage: unknown): void => {
      if (!isExpectedSender(event)) {
        loggerMain.warn("Ignored Renderer log message from an unexpected sender.");
        return;
      }

      try {
        const level = ensureRendererLogLevel(rawLevel);
        const message = ensureString(rawMessage, "Renderer log message");
        loggerMain.log(level, `[Renderer] ${message}`);
      } catch (e: unknown) {
        loggerMain.error(`Invalid Renderer log message: ${getErrorMessage(e)}`);
      }
    },
  );

  ipcMain.handle(
    IPC_CHANNEL_RENDERER_INVOKE,
    async (
      event: IpcMainInvokeEvent,
      rawCommand: unknown,
      rawData: unknown,
    ): Promise<InvokeResult<unknown>> => {
      if (!isExpectedSender(event)) {
        loggerMain.warn("Rejected Renderer invoke from an unexpected sender.");
        return createErrorResult(new Error("Unexpected IPC sender."));
      }

      const strCommandForLog = String(rawCommand);
      try {
        ensureExecutorRunning();
        if (
          typeof rawCommand !== "string" ||
          !Object.hasOwn(INVOKE_VALIDATOR, rawCommand)
        ) {
          throw new Error(`Unknown Renderer invoke command: ${strCommandForLog}`);
        }
        const command = rawCommand as ExecutorInvokeCommand;
        loggerMain.debug(`[renderer-invoke] ${command}`);

        const data = await executeInvoke(
          command,
          rawData,
          INVOKE_VALIDATOR,
          invokeHandlerMap,
        );
        return createSuccessResult(data);
      } catch (e: unknown) {
        loggerMain.error(
          `Error running IPC command ${strCommandForLog}: ${getErrorMessage(e)}`,
        );
        return createErrorResult(e);
      }
    },
  );
}
