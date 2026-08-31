// FileName: snippetCompletionProvider.ts

import * as vscode from "vscode";

import { log } from "./output";
import { runSyncBoundary } from "./errorHandling";
import { createManagedImportTextEditBuilder } from "../../Application/SnippetInsertion/managedImports";
import { planSnippetImportEdits } from "../../Application/SnippetInsertion/snippetImportEdits";
import { matchesSnippetCompletion } from "../../Domain/Snippet/snippetCompletionMatching";
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

interface SnippetCompletionContext {
  range: vscode.Range;
  searchText: string;
  qualifier?: string;
}

const REG_COMPLETION_EXPRESSION =
  /[_\p{ID_Start}][\p{ID_Continue}]*(?:\.[_\p{ID_Start}][\p{ID_Continue}]*)*\.?$/u;
const REG_IDENTIFIER_CONTINUATION = /[\p{ID_Continue}]$/u;
const REG_IDENTIFIER_SUFFIX = /^[\p{ID_Continue}]*/u;

/**
 * Read the whole identifier/member chain, not just its final two segments.
 *
 * A candidate may replace `Excel.op`, but never the `Excel.op` suffix of
 * `obj.Excel.op`, nor an identifier after `get_obj().` or `obj. `.
 * Qualifiers are checked against the actual catalog prefixes by the matcher.
 */
function getCompletionContext(
  document: vscode.TextDocument,
  position: vscode.Position,
): SnippetCompletionContext | undefined {
  const strLine = document.lineAt(position.line).text;
  const strLinePrefix = strLine.slice(0, position.character);
  const expressionMatch = REG_COMPLETION_EXPRESSION.exec(strLinePrefix);
  if (expressionMatch === null) {
    return undefined;
  }

  const intStartCharacter = expressionMatch.index;
  const strBeforeExpression = strLinePrefix.slice(0, intStartCharacter);
  if (
    REG_IDENTIFIER_CONTINUATION.test(strBeforeExpression) ||
    strBeforeExpression.trimEnd().endsWith(".")
  ) {
    return undefined;
  }

  const strExpression = expressionMatch[0];
  const intDotIndex = strExpression.lastIndexOf(".");
  const strSearchText = strExpression.slice(intDotIndex + 1);
  const strSuffix = REG_IDENTIFIER_SUFFIX.exec(strLine.slice(position.character))![0];

  return {
    // Replace the rest of an existing identifier when completing in its middle.
    range: new vscode.Range(
      position.with(undefined, intStartCharacter),
      position.with(undefined, position.character + strSuffix.length),
    ),
    searchText: strSearchText,
    qualifier: intDotIndex === -1 ? undefined : strExpression.slice(0, intDotIndex),
  };
}

function buildCompletionItem(
  completionContext: SnippetCompletionContext,
  snippet: Info_Snippet,
  importEdits: vscode.TextEdit[],
): vscode.CompletionItem | undefined {
  const importPlan = planSnippetImportEdits(completionContext.range, importEdits);

  if (importPlan === undefined) {
    // Skip overlapping managed-import edits that cannot be merged into the primary edit.
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
  completionItem.range = completionContext.range;
  completionItem.filterText = snippet.prefix;
  completionItem.additionalTextEdits = importPlan.additionalTextEdits;

  // This is only a tie-breaker; VS Code also considers match scores and user settings.
  if (completionContext.qualifier === undefined) {
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
    _token: vscode.CancellationToken,
    context: vscode.CompletionContext,
  ): vscode.ProviderResult<vscode.CompletionList> {
    return runSyncBoundary(
      "LiberRPA snippet completion failed",
      (): vscode.CompletionList | undefined => {
        const completionContext = getCompletionContext(document, position);
        if (completionContext === undefined) {
          return undefined;
        }

        const arrRelevantSnippet = this.arrSnippet.filter((snippet) =>
          matchesSnippetCompletion(
            completionContext.searchText,
            snippet.prefix,
            completionContext.qualifier,
          ),
        );
        log.trace(
          `[Completion] trigger=${context.triggerKind} ` +
            `qualifier=${JSON.stringify(completionContext.qualifier ?? "")} ` +
            `query=${JSON.stringify(completionContext.searchText)} ` +
            `relevant=${arrRelevantSnippet.length}`,
        );
        if (arrRelevantSnippet.length === 0) {
          return undefined;
        }

        const buildImportEdits = createManagedImportTextEditBuilder(
          document,
          this.repository.importSource,
        );
        const mapImportEdit = new Map<string, vscode.TextEdit[]>();

        const arrCompletionItem: vscode.CompletionItem[] = [];
        for (const snippet of arrRelevantSnippet) {
          const importsFingerprint = JSON.stringify(snippet.imports);
          let importEdits = mapImportEdit.get(importsFingerprint);
          if (importEdits === undefined) {
            importEdits = buildImportEdits(snippet.imports);
            mapImportEdit.set(importsFingerprint, importEdits);
          }

          const completionItem = buildCompletionItem(
            completionContext,
            snippet,
            importEdits,
          );
          if (completionItem !== undefined) {
            arrCompletionItem.push(completionItem);
          }
        }

        if (arrCompletionItem.length === 0) {
          return undefined;
        }

        // Re-evaluate the relevance gate as the user types. A complete list would let VS Code keep an earlier `i`/`in` result and fuzzy-match `intLast` against it without calling this provider again. Other providers remain independently managed by VS Code; this does not force them to refresh.
        return new vscode.CompletionList(arrCompletionItem, true);
      },
      undefined,
      false,
    );
  }
}
