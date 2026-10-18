// FileName: ipc.ts

import type {
  ConsoleAccountState,
  ConsoleExecutorPage,
  ConsoleSignInArgs,
} from "./consoleAccount";
import type { ExecutorConfig } from "./config";
import type { PackageDetails, PackageInstallResult, PackageSettings } from "./package";
import type {
  RunDetails,
  RunHistoryQueryOptions,
  RunHistoryPage,
  JobQueueItem,
} from "./run";
import type {
  ScheduleListItem,
  ScheduleDetails,
  ScheduleCreateData,
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
  // Packages.
  getPythonEnvironmentNames: {
    request: undefined;
    response: string[];
  };
  getProjectNames: {
    request: undefined;
    response: string[];
  };
  getProjectVersions: {
    request: string;
    response: string[];
  };
  getPackageDetails: {
    request: { project_name: string; project_version: string };
    response: PackageDetails | undefined;
  };
  installPackage: {
    request: undefined;
    response: PackageInstallResult;
  };
  savePackageSettings: {
    request: PackageSettings;
    response: void;
  };
  runPackage: {
    request: PackageSettings;
    response: void;
  };
  getPackageBoundSchedules: {
    request: number;
    response: { name: string }[];
  };
  deletePackage: {
    request: number;
    response: void;
  };

  // Schedules.
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

  // Job Queue.
  getJobQueue: {
    request: undefined;
    response: JobQueueItem[];
  };
  cancelQueuedRun: {
    request: string;
    response: void;
  };

  // Run History.
  getRunHistoryPage: {
    request: RunHistoryQueryOptions;
    response: RunHistoryPage;
  };
  getRunDetails: { request: number; response: RunDetails };
  openRunLogFolder: {
    request: number;
    response: void;
  };
  pythonCancel: {
    request: number;
    response: void;
  };
  getLocalRerunPackage: {
    request: number;
    response: PackageDetails;
  };

  // Settings.
  saveExecutorConfig: {
    request: ExecutorConfig;
    response: void;
  };
  chooseProjectLogFolder: {
    request: undefined;
    response: string | null;
  };
  openProjectLogFolder: {
    request: undefined;
    response: void;
  };

  // Console.
  getConsoleAccount: { request: undefined; response: ConsoleAccountState };
  saveConsoleAddress: { request: string; response: ConsoleAccountState };
  signInConsole: { request: ConsoleSignInArgs; response: ConsoleAccountState };
  getConsoleExecutorChoices: { request: number; response: ConsoleExecutorPage };
  associateConsoleExecutor: { request: string; response: ConsoleAccountState };
  signOutConsole: { request: undefined; response: ConsoleAccountState };
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
  | {
      type: "initializeSetting";
      data: {
        configDict: ExecutorConfig;
        defaultProjectLogFolderPath: string;
      };
    }
  | { type: "consoleAccountChanged"; data: ConsoleAccountState }
  | {
      type: "runHistoryChanged";
      data: { historyId: number };
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
