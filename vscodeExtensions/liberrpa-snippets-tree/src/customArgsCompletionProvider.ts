// FileName: customArgsCompletionProvider.ts
import { log } from "./output";
import type { ImportSourceConfig } from "./interface";
import { isRecord } from "./typeCheck";
import { runSyncBoundary } from "./errorHandling";
import { buildManagedImportTextEdits } from "./managedImports";
import { planSnippetImportEdits } from "./snippetImportEdits";

import * as fs from "node:fs";
import * as vscode from "vscode";

type CompletionContext =
  | "afterCustomArgs"
  | "afterBracket"
  | "insideDoubleQuote"
  | "insideSingleQuote";
const STR_CUSTOM_ARGS_NAME = "CustomArgs";
const DICT_CUSTOM_ARGS_IMPORTS = {
  "liberrpa.Modules": [STR_CUSTOM_ARGS_NAME],
};

/**
 * Create the completion item for the CustomArgs variable itself.
 *
 * Examples:
 *   Cus        -> CustomArgs
 *   Custom     -> CustomArgs
 *   CustomArgs -> CustomArgs
 *
 * Expressions after a dot, such as object.Custom, are ignored because
 * CustomArgs is a project-level variable rather than an object member.
 */
function buildCustomArgsVariableCompletion(
  document: vscode.TextDocument,
  position: vscode.Position,
  importSources: Record<string, ImportSourceConfig>
): vscode.CompletionItem | undefined {
  const wordRange = document.getWordRangeAtPosition(position, /[A-Za-z_][A-Za-z0-9_]*/);

  if (!wordRange) {
    return undefined;
  }

  const strTypedText = document.getText(wordRange);

  if (
    strTypedText.length === 0 ||
    !STR_CUSTOM_ARGS_NAME.toLowerCase().startsWith(strTypedText.toLowerCase())
  ) {
    return undefined;
  }

  // Do not suggest the project-level CustomArgs variable as an object member:
  // someObjectName.Custom...
  const intCharacterBeforeWord = wordRange.start.character - 1;
  if (
    intCharacterBeforeWord >= 0 &&
    document.lineAt(wordRange.start.line).text.charAt(intCharacterBeforeWord) === "."
  ) {
    return undefined;
  }

  const completionItem = new vscode.CompletionItem(
    STR_CUSTOM_ARGS_NAME,
    vscode.CompletionItemKind.Variable
  );

  const importEdits = buildManagedImportTextEdits(
    document,
    importSources,
    DICT_CUSTOM_ARGS_IMPORTS
  );
  const importPlan = planSnippetImportEdits(wordRange, importEdits);

  if (!importPlan) {
    return undefined;
  }

  completionItem.insertText = importPlan.snippetPrefix + STR_CUSTOM_ARGS_NAME;
  completionItem.range = wordRange;
  completionItem.additionalTextEdits = importPlan.additionalTextEdits;
  completionItem.detail = "LiberRPA custom project arguments";
  completionItem.documentation = new vscode.MarkdownString(
    "The custom project arguments defined in `project.flow`."
  );

  return completionItem;
}

function getCompletionContext(linePrefix: string): CompletionContext | undefined {
  const arrContexts: ReadonlyArray<[string, CompletionContext]> = [
    ['CustomArgs["', "insideDoubleQuote"],
    ["CustomArgs['", "insideSingleQuote"],
    ["CustomArgs[", "afterBracket"],
    ["CustomArgs", "afterCustomArgs"],
  ];

  for (const [strSuffix, context] of arrContexts) {
    if (!linePrefix.endsWith(strSuffix)) {
      continue;
    }

    const intStart = linePrefix.length - strSuffix.length;
    const strPreviousCharacter = intStart > 0 ? linePrefix[intStart - 1] : "";

    // CustomArgs is a standalone project variable, not a suffix of another identifier and not an object attribute.
    if (/[A-Za-z0-9_.]/.test(strPreviousCharacter)) {
      return undefined;
    }

    return context;
  }
  return undefined;
}

function getProjectFlowContent(document: vscode.TextDocument): string | undefined {
  const workspaceFolder = vscode.workspace.getWorkspaceFolder(document.uri);
  if (!workspaceFolder) {
    return undefined;
  }

  const projectFlowUri = vscode.Uri.joinPath(workspaceFolder.uri, "project.flow");
  const openDocument = vscode.workspace.textDocuments.find(
    (item) => item.uri.toString() === projectFlowUri.toString()
  );

  if (openDocument) {
    return openDocument.getText();
  }

  if (!fs.existsSync(projectFlowUri.fsPath)) {
    return undefined;
  }

  return fs.readFileSync(projectFlowUri.fsPath, "utf-8");
}

function extractCustomArgNames(content: string): string[] {
  const parsed: unknown = JSON.parse(content);
  if (!isRecord(parsed) || !Array.isArray(parsed.customPrjArgs)) {
    return [];
  }

  const arrResult: string[] = [];
  const setSeenNames = new Set<string>();

  for (const item of parsed.customPrjArgs) {
    if (!Array.isArray(item) || typeof item[0] !== "string") {
      continue;
    }

    const strKeyName = item[0];
    // Keep the first pair if it has duplicated keys.
    if (setSeenNames.has(strKeyName)) {
      continue;
    }

    setSeenNames.add(strKeyName);
    arrResult.push(strKeyName);
  }

  return arrResult;
}

function escapeQuotedContent(value: string, quoteCharacter: '"' | "'"): string {
  // JSON.stringify escapes every JSON control character, including backspace,
  // form feed, and NUL. Remove only its surrounding double quotes.
  const strJsonContent = JSON.stringify(value).slice(1, -1);
  return quoteCharacter === "'" ? strJsonContent.replace(/'/g, "\\'") : strJsonContent;
}

function buildInsertedText(context: CompletionContext, argName: string): string {
  switch (context) {
    case "afterCustomArgs":
      // Insert a complete dictionary lookup:
      // CustomArgs + ["customerName"]
      return `[${JSON.stringify(argName)}]`;

    case "afterBracket":
      // The editor already contains:
      // CustomArgs[]
      // Insert the complete quoted key between the brackets.
      return JSON.stringify(argName);

    case "insideDoubleQuote":
      // The editor already contains:
      // CustomArgs[""]
      // Insert only the escaped string content.
      return escapeQuotedContent(argName, '"');

    case "insideSingleQuote":
      // The editor already contains:
      // CustomArgs['']
      // Insert only the escaped string content.
      return escapeQuotedContent(argName, "'");
  }
}

export class CustomArgsCompletionItemProvider implements vscode.CompletionItemProvider {
  constructor(private readonly importSources: Record<string, ImportSourceConfig>) {}

  provideCompletionItems(
    document: vscode.TextDocument,
    position: vscode.Position
  ): vscode.ProviderResult<vscode.CompletionItem[]> {
    return runSyncBoundary(
      "CustomArgs completion failed",
      () => this.provideCompletionItemsInternal(document, position),
      [],
      false
    );
  }

  private provideCompletionItemsInternal(
    document: vscode.TextDocument,
    position: vscode.Position
  ): vscode.CompletionItem[] {
    const strLinePrefix = document.lineAt(position).text.substring(0, position.character);

    const context = getCompletionContext(strLinePrefix);

    /*
     * Context 1: the user has already typed CustomArgs.
     *
     * Examples:
     *   CustomArgs
     *   CustomArgs[
     *   CustomArgs["
     *   CustomArgs['
     *
     * In this context, provide the keys defined in project.flow.
     */
    if (context) {
      const content = getProjectFlowContent(document);

      if (content === undefined) {
        return [];
      }

      let arrArgNames: string[];

      try {
        arrArgNames = extractCustomArgNames(content);
      } catch (e) {
        // Users may be editing project.flow manually in text view instead of in LiberRPA Flowchart.
        log.debug(
          `[CustomArgs] project.flow is temporarily unavailable for completion: ${
            e instanceof Error ? e.message : String(e)
          }`
        );
        return [];
      }

      const range = new vscode.Range(position, position);
      const importEdits = buildManagedImportTextEdits(
        document,
        this.importSources,
        DICT_CUSTOM_ARGS_IMPORTS
      );
      const importPlan = planSnippetImportEdits(range, importEdits);

      if (!importPlan) {
        return [];
      }

      return arrArgNames.map((strArgName) => {
        const strInsertedText = buildInsertedText(context, strArgName);

        const completionItem = new vscode.CompletionItem(
          `[${JSON.stringify(strArgName)}]`,
          vscode.CompletionItemKind.Snippet
        );

        completionItem.insertText = importPlan.snippetPrefix + strInsertedText;
        completionItem.range = range;
        completionItem.additionalTextEdits = importPlan.additionalTextEdits;
        // Keep the same high sorting priority that the old quoted label had, while the visible label remains non-empty for an empty-string key.
        completionItem.sortText = JSON.stringify(strArgName);
        completionItem.detail = "LiberRPA custom project argument";

        return completionItem;
      });
    }

    /*
     * Context 2: the user is typing the CustomArgs variable itself.
     *
     * Examples:
     *   Cus
     *   Custom
     *
     * Provide CustomArgs even if it has never appeared in the current file.
     */
    const variableCompletion = buildCustomArgsVariableCompletion(
      document,
      position,
      this.importSources
    );

    return variableCompletion ? [variableCompletion] : [];
  }
}
