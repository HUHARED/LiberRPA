// FileName: completionProvider.ts
import { log } from "./output";
import type {
  DictSnippetCompletionCommandArg,
  DictSnippetRepository,
  DictSnippetTotalInfo,
} from "./interface";

import * as vscode from "vscode";

function getSnippetFingerprint(snippet: DictSnippetTotalInfo): string {
  return JSON.stringify({
    title: snippet.title,
    prefix: snippet.prefix,
    body: snippet.body,
    description: snippet.description,
    imports: snippet.imports,
  });
}

function flattenSnippetInfos(repository: DictSnippetRepository): DictSnippetTotalInfo[] {
  // IntelliSense uses a flat list, so TreeView category grouping is discarded.
  const arrResult: DictSnippetTotalInfo[] = [];
  const setSeenFingerprints = new Set<string>();

  for (const strCategoryName of repository.categoryOrder) {
    for (const dictSnippet of repository.categories[strCategoryName] ?? []) {
      const strFingerprint = getSnippetFingerprint(dictSnippet);

      // Skip only exact duplicates. A customized favorite with the same title remains available alongside the built-in snippet.
      if (setSeenFingerprints.has(strFingerprint)) {
        continue;
      }

      setSeenFingerprints.add(strFingerprint);
      arrResult.push(dictSnippet);
    }
  }

  return arrResult;
}

function buildCompletionItem(snippetInfo: DictSnippetTotalInfo): vscode.CompletionItem {
  const completionItem = new vscode.CompletionItem(
    snippetInfo.prefix,
    vscode.CompletionItemKind.Snippet
  );

  // Shown as secondary information in the IntelliSense details.
  completionItem.detail = `LiberRPA: ${snippetInfo.title}`;

  // Text under headline.
  completionItem.documentation = new vscode.MarkdownString(snippetInfo.description);

  completionItem.insertText = new vscode.SnippetString(snippetInfo.body.join("\n"));

  // item.filterText = `${snippetInfo.prefix} ${snippetInfo.title}`; Use snippets' prefix to search only.
  // item.sortText = `LiberRPA_${snippetInfo.title}`; Use prefixs' match degree to sort

  const dictCommandArg: DictSnippetCompletionCommandArg = {
    title: snippetInfo.title,
    imports: snippetInfo.imports,
  };

  completionItem.command = {
    command: "LiberRPA.updateManagedImportsAfterCompletion",
    // Required by VS Code. This internal command is not contributed to Command Palette.
    title: "Update LiberRPA Imports After Completion",
    // Pass one command argument object. VS Code command arguments must be provided as an array.
    arguments: [dictCommandArg],
  };

  return completionItem;
}

export class MainCompletionItemProvider implements vscode.CompletionItemProvider {
  private readonly completionItems: vscode.CompletionItem[];

  constructor(repository: DictSnippetRepository) {
    this.completionItems = flattenSnippetInfos(repository).map(buildCompletionItem);
    log.debug(
      `[Completion] Loaded ${this.completionItems.length} static completion snippets.`
    );
  }

  provideCompletionItems(): vscode.ProviderResult<vscode.CompletionItem[]> {
    return this.completionItems;
  }
}
