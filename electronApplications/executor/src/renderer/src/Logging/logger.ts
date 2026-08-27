// FileName: logger.ts

import type { Str_RendererLogLevel } from "../../../shared/ipc";

function sendLogToMain(level: Str_RendererLogLevel, message: unknown): void {
  const strMessage = String(message);
  console.log(`[${level}] ${strMessage}`);
  window.executor.sendLog(level, strMessage);
}

export const loggerRenderer = {
  error: (message: unknown): void => sendLogToMain("error", message),
  warn: (message: unknown): void => sendLogToMain("warn", message),
  info: (message: unknown): void => sendLogToMain("info", message),
  http: (message: unknown): void => sendLogToMain("http", message),
  verbose: (message: unknown): void => sendLogToMain("verbose", message),
  debug: (message: unknown): void => sendLogToMain("debug", message),
  silly: (message: unknown): void => sendLogToMain("silly", message),
};
