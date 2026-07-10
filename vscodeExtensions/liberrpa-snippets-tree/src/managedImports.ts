// FileName: managedImports.ts
import { log } from "./output";
import type { ImportManifest } from "./interface";

import * as vscode from "vscode";

const MANAGED_IMPORT_START = "# <LiberRPA imports: managed>";
const MANAGED_IMPORT_NOTICE =
  "# This block is managed by LiberRPA. Do not edit it manually.";
const MANAGED_IMPORT_END = "# </LiberRPA imports: managed>";

const PYTHON_ENCODING_PATTERN = /^#.*coding[:=]\s*[-\w.]+/;
const MODULE_DOCSTRING_START_PATTERN = /^(?:[rRuU]{0,2})?("""|''')/;
const FUTURE_IMPORT_PATTERN = /^from\s+__future__\s+import\b/;

interface ManagedImportBlock {
  startLine: number;
  endLine: number;
}

function findManagedImportBlock(
  document: vscode.TextDocument,
): ManagedImportBlock | undefined {
  let startLine: number | undefined;

  for (let line = 0; line < document.lineCount; line += 1) {
    const text = document.lineAt(line).text.trim();

    if (text === MANAGED_IMPORT_START) {
      if (startLine !== undefined) {
        throw new Error(
          "The Python file contains more than one LiberRPA managed import start marker.",
        );
      }

      startLine = line;
      continue;
    }

    if (text === MANAGED_IMPORT_END && startLine !== undefined) {
      return {
        startLine,
        endLine: line,
      };
    }
  }

  if (startLine !== undefined) {
    throw new Error("The LiberRPA managed import block is missing its end marker.");
  }

  return undefined;
}

function skipBlankAndCommentLines(
  document: vscode.TextDocument,
  startLine: number,
): number {
  let line = startLine;

  while (line < document.lineCount) {
    const text = document.lineAt(line).text.trim();

    if (text === "" || text.startsWith("#")) {
      line += 1;
      continue;
    }

    break;
  }

  return line;
}

function findModuleDocstringEndLine(
  document: vscode.TextDocument,
  startLine: number,
): number | undefined {
  if (startLine >= document.lineCount) {
    return undefined;
  }

  const firstLineText = document.lineAt(startLine).text.trimStart();
  const match = MODULE_DOCSTRING_START_PATTERN.exec(firstLineText);

  if (!match) {
    return undefined;
  }

  const delimiter = match[1];
  const contentAfterOpeningDelimiter = firstLineText.slice(match[0].length);

  // Single-line module docstring:
  // """Module documentation."""
  if (contentAfterOpeningDelimiter.includes(delimiter)) {
    return startLine;
  }

  // Multi-line module docstring.
  for (let line = startLine + 1; line < document.lineCount; line += 1) {
    if (document.lineAt(line).text.includes(delimiter)) {
      return line;
    }
  }

  throw new Error(
    "The Python module docstring is not closed, so LiberRPA imports cannot be inserted safely.",
  );
}

function findPythonStatementEndLine(
  document: vscode.TextDocument,
  startLine: number,
): number {
  let parenthesisDepth = 0;

  for (let line = startLine; line < document.lineCount; line += 1) {
    const text = document.lineAt(line).text;
    const codeWithoutComment = text.split("#", 1)[0];

    for (const character of codeWithoutComment) {
      if (character === "(") {
        parenthesisDepth += 1;
      } else if (character === ")") {
        parenthesisDepth -= 1;
      }
    }

    const hasBackslashContinuation = codeWithoutComment.trimEnd().endsWith("\\");

    if (parenthesisDepth <= 0 && !hasBackslashContinuation) {
      return line;
    }
  }

  return document.lineCount - 1;
}

function getDefaultInsertLine(document: vscode.TextDocument): number {
  let line = 0;

  // Keep a shebang on the first physical line.
  if (document.lineCount > 0 && document.lineAt(0).text.startsWith("#!")) {
    line = 1;
  }

  // Python allows an encoding declaration on the first or second physical line.
  for (
    let encodingLine = 0;
    encodingLine < Math.min(2, document.lineCount);
    encodingLine += 1
  ) {
    if (PYTHON_ENCODING_PATTERN.test(document.lineAt(encodingLine).text)) {
      line = Math.max(line, encodingLine + 1);
    }
  }

  // Keep file header comments, such as "# FileName:", before the import block.
  const possibleDocstringLine = skipBlankAndCommentLines(document, line);
  const docstringEndLine = findModuleDocstringEndLine(document, possibleDocstringLine);

  if (docstringEndLine !== undefined) {
    line = docstringEndLine + 1;
  } else {
    line = possibleDocstringLine;
  }

  // All __future__ imports must remain before normal imports.
  while (line < document.lineCount) {
    const possibleFutureImportLine = skipBlankAndCommentLines(document, line);

    if (possibleFutureImportLine >= document.lineCount) {
      return document.lineCount;
    }

    const text = document.lineAt(possibleFutureImportLine).text.trim();

    if (!FUTURE_IMPORT_PATTERN.test(text)) {
      return line;
    }

    line = findPythonStatementEndLine(document, possibleFutureImportLine) + 1;
  }

  return line;
}

function parseExistingManagedImports(
  document: vscode.TextDocument,
  block: ManagedImportBlock,
): string[] {
  const importNames: string[] = [];

  for (let line = block.startLine + 1; line < block.endLine; line += 1) {
    const text = document.lineAt(line).text.trim();
    const match = /^([A-Za-z_][A-Za-z0-9_]*)\s*,\s*$/.exec(text);

    if (match) {
      importNames.push(match[1]);
    }
  }

  return importNames;
}

function sortImportNames(importNames: string[], importOrder: string[]): string[] {
  const orderIndexes = new Map<string, number>();

  importOrder.forEach((name, index) => {
    orderIndexes.set(name, index);
  });

  const uniqueNames = [...new Set(importNames)];

  const knownNames = uniqueNames.filter((name) => orderIndexes.has(name));
  const unknownNames = uniqueNames.filter((name) => !orderIndexes.has(name));

  knownNames.sort(
    (left, right) =>
      (orderIndexes.get(left) ?? Number.MAX_SAFE_INTEGER) -
      (orderIndexes.get(right) ?? Number.MAX_SAFE_INTEGER),
  );

  unknownNames.sort();

  if (unknownNames.length > 0) {
    log.warn(
      `[Imports] Import names are missing from importOrder: ${unknownNames.join(", ")}.`,
    );
  }

  return [...knownNames, ...unknownNames];
}

function buildManagedImportBlock(importSource: string, importNames: string[]): string {
  const lines = [MANAGED_IMPORT_START, MANAGED_IMPORT_NOTICE];

  if (importNames.length > 0) {
    lines.push(`from ${importSource} import (`);

    for (const name of importNames) {
      lines.push(`    ${name},`);
    }

    lines.push(")");
  }

  lines.push(MANAGED_IMPORT_END);

  return lines.join("\n");
}

function getInsertPosition(
  document: vscode.TextDocument,
  insertLine: number,
): vscode.Position {
  if (insertLine >= document.lineCount) {
    return document.positionAt(document.getText().length);
  }

  return new vscode.Position(insertLine, 0);
}

function buildInsertedBlockText(
  document: vscode.TextDocument,
  insertLine: number,
  blockText: string,
): string {
  const previousLineIsBlank =
    insertLine === 0 || document.lineAt(insertLine - 1).text.trim() === "";

  const nextLineIsBlank =
    insertLine >= document.lineCount || document.lineAt(insertLine).text.trim() === "";

  const prefix = previousLineIsBlank ? "" : "\n";
  const suffix = nextLineIsBlank ? "\n" : "\n\n";

  return `${prefix}${blockText}${suffix}`;
}

export async function updateManagedImports(
  editor: vscode.TextEditor,
  importManifest: ImportManifest,
  importNamesToAdd: string[],
): Promise<void> {
  if (importNamesToAdd.length === 0) {
    log.trace("[Imports] No imports required for this snippet.");
    return;
  }

  const document = editor.document;
  const existingBlock = findManagedImportBlock(document);

  const existingImportNames = existingBlock
    ? parseExistingManagedImports(document, existingBlock)
    : [];

  const nextImportNames = sortImportNames(
    [...existingImportNames, ...importNamesToAdd],
    importManifest.importOrder,
  );

  const nextBlockText = buildManagedImportBlock(
    importManifest.importSource,
    nextImportNames,
  );

  log.trace(
    `[Imports] Updating managed imports. add=[${importNamesToAdd.join(
      ", ",
    )}], final=[${nextImportNames.join(", ")}], mode=${
      existingBlock ? "replace" : "insert"
    }.`,
  );

  const edited = await editor.edit((editBuilder) => {
    if (existingBlock) {
      const start = new vscode.Position(existingBlock.startLine, 0);
      const endLine = document.lineAt(existingBlock.endLine);
      const end = new vscode.Position(existingBlock.endLine, endLine.text.length);

      editBuilder.replace(new vscode.Range(start, end), nextBlockText);

      return;
    }

    const insertLine = getDefaultInsertLine(document);
    const insertPosition = getInsertPosition(document, insertLine);
    const insertedText = buildInsertedBlockText(document, insertLine, nextBlockText);

    editBuilder.insert(insertPosition, insertedText);
  });

  if (!edited) {
    throw new Error("Failed to update the LiberRPA managed import block.");
  }

  log.trace("[Imports] Managed import block updated.");
}
