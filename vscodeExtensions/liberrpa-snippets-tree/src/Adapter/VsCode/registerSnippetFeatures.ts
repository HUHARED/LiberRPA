// FileName: registerSnippetFeatures.ts

import * as vscode from "vscode";

import { runAsyncBoundary } from "./errorHandling";
import { CustomArgsCompletionItemProvider } from "./customArgsCompletionProvider";
import { SnippetCompletionItemProvider } from "./snippetCompletionProvider";
import { SnippetDropEditProvider } from "./snippetDropEditProvider";
import { STR_SNIPPET_DRAG_MIME, SnippetTreeDataProvider } from "./snippetTreeDataProvider";
import { insertSnippetFromTreeNode } from "../../Application/SnippetInsertion/insertSnippet";
import { isSnippetNodeCommandArg } from "../../Domain/Snippet/snippetValidation";
import type { Info_SnippetRepository } from "../../Domain/Snippet/snippetTypes";

export function registerSnippetFeatures(
  context: vscode.ExtensionContext,
  repository: Info_SnippetRepository,
): () => void {
  const treeDataProvider = new SnippetTreeDataProvider(repository);
  const completionItemProvider = new SnippetCompletionItemProvider(repository);

  context.subscriptions.push(
    /* TreeView-related */
    treeDataProvider,
    vscode.window.createTreeView("LiberRPA.snippetsTreeView", {
      treeDataProvider,
      showCollapseAll: true,
      canSelectMany: false,
      dragAndDropController: treeDataProvider,
    }),
    vscode.commands.registerCommand(
      "LiberRPA.insertSnippetByNodeClicking",
      async (value: unknown): Promise<void> => {
        await runAsyncBoundary(
          "Failed to insert LiberRPA snippet",
          async (): Promise<void> => {
            if (!isSnippetNodeCommandArg(value)) {
              throw new Error("Invalid Snippet Tree command argument.");
            }

            const editor = vscode.window.activeTextEditor;
            if (editor?.document.languageId !== "python") {
              throw new Error("Open a Python editor before inserting a LiberRPA snippet.");
            }

            await insertSnippetFromTreeNode(editor, value, repository.importSource);
          },
          true,
        );
      },
    ),

    /*
     * Drag-related: A custom tree MIME type lets snippets drop directly at the editor position instead of being treated as resources that require Shift.
     */
    vscode.languages.registerDocumentDropEditProvider(
      { language: "python" },
      new SnippetDropEditProvider(repository, (): void => {
        treeDataProvider.finishDrag();
      }),
      { dropMimeTypes: [STR_SNIPPET_DRAG_MIME] },
    ),
    /* Completion-related */
    vscode.languages.registerCompletionItemProvider(
      { language: "python", scheme: "file" },
      completionItemProvider,
      ".",
    ),
    vscode.languages.registerCompletionItemProvider(
      { language: "python", scheme: "file" },
      new CustomArgsCompletionItemProvider(repository.importSource),
      "[",
      '"',
      "'",
    ),
  );

  return (): void => {
    treeDataProvider.refresh(repository);
    completionItemProvider.refresh();
  };
}
