// FileName: output.ts
import * as vscode from "vscode";
export const outputChannel = vscode.window.createOutputChannel("liberrpa-snippets-tree");
outputChannel.show(true);
