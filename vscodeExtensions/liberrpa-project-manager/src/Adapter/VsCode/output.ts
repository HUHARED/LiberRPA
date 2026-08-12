// FileName: output.ts

import * as vscode from "vscode";

const SHOW_LOGS_ACTION = "Show Logs";

export const log = vscode.window.createOutputChannel("liberrpa-project-manager", {
  log: true,
});

// Show the output channel automatically during development.
// It can help users learn more information.
// Remove this before publishing if it becomes too intrusive.
// log.show(true);

export function showLogs(): void {
  log.show();
}

export async function showErrorMessageWithLogs(message: string): Promise<void> {
  const strSelectedAction = await vscode.window.showErrorMessage(message, SHOW_LOGS_ACTION);
  if (strSelectedAction === SHOW_LOGS_ACTION) {
    showLogs();
  }
}

export async function showWarningMessageWithLogs(message: string): Promise<void> {
  const strSelectedAction = await vscode.window.showWarningMessage(
    message,
    SHOW_LOGS_ACTION,
  );
  if (strSelectedAction === SHOW_LOGS_ACTION) {
    showLogs();
  }
}
