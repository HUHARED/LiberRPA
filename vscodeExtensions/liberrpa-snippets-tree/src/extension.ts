// FileName: extension.ts
import { log } from "./output";
import type { DictSnippetNodeCommandArg, DictSnippetRepository } from "./interface";

import { SnippetTreeDataProvider, STR_SNIPPET_DRAG_MIME } from "./treeViewProvider";
import { DropEditProvider } from "./documentDropProvider";
import { MainCompletionItemProvider } from "./completionProvider";
import { CustomArgsCompletionItemProvider } from "./customArgsCompletionProvider";

import { loadSnippetRepository, insertSnippetFromTreeNode } from "./handleSnippets";
import { updateManagedImports } from "./managedImports";
import { reportError, runAsyncBoundary } from "./errorHandling";

import * as vscode from "vscode";

function registerExtensionFeatures(
  context: vscode.ExtensionContext,
  repository: DictSnippetRepository
): void {
  const treeViewProvider = new SnippetTreeDataProvider(repository);

  /* TreeView-related */
  context.subscriptions.push(
    vscode.window.createTreeView("LiberRPA.snippetsTreeView", {
      treeDataProvider: treeViewProvider,
      showCollapseAll: true,
      canSelectMany: false,
      dragAndDropController: treeViewProvider,
    })
  );
  context.subscriptions.push(
    vscode.commands.registerCommand(
      "LiberRPA.insertSnippetByNodeClicking",
      async (arg: DictSnippetNodeCommandArg): Promise<void> => {
        await runAsyncBoundary(
          "Failed to insert LiberRPA snippet",
          async (): Promise<void> => {
            const editor = vscode.window.activeTextEditor;

            if (!editor || editor.document.languageId !== "python") {
              throw new Error("Open a Python editor before inserting a LiberRPA snippet.");
            }

            const inserted = await insertSnippetFromTreeNode(
              editor,
              arg.body,
              arg.insertionMode
            );

            if (!inserted) {
              throw new Error(`VS Code rejected snippet ${arg.title}.`);
            }

            await updateManagedImports(
              editor.document,
              repository.importSources,
              arg.imports
            );

            log.debug(`[Click] Inserted snippet: ${arg.title}.`);
          },
          true
        );
      }
    )
  );

  /*
   * Drag-related: A custom tree MIME type lets snippets drop directly at the editor position instead of being treated as resources that require Shift.
   */
  context.subscriptions.push(
    vscode.languages.registerDocumentDropEditProvider(
      { language: "python" },
      new DropEditProvider(repository, () => treeViewProvider.finishDrag()),
      { dropMimeTypes: [STR_SNIPPET_DRAG_MIME] }
    )
  );

  /* Completion-related */
  context.subscriptions.push(
    vscode.languages.registerCompletionItemProvider(
      { language: "python", scheme: "file" },
      new MainCompletionItemProvider(repository)
    )
  );
  context.subscriptions.push(
    vscode.languages.registerCompletionItemProvider(
      { language: "python", scheme: "file" },
      new CustomArgsCompletionItemProvider(repository.importSources),
      "[",
      '"',
      "'"
    )
  );
}

export function activate(context: vscode.ExtensionContext): void {
  // Let vscode manage log's lifecycle.
  context.subscriptions.push(log);

  try {
    const repository = loadSnippetRepository();
    registerExtensionFeatures(context, repository);

    log.info("LiberRPA Snippets Tree activated.");
  } catch (e) {
    reportError("Failed to activate LiberRPA Snippets Tree", e, true);

    // Activation did not complete, so report the failure to VS Code as well.
    throw e;
  }
}

export function deactivate(): void {
  log.info("LiberRPA Snippets Tree deactivated.");
}
