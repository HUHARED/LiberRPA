// FileName: snippetCompletionProvider.ts

import * as vscode from "vscode";

import { log } from "./output";
import { runSyncBoundary } from "./errorHandling";
import { createManagedImportTextEditBuilder } from "../../Application/SnippetInsertion/managedImports";
import { planSnippetImportEdits } from "../../Application/SnippetInsertion/snippetImportEdits";
import type {
  Info_Snippet,
  Info_SnippetRepository,
} from "../../Domain/Snippet/snippetTypes";

function getSnippetFingerprint(snippet: Info_Snippet): string {
  return JSON.stringify({
    title: snippet.title,
    label: snippet.label,
    prefix: snippet.prefix,
    body: snippet.body,
    description: snippet.description,
    imports: snippet.imports,
    insertionMode: snippet.insertionMode,
  });
}

function flattenSnippets(repository: Info_SnippetRepository): Info_Snippet[] {
  // IntelliSense uses a flat list, so TreeView category grouping is discarded.
  const arrResult: Info_Snippet[] = [];
  const setSeenFingerprint = new Set<string>();

  for (const categoryName of repository.categoryOrder) {
    for (const snippet of repository.snippetByCategory[categoryName] ?? []) {
      const fingerprint = getSnippetFingerprint(snippet);

      // Skip exact duplicates only. A customized Favorite remains available alongside the built-in Snippet.
      if (setSeenFingerprint.has(fingerprint)) {
        continue;
      }

      setSeenFingerprint.add(fingerprint);
      arrResult.push(snippet);
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
  const linePrefix = document.lineAt(position.line).text.slice(0, position.character);
  const expectedPrefix = snippetPrefix.toLowerCase();
  const intMaximumLength = Math.min(linePrefix.length, snippetPrefix.length);

  for (let intLength = intMaximumLength; intLength > 0; intLength -= 1) {
    const intStart = linePrefix.length - intLength;
    const typedPrefix = linePrefix.slice(intStart);

    if (!expectedPrefix.startsWith(typedPrefix.toLowerCase())) {
      continue;
    }

    // Do not treat Mouse.cli inside OtherMouse.cli or obj.Mouse.cli as a standalone LiberRPA prefix.
    const previousCharacter = intStart > 0 ? linePrefix[intStart - 1] : "";
    if (/[A-Za-z0-9_.]/.test(previousCharacter)) {
      continue;
    }

    return new vscode.Range(position.with(undefined, intStart), position);
  }

  // At whitespace or an otherwise empty insertion point, show all snippets.
  if (linePrefix.length === 0 || !/[A-Za-z0-9_.]/.test(linePrefix[linePrefix.length - 1])) {
    return new vscode.Range(position, position);
  }

  return undefined;
}

function buildCompletionItem(
  document: vscode.TextDocument,
  position: vscode.Position,
  snippet: Info_Snippet,
  buildImportEdits: (imports: Info_Snippet["imports"]) => vscode.TextEdit[],
): vscode.CompletionItem | undefined {
  const range = getCompletionRange(document, position, snippet.prefix);
  if (!range) {
    return undefined;
  }

  const importEdits = buildImportEdits(snippet.imports);
  const importPlan = planSnippetImportEdits(range, importEdits);

  if (importPlan === undefined) {
    // This can occur only when completion is requested inside the managed import block, which is intentionally not an editable Snippet target.
    return undefined;
  }

  const completionItem = new vscode.CompletionItem(
    snippet.prefix,
    vscode.CompletionItemKind.Snippet,
  );

  // Shown as secondary information in the IntelliSense details.
  completionItem.detail = `LiberRPA: ${snippet.title}`;

  // Text under headline.
  completionItem.documentation = new vscode.MarkdownString(snippet.description);

  completionItem.insertText = new vscode.SnippetString(
    importPlan.snippetPrefix + snippet.body.join("\n"),
  );
  completionItem.range = range;
  completionItem.additionalTextEdits = importPlan.additionalTextEdits;

  // item.filterText = `${snippetInfo.prefix} ${snippetInfo.title}`; Use snippets' prefix to search only.
  // item.sortText = `LiberRPA_${snippetInfo.title}`; Use prefixs' match degree to sort

  return completionItem;
}

export class SnippetCompletionItemProvider implements vscode.CompletionItemProvider {
  private arrSnippet: Info_Snippet[] = [];

  constructor(private readonly repository: Info_SnippetRepository) {
    this.refresh();
  }

  refresh(): void {
    this.arrSnippet = flattenSnippets(this.repository);
    log.debug(`[Completion] Loaded ${this.arrSnippet.length} completion snippets.`);
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
          this.repository.importSource,
        );
        const mapImportEdit = new Map<string, vscode.TextEdit[]>();

        return this.arrSnippet.flatMap((snippet) => {
          const importsFingerprint = JSON.stringify(snippet.imports);
          const getImportEdits = (): vscode.TextEdit[] => {
            const cachedEdits = mapImportEdit.get(importsFingerprint);
            if (cachedEdits !== undefined) {
              return cachedEdits;
            }

            const importEdits = buildImportEdits(snippet.imports);
            mapImportEdit.set(importsFingerprint, importEdits);
            return importEdits;
          };

          const completionItem = buildCompletionItem(
            document,
            position,
            snippet,
            getImportEdits,
          );
          return completionItem === undefined ? [] : [completionItem];
        });
      },
      [],
      false,
    );
  }
}
