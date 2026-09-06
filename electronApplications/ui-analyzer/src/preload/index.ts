// FileName: index.ts

import { contextBridge, ipcRenderer } from "electron";
import type {
  DictInvokeResult,
  MainInvokeCommand,
  RendererLogLevel,
  UiAnalyzerInitialization,
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

const SET_INITIALIZATION_KEYS = new Set([
  "localServerPort",
  "theme",
  "minimizeWindow",
  "token",
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

function isUiAnalyzerInitialization(value: unknown): value is UiAnalyzerInitialization {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return false;
  }

  const dictValue = value as Record<string, unknown>;
  const arrKey = Object.keys(dictValue);

  return (
    arrKey.length === SET_INITIALIZATION_KEYS.size &&
    arrKey.every((strKey) => SET_INITIALIZATION_KEYS.has(strKey)) &&
    typeof dictValue.localServerPort === "number" &&
    Number.isSafeInteger(dictValue.localServerPort) &&
    dictValue.localServerPort >= 1 &&
    dictValue.localServerPort <= 65_535 &&
    (dictValue.theme === "light" || dictValue.theme === "dark") &&
    typeof dictValue.minimizeWindow === "boolean" &&
    typeof dictValue.token === "string" &&
    dictValue.token.trim() !== ""
  );
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

  onInitSetting(callback: (data: UiAnalyzerInitialization) => void): () => void {
    const listener = (
      _event: Electron.IpcRendererEvent,
      command: string,
      data?: unknown,
    ): void => {
      if (command !== "init-setting") {
        return;
      }

      if (!isUiAnalyzerInitialization(data)) {
        ipcRenderer.send("send-from-renderer-log", {
          level: "error",
          message: "Blocked invalid UI Analyzer initialization payload.",
        });
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
