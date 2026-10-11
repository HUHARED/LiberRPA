// FileName: ipc.ts

import type {
  ConsoleAccountState,
  ConsoleExecutorPage,
  ConsoleSignInArgs,
} from "./consoleAccount";
import type { ExecutorConfig } from "./config";
import type {
  ProjectDetails,
  ProjectPackageInstallResult,
  ProjectSettingsUpdate,
} from "./project";
import type {
  RunDetails,
  RunHistoryQueryOptions,
  RunHistoryPage,
  JobQueueItem,
} from "./run";
import type {
  ScheduleCreateData,
  ScheduleDetails,
  ScheduleListItem,
  ScheduleUpdateData,
} from "./schedule";

export const IPC_CHANNEL_RENDERER_LOG = "executor:renderer-log";
export const IPC_CHANNEL_RENDERER_INVOKE = "executor:renderer-invoke";
export const IPC_CHANNEL_MAIN_MESSAGE = "executor:main-message";

export type RendererLogLevel =
  | "error"
  | "warn"
  | "info"
  | "http"
  | "verbose"
  | "debug"
  | "silly";

interface ExecutorInvokeContract {
  getConsoleAccount: { request: undefined; response: ConsoleAccountState };
  saveConsoleAddress: { request: string; response: ConsoleAccountState };
  signInConsole: { request: ConsoleSignInArgs; response: ConsoleAccountState };
  getConsoleExecutorChoices: { request: number; response: ConsoleExecutorPage };
  associateConsoleExecutor: { request: string; response: ConsoleAccountState };
  signOutConsole: { request: undefined; response: ConsoleAccountState };
  openProjectLogFolder: {
    request: undefined;
    response: void;
  };
  saveExecutorConfig: {
    request: ExecutorConfig;
    response: void;
  };
  runProject: {
    request: ProjectSettingsUpdate;
    response: void;
  };
  getPythonEnvironmentNames: {
    request: undefined;
    response: string[];
  };
  installProjectPackage: {
    request: undefined;
    response: ProjectPackageInstallResult;
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
    response: ProjectDetails | undefined;
  };
  saveProjectSettings: {
    request: ProjectSettingsUpdate;
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
    response: ScheduleListItem[];
  };
  getScheduleDetail: {
    request: string;
    response: ScheduleDetails | undefined;
  };
  createSchedule: {
    request: ScheduleCreateData;
    response: void;
  };
  saveSchedule: {
    request: ScheduleUpdateData;
    response: void;
  };
  setScheduleEnabled: { request: { id: number; enabled: boolean }; response: void };
  deleteSchedule: {
    request: number;
    response: void;
  };
  getRunDetails: { request: number; response: RunDetails };
  getRunHistoryPage: {
    request: RunHistoryQueryOptions;
    response: RunHistoryPage;
  };
  getJobQueue: {
    request: undefined;
    response: JobQueueItem[];
  };
  cancelQueuedRun: {
    request: string;
    response: void;
  };
  openRunLogFolder: {
    request: number;
    response: void;
  };
  rerunLocalRun: {
    request: number;
    response: void;
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

export type ExecutorInvokeCommand = keyof ExecutorInvokeContract;

export type ExecutorInvokeRequest<C extends ExecutorInvokeCommand> =
  ExecutorInvokeContract[C]["request"];
export type ExecutorInvokeResponse<C extends ExecutorInvokeCommand> =
  ExecutorInvokeContract[C]["response"];

export type TypeIpcArgs<T> = [T] extends [undefined] ? [] : [data: T];

export type InvokeResult<T> =
  | {
      success: true;
      data: T;
    }
  | {
      success: false;
      error: string;
    };

export type MainMessage =
  | { type: "consoleAccountChanged"; data: ConsoleAccountState }
  | {
      type: "initializeSetting";
      data: {
        configDict: ExecutorConfig;
        defaultProjectLogFolderPath: string;
      };
    }
  | {
      type: "runEnded";
    }
  | {
      type: "jobQueueChanged";
      data: {
        items: JobQueueItem[];
      };
    };

export interface ExecutorPreloadApi {
  sendLog(level: RendererLogLevel, message: string): void;

  invoke<C extends ExecutorInvokeCommand>(
    command: C,
    ...args: TypeIpcArgs<ExecutorInvokeRequest<C>>
  ): Promise<InvokeResult<ExecutorInvokeResponse<C>>>;

  onMainMessage(listener: (message: MainMessage) => void): () => void;
}
