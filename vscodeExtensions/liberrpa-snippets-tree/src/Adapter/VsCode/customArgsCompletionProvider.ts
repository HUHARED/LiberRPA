// FileName: customArgsCompletionProvider.ts

import * as fs from "node:fs";
import * as vscode from "vscode";

import { log } from "./output";
import type { DictImportSourceConfig } from "../../Domain/Snippet/snippetTypes";
import { isRecord } from "../../Common/typeCheck";
import { reportError } from "./errorHandling";
import type { CustomArgsKeyIndex } from "./customArgsKeyIndex";
import {
  getCustomArgsCompletionContext,
  isPythonCodeAtOffset,
  type CustomArgsContextKind,
} from "../../Domain/CustomArgs/customArgsCompletionContext";
import { buildManagedImportTextEdits } from "../../Application/SnippetInsertion/managedImports";
import { planSnippetImportEdits } from "../../Application/SnippetInsertion/snippetImportEdits";

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
  importSources: Record<string, DictImportSourceConfig>,
): vscode.CompletionItem | undefined {
  const wordRange = document.getWordRangeAtPosition(position, /[A-Za-z_][A-Za-z0-9_]*/);

  if (!wordRange) {
    return undefined;
  }

  if (!isPythonCodeAtOffset(document.getText(), document.offsetAt(wordRange.start))) {
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
  const strBeforeWord = document
    .lineAt(wordRange.start.line)
    .text.slice(0, wordRange.start.character);
  if (strBeforeWord.trimEnd().endsWith(".")) {
    return undefined;
  }

  const completionItem = new vscode.CompletionItem(
    STR_CUSTOM_ARGS_NAME,
    vscode.CompletionItemKind.Variable,
  );

  const importEdits = buildManagedImportTextEdits(
    document,
    importSources,
    DICT_CUSTOM_ARGS_IMPORTS,
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
    "The custom project arguments defined in `project.flow`.",
  );

  return completionItem;
}

function getProjectFlowContent(document: vscode.TextDocument): string | undefined {
  const workspaceFolder = vscode.workspace.getWorkspaceFolder(document.uri);
  if (!workspaceFolder) {
    return undefined;
  }

  const projectFlowUri = vscode.Uri.joinPath(workspaceFolder.uri, "project.flow");
  const openDocument = vscode.workspace.textDocuments.find(
    (item: vscode.TextDocument) => item.uri.toString() === projectFlowUri.toString(),
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

function buildInsertedText(context: CustomArgsContextKind, argName: string): string {
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
  constructor(
    private readonly importSources: Record<string, DictImportSourceConfig>,
    private readonly keyIndex: CustomArgsKeyIndex,
  ) {}

  async provideCompletionItems(
    document: vscode.TextDocument,
    position: vscode.Position,
    token: vscode.CancellationToken,
  ): Promise<vscode.CompletionItem[] | undefined> {
    try {
      return await this.provideCompletionItemsInternal(document, position, token);
    } catch (e) {
      reportError("CustomArgs completion failed", e, false);
      return undefined;
    }
  }

  private async provideCompletionItemsInternal(
    document: vscode.TextDocument,
    position: vscode.Position,
    token: vscode.CancellationToken,
  ): Promise<vscode.CompletionItem[] | undefined> {
    if (token.isCancellationRequested || document.isClosed) {
      return undefined;
    }
    const intDocumentVersion = document.version;
    const context = getCustomArgsCompletionContext(
      document.getText(),
      document.offsetAt(position),
    );
    if (!context) {
      const variableCompletion = buildCustomArgsVariableCompletion(
        document,
        position,
        this.importSources,
      );
      return variableCompletion ? [variableCompletion] : undefined;
    }

    const content = getProjectFlowContent(document);
    const folder = vscode.workspace.getWorkspaceFolder(document.uri);
    if (content === undefined || !folder) {
      return undefined;
    }

    let arrArgName: string[];
    try {
      arrArgName = extractCustomArgNames(content);
    } catch (e) {
      log.debug(
        `[CustomArgs] project.flow is temporarily unavailable for completion: ${
          e instanceof Error ? e.message : String(e)
        }`,
      );
      return undefined;
    }

    if (context.keyPath.length > 0) {
      // Source observations may describe only arguments declared by this Project.
      if (!arrArgName.includes(context.keyPath[0])) {
        return undefined;
      }
      arrArgName = await this.keyIndex.getChildKeys(folder, context.keyPath);
    }
    if (
      token.isCancellationRequested ||
      document.isClosed ||
      document.version !== intDocumentVersion ||
      arrArgName.length === 0
    ) {
      return undefined;
    }

    const range = new vscode.Range(
      document.positionAt(context.startOffset),
      document.positionAt(context.endOffset),
    );
    const importEdits = buildManagedImportTextEdits(
      document,
      this.importSources,
      DICT_CUSTOM_ARGS_IMPORTS,
    );
    const importPlan = planSnippetImportEdits(range, importEdits);
    if (!importPlan) {
      return undefined;
    }

    return arrArgName.map((strArgName) => {
      const strInsertedText = buildInsertedText(context.kind, strArgName);
      const completionItem = new vscode.CompletionItem(
        `[${JSON.stringify(strArgName)}]`,
        vscode.CompletionItemKind.Snippet,
      );
      completionItem.insertText = importPlan.snippetPrefix + strInsertedText;
      completionItem.range = range;
      completionItem.additionalTextEdits = importPlan.additionalTextEdits;
      completionItem.filterText = strInsertedText;
      completionItem.sortText = JSON.stringify(strArgName);
      completionItem.detail =
        context.keyPath.length === 0
          ? "LiberRPA custom project argument"
          : "LiberRPA source-defined CustomArgs key";
      if (context.keyPath.length > 0) {
        completionItem.documentation = new vscode.MarkdownString(
          "A key found in an explicit CustomArgs assignment in this Project. " +
            "This suggestion does not guarantee that the key exists at runtime.",
        );
      }
      return completionItem;
    });
  }
}
