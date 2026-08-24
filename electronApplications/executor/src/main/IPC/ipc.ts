import { ipcMain } from "electron";
import type { IpcMainEvent, IpcMainInvokeEvent } from "electron";

import {
  dictConfigExecutor,
  saveExecutorConfigDict,
  chooseProjectLogFolder,
  validateExecutorConfig,
} from "../Config/config";
import { getPythonEnvironmentNames, getPythonEnvironmentPath } from "../Config/environment";
import {
  dbDeleteProject,
  dbSelectProjectBoundSchedules,
  dbSelectProjectDetail,
  dbSelectProjectNames,
  dbSelectProjectNewestVersionDetail,
  dbSelectProjectVersions,
  dbUpdateProjectDetail,
} from "../Database/projectRepository";
import {
  dbDeleteSchedule,
  dbInsertSchedule,
  dbSelectScheduleDetail,
  dbSelectScheduleList,
  dbUpdateSchedule,
} from "../Database/scheduleRepository";
import { dbSelectRunHistoryPage } from "../Database/runHistoryRepository";
import { fileDeleteExecutorPackage, fileOpenFolder } from "../FileSystem/executorFiles";
import { importProjectPackage } from "../Package/packageImport";
import { pythonCancel, pythonRun } from "../Run/projectRunner";
import { loggerMain } from "../Logging/logger";
import {
  cancelWaitingRun,
  getRunQueueItems,
  refreshSchedulerEngine,
} from "../Scheduler/schedulerEngine";
import {
  ensureRunHistoryOptions,
  ensureInvokeCommand,
  ensureNoData,
  ensurePackageRef,
  ensurePositiveIntegerData,
  ensureProjectRef,
  ensureProjectRun,
  ensureProjectUpdate,
  ensureRendererLogLevel,
  ensureScheduleCreate,
  ensureScheduleUpdate,
  ensureStringData,
  ensureWaitingRunRef,
} from "./validation";
import { IPC_CHANNEL_RENDERER_INVOKE, IPC_CHANNEL_RENDERER_LOG } from "../../shared/ipc";
import type {
  DictInvokeResult,
  TypeExecutorInvokeCommand,
  TypeExecutorInvokeRequest,
  TypeExecutorInvokeResponse,
} from "../../shared/ipc";

function getErrorMessage(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

function createSuccessResult<T>(data: T): DictInvokeResult<T> {
  return { success: true, data };
}

function createErrorResult(e: unknown): DictInvokeResult<never> {
  return { success: false, error: getErrorMessage(e) };
}

type ExecutorInvokeValidatorMap = {
  [C in TypeExecutorInvokeCommand]: (rawData: unknown) => TypeExecutorInvokeRequest<C>;
};

type ExecutorInvokeHandlerMap = {
  [C in TypeExecutorInvokeCommand]: (
    data: TypeExecutorInvokeRequest<C>,
  ) => TypeExecutorInvokeResponse<C> | Promise<TypeExecutorInvokeResponse<C>>;
};

const INVOKE_VALIDATOR = {
  openProjectLogFolder: (rawData: unknown) =>
    ensureStringData(rawData, "openProjectLogFolder"),
  saveExecutorConfig: (rawData: unknown) => validateExecutorConfig(rawData),
  pythonRun: ensureProjectRun,
  getPythonEnvironmentNames: (rawData: unknown) =>
    ensureNoData(rawData, "getPythonEnvironmentNames"),
  importProjectPackage: (rawData: unknown) => ensureNoData(rawData, "importProjectPackage"),
  deleteExecutorPackage: ensurePackageRef,
  getProjectNames: (rawData: unknown) => ensureNoData(rawData, "getProjectNames"),
  getProjectVersions: (rawData: unknown) => ensureStringData(rawData, "getProjectVersions"),
  getProjectDetail: ensureProjectRef,
  saveProjectDetail: ensureProjectUpdate,
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
  cancelWaitingRun: ensureWaitingRunRef,
  openFolder: (rawData: unknown) => ensureStringData(rawData, "openFolder"),
  getNewestProjectVersionDetail: (rawData: unknown) =>
    ensureStringData(rawData, "getNewestProjectVersionDetail"),
  pythonCancel: (rawData: unknown) => ensurePositiveIntegerData(rawData, "pythonCancel"),
  chooseProjectLogFolder: (rawData: unknown) =>
    ensureNoData(rawData, "chooseProjectLogFolder"),
} satisfies ExecutorInvokeValidatorMap;

function createInvokeHandlerMap(): ExecutorInvokeHandlerMap {
  return {
    async openProjectLogFolder(strFolderPath) {
      await fileOpenFolder(strFolderPath);
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

    async pythonRun(dictDetail) {
      await pythonRun(dictDetail);
    },

    getPythonEnvironmentNames() {
      return getPythonEnvironmentNames();
    },

    async importProjectPackage() {
      return await importProjectPackage();
    },

    deleteExecutorPackage(dictPackage) {
      fileDeleteExecutorPackage(dictPackage.name, dictPackage.version);
    },

    getProjectNames() {
      return dbSelectProjectNames();
    },

    getProjectVersions(strName) {
      return dbSelectProjectVersions(strName);
    },

    getProjectDetail(dictProject) {
      return dbSelectProjectDetail(dictProject.name, dictProject.version);
    },

    saveProjectDetail(dictDetail) {
      getPythonEnvironmentPath(dictDetail.python_environment_name);
      dbUpdateProjectDetail(dictDetail);
    },

    getProjectBoundSchedules(intProjectId) {
      return dbSelectProjectBoundSchedules(intProjectId);
    },

    deleteProject(intProjectId) {
      dbDeleteProject(intProjectId);
    },

    getScheduleList() {
      return dbSelectScheduleList();
    },

    getScheduleDetail(strName) {
      return dbSelectScheduleDetail(strName);
    },

    createSchedule(dictDetail) {
      dbInsertSchedule(dictDetail);
      refreshSchedulerEngine();
    },

    saveSchedule(dictDetail) {
      dbUpdateSchedule(dictDetail);
      refreshSchedulerEngine();
    },

    deleteSchedule(intScheduleId) {
      dbDeleteSchedule(intScheduleId);
      refreshSchedulerEngine();
    },

    getRunHistoryPage(options) {
      return dbSelectRunHistoryPage(options);
    },

    getRunQueue() {
      return getRunQueueItems();
    },

    cancelWaitingRun(dictRun) {
      cancelWaitingRun(dictRun.schedule_name, dictRun.estimated_run_at_ms);
    },

    async openFolder(strFolderPath) {
      await fileOpenFolder(strFolderPath);
    },

    getNewestProjectVersionDetail(strName) {
      return dbSelectProjectNewestVersionDetail(strName);
    },

    pythonCancel(intRunHistoryId) {
      pythonCancel(intRunHistoryId);
    },

    async chooseProjectLogFolder() {
      return await chooseProjectLogFolder();
    },
  };
}

async function executeInvoke<C extends TypeExecutorInvokeCommand>(
  command: C,
  rawData: unknown,
  validatorMap: ExecutorInvokeValidatorMap,
  handlerMap: ExecutorInvokeHandlerMap,
): Promise<TypeExecutorInvokeResponse<C>> {
  const data = validatorMap[command](rawData);
  return await handlerMap[command](data);
}

export function registerExecutorIpc(): void {
  const invokeHandlerMap = createInvokeHandlerMap();

  ipcMain.on(
    IPC_CHANNEL_RENDERER_LOG,
    (_event: IpcMainEvent, rawLevel: unknown, rawMessage: unknown): void => {
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
      _event: IpcMainInvokeEvent,
      rawCommand: unknown,
      rawData: unknown,
    ): Promise<DictInvokeResult<unknown>> => {
      let strCommandForLog = String(rawCommand);
      try {
        const command = ensureInvokeCommand(rawCommand);
        strCommandForLog = command;
        loggerMain.debug(
          `[renderer-invoke] (${command}) ${JSON.stringify(rawData, null, 2)}`,
        );

        const data = await executeInvoke(
          command,
          rawData,
          INVOKE_VALIDATOR,
          invokeHandlerMap,
        );
        return createSuccessResult(data);
      } catch (e: unknown) {
        loggerMain.error(`Error running IPC command: ${strCommandForLog}`, e);
        return createErrorResult(e);
      }
    },
  );
}
