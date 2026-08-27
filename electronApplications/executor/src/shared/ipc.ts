// FileName: ipc.ts

import type { Dict_ExecutorConfig } from "./config";
import type {
  Dict_ProjectDetail,
  Dict_ProjectPackage_ImportResult,
  Dict_ProjectSettingsUpdate,
} from "./project";
import type {
  Dict_RunHistory_Options,
  Dict_RunHistory_Page,
  Dict_ListItem_RunQueue,
} from "./run";
import type {
  Dict_ScheduleCreate,
  Dict_Detail_Schedule,
  Dict_ListItem_Schedule,
  Dict_ScheduleUpdate,
} from "./schedule";

export const IPC_CHANNEL_RENDERER_LOG = "executor:renderer-log";
export const IPC_CHANNEL_RENDERER_INVOKE = "executor:renderer-invoke";
export const IPC_CHANNEL_MAIN_MESSAGE = "executor:main-message";

export type Str_RendererLogLevel =
  | "error"
  | "warn"
  | "info"
  | "http"
  | "verbose"
  | "debug"
  | "silly";

export interface Dict_ExecutorInvoke_Contract {
  openProjectLogFolder: {
    request: undefined;
    response: void;
  };
  saveExecutorConfig: {
    request: Dict_ExecutorConfig;
    response: void;
  };
  runProject: {
    request: number;
    response: void;
  };
  getPythonEnvironmentNames: {
    request: undefined;
    response: string[];
  };
  importProjectPackage: {
    request: undefined;
    response: Dict_ProjectPackage_ImportResult;
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
    response: Dict_ProjectDetail | undefined;
  };
  saveProjectSettings: {
    request: Dict_ProjectSettingsUpdate;
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
    response: Dict_ListItem_Schedule[];
  };
  getScheduleDetail: {
    request: string;
    response: Dict_Detail_Schedule | undefined;
  };
  createSchedule: {
    request: Dict_ScheduleCreate;
    response: void;
  };
  saveSchedule: {
    request: Dict_ScheduleUpdate;
    response: void;
  };
  deleteSchedule: {
    request: number;
    response: void;
  };
  getRunHistoryPage: {
    request: Dict_RunHistory_Options;
    response: Dict_RunHistory_Page;
  };
  getRunQueue: {
    request: undefined;
    response: Dict_ListItem_RunQueue[];
  };
  cancelWaitingRun: {
    request: {
      schedule_name: string;
      estimated_run_at_ms: number;
    };
    response: void;
  };
  openRunLogFolder: {
    request: number;
    response: void;
  };
  runMostRecentlyImportedProjectVersion: {
    request: string;
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

export type Str_ExecutorInvokeCommand = keyof Dict_ExecutorInvoke_Contract;

export type Type_ExecutorInvoke_Request<C extends Str_ExecutorInvokeCommand> =
  Dict_ExecutorInvoke_Contract[C]["request"];
export type Type_ExecutorInvoke_Response<C extends Str_ExecutorInvokeCommand> =
  Dict_ExecutorInvoke_Contract[C]["response"];

export type TypeIpcArgs<T> = [T] extends [undefined] ? [] : [data: T];

export type Dict_Result_Invoke<T> =
  | {
      success: true;
      data: T;
    }
  | {
      success: false;
      error: string;
    };

export type Dict_Message_Main =
  | {
      type: "initializeSetting";
      data: {
        configDict: Dict_ExecutorConfig;
        defaultProjectLogFolderPath: string;
      };
    }
  | {
      type: "runEnded";
    }
  | {
      type: "runQueueChanged";
      data: {
        items: Dict_ListItem_RunQueue[];
      };
    };

export interface ExecutorPreloadApi {
  sendLog(level: Str_RendererLogLevel, message: string): void;

  invoke<C extends Str_ExecutorInvokeCommand>(
    command: C,
    ...args: TypeIpcArgs<Type_ExecutorInvoke_Request<C>>
  ): Promise<Dict_Result_Invoke<Type_ExecutorInvoke_Response<C>>>;

  onMainMessage(listener: (message: Dict_Message_Main) => void): () => void;
}
