// FileName: extension.ts
import { log } from "./output";
import type { SnippetNodeCommandArg, SnippetCompletionCommandArg } from "./interface";

import { SnippetTreeDataProvider, checkWhetherHandleDrop } from "./treeViewProvider";
import { LiberRPACompletionItemProvider } from "./completionProvider";

import { insertSnippet } from "./utils";
import { getImportManifest } from "./handleSnippets";
import { updateManagedImports } from "./managedImports";
import * as vscode from "vscode";

export function activate(context: vscode.ExtensionContext): void {
  console.log(
    `[liberrpa-snippets-tree] Current log level: ${vscode.LogLevel[log.logLevel]}`,
  );

  log.info("LiberRPA Snippets Tree activated.");

  /* TreeView-related */
  const treeViewProvider = new SnippetTreeDataProvider();
  context.subscriptions.push(
    vscode.window.createTreeView("LiberRPA.snippetsTreeView", {
      treeDataProvider: treeViewProvider,
      showCollapseAll: true,
      canSelectMany: false,
      dragAndDropController: treeViewProvider,
    }),
  );
  context.subscriptions.push(
    vscode.commands.registerCommand(
      "LiberRPA.insertSnippetByNodeClicking",
      async (arg: SnippetNodeCommandArg): Promise<void> => {
        try {
          // Click insertion path:
          // TreeItem.command -> LiberRPA.insertSnippetByNodeClicking -> insert snippet -> update imports.
          log.debug(
            `[Click] Inserting snippet: ${arg.title}, imports=[${arg.importNames.join(", ")}].`,
          );

          /* Insert the snippet. */
          const inserted = await insertSnippet(arg.body);
          if (!inserted) {
            log.error(`[Click] Failed to insert snippet: ${arg.title}.`);
            void vscode.window.showWarningMessage(
              `Failed to insert LiberRPA snippet: ${arg.title}`,
            );
            return;
          }

          /* Update imports. */
          const editor = vscode.window.activeTextEditor;
          if (!editor) {
            log.error(`[Click] No active editor after inserting snippet: ${arg.title}.`);
            void vscode.window.showWarningMessage(
              "No active editor for updating LiberRPA imports.",
            );
            return;
          }
          await updateManagedImports(editor, getImportManifest(), arg.importNames);

          log.debug(`[Click] Snippet inserted: ${arg.title}.`);
        } catch (e) {
          log.error(
            `[Click] Failed to insert LiberRPA snippet: ${e instanceof Error ? e.message : String(e)}`,
          );
          void vscode.window.showErrorMessage(
            `Failed to insert LiberRPA snippet: ${e instanceof Error ? e.message : String(e)}`,
          );
        }
      },
    ),
  );
  context.subscriptions.push(
    vscode.workspace.onDidChangeTextDocument((event): void => {
      // Drag insertion path:
      // VS Code first inserts a temporary drop marker into the editor.
      // checkWhetherHandleDrop() replaces that marker with the real snippet and updates imports.

      // Once the file content changed, the inside logic of the function will analyze whether it was triggered by dragging event and then choose the correct following behavior.
      void checkWhetherHandleDrop(event);
    }),
  );

  /* Completion-related */
  context.subscriptions.push(
    vscode.languages.registerCompletionItemProvider(
      { language: "python", scheme: "file" },
      new LiberRPACompletionItemProvider(),
    ),
  );
  context.subscriptions.push(
    vscode.commands.registerCommand(
      "LiberRPA.updateManagedImportsAfterCompletion",
      async (arg: SnippetCompletionCommandArg): Promise<void> => {
        try {
          const editor = vscode.window.activeTextEditor;
          if (!editor) {
            log.error(`[Completion] No active editor for updating imports: ${arg.title}.`);
            return;
          }

          log.debug(
            `[Completion] Update imports for snippet: ${arg.title}, imports=[${arg.importNames.join(", ")}].`,
          );

          await updateManagedImports(editor, getImportManifest(), arg.importNames);
        } catch (e) {
          const message = e instanceof Error ? e.message : String(e);
          log.error(`[Completion] Failed to update imports: ${message}`);
          void vscode.window.showErrorMessage(
            `Failed to update LiberRPA imports: ${message}`,
          );
        }
      },
    ),
  );
}

export function deactivate(): void {
  log.debug('"liberrpa-snippets-tree" is now deactivated.');
}
