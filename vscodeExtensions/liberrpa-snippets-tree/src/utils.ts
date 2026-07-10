// FileName: utils.ts
import * as vscode from "vscode";

export async function insertSnippet(snippetsLines: string[]): Promise<boolean> {
  const editor = vscode.window.activeTextEditor;

  if (!editor) {
    void vscode.window.showInformationMessage("No active editor!");
    return false;
  }

  const positionCurrent = editor.selection.active;
  const intLineNumberCurrent = positionCurrent.line;
  const lineObjCurrent = editor.document.lineAt(intLineNumberCurrent);
  const boolEmptyLine = lineObjCurrent.isEmptyOrWhitespace;
  const snippetObj = new vscode.SnippetString(snippetsLines.join("\n"));

  if (boolEmptyLine) {
    return await editor.insertSnippet(snippetObj);
  }

  if (snippetsLines[0].startsWith(" # type: ignore")) {
    const positionEnd = new vscode.Position(
      intLineNumberCurrent,
      lineObjCurrent.text.length,
    );
    editor.selection = new vscode.Selection(positionEnd, positionEnd);
    return await editor.insertSnippet(snippetObj);
  }

  const currentLineIndent = lineObjCurrent.text.match(/^\s*/)?.[0] || "";
  const positionNextLine = new vscode.Position(
    intLineNumberCurrent + 1,
    currentLineIndent.length,
  );

  const edited = await editor.edit((editBuilder) => {
    editBuilder.insert(
      positionCurrent.with(intLineNumberCurrent, lineObjCurrent.text.length),
      "\n" + currentLineIndent,
    );
  });

  if (!edited) {
    return false;
  }

  editor.selection = new vscode.Selection(positionNextLine, positionNextLine);
  return await editor.insertSnippet(snippetObj);
}

export const dictIconMapping: { [key: string]: string } = {
  Favorite: "sparkle",

  Basic: "circle-large-outline",
  LogicControl: "git-compare",
  Log: "pencil",

  Mouse: "inspect",
  Keyboard: "keyboard",
  Window: "multiple-windows",
  UiInterface: "target",

  Browser: "globe",
  Excel: "book",
  Outlook: "mail-read",
  Application: "circuit-board",
  Database: "database",

  Data: "file-binary",
  Str: "symbol-text",
  List: "symbol-array",
  Dict: "json",
  Regex: "regex",
  Math: "symbol-operator",
  Time: "calendar",
  File: "request-changes",
  OCR: "search-fuzzy",

  Web: "cloud",
  Mail: "mail",
  FTP: "references",

  Clipboard: "clippy",
  System: "terminal",
  Credential: "key",

  ScreenPrint: "info",
  Dialog: "bell",
  Trigger: "rocket",
};
