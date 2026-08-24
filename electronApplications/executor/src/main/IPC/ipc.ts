import { ipcMain } from "electron";
import type { IpcMainEvent, IpcMainInvokeEvent, WebContents } from "electron";

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
  dbSelectRunHistoryLogPath,
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
import { importProjectPackage } from "../Package/packageImport";
import { deleteInstalledProject } from "../Package/projectInstallation";
import {
  runInstalledProject,
  runMostRecentlyImportedProjectVersion,
} from "../Run/manualRun";
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
  openProjectLogFolder: (rawData: unknown) => ensureNoData(rawData, "openProjectLogFolder"),
  saveExecutorConfig: (rawData: unknown) => validateExecutorConfig(rawData),
  runProject: (rawData: unknown) => ensurePositiveIntegerData(rawData, "runProject"),
  getPythonEnvironmentNames: (rawData: unknown) =>
    ensureNoData(rawData, "getPythonEnvironmentNames"),
  importProjectPackage: (rawData: unknown) => ensureNoData(rawData, "importProjectPackage"),
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
  cancelWaitingRun: ensureWaitingRunRef,
  openRunLogFolder: (rawData: unknown) =>
    ensurePositiveIntegerData(rawData, "openRunLogFolder"),
  runMostRecentlyImportedProjectVersion: (rawData: unknown) =>
    ensureStringData(rawData, "runMostRecentlyImportedProjectVersion"),
  pythonCancel: (rawData: unknown) => ensurePositiveIntegerData(rawData, "pythonCancel"),
  chooseProjectLogFolder: (rawData: unknown) =>
    ensureNoData(rawData, "chooseProjectLogFolder"),
} satisfies ExecutorInvokeValidatorMap;

function createInvokeHandlerMap(): ExecutorInvokeHandlerMap {
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

    async importProjectPackage() {
      return await importProjectPackage();
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

    saveProjectSettings(dictDetail) {
      getPythonEnvironmentPath(dictDetail.python_environment_name);
      dbUpdateProjectSettings(dictDetail);
    },

    getProjectBoundSchedules(intProjectId) {
      return dbSelectProjectBoundSchedules(intProjectId);
    },

    deleteProject(intProjectId) {
      deleteInstalledProject(intProjectId);
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

    async openRunLogFolder(intRunHistoryId) {
      const strLogFolderPath = dbSelectRunHistoryLogPath(intRunHistoryId);
      if (strLogFolderPath === undefined) {
        throw new Error(`Run History record not found: ${intRunHistoryId}`);
      }
      await fileOpenFolder(strLogFolderPath);
    },

    async runMostRecentlyImportedProjectVersion(strProjectName) {
      await runMostRecentlyImportedProjectVersion(strProjectName);
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
    ): Promise<DictInvokeResult<unknown>> => {
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
        loggerMain.error(`Error running IPC command: ${strCommandForLog}`, e);
        return createErrorResult(e);
      }
    },
  );
}
