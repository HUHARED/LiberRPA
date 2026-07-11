// FileName: extension.ts
import { log } from "./output";
import type {
  DictSnippetCompletionCommandArg,
  DictSnippetNodeCommandArg,
  DictSnippetRepository,
} from "./interface";

import { SnippetTreeDataProvider } from "./treeViewProvider";
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
            const inserted = await insertSnippetFromTreeNode(arg.body, arg.insertionMode);

            if (!inserted) {
              throw new Error(`VS Code rejected snippet ${arg.title}.`);
            }

            const editor = vscode.window.activeTextEditor;

            if (!editor) {
              throw new Error(
                `No active editor was found after inserting snippet ${arg.title}.`
              );
            }

            await updateManagedImports(editor, repository.importSources, arg.imports);

            log.debug(`[Click] Inserted snippet: ${arg.title}.`);
          },
          true
        );
      }
    )
  );

  /* Drag-related */
  context.subscriptions.push(
    vscode.workspace.onDidChangeTextDocument((event): void => {
      void runAsyncBoundary(
        "Failed to insert dragged LiberRPA snippet",
        async (): Promise<void> => {
          await treeViewProvider.handlePossibleSnippetDrop(event);
        },
        true
      );
    })
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
      new CustomArgsCompletionItemProvider(),
      "[",
      '"',
      "'"
    )
  );
  context.subscriptions.push(
    vscode.commands.registerCommand(
      "LiberRPA.updateManagedImportsAfterCompletion",
      async (arg: DictSnippetCompletionCommandArg): Promise<void> => {
        await runAsyncBoundary(
          "Failed to update LiberRPA managed imports",
          async (): Promise<void> => {
            const editor = vscode.window.activeTextEditor;

            if (!editor) {
              throw new Error(`No active editor was found for completion ${arg.title}.`);
            }

            await updateManagedImports(editor, repository.importSources, arg.imports);

            log.debug(`[Completion] Updated imports for: ${arg.title}.`);
          },
          true
        );
      }
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
