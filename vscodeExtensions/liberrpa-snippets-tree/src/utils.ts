// FileName: utils.ts
import * as vscode from "vscode";

export function insertSnippet(snippetsLines: string[]): void {
  // console.log("--insertSnippet--");
  const editor = vscode.window.activeTextEditor;

  if (!editor) {
    vscode.window.showInformationMessage("No active editor!");
    return;
  }

  const positionCurrent = editor.selection.active;
  const intLineNumberCurrent = positionCurrent.line;
  const lineObjCurrent = editor.document.lineAt(intLineNumberCurrent);
  const isEmptyLine = lineObjCurrent.isEmptyOrWhitespace;

  // Insert snippets
  if (isEmptyLine) {
    // console.log("It's empty line.");
    editor.insertSnippet(new vscode.SnippetString(snippetsLines.join("\n")));
  } else {
    // console.log("It's not empty line.");

    // console.log(snippetsLines);

    // If the snippet is " # type: ignore", insert it at the line end.
    if (snippetsLines[0].startsWith(" # type: ignore")) {
      // console.log(" # type: ignore");

      const positionEnd = new vscode.Position(
        intLineNumberCurrent,
        lineObjCurrent.text.length
      );
      editor.selection = new vscode.Selection(positionEnd, positionEnd);
      editor.insertSnippet(new vscode.SnippetString(snippetsLines.join("\n")));

      return;
    }

    // In other situation, Create a new line, and move to it, then insert.
    const currentLineIndent = lineObjCurrent.text.match(/^\s*/)?.[0] || "";
    const positionNextLine = new vscode.Position(
      intLineNumberCurrent + 1,
      currentLineIndent.length
    );
    editor
      .edit((editBuilder) => {
        editBuilder.insert(
          positionCurrent.with(intLineNumberCurrent, lineObjCurrent.text.length),
          "\n" + currentLineIndent
        );
      })
      .then(() => {
        // Update the cursor position to the indented new line
        editor.selection = new vscode.Selection(positionNextLine, positionNextLine);
        editor.insertSnippet(new vscode.SnippetString(snippetsLines.join("\n")));
      });
  }
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

  HTTP: "cloud",
  Mail: "mail",
  FTP: "references",

  Clipboard: "clippy",
  System: "terminal",
  Credential: "key",

  ScreenPrint: "info",
  Dialog: "bell",
};
