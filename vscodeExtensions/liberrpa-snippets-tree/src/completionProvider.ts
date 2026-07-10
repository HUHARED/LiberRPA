// FileName: completionProvider.ts
import { log } from "./output";
import type { SnippetTotalInfo, SnippetCompletionCommandArg } from "./interface";
import { getSnippets } from "./handleSnippets";

import * as vscode from "vscode";

function flattenSnippetInfos(): SnippetTotalInfo[] {
  // IntelliSense uses a flat list, so TreeView category grouping is discarded.
  const snippetsDict = getSnippets();
  const result: SnippetTotalInfo[] = [];

  for (const snippets of Object.values(snippetsDict)) {
    result.push(...Object.values(snippets));
  }

  return result;
}

function buildCompletionItem(snippetInfo: SnippetTotalInfo): vscode.CompletionItem {
  const item = new vscode.CompletionItem(
    snippetInfo.prefix,
    vscode.CompletionItemKind.Snippet,
  );

  // Shown as secondary information in the IntelliSense details.
  item.detail = `LiberRPA: ${snippetInfo.title}`;
  item.documentation = new vscode.MarkdownString(snippetInfo.description); // Text under headline.
  item.insertText = new vscode.SnippetString(snippetInfo.body.join("\n"));
  // item.filterText = `${snippetInfo.prefix} ${snippetInfo.title}`; Use snippets' prefix to search only.
  // item.sortText = `LiberRPA_${snippetInfo.title}`; Use prefixs' match degree to sort

  // Run a command to import and sort dependencies after users choose a snippet.
  const importArg: SnippetCompletionCommandArg = {
    title: snippetInfo.title,
    importNames: snippetInfo.importNames,
  };
  item.command = {
    command: "LiberRPA.updateManagedImportsAfterCompletion",
    // Required by VS Code. This internal command is not contributed to Command Palette.
    title: "Update LiberRPA Imports After Completion",
    // Pass one command argument object. VS Code command arguments must be provided as an array.
    arguments: [importArg],
  };

  return item;
}

export class LiberRPACompletionItemProvider implements vscode.CompletionItemProvider {
  private completionItems: vscode.CompletionItem[] | undefined;

  provideCompletionItems(): vscode.ProviderResult<vscode.CompletionItem[]> {
    try {
      if (!this.completionItems) {
        const snippetInfos = flattenSnippetInfos();
        this.completionItems = snippetInfos.map(buildCompletionItem);

        log.debug(
          `[Completion] Loaded ${this.completionItems.length} completion snippets.`,
        );
      }

      return this.completionItems;
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      log.error(`[Completion] Failed to load snippets: ${message}`);
      return [];
    }
  }
}
