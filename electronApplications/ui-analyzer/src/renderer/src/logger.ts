// FileName: logger.ts

import type { RendererLogLevel } from "../../shared/interface";

function formatLogMessage(message: unknown): string {
  if (typeof message === "string") {
    return message;
  }

  if (message instanceof Error) {
    return message.stack ?? message.message;
  }

  try {
    return JSON.stringify(message);
  } catch {
    return String(message);
  }
}

function sendLogToMain(level: RendererLogLevel, message: unknown): void {
  const strFormattedMessage = formatLogMessage(message);

  console.log(`[${level}] ${strFormattedMessage}`);
  window.uiAnalyzer.logToMain(level, strFormattedMessage);
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
