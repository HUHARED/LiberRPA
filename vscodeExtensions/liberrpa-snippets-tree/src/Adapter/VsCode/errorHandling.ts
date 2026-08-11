// FileName: errorHandling.ts

import * as vscode from "vscode";

import { log } from "./output";

/**
 * Log an unexpected error and optionally notify the user.
 *
 * User notifications contain only the concise message.
 * The stack trace is written to the log channel at Debug level.
 */
export function reportError(context: string, error: unknown, notifyUser: boolean): void {
  const strMessage = error instanceof Error ? error.message : String(error);

  log.error(`[${context}] ${strMessage}`);

  if (error instanceof Error && error.stack) {
    log.debug(error.stack);
  }

  if (!notifyUser) {
    return;
  }

  void vscode.window
    .showErrorMessage(`${context}: ${strMessage}`, "Show Logs")
    .then((action: string | undefined) => {
      if (action === "Show Logs") {
        log.show(true);
      }
    });
}

/** Log a recoverable problem and optionally warn the user. */
export function reportWarning(context: string, error: unknown, notifyUser: boolean): void {
  const strMessage = error instanceof Error ? error.message : String(error);

  log.warn(`[${context}] ${strMessage}`);

  if (!notifyUser) {
    return;
  }

  void vscode.window
    .showWarningMessage(`${context}: ${strMessage}`, "Show Logs")
    .then((action: string | undefined) => {
      if (action === "Show Logs") {
        log.show(true);
      }
    });
}

/**
 * Error boundary for asynchronous VS Code entry points.
 */
export async function runAsyncBoundary(
  context: string,
  task: () => Promise<void>,
  notifyUser: boolean,
): Promise<void> {
  try {
    await task();
  } catch (e) {
    reportError(context, e, notifyUser);
  }
}

/**
 * Error boundary for synchronous VS Code entry points.
 */
export function runSyncBoundary<T>(
  context: string,
  task: () => T,
  fallback: T,
  notifyUser: boolean,
): T {
  try {
    return task();
  } catch (e) {
    reportError(context, e, notifyUser);
    return fallback;
  }
}
