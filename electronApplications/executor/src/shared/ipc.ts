// FileName: ipc.ts

import type {
  DictColumns_History_ListItem_Limit_DB,
  DictColumns_Project_Detail_DB,
  DictColumns_Project_Detail_Run,
  DictColumns_Project_Detail_ToUpdate,
  DictColumns_Scheduler_Detail_DB,
  DictColumns_Scheduler_Detail_ToInsert,
  DictColumns_Scheduler_Detail_ToUpdate,
  DictColumns_Scheduler_ListItem_DB,
  DictExecutorConfig,
  Dict_History_Options,
  DictProjectPackageImportResult,
} from "./interface";

export const IPC_CHANNEL_RENDERER_LOG = "executor:renderer-log";
export const IPC_CHANNEL_RENDERER_INVOKE = "executor:renderer-invoke";
export const IPC_CHANNEL_MAIN_MESSAGE = "executor:main-message";

export type TypeRendererLogLevel =
  | "error"
  | "warn"
  | "info"
  | "http"
  | "verbose"
  | "debug"
  | "silly";

export interface DictExecutorInvokeContract {
  openProjectLogFolder: {
    request: string;
    response: void;
  };
  saveExecutorConfig: {
    request: DictExecutorConfig;
    response: void;
  };
  pythonRun: {
    request: DictColumns_Project_Detail_Run;
    response: void;
  };
  getPythonEnvironmentNames: {
    request: undefined;
    response: string[];
  };
  importProjectPackage: {
    request: undefined;
    response: DictProjectPackageImportResult;
  };
  deleteExecutorPackage: {
    request: { name: string; version: string };
    response: void;
  };
  selectProjectNames: {
    request: undefined;
    response: { name: string }[];
  };
  selectProjectVersions: {
    request: string;
    response: { version: string }[];
  };
  selectProjectDetail: {
    request: { name: string; version: string };
    response: DictColumns_Project_Detail_DB | undefined;
  };
  updateProjectDetail: {
    request: DictColumns_Project_Detail_ToUpdate;
    response: void;
  };
  selectProjectBindSchedulers: {
    request: number;
    response: { name: string }[];
  };
  deleteProject: {
    request: number;
    response: void;
  };
  selectSchedulerList: {
    request: undefined;
    response: DictColumns_Scheduler_ListItem_DB[];
  };
  selectSchedulerDetail: {
    request: string;
    response: DictColumns_Scheduler_Detail_DB | undefined;
  };
  insertSchedulerDetail: {
    request: DictColumns_Scheduler_Detail_ToInsert;
    response: void;
  };
  updateSchedulerDetail: {
    request: DictColumns_Scheduler_Detail_ToUpdate;
    response: void;
  };
  deleteScheduler: {
    request: number;
    response: void;
  };
  selectHistoryList: {
    request: Dict_History_Options;
    response: DictColumns_History_ListItem_Limit_DB;
  };
  hasRunningHistory: {
    request: undefined;
    response: boolean;
  };
  openFolder: {
    request: string;
    response: void;
  };
  selectNewestProjectVersionDetail: {
    request: string;
    response: DictColumns_Project_Detail_DB | undefined;
  };
  pythonCancel: {
    request: number;
    response: void;
  };
  selectProjectLogFolder: {
    request: undefined;
    response: string | null;
  };
  cleanLogFoldersByTimeout: {
    request: number;
    response: void;
  };
  cleanVideosByTimeout: {
    request: number;
    response: void;
  };
  cleanVideosBySize: {
    request: number;
    response: void;
  };
}

export type TypeExecutorInvokeCommand = keyof DictExecutorInvokeContract;

export type TypeExecutorInvokeRequest<C extends TypeExecutorInvokeCommand> =
  DictExecutorInvokeContract[C]["request"];
export type TypeExecutorInvokeResponse<C extends TypeExecutorInvokeCommand> =
  DictExecutorInvokeContract[C]["response"];

export type TypeIpcArgs<T> = [T] extends [undefined] ? [] : [data: T];

export type DictInvokeResult<T> =
  | {
      success: true;
      data: T;
    }
  | {
      success: false;
      error: string;
    };

export type DictMainMessage =
  | {
      type: "initializeSetting";
      data: DictExecutorConfig;
    }
  | {
      type: "pythonTaskEnded";
    };

export interface ExecutorPreloadApi {
  sendLog(level: TypeRendererLogLevel, message: string): void;

  invoke<C extends TypeExecutorInvokeCommand>(
    command: C,
    ...args: TypeIpcArgs<TypeExecutorInvokeRequest<C>>
  ): Promise<DictInvokeResult<TypeExecutorInvokeResponse<C>>>;

  onMainMessage(listener: (message: DictMainMessage) => void): () => void;
}
