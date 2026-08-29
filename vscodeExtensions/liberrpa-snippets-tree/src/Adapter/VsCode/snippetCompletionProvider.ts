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

interface Info_CompletionMatch {
  range: vscode.Range;
  filterText: string;
}

function findCompletionSuffixStart(
  linePrefix: string,
  expectedPrefix: string,
): number | undefined {
  const strExpectedPrefixLower = expectedPrefix.toLowerCase();
  const intMaximumLength = Math.min(linePrefix.length, expectedPrefix.length);

  for (let intLength = intMaximumLength; intLength > 0; intLength -= 1) {
    const intStart = linePrefix.length - intLength;
    const strTypedPrefix = linePrefix.slice(intStart);

    if (!strExpectedPrefixLower.startsWith(strTypedPrefix.toLowerCase())) {
      continue;
    }

    // Do not match a suffix inside another identifier or qualified expression.
    const strPreviousCharacter = intStart > 0 ? linePrefix[intStart - 1] : "";
    if (/[A-Za-z0-9_.]/.test(strPreviousCharacter)) {
      continue;
    }

    return intStart;
  }

  return undefined;
}

function getCompletionMatchPrefix(snippetPrefix: string): string[] {
  const arrResult = [snippetPrefix];
  const strFinalSegment = snippetPrefix.slice(snippetPrefix.lastIndexOf(".") + 1);

  if (strFinalSegment !== snippetPrefix) {
    arrResult.push(strFinalSegment);
  }

  for (
    let intUnderscoreIndex = strFinalSegment.indexOf("_");
    intUnderscoreIndex !== -1;
    intUnderscoreIndex = strFinalSegment.indexOf("_", intUnderscoreIndex + 1)
  ) {
    const strSuffix = strFinalSegment.slice(intUnderscoreIndex + 1);
    if (strSuffix.length > 0 && !arrResult.includes(strSuffix)) {
      arrResult.push(strSuffix);
    }
  }

  return arrResult;
}

/**
 * Match the complete Snippet prefix, its final dot-separated segment, or a
 * suffix that starts after a snake_case boundary.
 *
 * Examples:
 *
 * - `Log.d`, `d`, `deb`, and `debug` match `Log.debug`;
 * - `Str.c`, `case_`, `to_`, `to_upper`, and `upper` match
 *   `Str.case_to_upper`;
 * - `obj.to_upper` and `other_to_upper` are rejected.
 *
 * The explicit range also makes VS Code replace `Mouse.cli` as a whole instead
 * of treating only `cli` as the current word.
 */
function getCompletionMatch(
  document: vscode.TextDocument,
  position: vscode.Position,
  snippetPrefix: string,
): Info_CompletionMatch | undefined {
  const strLinePrefix = document.lineAt(position.line).text.slice(0, position.character);

  for (const strMatchPrefix of getCompletionMatchPrefix(snippetPrefix)) {
    const intMatchStart = findCompletionSuffixStart(strLinePrefix, strMatchPrefix);

    if (intMatchStart !== undefined) {
      return {
        range: new vscode.Range(position.with(undefined, intMatchStart), position),
        filterText: strMatchPrefix,
      };
    }
  }

  // At whitespace or an otherwise empty insertion point, show all snippets.
  if (
    strLinePrefix.length === 0 ||
    !/[A-Za-z0-9_.]/.test(strLinePrefix[strLinePrefix.length - 1])
  ) {
    return {
      range: new vscode.Range(position, position),
      filterText: snippetPrefix,
    };
  }

  return undefined;
}

function buildCompletionItem(
  document: vscode.TextDocument,
  position: vscode.Position,
  snippet: Info_Snippet,
  buildImportEdits: (imports: Info_Snippet["imports"]) => vscode.TextEdit[],
): vscode.CompletionItem | undefined {
  const completionMatch = getCompletionMatch(document, position, snippet.prefix);
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
