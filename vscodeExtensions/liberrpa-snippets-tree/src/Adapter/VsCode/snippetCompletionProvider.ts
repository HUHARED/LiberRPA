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

interface Info_CompletionContext {
  range: vscode.Range;
  qualifier?: string;
}

interface Info_CompletionMatch {
  range: vscode.Range;
  filterText: string;
  isLooseMatch: boolean;
}

/**
 * Determine only the text range that a Snippet completion may replace.
 *
 * Candidate filtering is intentionally left to VS Code so its normal fuzzy
 * matching can combine LiberRPA Snippets with Python language-service results.
 *
 * Examples:
 *
 * - `exop` is treated as an unqualified identifier and may fuzzy-match
 *   `Excel.open_excel_file`;
 * - `Excel.op` is treated as a qualified LiberRPA prefix;
 * - `obj.op` is rejected later unless `obj` is the first segment of the
 *   Snippet prefix.
 */
function getCompletionContext(
  document: vscode.TextDocument,
  position: vscode.Position,
): Info_CompletionContext | undefined {
  const strLinePrefix = document.lineAt(position.line).text.slice(0, position.character);

  const qualifiedMatch = /([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)?$/.exec(
    strLinePrefix,
  );
  if (qualifiedMatch !== null) {
    const strTypedExpression = qualifiedMatch[0];
    return {
      range: new vscode.Range(
        position.with(undefined, position.character - strTypedExpression.length),
        position,
      ),
      qualifier: qualifiedMatch[1],
    };
  }

  const identifierMatch = /[A-Za-z_][A-Za-z0-9_]*$/.exec(strLinePrefix);
  if (identifierMatch === null) {
    return undefined;
  }

  return {
    range: new vscode.Range(
      position.with(undefined, position.character - identifierMatch[0].length),
      position,
    ),
  };
}

function getSnippetQualifier(snippetPrefix: string): string | undefined {
  const intDotIndex = snippetPrefix.indexOf(".");
  return intDotIndex === -1 ? undefined : snippetPrefix.slice(0, intDotIndex);
}

function getCompletionMatch(
  completionContext: Info_CompletionContext,
  snippetPrefix: string,
): Info_CompletionMatch | undefined {
  if (completionContext.qualifier !== undefined) {
    if (getSnippetQualifier(snippetPrefix) !== completionContext.qualifier) {
      return undefined;
    }

    return {
      range: completionContext.range,
      filterText: snippetPrefix,
      isLooseMatch: false,
    };
  }

  return {
    range: completionContext.range,
    filterText: snippetPrefix,
    isLooseMatch: true,
  };
}

function buildCompletionItem(
  completionContext: Info_CompletionContext,
  snippet: Info_Snippet,
  buildImportEdits: (imports: Info_Snippet["imports"]) => vscode.TextEdit[],
): vscode.CompletionItem | undefined {
  const completionMatch = getCompletionMatch(completionContext, snippet.prefix);
  if (!completionMatch) {
    return undefined;
  }

  const importEdits = buildImportEdits(snippet.imports);
  const importPlan = planSnippetImportEdits(completionMatch.range, importEdits);

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
  const documentation = new vscode.MarkdownString();
  documentation.appendCodeblock(snippet.body.join("\n"), "python");
  if (snippet.description.length > 0) {
    documentation.appendMarkdown("\n\n");
    documentation.appendMarkdown(snippet.description);
  }
  completionItem.documentation = documentation;

  completionItem.insertText = new vscode.SnippetString(
    importPlan.snippetPrefix + snippet.body.join("\n"),
  );
  completionItem.range = completionMatch.range;
  completionItem.filterText = completionMatch.filterText;
  completionItem.additionalTextEdits = importPlan.additionalTextEdits;

  // Unqualified fuzzy matches supplement Python language-service completions instead of competing with them at the same sort position.
  if (completionMatch.isLooseMatch) {
    completionItem.sortText = `z_LiberRPA_${snippet.prefix}`;
  }

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
      (): vscode.CompletionItem[] | undefined => {
        const completionContext = getCompletionContext(document, position);
        if (completionContext === undefined) {
          return undefined;
        }

        const buildImportEdits = createManagedImportTextEditBuilder(
          document,
          this.repository.importSource,
        );
        const mapImportEdit = new Map<string, vscode.TextEdit[]>();

        const arrCompletionItem = this.arrSnippet.flatMap((snippet) => {
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
            completionContext,
            snippet,
            getImportEdits,
          );
          return completionItem === undefined ? [] : [completionItem];
        });

        if (arrCompletionItem.length === 0) {
          return undefined;
        }

        return arrCompletionItem;
      },
      undefined,
      false,
    );
  }
}
