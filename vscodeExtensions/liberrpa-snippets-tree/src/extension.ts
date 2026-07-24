// FileName: extension.ts
import { log } from "./output";
import type { DictSnippetNodeCommandArg, DictSnippetRepository } from "./interface";

import { SnippetTreeDataProvider, STR_SNIPPET_DRAG_MIME } from "./treeViewProvider";
import { DropEditProvider } from "./documentDropProvider";
import { MainCompletionItemProvider } from "./completionProvider";
import { CustomArgsCompletionItemProvider } from "./customArgsCompletionProvider";

import {
  loadSnippetRepository,
  insertSnippetFromTreeNode,
  replaceSnippetRepository,
} from "./handleSnippets";
import { updateManagedImports } from "./managedImports";
import { reportError, reportWarning, runAsyncBoundary } from "./errorHandling";

import * as vscode from "vscode";

const INT_REPOSITORY_RELOAD_DELAY_MS = 300;

function getSingleWorkspaceFolder(): vscode.WorkspaceFolder | undefined {
  const arrWorkspaceFolders = vscode.workspace.workspaceFolders;

  if (arrWorkspaceFolders === undefined || arrWorkspaceFolders.length !== 1) {
    return undefined;
  }

  return arrWorkspaceFolders[0];
}

function registerExtensionFeatures(
  context: vscode.ExtensionContext,
  repository: DictSnippetRepository,
): () => void {
  const treeViewProvider = new SnippetTreeDataProvider(repository);
  const mainCompletionItemProvider = new MainCompletionItemProvider(repository);

  /* TreeView-related */
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
              arg.insertionMode,
            );

            if (!inserted) {
              throw new Error(`VS Code rejected snippet ${arg.title}.`);
            }

            await updateManagedImports(
              editor.document,
              repository.importSources,
              arg.imports,
            );

            log.debug(`[Click] Inserted snippet: ${arg.title}.`);
          },
          true,
        );
      },
    ),
  );

  /*
   * Drag-related: A custom tree MIME type lets snippets drop directly at the editor position instead of being treated as resources that require Shift.
   */
  context.subscriptions.push(
    vscode.languages.registerDocumentDropEditProvider(
      { language: "python" },
      new DropEditProvider(repository, () => treeViewProvider.finishDrag()),
      { dropMimeTypes: [STR_SNIPPET_DRAG_MIME] },
    ),
  );

  /* Completion-related */
  context.subscriptions.push(
    vscode.languages.registerCompletionItemProvider(
      { language: "python", scheme: "file" },
      mainCompletionItemProvider,
    ),
  );
  context.subscriptions.push(
    vscode.languages.registerCompletionItemProvider(
      { language: "python", scheme: "file" },
      new CustomArgsCompletionItemProvider(repository.importSources),
      "[",
      '"',
      "'",
    ),
  );

  return (): void => {
    treeViewProvider.refresh(repository);
    mainCompletionItemProvider.refresh();
  };
}

function loadInitialRepository(): DictSnippetRepository {
  const workspaceFolder = getSingleWorkspaceFolder();

  try {
    return loadSnippetRepository(workspaceFolder);
  } catch (e) {
    // A damaged Component catalog should not disable built-in snippets.
    reportWarning("Component snippets were skipped", e, true);
    return loadSnippetRepository();
  }
}

export function activate(context: vscode.ExtensionContext): void {
  // Let vscode manage log's lifecycle.
  context.subscriptions.push(log);

  try {
    const repository = loadInitialRepository();
    const refreshFeatures = registerExtensionFeatures(context, repository);

    let componentWatcherDisposable: vscode.Disposable | undefined;
    let reloadTimer: NodeJS.Timeout | undefined;

    const reloadRepository = (): void => {
      reloadTimer = undefined;

      try {
        const nextRepository = loadSnippetRepository(getSingleWorkspaceFolder());
        replaceSnippetRepository(repository, nextRepository);
        refreshFeatures();

        log.info("LiberRPA snippet repository reloaded.");
      } catch (e) {
        // Keep the last valid repository during a transient or damaged _Components replacement instead of clearing working snippets.
        reportWarning("Failed to reload Component snippets", e, true);
      }
    };

    const scheduleRepositoryReload = (): void => {
      if (reloadTimer !== undefined) {
        clearTimeout(reloadTimer);
      }

      reloadTimer = setTimeout(reloadRepository, INT_REPOSITORY_RELOAD_DELAY_MS);
    };

    const updateComponentWatcher = (): void => {
      componentWatcherDisposable?.dispose();
      componentWatcherDisposable = undefined;

      const workspaceFolder = getSingleWorkspaceFolder();
      if (!workspaceFolder) {
        return;
      }

      const watcher = vscode.workspace.createFileSystemWatcher(
        new vscode.RelativePattern(
          workspaceFolder,
          "_Components/*.dist-info/liberrpa/snippets_catalog.json",
        ),
      );

      componentWatcherDisposable = vscode.Disposable.from(
        watcher,
        watcher.onDidCreate(scheduleRepositoryReload),
        watcher.onDidChange(scheduleRepositoryReload),
        watcher.onDidDelete(scheduleRepositoryReload),
      );
    };

    updateComponentWatcher();

    context.subscriptions.push(
      vscode.workspace.onDidChangeWorkspaceFolders(() => {
        updateComponentWatcher();
        scheduleRepositoryReload();
      }),
      vscode.commands.registerCommand("LiberRPA.refreshSnippetRepository", (): void => {
        scheduleRepositoryReload();
      }),
      new vscode.Disposable(() => {
        componentWatcherDisposable?.dispose();

        if (reloadTimer !== undefined) {
          clearTimeout(reloadTimer);
        }
      }),
    );

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
