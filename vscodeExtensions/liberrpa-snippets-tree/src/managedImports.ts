// FileName: managedImports.ts
import { log } from "./output";
import type { DictImportsInfo, DictImportSourceConfig } from "./interface";

import * as vscode from "vscode";

/*
Managed import block format:

# <LiberRPA imports: managed>
# This block is managed by LiberRPA. Do not edit it manually.
from liberrpa.Modules import (
    Mouse,
)

from ExcelTools import (
    Workbook as ExcelTools_Workbook,
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

// Handles ordinary top-level Python module docstrings that start with single or triple quotes, optionally prefixed by r/R/u/U.
// Examples:
// """Module docstring."""
// r"""Raw module docstring."""
// "Module docstring."
const STR_MODULE_DOCSTRING_START_PATTERN = /^(?:[rRuU]{0,2})?("""|'''|"|')/;

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
  document: vscode.TextDocument,
): ManagedImportBlock | undefined {
  let intStartLine: number | undefined;
  let dictBlock: ManagedImportBlock | undefined;

  for (let intLine = 0; intLine < document.lineCount; intLine += 1) {
    const strRawText = document.lineAt(intLine).text;
    const strText = strRawText.trim();

    if (strText === STR_MANAGED_IMPORT_START) {
      if (strRawText !== STR_MANAGED_IMPORT_START) {
        throw new Error(
          `The LiberRPA managed import start marker on line ${intLine + 1} must appear alone without indentation or trailing whitespace.`,
        );
      }

      // A second start marker before finding an end marker means that the file contains a nested block.
      // A start marker after a complete block means that the file contains two managed blocks.
      if (intStartLine !== undefined) {
        throw new Error(
          `The Python file contains a nested LiberRPA managed import start marker on line ${intLine + 1}.`,
        );
      }
      if (dictBlock !== undefined) {
        throw new Error(
          `The Python file contains more than one LiberRPA managed import block; the second block starts on line ${intLine + 1}.`,
        );
      }

      intStartLine = intLine;
      continue;
    }

    if (strText !== STR_MANAGED_IMPORT_END) {
      continue;
    }

    if (strRawText !== STR_MANAGED_IMPORT_END) {
      throw new Error(
        `The LiberRPA managed import end marker on line ${intLine + 1} must appear alone without indentation or trailing whitespace.`,
      );
    }

    if (intStartLine === undefined) {
      throw new Error(
        `The Python file contains a LiberRPA managed import end marker without a matching start marker on line ${intLine + 1}.`,
      );
    }

    dictBlock = { startLine: intStartLine, endLine: intLine };
    intStartLine = undefined;
  }

  // A start marker without an end marker should not be overwritten, because doing so could delete or duplicate user code.
  if (intStartLine !== undefined) {
    throw new Error(
      `The LiberRPA managed import block starting on line ${intStartLine + 1} is missing its end marker.`,
    );
  }

  return dictBlock;
}

/**
 * Move downward past blank lines and comment-only lines.
 *
 * This is mainly used while locating the insertion point near the top of a
 * Python file. Header comments such as "# FileName:" should stay above imports.
 */
function skipBlankAndCommentLines(
  document: vscode.TextDocument,
  startLine: number,
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
 * This intentionally handles only simple single- or triple-quoted docstrings. It is not intended to be a complete Python parser.
 */
function findModuleDocstringEndLine(
  document: vscode.TextDocument,
  startLine: number,
): number | undefined {
  if (startLine >= document.lineCount) {
    return undefined;
  }

  const strFirstLineText = document.lineAt(startLine).text.trimStart();
  const match = STR_MODULE_DOCSTRING_START_PATTERN.exec(strFirstLineText);

  if (!match) {
    return undefined;
  }

  // match[1] is a single- or triple-quote delimiter.
  const strDelimiter = match[1];
  const strTextAfterOpening = strFirstLineText.slice(match[0].length);

  if (strDelimiter.length === 1) {
    let boolEscaped = false;

    for (const strCharacter of strTextAfterOpening) {
      if (strCharacter === strDelimiter && !boolEscaped) {
        return startLine;
      }

      if (strCharacter === "\\" && !boolEscaped) {
        boolEscaped = true;
      } else {
        boolEscaped = false;
      }
    }

    throw new Error(
      "The single-quoted Python module docstring is not closed on its starting line, so LiberRPA imports cannot be inserted safely.",
    );
  }

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
    "The Python module docstring is not closed, so LiberRPA imports cannot be inserted safely.",
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
  startLine: number,
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
  // A document containing only whitespace is still an empty Python script.
  // Insert at its beginning instead of after its final blank line.
  if (document.getText().trim() === "") {
    return 0;
  }

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
  const intDocstringEndLine = findModuleDocstringEndLine(
    document,
    intPossibleDocstringLine,
  );

  // If there is a module docstring, continue after it.
  // Otherwise, continue from the first non-comment/non-blank line.
  intLine =
    intDocstringEndLine === undefined ? intPossibleDocstringLine : intDocstringEndLine + 1;

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
function getExpectedImportAlias(
  importSource: string,
  importName: string,
  sourceConfigDict: DictImportSourceConfig | undefined,
): string | undefined {
  if (sourceConfigDict?.aliasMode === "source_module") {
    return `${importSource}_${importName}`;
  }

  return undefined;
}

function parseExistingManagedImports(
  document: vscode.TextDocument,
  block: ManagedImportBlock,
  importSourceDict: Record<string, DictImportSourceConfig>,
): DictImportsInfo {
  const dictResult: DictImportsInfo = {};

  // The source currently being read inside:
  // from <currentSource> import (
  let strCurrentSource: string | undefined;

  for (let intLine = block.startLine + 1; intLine < block.endLine; intLine += 1) {
    const strText = document.lineAt(intLine).text.trim();

    if (!strCurrentSource) {
      if (strText === "" || strText === STR_MANAGED_IMPORT_NOTICE) {
        continue;
      }

      // Start of one import group.
      const sourceMatch =
        /^from\s+([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\s+import\s+\($/.exec(
          strText,
        );

      if (sourceMatch) {
        strCurrentSource = sourceMatch[1];
        dictResult[strCurrentSource] ??= [];
        continue;
      }

      throw new Error(
        `Unexpected content in the LiberRPA managed import block on line ${intLine + 1}: ${strText}`,
      );
    }

    // Empty lines inside an import group are harmless and may exist in files created by an older version. The rebuilt block removes them.
    if (strText === "") {
      continue;
    }

    // End of the current import group.
    if (strText === ")") {
      strCurrentSource = undefined;
      continue;
    }

    // Import entry, for example:
    // Mouse,
    // Workbook as ExcelTools_Workbook,
    const importEntryMatch =
      /^([A-Za-z_][A-Za-z0-9_]*)(?:\s+as\s+([A-Za-z_][A-Za-z0-9_]*))?\s*,\s*$/.exec(
        strText,
      );

    if (!importEntryMatch) {
      throw new Error(
        `Invalid import entry in the LiberRPA managed import block on line ${intLine + 1}: ${strText}`,
      );
    }

    const strImportName = importEntryMatch[1];
    const strActualAlias = importEntryMatch[2];
    const strExpectedAlias = getExpectedImportAlias(
      strCurrentSource,
      strImportName,
      importSourceDict[strCurrentSource],
    );

    if (strActualAlias !== strExpectedAlias) {
      const strExpectedText =
        strExpectedAlias === undefined
          ? `Import ${strImportName} from ${strCurrentSource} must not use an alias.`
          : `Expected alias ${strExpectedAlias} for ${strCurrentSource}.${strImportName}.`;

      throw new Error(
        `${strExpectedText} Invalid entry on line ${intLine + 1}: ${strText}`,
      );
    }

    dictResult[strCurrentSource].push(strImportName);
  }

  if (strCurrentSource !== undefined) {
    throw new Error(
      `The import group for ${strCurrentSource} in the LiberRPA managed block is missing its closing parenthesis.`,
    );
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
  sourceConfig: DictImportSourceConfig | undefined,
): string[] {
  const arrUniqueNames = [...new Set(importNames)];

  // A source without configuration can still be preserved. Alphabetical order
  // is used as a predictable fallback.
  if (!sourceConfig) {
    log.warn(
      `[Imports] Import source ${importSource} has no order configuration; names are sorted alphabetically.`,
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
  arrKnownNames.sort(
    (left, right) => mapOrderIndexes.get(left)! - mapOrderIndexes.get(right)!,
  );

  arrUnknownNames.sort();

  if (arrUnknownNames.length > 0) {
    log.warn(
      `[Imports] Names are missing from ${importSource}'s import order: ${arrUnknownNames.join(", ")}.`,
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
  importSources: Record<string, DictImportSourceConfig>,
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
  importSources: Record<string, DictImportSourceConfig>,
): DictImportsInfo {
  const dictResult: DictImportsInfo = {};

  // A Set produces the union of import sources from both objects.
  const setAllSource = new Set([
    ...Object.keys(existingImports),
    ...Object.keys(importsToAdd),
  ]);

  for (const strSource of setAllSource) {
    dictResult[strSource] = sortImportNames(
      strSource,
      [...(existingImports[strSource] ?? []), ...(importsToAdd[strSource] ?? [])],
      importSources[strSource],
    );
  }

  return dictResult;
}

/**
 * Convert the normalized import data back into the managed Python block text.
 */
function buildManagedImportBlock(
  imports: DictImportsInfo,
  importSources: Record<string, DictImportSourceConfig>,
  strEol: string,
): string {
  const arrLine = [STR_MANAGED_IMPORT_START, STR_MANAGED_IMPORT_NOTICE];
  const arrSource = sortImportSources(imports, importSources);

  let boolHasImportGroup = false;

  arrSource.forEach((strSourceName) => {
    const arrImportName = imports[strSourceName];

    // Empty groups do not produce Python import statements.
    if (arrImportName.length === 0) {
      return;
    }

    // Separate different import sources with one blank line.
    if (boolHasImportGroup) {
      arrLine.push("");
    }

    arrLine.push(`from ${strSourceName} import (`);

    const dictSourceConfig = importSources[strSourceName];

    for (const strimportName of arrImportName) {
      const strAlias = getExpectedImportAlias(
        strimportName,
        strimportName,
        dictSourceConfig,
      );
      const strImportEntry =
        strAlias === undefined ? strimportName : `${strimportName} as ${strAlias}`;
      arrLine.push(`    ${strImportEntry},`);
    }

    arrLine.push(")");
    boolHasImportGroup = true;
  });

  arrLine.push(STR_MANAGED_IMPORT_END);
  return arrLine.join(strEol);
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
  blockText: string,
  strEol: string,
): string {
  const boolPreviousLineIsBlank =
    insertLine === 0 || document.lineAt(insertLine - 1).text.trim() === "";

  const boolNextLineIsBlank =
    insertLine >= document.lineCount || document.lineAt(insertLine).text.trim() === "";

  const strPrefix = boolPreviousLineIsBlank ? "" : strEol;
  const strSuffix = boolNextLineIsBlank ? strEol : strEol.repeat(2);

  return `${strPrefix}${blockText}${strSuffix}`;
}

function getDocumentEol(document: vscode.TextDocument): string {
  return document.eol === vscode.EndOfLine.CRLF ? "\r\n" : "\n";
}

/**
 * Build the text edits needed to add imports to one Python document.
 *
 * The function does not apply the edits. Completion and drop providers can therefore attach them to the same VS Code operation that inserts a snippet.
 */
export function createManagedImportTextEditBuilder(
  document: vscode.TextDocument,
  importSources: Record<string, DictImportSourceConfig>,
): (importsToAdd: DictImportsInfo) => vscode.TextEdit[] {
  let prepared:
    | {
        block: ManagedImportBlock | undefined;
        existingImports: DictImportsInfo;
        eol: string;
        insertLine: number | undefined;
      }
    | undefined;

  return (importsToAdd: DictImportsInfo): vscode.TextEdit[] => {
    if (Object.values(importsToAdd).every((names) => names.length === 0)) {
      return [];
    }

    if (!prepared) {
      const block = findManagedImportBlock(document);
      prepared = {
        block,
        existingImports: block
          ? parseExistingManagedImports(document, block, importSources)
          : {},
        eol: getDocumentEol(document),
        insertLine: block ? undefined : getDefaultInsertLine(document),
      };
    }

    const dictNextImports = mergeImports(
      prepared.existingImports,
      importsToAdd,
      importSources,
    );
    const strNextBlockText = buildManagedImportBlock(
      dictNextImports,
      importSources,
      prepared.eol,
    );

    if (prepared.block) {
      const positionStart = new vscode.Position(prepared.block.startLine, 0);
      const endLine = document.lineAt(prepared.block.endLine);
      const positionEnd = new vscode.Position(prepared.block.endLine, endLine.text.length);
      const range = new vscode.Range(positionStart, positionEnd);

      if (document.getText(range) === strNextBlockText) {
        return [];
      }

      return [vscode.TextEdit.replace(range, strNextBlockText)];
    }

    // insertLine is prepared whenever no managed block exists.
    const intInsertLine = prepared.insertLine!;
    const positionInsert =
      intInsertLine >= document.lineCount
        ? document.positionAt(document.getText().length)
        : new vscode.Position(intInsertLine, 0);

    return [
      vscode.TextEdit.insert(
        positionInsert,
        buildInsertedBlockText(document, intInsertLine, strNextBlockText, prepared.eol),
      ),
    ];
  };
}

export function buildManagedImportTextEdits(
  document: vscode.TextDocument,
  importSources: Record<string, DictImportSourceConfig>,
  importsToAdd: DictImportsInfo,
): vscode.TextEdit[] {
  return createManagedImportTextEditBuilder(document, importSources)(importsToAdd);
}

const mapImportUpdateQueues = new Map<string, Promise<void>>();

async function applyManagedImportUpdate(
  document: vscode.TextDocument,
  importSources: Record<string, DictImportSourceConfig>,
  importsToAdd: DictImportsInfo,
): Promise<void> {
  const arrEdits = buildManagedImportTextEdits(document, importSources, importsToAdd);

  if (arrEdits.length === 0) {
    return;
  }

  const workspaceEdit = new vscode.WorkspaceEdit();
  workspaceEdit.set(document.uri, arrEdits);

  const boolEdited = await vscode.workspace.applyEdit(workspaceEdit);
  if (!boolEdited) {
    throw new Error("Failed to update the LiberRPA managed import block.");
  }

  log.debug("[Imports] Managed import block updated.");
}

/**
 * Add snippet-required imports to one Python document.
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
  document: vscode.TextDocument,
  importSources: Record<string, DictImportSourceConfig>,
  importsToAdd: DictImportsInfo,
): Promise<void> {
  const strDisplayPath = getDisplayPath(document);
  log.trace(`[Imports] Queued managed import update for ${strDisplayPath}.`);

  const strDocumentKey = document.uri.toString();
  const previousUpdate = mapImportUpdateQueues.get(strDocumentKey) ?? Promise.resolve();

  const currentUpdate = previousUpdate
    .catch(() => undefined)
    .then(() => applyManagedImportUpdate(document, importSources, importsToAdd))
    .finally(() => {
      if (mapImportUpdateQueues.get(strDocumentKey) === currentUpdate) {
        mapImportUpdateQueues.delete(strDocumentKey);
      }
    });

  mapImportUpdateQueues.set(strDocumentKey, currentUpdate);
  await currentUpdate;
}
