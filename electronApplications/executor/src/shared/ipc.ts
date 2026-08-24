// FileName: ipc.ts

import type { DictExecutorConfig } from "./config";
import type {
  DictProjectDetail,
  DictProjectPackageImportResult,
  DictProjectUpdate,
} from "./project";
import type {
  DictProjectRunDetail,
  DictRunHistoryOptions,
  DictRunHistoryPage,
  DictRunQueueListItem,
} from "./run";
import type {
  DictScheduleCreate,
  DictScheduleDetail,
  DictScheduleListItem,
  DictScheduleUpdate,
} from "./schedule";

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
    request: DictProjectRunDetail;
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
  getProjectNames: {
    request: undefined;
    response: { name: string }[];
  };
  getProjectVersions: {
    request: string;
    response: { version: string }[];
  };
  getProjectDetail: {
    request: { name: string; version: string };
    response: DictProjectDetail | undefined;
  };
  saveProjectDetail: {
    request: DictProjectUpdate;
    response: void;
  };
  getProjectBoundSchedules: {
    request: number;
    response: { name: string }[];
  };
  deleteProject: {
    request: number;
    response: void;
  };
  getScheduleList: {
    request: undefined;
    response: DictScheduleListItem[];
  };
  getScheduleDetail: {
    request: string;
    response: DictScheduleDetail | undefined;
  };
  createSchedule: {
    request: DictScheduleCreate;
    response: void;
  };
  saveSchedule: {
    request: DictScheduleUpdate;
    response: void;
  };
  deleteSchedule: {
    request: number;
    response: void;
  };
  getRunHistoryPage: {
    request: DictRunHistoryOptions;
    response: DictRunHistoryPage;
  };
  getRunQueue: {
    request: undefined;
    response: DictRunQueueListItem[];
  };
  cancelWaitingRun: {
    request: {
      schedule_name: string;
      estimated_run_at_ms: number;
    };
    response: void;
  };
  openFolder: {
    request: string;
    response: void;
  };
  getNewestProjectVersionDetail: {
    request: string;
    response: DictProjectDetail | undefined;
  };
  pythonCancel: {
    request: number;
    response: void;
  };
  chooseProjectLogFolder: {
    request: undefined;
    response: string | null;
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
      data: {
        config: DictExecutorConfig;
        defaultProjectLogFolderPath: string;
      };
    }
  | {
      type: "runEnded";
    }
  | {
      type: "runQueueChanged";
      data: {
        items: DictRunQueueListItem[];
      };
    };

export interface ExecutorPreloadApi {
  sendLog(level: TypeRendererLogLevel, message: string): void;

  invoke<C extends TypeExecutorInvokeCommand>(
    command: C,
    ...args: TypeIpcArgs<TypeExecutorInvokeRequest<C>>
  ): Promise<DictInvokeResult<TypeExecutorInvokeResponse<C>>>;

  onMainMessage(listener: (message: DictMainMessage) => void): () => void;
}
