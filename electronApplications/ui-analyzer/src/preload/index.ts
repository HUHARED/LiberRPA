// FileName: index.ts
import { contextBridge, ipcRenderer } from "electron";
import type {
  DictBasicConfig,
  DictInvokeResult,
  MainInvokeCommand,
  RendererLogLevel,
} from "../shared/interface";

const SET_ALLOWED_INVOKE_COMMANDS = new Set<MainInvokeCommand>([
  "cmd-minimize-window",
  "cmd-restore-window",
  "cmd-toggle-socket-status",
]);

const SET_ALLOWED_LOG_LEVELS = new Set<RendererLogLevel>([
  "error",
  "warn",
  "info",
  "http",
  "verbose",
  "debug",
  "silly",
]);

function isDictInvokeResult(value: unknown): value is DictInvokeResult {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const dictValue = value as Record<string, unknown>;

  if (dictValue.success === true) {
    return true;
  }

  return dictValue.success === false && typeof dictValue.data === "string";
}

function isDictBasicConfig(value: unknown): value is DictBasicConfig {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const dictValue = value as Record<string, unknown>;

  return (
    typeof dictValue.outputLogPath === "string" &&
    typeof dictValue.localServerPort === "number" &&
    (dictValue.uiAnalyzerTheme === "light" || dictValue.uiAnalyzerTheme === "dark") &&
    typeof dictValue.uiAnalyzerMinimizeWindow === "boolean" &&
    typeof dictValue.componentRepositoryPath === "string"
  );
}

function isInitSettingData(data: unknown): data is [DictBasicConfig, string] {
  if (!Array.isArray(data) || data.length !== 2) {
    return false;
  }

  const [dictBasicConfig, token] = data;

  return isDictBasicConfig(dictBasicConfig) && typeof token === "string";
}

const uiAnalyzerApi = {
  logToMain(level: RendererLogLevel, message: string): void {
    if (!SET_ALLOWED_LOG_LEVELS.has(level)) {
      ipcRenderer.send("send-from-renderer-log", {
        level: "info",
        message: `Blocked unknown log level: ${level}`,
      });
      return;
    }

    ipcRenderer.send("send-from-renderer-log", { level, message });
  },

  async invokeMain(command: MainInvokeCommand, data?: unknown): Promise<DictInvokeResult> {
    if (!SET_ALLOWED_INVOKE_COMMANDS.has(command)) {
      return {
        success: false,
        data: `Blocked IPC command: ${command}`,
      };
    }

    const result: unknown = await ipcRenderer.invoke("invoke-from-renderer", command, data);

    if (!isDictInvokeResult(result)) {
      return {
        success: false,
        data: "Invalid IPC response from main process.",
      };
    }

    return result;
  },

  onInitSetting(callback: (data: [DictBasicConfig, string]) => void): () => void {
    const listener = (
      _event: Electron.IpcRendererEvent,
      command: string,
      data?: unknown,
    ): void => {
      if (command !== "init-setting") {
        return;
      }

      if (!isInitSettingData(data)) {
        return;
      }

      callback(data);
    };

    ipcRenderer.on("send-from-main", listener);

    return () => {
      ipcRenderer.off("send-from-main", listener);
    };
  },
};

contextBridge.exposeInMainWorld("uiAnalyzer", uiAnalyzerApi);
