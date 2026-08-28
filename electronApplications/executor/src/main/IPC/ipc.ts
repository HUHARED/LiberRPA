// FileName: ipc.ts

import { ipcMain } from "electron";
import type { IpcMainEvent, IpcMainInvokeEvent, WebContents } from "electron";

import { getErrorMessage } from "../../shared/error";
import {
  chooseProjectLogFolder,
  dictConfigExecutor,
  getEffectiveProjectLogFolderPath,
  saveExecutorConfigDict,
  validateExecutorConfig,
} from "../Config/executorConfig";
import { getPythonEnvironmentNames, getPythonEnvironmentPath } from "../Config/environment";
import {
  dbSelectProjectBoundSchedules,
  dbSelectProjectDetail,
  dbSelectProjectNames,
  dbSelectProjectVersions,
  dbUpdateProjectSettings,
} from "../Database/projectRepository";
import {
  dbSelectRunHistoryLogLocation,
  dbSelectRunHistoryPage,
} from "../Database/runHistoryRepository";
import {
  dbDeleteSchedule,
  dbInsertSchedule,
  dbSelectScheduleDetail,
  dbSelectScheduleList,
  dbUpdateSchedule,
} from "../Database/scheduleRepository";
import { fileOpenFolder } from "../FileSystem/executorFiles";
import { loggerMain } from "../Logging/logger";
import { installProjectPackage } from "../Package/packageInstallation";
import { deleteInstalledProject } from "../Package/projectDeletion";
import {
  runInstalledProject,
  runMostRecentlyInstalledProjectVersion,
} from "../Run/manualRun";
import { ensureExistingRunLogFolderPath } from "../Run/logPath";
import { pythonCancel } from "../Run/projectRunner";
import {
  cancelWaitingRun,
  getRunQueueItems,
  refreshSchedulerEngine,
} from "../Scheduler/schedulerEngine";
import {
  ensureInvokeCommand,
  ensureNoData,
  ensurePositiveIntegerData,
  ensureProjectRef,
  ensureProjectSettingsUpdate,
  ensureRendererLogLevel,
  ensureRunHistoryOptions,
  ensureScheduleCreate,
  ensureScheduleUpdate,
  ensureStringData,
  ensureWaitingRunId,
} from "./validation";
import { IPC_CHANNEL_RENDERER_INVOKE, IPC_CHANNEL_RENDERER_LOG } from "../../shared/ipc";
import type {
  Dict_Result_Invoke,
  Str_ExecutorInvokeCommand,
  Type_ExecutorInvoke_Request,
  Type_ExecutorInvoke_Response,
} from "../../shared/ipc";

function createSuccessResult<T>(data: T): Dict_Result_Invoke<T> {
  return { success: true, data };
}

function createErrorResult(e: unknown): Dict_Result_Invoke<never> {
  return { success: false, error: getErrorMessage(e) };
}

type Map_ExecutorInvoke_Validator = {
  [C in Str_ExecutorInvokeCommand]: (rawData: unknown) => Type_ExecutorInvoke_Request<C>;
};

type Map_ExecutorInvoke_Handler = {
  [C in Str_ExecutorInvokeCommand]: (
    data: Type_ExecutorInvoke_Request<C>,
  ) => Type_ExecutorInvoke_Response<C> | Promise<Type_ExecutorInvoke_Response<C>>;
};

const INVOKE_VALIDATOR = {
  openProjectLogFolder: (rawData: unknown) => ensureNoData(rawData, "openProjectLogFolder"),
  saveExecutorConfig: (rawData: unknown) => validateExecutorConfig(rawData),
  runProject: (rawData: unknown) => ensurePositiveIntegerData(rawData, "runProject"),
  getPythonEnvironmentNames: (rawData: unknown) =>
    ensureNoData(rawData, "getPythonEnvironmentNames"),
  installProjectPackage: (rawData: unknown) =>
    ensureNoData(rawData, "installProjectPackage"),
  getProjectNames: (rawData: unknown) => ensureNoData(rawData, "getProjectNames"),
  getProjectVersions: (rawData: unknown) => ensureStringData(rawData, "getProjectVersions"),
  getProjectDetail: ensureProjectRef,
  saveProjectSettings: ensureProjectSettingsUpdate,
  getProjectBoundSchedules: (rawData: unknown) =>
    ensurePositiveIntegerData(rawData, "getProjectBoundSchedules"),
  deleteProject: (rawData: unknown) => ensurePositiveIntegerData(rawData, "deleteProject"),
  getScheduleList: (rawData: unknown) => ensureNoData(rawData, "getScheduleList"),
  getScheduleDetail: (rawData: unknown) => ensureStringData(rawData, "getScheduleDetail"),
  createSchedule: ensureScheduleCreate,
  saveSchedule: ensureScheduleUpdate,
  deleteSchedule: (rawData: unknown) =>
    ensurePositiveIntegerData(rawData, "deleteSchedule"),
  getRunHistoryPage: ensureRunHistoryOptions,
  getRunQueue: (rawData: unknown) => ensureNoData(rawData, "getRunQueue"),
  cancelWaitingRun: ensureWaitingRunId,
  openRunLogFolder: (rawData: unknown) =>
    ensurePositiveIntegerData(rawData, "openRunLogFolder"),
  runMostRecentlyInstalledProjectVersion: (rawData: unknown) =>
    ensureStringData(rawData, "runMostRecentlyInstalledProjectVersion"),
  pythonCancel: (rawData: unknown) => ensurePositiveIntegerData(rawData, "pythonCancel"),
  chooseProjectLogFolder: (rawData: unknown) =>
    ensureNoData(rawData, "chooseProjectLogFolder"),
} satisfies Map_ExecutorInvoke_Validator;

function createInvokeHandlerMap(): Map_ExecutorInvoke_Handler {
  return {
    async openProjectLogFolder() {
      await fileOpenFolder(getEffectiveProjectLogFolderPath());
    },

    saveExecutorConfig(dictConfig) {
      const boolTimezoneChanged = dictConfig.timezone !== dictConfigExecutor.timezone;
      saveExecutorConfigDict(dictConfig);
      // Other Main Process modules read this shared in-memory config.
      Object.assign(dictConfigExecutor, dictConfig);
      if (boolTimezoneChanged) {
        refreshSchedulerEngine();
      }
    },

    async runProject(intProjectId) {
      await runInstalledProject(intProjectId);
    },

    getPythonEnvironmentNames() {
      return getPythonEnvironmentNames();
    },

    async installProjectPackage() {
      return await installProjectPackage();
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

    saveProjectSettings(detailDict) {
      getPythonEnvironmentPath(detailDict.python_environment_name);
      dbUpdateProjectSettings(detailDict);
    },

    getProjectBoundSchedules(projectId) {
      return dbSelectProjectBoundSchedules(projectId);
    },

    deleteProject(projectId) {
      deleteInstalledProject(projectId);
    },

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

    deleteSchedule(scheduleId) {
      dbDeleteSchedule(scheduleId);
      refreshSchedulerEngine();
    },

    getRunHistoryPage(optionsDict) {
      return dbSelectRunHistoryPage(optionsDict);
    },

    getRunQueue() {
      return getRunQueueItems();
    },

    cancelWaitingRun(queueId) {
      cancelWaitingRun(queueId);
    },

    async openRunLogFolder(runHistoryId) {
      const logLocation = dbSelectRunHistoryLogLocation(runHistoryId);
      if (logLocation === undefined) {
        throw new Error(`Run History record not found: ${runHistoryId}`);
      }
      await fileOpenFolder(ensureExistingRunLogFolderPath(logLocation.log_path));
    },

    async runMostRecentlyInstalledProjectVersion(projectName) {
      await runMostRecentlyInstalledProjectVersion(projectName);
    },

    pythonCancel(runHistoryId) {
      pythonCancel(runHistoryId);
    },

    async chooseProjectLogFolder() {
      return await chooseProjectLogFolder();
    },
  };
}

async function executeInvoke<C extends Str_ExecutorInvokeCommand>(
  command: C,
  rawData: unknown,
  validatorMap: Map_ExecutorInvoke_Validator,
  handlerMap: Map_ExecutorInvoke_Handler,
): Promise<Type_ExecutorInvoke_Response<C>> {
  const data = validatorMap[command](rawData);
  return await handlerMap[command](data);
}

export function registerExecutorIpc(
  getExpectedWebContents: () => WebContents | undefined,
): void {
  const invokeHandlerMap = createInvokeHandlerMap();

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
    ): Promise<Dict_Result_Invoke<unknown>> => {
      if (!isExpectedSender(event)) {
        loggerMain.warn("Rejected Renderer invoke from an unexpected sender.");
        return createErrorResult(new Error("Unexpected IPC sender."));
      }

      let strCommandForLog = String(rawCommand);
      try {
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
