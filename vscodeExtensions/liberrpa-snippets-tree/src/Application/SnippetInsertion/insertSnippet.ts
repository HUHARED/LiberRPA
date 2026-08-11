// FileName: insertSnippet.ts

import * as vscode from "vscode";

import { log } from "../../Adapter/VsCode/output";
import { updateManagedImports } from "./managedImports";
import type {
  SnippetInsertionMode,
  DictImportSourceConfig,
  DictSnippetNodeCommandArg,
} from "../../Domain/Snippet/snippetTypes";

async function insertSnippetBody(
  editor: vscode.TextEditor,
  snippetBody: string[],
  insertionMode: SnippetInsertionMode,
): Promise<boolean> {
  const snippet = new vscode.SnippetString(snippetBody.join("\n"));

  if (insertionMode === "cursor") {
    return await editor.insertSnippet(snippet);
  }

  const currentPosition = editor.selection.active;
  const intCurrentLine = currentPosition.line;
  const currentLine = editor.document.lineAt(intCurrentLine);

  if (currentLine.isEmptyOrWhitespace) {
    return await editor.insertSnippet(snippet);
  }

  if (snippetBody[0].startsWith(" # type: ignore")) {
    const lineEndPosition = new vscode.Position(intCurrentLine, currentLine.text.length);
    editor.selection = new vscode.Selection(lineEndPosition, lineEndPosition);
    return await editor.insertSnippet(snippet);
  }

  const currentLineIndent = currentLine.text.match(/^\s*/)?.[0] ?? "";
  const boolEdited = await editor.edit((editBuilder: vscode.TextEditorEdit) => {
    editBuilder.insert(
      currentPosition.with(intCurrentLine, currentLine.text.length),
      `\n${currentLineIndent}`,
    );
  });
  if (!boolEdited) {
    throw new Error("Failed to create a new line for the snippet.");
  }

  const nextLinePosition = new vscode.Position(
    intCurrentLine + 1,
    currentLineIndent.length,
  );
  editor.selection = new vscode.Selection(nextLinePosition, nextLinePosition);
  return await editor.insertSnippet(snippet);
}

export async function insertSnippetFromTreeNode(
  editor: vscode.TextEditor,
  commandArg: DictSnippetNodeCommandArg,
  importSource: Record<string, DictImportSourceConfig>,
): Promise<void> {
  const boolInserted = await insertSnippetBody(
    editor,
    commandArg.body,
    commandArg.insertionMode,
  );
  if (!boolInserted) {
    throw new Error(`VS Code rejected snippet ${commandArg.title}.`);
  }

  await updateManagedImports(editor.document, importSource, commandArg.imports);
  log.debug(`[Click] Inserted snippet: ${commandArg.title}.`);
}
