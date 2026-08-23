// FileName: ipc.ts

import { ipcMain } from "electron";
import type { IpcMainEvent, IpcMainInvokeEvent, WebContents } from "electron";

import {
  dictConfigExecutor,
  getPythonEnvironmentNames,
  getPythonEnvironmentPath,
  saveExecutorConfigDict,
  selectProjectLogFolder,
  validateExecutorConfig,
} from "./commonFunc";
import {
  dbDeleteProject,
  dbDeleteScheduler,
  dbInsertSchedulerDetail,
  dbSelectCountHistoryRunning,
  dbSelectLimitHistoryList,
  dbSelectProjectBindSchedulers,
  dbSelectProjectDetail,
  dbSelectProjectNames,
  dbSelectProjectNewestVersionDetail,
  dbSelectProjectVersions,
  dbSelectSchedulerDetail,
  dbSelectSchedulerList,
  dbUpdateProjectDetail,
  dbUpdateSchedulerDetail,
} from "./database";
import { fileDeleteExecutorPackage, fileOpenFolder } from "./fileFunc";
import { importProjectPackage } from "./packageImport";
import { pythonCancel, pythonRun } from "./pythonFunc";
import {
  logCleanFolderByTimeout,
  logCleanVideoBySize,
  logCleanVideoByTimeout,
} from "./logCleanFunc";
import { loggerMain } from "./logger";
import {
  ensureHistoryOptions,
  ensureInvokeCommand,
  ensureNoData,
  ensureNonNegativeNumberData,
  ensurePackageRef,
  ensurePositiveIntegerData,
  ensureProjectRef,
  ensureProjectRun,
  ensureProjectUpdate,
  ensureRendererLogLevel,
  ensureSchedulerInsert,
  ensureSchedulerUpdate,
  ensureStringData,
} from "./ipcValidation";
import { IPC_CHANNEL_RENDERER_INVOKE, IPC_CHANNEL_RENDERER_LOG } from "../shared/ipc";
import type {
  DictInvokeResult,
  TypeExecutorInvokeCommand,
  TypeExecutorInvokeRequest,
  TypeExecutorInvokeResponse,
} from "../shared/ipc";

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
  selectProjectNames: (rawData: unknown) => ensureNoData(rawData, "selectProjectNames"),
  selectProjectVersions: (rawData: unknown) =>
    ensureStringData(rawData, "selectProjectVersions"),
  selectProjectDetail: ensureProjectRef,
  updateProjectDetail: ensureProjectUpdate,
  selectProjectBindSchedulers: (rawData: unknown) =>
    ensurePositiveIntegerData(rawData, "selectProjectBindSchedulers"),
  deleteProject: (rawData: unknown) => ensurePositiveIntegerData(rawData, "deleteProject"),
  selectSchedulerList: (rawData: unknown) => ensureNoData(rawData, "selectSchedulerList"),
  selectSchedulerDetail: (rawData: unknown) =>
    ensureStringData(rawData, "selectSchedulerDetail"),
  insertSchedulerDetail: ensureSchedulerInsert,
  updateSchedulerDetail: ensureSchedulerUpdate,
  deleteScheduler: (rawData: unknown) =>
    ensurePositiveIntegerData(rawData, "deleteScheduler"),
  selectHistoryList: ensureHistoryOptions,
  hasRunningHistory: (rawData: unknown) => ensureNoData(rawData, "hasRunningHistory"),
  openFolder: (rawData: unknown) => ensureStringData(rawData, "openFolder"),
  selectNewestProjectVersionDetail: (rawData: unknown) =>
    ensureStringData(rawData, "selectNewestProjectVersionDetail"),
  pythonCancel: (rawData: unknown) => ensurePositiveIntegerData(rawData, "pythonCancel"),
  selectProjectLogFolder: (rawData: unknown) =>
    ensureNoData(rawData, "selectProjectLogFolder"),
  cleanLogFoldersByTimeout: (rawData: unknown) =>
    ensureNonNegativeNumberData(rawData, "cleanLogFoldersByTimeout"),
  cleanVideosByTimeout: (rawData: unknown) =>
    ensureNonNegativeNumberData(rawData, "cleanVideosByTimeout"),
  cleanVideosBySize: (rawData: unknown) =>
    ensureNonNegativeNumberData(rawData, "cleanVideosBySize"),
} satisfies ExecutorInvokeValidatorMap;

function createInvokeHandlerMap(
  getWebContents: () => WebContents,
): ExecutorInvokeHandlerMap {
  return {
    async openProjectLogFolder(strFolderPath) {
      await fileOpenFolder(strFolderPath);
    },

    saveExecutorConfig(dictConfig) {
      saveExecutorConfigDict(dictConfig);
      // Other Main Process modules read this shared in-memory config.
      Object.assign(dictConfigExecutor, dictConfig);
    },

    async pythonRun(dictDetail) {
      await pythonRun(dictDetail, getWebContents());
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

    selectProjectNames() {
      return dbSelectProjectNames();
    },

    selectProjectVersions(strName) {
      return dbSelectProjectVersions(strName);
    },

    selectProjectDetail(dictProject) {
      return dbSelectProjectDetail(dictProject.name, dictProject.version);
    },

    updateProjectDetail(dictDetail) {
      getPythonEnvironmentPath(dictDetail.python_environment_name);
      dbUpdateProjectDetail(dictDetail);
    },

    selectProjectBindSchedulers(intProjectId) {
      return dbSelectProjectBindSchedulers(intProjectId);
    },

    deleteProject(intProjectId) {
      dbDeleteProject(intProjectId);
    },

    selectSchedulerList() {
      return dbSelectSchedulerList();
    },

    selectSchedulerDetail(strName) {
      return dbSelectSchedulerDetail(strName);
    },

    insertSchedulerDetail(dictDetail) {
      dbInsertSchedulerDetail(dictDetail);
    },

    updateSchedulerDetail(dictDetail) {
      dbUpdateSchedulerDetail(dictDetail);
    },

    deleteScheduler(intSchedulerId) {
      dbDeleteScheduler(intSchedulerId);
    },

    selectHistoryList(options) {
      return dbSelectLimitHistoryList(options);
    },

    hasRunningHistory() {
      return dbSelectCountHistoryRunning();
    },

    async openFolder(strFolderPath) {
      await fileOpenFolder(strFolderPath);
    },

    selectNewestProjectVersionDetail(strName) {
      return dbSelectProjectNewestVersionDetail(strName);
    },

    pythonCancel(intHistoryId) {
      pythonCancel(intHistoryId, getWebContents());
    },

    async selectProjectLogFolder() {
      return await selectProjectLogFolder();
    },

    cleanLogFoldersByTimeout(floatTimeoutDays) {
      logCleanFolderByTimeout(floatTimeoutDays);
    },

    cleanVideosByTimeout(floatTimeoutDays) {
      logCleanVideoByTimeout(floatTimeoutDays);
    },

    cleanVideosBySize(floatSizeGb) {
      logCleanVideoBySize(floatSizeGb);
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

export function registerExecutorIpc(getWebContents: () => WebContents): void {
  const invokeHandlerMap = createInvokeHandlerMap(getWebContents);

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
