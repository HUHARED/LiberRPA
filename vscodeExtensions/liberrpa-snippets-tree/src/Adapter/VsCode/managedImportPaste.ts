// FileName: managedImportPaste.ts

import * as vscode from "vscode";

import { analyzeManagedImportNames } from "../Python/managedImportAnalysis";
import { reportError, reportWarning } from "./errorHandling";
import { log } from "./output";
import {
  buildManagedImportsFromReferencedNames,
  buildManagedImportSymbolIndex,
} from "../../Application/SnippetInsertion/managedImportRecognition";
import { updateManagedImports } from "../../Application/SnippetInsertion/managedImports";
import type { Info_SnippetRepository } from "../../Domain/Snippet/snippetTypes";

const STR_PYTHON_PASTE_INDENT_EXTENSION = "hyesun.py-paste-indent";
const STR_PYTHON_PASTE_INDENT_COMMAND = "pyPasteIndent.pasteIndent";
const STR_STANDARD_PASTE_COMMAND = "editor.action.clipboardPasteAction";
const STR_MANAGED_PASTE_COMMAND = "LiberRPA.snippetsTree.pastePythonWithManagedImports";
const INT_PASTE_CHANGE_WAIT_MS = 1000;
const INT_PASTE_SETTLE_DELAY_MS = 50;

async function executePythonPaste(document: vscode.TextDocument): Promise<boolean> {
  const strPasteCommand =
    vscode.extensions.getExtension(STR_PYTHON_PASTE_INDENT_EXTENSION) === undefined
      ? STR_STANDARD_PASTE_COMMAND
      : STR_PYTHON_PASTE_INDENT_COMMAND;

  const intVersionBeforePaste = document.version;
  let changeDisposable: vscode.Disposable | undefined;

  const changePromise = new Promise<boolean>((resolve) => {
    changeDisposable = vscode.workspace.onDidChangeTextDocument((event) => {
      if (event.document.uri.toString() !== document.uri.toString()) {
        return;
      }
      if (event.document.version === intVersionBeforePaste) {
        return;
      }
      resolve(true);
    });
  });

  try {
    await vscode.commands.executeCommand(strPasteCommand);
    if (document.version !== intVersionBeforePaste) {
      return true;
    }

    return await Promise.race([
      changePromise,
      new Promise<boolean>((resolve) => {
        setTimeout(() => resolve(false), INT_PASTE_CHANGE_WAIT_MS);
      }),
    ]);
  } finally {
    changeDisposable?.dispose();
  }
}

async function updateManagedImportsAfterPaste(
  document: vscode.TextDocument,
  repository: Info_SnippetRepository,
  strHelperPath: string,
  symbolIndex: ReturnType<typeof buildManagedImportSymbolIndex>,
): Promise<void> {
  const intAnalyzedVersion = document.version;
  const arrReferencedName = await analyzeManagedImportNames(
    strHelperPath,
    document.getText(),
    symbolIndex.arrKnownName,
  );

  if (arrReferencedName === null) {
    log.trace(
      "[PasteImports] Managed import analysis skipped because the Python file is not parseable.",
    );
    return;
  }

  if (document.version !== intAnalyzedVersion) {
    log.trace(
      "[PasteImports] Managed import analysis skipped because the document changed during analysis.",
    );
    return;
  }

  const dictImport = buildManagedImportsFromReferencedNames(arrReferencedName, symbolIndex);
  if (Object.keys(dictImport).length === 0) {
    log.trace("[PasteImports] No missing managed import candidates were found.");
    return;
  }

  await updateManagedImports(document, repository.importSource, dictImport);
  log.debug(
    `[PasteImports] Managed imports checked after paste; referenced=${arrReferencedName.length}.`,
  );
}

export function registerManagedImportPaste(
  repository: Info_SnippetRepository,
  strHelperPath: string,
): vscode.Disposable {
  return vscode.commands.registerCommand(
    STR_MANAGED_PASTE_COMMAND,
    async (): Promise<void> => {
      const editor = vscode.window.activeTextEditor;
      if (editor?.document.languageId !== "python") {
        await vscode.commands.executeCommand(STR_STANDARD_PASTE_COMMAND);
        return;
      }

      const document = editor.document;
      const symbolIndex = buildManagedImportSymbolIndex(repository.importSource);
      let boolAnalyzeAfterPaste = symbolIndex.arrKnownName.length > 0;

      if (boolAnalyzeAfterPaste) {
        try {
          const strClipboardText = await vscode.env.clipboard.readText();
          boolAnalyzeAfterPaste = symbolIndex.arrKnownName.some((strName) =>
            strClipboardText.includes(strName),
          );
        } catch (e) {
          log.debug(
            `[PasteImports] Clipboard pre-check failed; full analysis will continue: ${e instanceof Error ? e.message : String(e)}`,
          );
        }
      }

      let boolDocumentChanged: boolean;
      try {
        boolDocumentChanged = await executePythonPaste(document);
      } catch (e) {
        reportError("Failed to paste Python code", e, true);
        return;
      }

      if (!boolDocumentChanged || !boolAnalyzeAfterPaste) {
        return;
      }

      await new Promise<void>((resolve) => {
        setTimeout(resolve, INT_PASTE_SETTLE_DELAY_MS);
      });

      try {
        await updateManagedImportsAfterPaste(
          document,
          repository,
          strHelperPath,
          symbolIndex,
        );
      } catch (e) {
        // Paste has already succeeded, so report only the optional import update.
        reportWarning("Managed imports were not updated after paste", e, true);
      }
    },
  );
}
