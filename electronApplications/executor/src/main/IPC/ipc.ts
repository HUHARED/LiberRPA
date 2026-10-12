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
import {
  getPythonEnvironmentNames,
  validatePythonEnvironmentName,
} from "../Config/environment";
import {
  dbSelectProjectNames,
  dbSelectProjectVersions,
  dbSelectProjectBoundSchedules,
  dbSelectProjectDetail,
  dbUpdateProjectSettings,
} from "../Database/projectRepository";
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
import { installProjectPackage } from "../Package/packageInstallation";
import { deleteInstalledProject } from "../Package/projectDeletion";
import { runInstalledProject, rerunLocalRun } from "../Run/manualRun";
import { ensureExistingRunLogFolderPath } from "../Run/logPath";
import { cancelRunByHistoryId } from "../Run/projectRunner";
import {
  cancelQueuedRun,
  getJobQueueItems,
  refreshSchedulerEngine,
} from "../Scheduler/schedulerEngine";
import {
  ensureRendererLogLevel,
  ensureInvokeCommand,
  ensureNoData,
  ensureStringData,
  ensurePositiveIntegerData,
  ensureProjectRef,
  ensureProjectSettingsUpdate,
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
  // Projects.
  getPythonEnvironmentNames: (rawData: unknown) =>
    ensureNoData(rawData, "getPythonEnvironmentNames"),
  getProjectNames: (rawData: unknown) => ensureNoData(rawData, "getProjectNames"),
  getProjectVersions: (rawData: unknown) => ensureStringData(rawData, "getProjectVersions"),
  getProjectDetail: ensureProjectRef,
  installProjectPackage: (rawData: unknown) =>
    ensureNoData(rawData, "installProjectPackage"),
  saveProjectSettings: ensureProjectSettingsUpdate,
  runProject: ensureProjectSettingsUpdate,
  getProjectBoundSchedules: (rawData: unknown) =>
    ensurePositiveIntegerData(rawData, "getProjectBoundSchedules"),
  deleteProject: (rawData: unknown) => ensurePositiveIntegerData(rawData, "deleteProject"),

  // Schedules.
  getScheduleList: (rawData: unknown) => ensureNoData(rawData, "getScheduleList"),
  getScheduleDetail: (rawData: unknown) => ensureStringData(rawData, "getScheduleDetail"),
  createSchedule: ensureScheduleCreate,
  saveSchedule: ensureScheduleUpdate,
  setScheduleEnabled: ensureScheduleEnabled,
  deleteSchedule: (rawData: unknown) =>
    ensurePositiveIntegerData(rawData, "deleteSchedule"),

  // Job Queue.
  getJobQueue: (rawData: unknown) => ensureNoData(rawData, "getJobQueue"),
  cancelQueuedRun: ensureQueuedRunId,

  // Run History.
  getRunHistoryPage: ensureRunHistoryOptions,
  getRunDetails: (rawData: unknown) => ensurePositiveIntegerData(rawData, "Run History ID"),
  openRunLogFolder: (rawData: unknown) =>
    ensurePositiveIntegerData(rawData, "openRunLogFolder"),
  pythonCancel: (rawData: unknown) => ensurePositiveIntegerData(rawData, "pythonCancel"),
  rerunLocalRun: (rawData: unknown) => ensurePositiveIntegerData(rawData, "rerunLocalRun"),

  // Settings.
  saveExecutorConfig: (rawData: unknown) => parseExecutorConfig(rawData),
  chooseProjectLogFolder: (rawData: unknown) =>
    ensureNoData(rawData, "chooseProjectLogFolder"),
  openProjectLogFolder: (rawData: unknown) => ensureNoData(rawData, "openProjectLogFolder"),

  // Console.
  getConsoleAccount: (rawData: unknown) => ensureNoData(rawData, "getConsoleAccount"),
  saveConsoleAddress: (rawData: unknown) => ensureStringData(rawData, "Console URL"),
  signInConsole: ensureConsoleSignIn,
  getConsoleExecutorChoices: (rawData: unknown) =>
    ensurePositiveIntegerData(rawData, "Executor choices page"),
  associateConsoleExecutor: (rawData: unknown) => ensureStringData(rawData, "Executor ID"),
  signOutConsole: (rawData: unknown) => ensureNoData(rawData, "signOutConsole"),
} satisfies ExecutorInvokeValidators;

function createInvokeHandlerMap(ensureExecutorRunning: () => void): ExecutorInvokeHandlers {
  return {
    // Projects.
    getPythonEnvironmentNames() {
      return getPythonEnvironmentNames();
    },

    getProjectNames() {
      return dbSelectProjectNames();
    },

    getProjectVersions(name) {
      return dbSelectProjectVersions(name);
    },

    getProjectDetail(projectDict) {
      return dbSelectProjectDetail(projectDict.name, projectDict.version);
    },

    async installProjectPackage() {
      return await installProjectPackage(ensureExecutorRunning);
    },

    saveProjectSettings(detailDict) {
      validatePythonEnvironmentName(detailDict.python_environment_name);
      dbUpdateProjectSettings(detailDict);
    },

    async runProject(intProjectId) {
      await runInstalledProject(intProjectId);
    },

    getProjectBoundSchedules(projectId) {
      return dbSelectProjectBoundSchedules(projectId);
    },

    deleteProject(projectId) {
      deleteInstalledProject(projectId);
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

    pythonCancel(runHistoryId) {
      cancelRunByHistoryId(runHistoryId);
    },

    rerunLocalRun,

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
        const message = ensureStringData(rawMessage, "Renderer log message");
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

      let strCommandForLog = String(rawCommand);
      try {
        ensureExecutorRunning();
        const command = ensureInvokeCommand(rawCommand);
        strCommandForLog = command;
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
