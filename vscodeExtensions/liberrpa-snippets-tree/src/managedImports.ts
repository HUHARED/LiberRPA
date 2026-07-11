// FileName: managedImports.ts
import { log } from "./output";
import type { DictImportsInfo, ImportSourceConfig } from "./interface";

import * as vscode from "vscode";

/*
Managed import block format:

# <LiberRPA imports: managed>
# This block is managed by LiberRPA. Do not edit it manually.
from liberrpa.Modules import (
    Mouse,
)
# </LiberRPA imports: managed>

This module has two main jobs:

1. If the block already exists:
    - read its current imports;
    - merge new imports into them;
    - sort them;
    - replace the whole block.

2. If the block does not exist:
    - find a safe position near the top of the Python file;
    - keep shebang, encoding declaration, module docstring, and __future__ imports first;
    - insert a new managed block there.
*/

const STR_MANAGED_IMPORT_START = "# <LiberRPA imports: managed>";
const STR_MANAGED_IMPORT_NOTICE =
  "# This block is managed by LiberRPA. Do not edit it manually.";
const STR_MANAGED_IMPORT_END = "# </LiberRPA imports: managed>";

// Python source-file encoding declaration, for example:
// # -*- coding: utf-8 -*-
// # coding=utf-8
const STR_PYTHON_ENCODING_PATTERN = /^#.*coding[:=]\s*[-\w.]+/;

// Only handles ordinary top-level Python module docstrings that start with
// triple single or double quotes, optionally prefixed by r/R/u/U.
// Examples:
// """Module docstring."""
// r"""Raw module docstring."""
const STR_MODULE_DOCSTRING_START_PATTERN = /^(?:[rRuU]{0,2})?("""|''')/;

// __future__ imports must remain before normal imports.
const STR_FUTURE_IMPORT_PATTERN = /^from\s+__future__\s+import\b/;

/**
 * The inclusive start and end line numbers of an existing managed block.
 */
interface ManagedImportBlock {
  startLine: number;
  endLine: number;
}

/**
 * Find an existing LiberRPA managed import block.
 *
 * Returns undefined when the file does not have a managed block.
 * Throws when the marker structure is clearly broken, because silently
 * inserting another block would make the file harder to repair.
 */
function findManagedImportBlock(
  document: vscode.TextDocument
): ManagedImportBlock | undefined {
  let intStartLine: number | undefined;

  for (let intLine = 0; intLine < document.lineCount; intLine += 1) {
    const strText = document.lineAt(intLine).text.trim();

    if (strText === STR_MANAGED_IMPORT_START) {
      // A second start marker before finding an end marker means that the file already contains an invalid/nested managed block.
      if (intStartLine !== undefined) {
        throw new Error(
          "The Python file contains more than one LiberRPA managed import start marker."
        );
      }

      intStartLine = intLine;
      continue;
    }

    // The end marker only belongs to a block after a start marker has already been found.
    if (strText === STR_MANAGED_IMPORT_END && intStartLine !== undefined) {
      return { startLine: intStartLine, endLine: intLine };
    }
  }

  // A start marker without an end marker should not be overwritten, because doing so could delete or duplicate user code.
  if (intStartLine !== undefined) {
    throw new Error("The LiberRPA managed import block is missing its end marker.");
  }

  return undefined;
}

/**
 * Move downward past blank lines and comment-only lines.
 *
 * This is mainly used while locating the insertion point near the top of a
 * Python file. Header comments such as "# FileName:" should stay above imports.
 */
function skipBlankAndCommentLines(
  document: vscode.TextDocument,
  startLine: number
): number {
  let intLine = startLine;

  while (intLine < document.lineCount) {
    const strText = document.lineAt(intLine).text.trim();

    if (strText === "" || strText.startsWith("#")) {
      intLine += 1;
      continue;
    }

    break;
  }

  return intLine;
}

/**
 * If startLine begins a Python module docstring, return its closing line.
 *
 * Returns undefined when startLine is not a module docstring.
 *
 * This intentionally handles only simple triple-quoted docstrings. It is not intended to be a complete Python parser.
 */
function findModuleDocstringEndLine(
  document: vscode.TextDocument,
  startLine: number
): number | undefined {
  if (startLine >= document.lineCount) {
    return undefined;
  }

  const strFirstLineText = document.lineAt(startLine).text.trimStart();
  const match = STR_MODULE_DOCSTRING_START_PATTERN.exec(strFirstLineText);

  if (!match) {
    return undefined;
  }

  // match[1] is either """ or '''.
  const strDelimiter = match[1];
  const strTextAfterOpening = strFirstLineText.slice(match[0].length);

  // Single-line docstring:
  // """Module documentation."""
  if (strTextAfterOpening.includes(strDelimiter)) {
    return startLine;
  }

  // Multi-line docstring: search for the first later line containing
  // the same closing triple-quote delimiter.
  for (let intLine = startLine + 1; intLine < document.lineCount; intLine += 1) {
    if (document.lineAt(intLine).text.includes(strDelimiter)) {
      return intLine;
    }
  }

  // Do not guess an insertion position when the docstring is incomplete.
  throw new Error(
    "The Python module docstring is not closed, so LiberRPA imports cannot be inserted safely."
  );
}

/**
 * Find the final physical line of one Python statement.
 *
 * This is used for multi-line __future__ imports, for example:
 *
 * from __future__ import (
 *     annotations,
 * )
 *
 * It tracks parentheses and explicit "\\" line continuations. This is a small,
 * purpose-specific check rather than a full Python syntax parser.
 */
function findPythonStatementEndLine(
  document: vscode.TextDocument,
  startLine: number
): number {
  let intParenthesisDepth = 0;

  for (let intLine = startLine; intLine < document.lineCount; intLine += 1) {
    // Ignore trailing comments so parentheses inside comments do not affect
    // the statement-depth calculation.
    const strCode = document.lineAt(intLine).text.split("#", 1)[0];

    for (const character of strCode) {
      if (character === "(") {
        intParenthesisDepth += 1;
      } else if (character === ")") {
        intParenthesisDepth -= 1;
      }
    }

    // The statement ends only when:
    // 1. all opened parentheses have been closed; and
    // 2. the line does not explicitly continue with "\\".
    if (intParenthesisDepth <= 0 && !strCode.trimEnd().endsWith("\\")) {
      return intLine;
    }
  }

  // If the statement is incomplete, return the final document line.
  // The caller will therefore insert only after the visible statement text.
  return document.lineCount - 1;
}

/**
 * Decide where a new managed import block should be inserted.
 *
 * Desired order:
 *
 * 1. shebang
 * 2. encoding declaration
 * 3. file-header comments
 * 4. module docstring
 * 5. __future__ imports
 * 6. LiberRPA managed imports
 * 7. ordinary imports and code
 */
function getDefaultInsertLine(document: vscode.TextDocument): number {
  let intLine = 0;

  // A shebang must remain on the first physical line.
  if (document.lineCount > 0 && document.lineAt(0).text.startsWith("#!")) {
    intLine = 1;
  }

  // Python allows an encoding declaration only on the first or second
  // physical line, so no later lines need to be checked.
  for (
    let intEncodingLine = 0;
    intEncodingLine < Math.min(2, document.lineCount);
    intEncodingLine += 1
  ) {
    if (STR_PYTHON_ENCODING_PATTERN.test(document.lineAt(intEncodingLine).text)) {
      intLine = Math.max(intLine, intEncodingLine + 1);
    }
  }

  // Skip header comments and blank lines before checking for a module
  // docstring. For example, "# FileName:" should stay above the docstring.
  const intPossibleDocstringLine = skipBlankAndCommentLines(document, intLine);
  const intDocstringEndLine = findModuleDocstringEndLine(document, intPossibleDocstringLine);

  // If there is a module docstring, continue after it.
  // Otherwise, continue from the first non-comment/non-blank line.
  intLine = intDocstringEndLine === undefined ? intPossibleDocstringLine : intDocstringEndLine + 1;

  // There can be more than one __future__ import. Keep moving downward until
  // the first ordinary statement is found.
  while (intLine < document.lineCount) {
    const intPossibleFutureLine = skipBlankAndCommentLines(document, intLine);

    // The file ends after comments/blank lines.
    if (intPossibleFutureLine >= document.lineCount) {
      return document.lineCount;
    }

    const strText = document.lineAt(intPossibleFutureLine).text.trim();

    // The first non-future statement is where the managed block should be
    // inserted. Return "line" rather than possibleFutureLine so existing blank
    // lines/comments remain below the previous metadata section.
    if (!STR_FUTURE_IMPORT_PATTERN.test(strText)) {
      return intLine;
    }

    // Skip the complete __future__ statement, including a parenthesized
    // multi-line import.
    intLine = findPythonStatementEndLine(document, intPossibleFutureLine) + 1;
  }

  return intLine;
}

/**
 * Read imports from an existing managed block.
 *
 * Supported managed format:
 *
 * from some.module import (
 *     NameA,
 *     NameB,
 * )
 *
 * The returned object is grouped by import source:
 *
 * {
 *   "some.module": ["NameA", "NameB"]
 * }
 */
function parseExistingManagedImports(
  document: vscode.TextDocument,
  block: ManagedImportBlock
): DictImportsInfo {
  const dictResult: DictImportsInfo = {};

  // The source currently being read inside:
  // from <currentSource> import (
  let strCurrentSource: string | undefined;

  for (let intLine = block.startLine + 1; intLine < block.endLine; intLine += 1) {
    const strText = document.lineAt(intLine).text.trim();

    // Start of one import group.
    const sourceMatch = /^from\s+(.+?)\s+import\s+\($/.exec(strText);

    if (sourceMatch) {
      strCurrentSource = sourceMatch[1];
      dictResult[strCurrentSource] ??= [];
      continue;
    }

    // End of the current import group.
    if (strText === ")") {
      strCurrentSource = undefined;
      continue;
    }

    // Ignore notice text, blank lines, or unsupported text outside an
    // active "from ... import (" group.
    if (!strCurrentSource) {
      continue;
    }

    // Import name line, for example: "Mouse,"
    const nameMatch = /^([A-Za-z_][A-Za-z0-9_]*)\s*,\s*$/.exec(strText);

    if (nameMatch) {
      dictResult[strCurrentSource].push(nameMatch[1]);
    }
  }

  return dictResult;
}

/**
 * Remove duplicate names and sort names within one import source.
 *
 * Known names follow sourceConfig.order.
 * Unknown names are kept, sorted alphabetically, and placed after known names.
 * Keeping unknown names avoids silently deleting imports already present in
 * the user's managed block.
 */
function sortImportNames(
  importSource: string,
  importNames: string[],
  sourceConfig: ImportSourceConfig | undefined
): string[] {
  const arrUniqueNames = [...new Set(importNames)];

  // A source without configuration can still be preserved. Alphabetical order
  // is used as a predictable fallback.
  if (!sourceConfig) {
    log.warn(
      `[Imports] Import source ${importSource} has no order configuration; names are sorted alphabetically.`
    );
    return arrUniqueNames.sort();
  }

  // Convert the configured order into name -> numeric position so sorting
  // does not repeatedly scan the whole order array.
  const mapOrderIndexes = new Map(sourceConfig.order.map((name, index) => [name, index]));

  const arrKnownNames = arrUniqueNames.filter((name) => mapOrderIndexes.has(name));
  const arrUnknownNames = arrUniqueNames.filter((name) => !mapOrderIndexes.has(name));

  // The non-null assertion is safe here because knownNames only contains
  // values already confirmed by orderIndexes.has(name).
  arrKnownNames.sort((left, right) => mapOrderIndexes.get(left)! - mapOrderIndexes.get(right)!);

  arrUnknownNames.sort();

  if (arrUnknownNames.length > 0) {
    log.warn(
      `[Imports] Names are missing from ${importSource}'s import order: ${arrUnknownNames.join(", ")}.`
    );
  }

  return [...arrKnownNames, ...arrUnknownNames];
}

/**
 * Sort import source groups.
 *
 * Sources declared in the catalog configuration keep their configured object
 * order. Sources not declared there are kept afterwards in alphabetical order.
 */
function sortImportSources(
  imports: DictImportsInfo,
  importSources: Record<string, ImportSourceConfig>
): string[] {
  const arrConfiguredSources = Object.keys(importSources);
  const arrPresentSources = Object.keys(imports);

  return [
    ...arrConfiguredSources.filter((source) => arrPresentSources.includes(source)),
    ...arrPresentSources.filter((source) => !arrConfiguredSources.includes(source)).sort(),
  ];
}

/**
 * Merge the imports already present in the file with the imports required by
 * the newly inserted snippet.
 *
 * Example:
 *
 * existingImports:
 *   liberrpa.Modules -> [Mouse]
 *
 * importsToAdd:
 *   liberrpa.Modules -> [Mouse, Excel]
 *
 * result:
 *   liberrpa.Modules -> [Mouse, Excel]
 *
 * sortImportNames also removes duplicates and applies the configured order.
 */
function mergeImports(
  existingImports: DictImportsInfo,
  importsToAdd: DictImportsInfo,
  importSources: Record<string, ImportSourceConfig>
): DictImportsInfo {
  const dictResult: DictImportsInfo = {};

  // A Set produces the union of import sources from both objects.
  const setAllSources = new Set([
    ...Object.keys(existingImports),
    ...Object.keys(importsToAdd),
  ]);

  for (const strSource of setAllSources) {
    dictResult[strSource] = sortImportNames(
      strSource,
      [...(existingImports[strSource] ?? []), ...(importsToAdd[strSource] ?? [])],
      importSources[strSource]
    );
  }

  return dictResult;
}

/**
 * Convert the normalized import data back into the managed Python block text.
 */
function buildManagedImportBlock(
  imports: DictImportsInfo,
  importSources: Record<string, ImportSourceConfig>
): string {
  const arrLines = [STR_MANAGED_IMPORT_START, STR_MANAGED_IMPORT_NOTICE];
  const arrSources = sortImportSources(imports, importSources);

  arrSources.forEach((strName, intIndex) => {
    const importNames = imports[strName];

    // Empty groups do not produce Python import statements.
    if (importNames.length === 0) {
      return;
    }

    // Separate different import sources with one blank line.
    if (intIndex > 0) {
      arrLines.push("");
    }

    arrLines.push(`from ${strName} import (`);

    for (const name of importNames) {
      arrLines.push(`    ${name},`);
    }

    arrLines.push(")");
  });

  arrLines.push(STR_MANAGED_IMPORT_END);
  return arrLines.join("\n");
}

function getDisplayPath(document: vscode.TextDocument): string {
  const workspaceFolder = vscode.workspace.getWorkspaceFolder(document.uri);

  if (!workspaceFolder) {
    return document.uri.fsPath;
  }

  return vscode.workspace.asRelativePath(document.uri, false);
}

/**
 * Add only the blank lines needed around a newly inserted block.
 *
 * - No extra prefix when the previous line is already blank or the block is
 *   inserted at the start of the file.
 * - One newline after the block when the next line is already blank/end-of-file.
 * - Two newlines after the block when ordinary code follows immediately.
 */
function buildInsertedBlockText(
  document: vscode.TextDocument,
  insertLine: number,
  blockText: string
): string {
  const boolPreviousLineIsBlank =
    insertLine === 0 || document.lineAt(insertLine - 1).text.trim() === "";

  const boolNextLineIsBlank =
    insertLine >= document.lineCount || document.lineAt(insertLine).text.trim() === "";

  const strPrefix = boolPreviousLineIsBlank ? "" : "\n";
  const strSuffix = boolNextLineIsBlank ? "\n" : "\n\n";

  return `${strPrefix}${blockText}${strSuffix}`;
}

/**
 * Add snippet-required imports to the current Python editor.
 *
 * High-level flow:
 *
 * 1. Ignore a snippet that requires no imports.
 * 2. Find and parse an existing managed block, if present.
 * 3. Merge existing imports with the new imports.
 * 4. Rebuild the complete managed block.
 * 5. Replace the old block or insert a new block.
 */
export async function updateManagedImports(
  editor: vscode.TextEditor,
  importSources: Record<string, ImportSourceConfig>,
  importsToAdd: DictImportsInfo
): Promise<void> {
  // A snippet can be pure Python syntax and require no managed imports.
  if (Object.values(importsToAdd).every((names) => names.length === 0)) {
    return;
  }

  const document = editor.document;

  // Existing block path:
  // parse and preserve its current imports before adding new ones.
  const dictBlock = findManagedImportBlock(document);
  const dictExistingImports = dictBlock ? parseExistingManagedImports(document, dictBlock) : {};

  // Produce one normalized data structure before generating any text.
  const dictNextImports = mergeImports(dictExistingImports, importsToAdd, importSources);

  const strNextBlockText = buildManagedImportBlock(dictNextImports, importSources);

  const strDisplayPath = getDisplayPath(document);
  log.trace(
    `[Imports] Updating managed block in ${strDisplayPath}; mode=${dictBlock ? "replace" : "insert"}.`
  );

  const edited = await editor.edit((editBuilder) => {
    if (dictBlock) {
      // Replace the entire managed block. Rebuilding the whole block is simpler
      // and safer than trying to patch individual lines in place.
      const positionStart = new vscode.Position(dictBlock.startLine, 0);
      const endLine = document.lineAt(dictBlock.endLine);
      const positionEnd = new vscode.Position(dictBlock.endLine, endLine.text.length);

      editBuilder.replace(new vscode.Range(positionStart, positionEnd), strNextBlockText);

      return;
    }

    // No block exists yet. Find a safe Python module-level insertion position.
    const intInsertLine = getDefaultInsertLine(document);

    // VS Code positions normally refer to a line/column. At end-of-file, use
    // the final text offset because insertLine can equal document.lineCount.
    const positionInsert =
      intInsertLine >= document.lineCount
        ? document.positionAt(document.getText().length)
        : new vscode.Position(intInsertLine, 0);

    editBuilder.insert(
      positionInsert,
      buildInsertedBlockText(document, intInsertLine, strNextBlockText)
    );
  });

  if (!edited) {
    throw new Error("Failed to update the LiberRPA managed import block.");
  }

  log.debug("[Imports] Managed import block updated.");
}
