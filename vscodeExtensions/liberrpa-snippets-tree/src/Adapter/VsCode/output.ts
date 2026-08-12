// FileName: output.ts
import * as vscode from "vscode";

export const log = vscode.window.createOutputChannel("liberrpa-snippets-tree", {
  log: true,
});

// Show the output channel automatically during development.
// It can help users learn more information.
// Remove this before publishing if it becomes too intrusive.
// log.show(true);
