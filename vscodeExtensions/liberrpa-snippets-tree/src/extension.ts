// FileName: extension.ts

import type * as vscode from "vscode";

import { log } from "./Adapter/VsCode/output";
import { reportError } from "./Adapter/VsCode/errorHandling";
import { registerSnippetFeatures } from "./Adapter/VsCode/registerSnippetFeatures";
import { SnippetRepositorySession } from "./Application/SnippetRepository/snippetRepositorySession";
import { createEmptySnippetRepository } from "./Domain/Snippet/snippetRepository";

export function activate(context: vscode.ExtensionContext): void {
  // Let vscode manage log's lifecycle.
  context.subscriptions.push(log);

  try {
    const repository = createEmptySnippetRepository();
    const refreshFeatures = registerSnippetFeatures(context, repository);
    const repositorySession = new SnippetRepositorySession(
      context.extensionPath,
      repository,
      refreshFeatures,
    );

    context.subscriptions.push(repositorySession);
    repositorySession.start();

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
