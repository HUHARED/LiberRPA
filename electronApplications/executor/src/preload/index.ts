// FileName: index.ts

import { contextBridge, ipcRenderer } from "electron";

import {
  IPC_CHANNEL_MAIN_MESSAGE,
  IPC_CHANNEL_RENDERER_INVOKE,
  IPC_CHANNEL_RENDERER_LOG,
} from "../shared/ipc";
import type { Dict_Message_Main, ExecutorPreloadApi } from "../shared/ipc";

const sendLog: ExecutorPreloadApi["sendLog"] = (level, message) => {
  ipcRenderer.send(IPC_CHANNEL_RENDERER_LOG, level, message);
};

const invoke: ExecutorPreloadApi["invoke"] = (command, ...args) => {
  return ipcRenderer.invoke(IPC_CHANNEL_RENDERER_INVOKE, command, args[0]);
};

const onMainMessage: ExecutorPreloadApi["onMainMessage"] = (listener) => {
  const handleMessage = (
    _event: Electron.IpcRendererEvent,
    message: Dict_Message_Main,
  ): void => {
    listener(message);
  };

  ipcRenderer.on(IPC_CHANNEL_MAIN_MESSAGE, handleMessage);
  return () => {
    ipcRenderer.removeListener(IPC_CHANNEL_MAIN_MESSAGE, handleMessage);
  };
};

const executorApi: ExecutorPreloadApi = {
  sendLog,
  invoke,
  onMainMessage,
};

contextBridge.exposeInMainWorld("executor", executorApi);
