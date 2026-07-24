// FileName: completionProvider.ts
import { log } from "./output";
import type { DictSnippetRepository, DictSnippetTotalInfo } from "./interface";
import { createManagedImportTextEditBuilder } from "./managedImports";
import { planSnippetImportEdits } from "./snippetImportEdits";
import { runSyncBoundary } from "./errorHandling";

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

/**
 * Return the range of the partially typed snippet prefix.
 *
 * VS Code normally treats only `cli` in `Mouse.cli` as the current word.
 * The explicit range makes completion replace `Mouse.cli` as a whole.
 */
function getCompletionRange(
  document: vscode.TextDocument,
  position: vscode.Position,
  snippetPrefix: string,
): vscode.Range | undefined {
  const strLinePrefix = document.lineAt(position.line).text.slice(0, position.character);
  const strExpected = snippetPrefix.toLowerCase();
  const intMaximumLength = Math.min(strLinePrefix.length, snippetPrefix.length);

  for (let intLength = intMaximumLength; intLength > 0; intLength -= 1) {
    const intStart = strLinePrefix.length - intLength;
    const strTyped = strLinePrefix.slice(intStart);

    if (!strExpected.startsWith(strTyped.toLowerCase())) {
      continue;
    }

    // Do not treat Mouse.cli inside OtherMouse.cli or obj.Mouse.cli as a standalone LiberRPA prefix.
    const strPreviousCharacter = intStart > 0 ? strLinePrefix[intStart - 1] : "";
    if (/[A-Za-z0-9_.]/.test(strPreviousCharacter)) {
      continue;
    }

    return new vscode.Range(position.with(undefined, intStart), position);
  }

  // At whitespace or an otherwise empty insertion point, show all snippets.
  if (
    strLinePrefix.length === 0 ||
    !/[A-Za-z0-9_.]/.test(strLinePrefix[strLinePrefix.length - 1])
  ) {
    return new vscode.Range(position, position);
  }

  return undefined;
}

function buildCompletionItem(
  document: vscode.TextDocument,
  position: vscode.Position,
  snippetInfo: DictSnippetTotalInfo,
  buildImportEdits: (imports: DictSnippetTotalInfo["imports"]) => vscode.TextEdit[],
): vscode.CompletionItem | undefined {
  const range = getCompletionRange(document, position, snippetInfo.prefix);
  if (!range) {
    return undefined;
  }

  const importEdits = buildImportEdits(snippetInfo.imports);
  const importPlan = planSnippetImportEdits(range, importEdits);

  if (!importPlan) {
    // This occurs only when completion is requested from inside the managed import block. That block is intentionally not an editable snippet target.
    return undefined;
  }

  const completionItem = new vscode.CompletionItem(
    snippetInfo.prefix,
    vscode.CompletionItemKind.Snippet,
  );

  // Shown as secondary information in the IntelliSense details.
  completionItem.detail = `LiberRPA: ${snippetInfo.title}`;

  // Text under headline.
  completionItem.documentation = new vscode.MarkdownString(snippetInfo.description);

  completionItem.insertText = new vscode.SnippetString(
    importPlan.snippetPrefix + snippetInfo.body.join("\n"),
  );
  completionItem.range = range;
  completionItem.additionalTextEdits = importPlan.additionalTextEdits;

  // item.filterText = `${snippetInfo.prefix} ${snippetInfo.title}`; Use snippets' prefix to search only.
  // item.sortText = `LiberRPA_${snippetInfo.title}`; Use prefixs' match degree to sort

  return completionItem;
}

export class MainCompletionItemProvider implements vscode.CompletionItemProvider {
  private snippetInfos: DictSnippetTotalInfo[] = [];

  constructor(private readonly repository: DictSnippetRepository) {
    this.refresh();
  }

  refresh(): void {
    this.snippetInfos = flattenSnippetInfos(this.repository);
    log.debug(`[Completion] Loaded ${this.snippetInfos.length} completion snippets.`);
  }

  provideCompletionItems(
    document: vscode.TextDocument,
    position: vscode.Position,
  ): vscode.ProviderResult<vscode.CompletionItem[]> {
    return runSyncBoundary(
      "LiberRPA snippet completion failed",
      () => {
        const buildImportEdits = createManagedImportTextEditBuilder(
          document,
          this.repository.importSources,
        );
        const mapEditsByImports = new Map<string, vscode.TextEdit[]>();

        return this.snippetInfos.flatMap((snippetInfo) => {
          const strImportsFingerprint = JSON.stringify(snippetInfo.imports);
          const getImportEdits = (): vscode.TextEdit[] => {
            const cachedEdits = mapEditsByImports.get(strImportsFingerprint);
            if (cachedEdits) {
              return cachedEdits;
            }

            const importEdits = buildImportEdits(snippetInfo.imports);
            mapEditsByImports.set(strImportsFingerprint, importEdits);
            return importEdits;
          };

          const completionItem = buildCompletionItem(
            document,
            position,
            snippetInfo,
            getImportEdits,
          );
          return completionItem ? [completionItem] : [];
        });
      },
      [],
      false,
    );
  }
}
