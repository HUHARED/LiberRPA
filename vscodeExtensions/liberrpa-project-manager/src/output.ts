// FileName: output.ts
import * as vscode from "vscode";

export const log = vscode.window.createOutputChannel("liberrpa-project-manager", {
  log: true,
});

// Show the output channel automatically during development.
// Remove this before publishing if it becomes too intrusive.
log.show(true);
