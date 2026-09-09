// FileName: snippetInsertionText.ts

import type { Info_Snippet } from "../../Domain/Snippet/snippetTypes";

export interface SnippetTextForInsertion {
  insertionText: string;
  previewText: string;
}

const REG_RETURN_VALUE_FUNCTION_CALL =
  /^\$\{1:[A-Za-z_][A-Za-z0-9_]*\} = ((?:[A-Za-z_][A-Za-z0-9_]*\.)*[A-Za-z_][A-Za-z0-9_]*\(.*\))$/u;

/**
 * Check whether the current line contains non-whitespace text before an
 * insertion or replacement position.
 */
export function hasNonWhitespaceTextBefore(strLine: string, intCharacter: number): boolean {
  return strLine.slice(0, intCharacter).trim().length > 0;
}

/**
 * Select the Snippet text for the current insertion context.
 *
 * A standard generated return-value Snippet has this exact structure:
 *
 * ${1:result} = Module.function(...)
 * $0
 *
 * When that Snippet is inserted after existing code on the same line, only
 * the function call is inserted so it can be used as an expression. Other
 * Snippet structures remain unchanged.
 */
export function getSnippetTextForInsertion(
  snippet: Pick<Info_Snippet, "body" | "insertionMode">,
  boolInlineContext: boolean,
): SnippetTextForInsertion {
  const strOriginalText = snippet.body.join("\n");

  if (
    !boolInlineContext ||
    snippet.insertionMode !== "line" ||
    snippet.body.length !== 2 ||
    snippet.body[1] !== "$0"
  ) {
    return {
      insertionText: strOriginalText,
      previewText: strOriginalText,
    };
  }

  const returnValueFunctionCallMatch = REG_RETURN_VALUE_FUNCTION_CALL.exec(snippet.body[0]);
  if (returnValueFunctionCallMatch === null) {
    return {
      insertionText: strOriginalText,
      previewText: strOriginalText,
    };
  }

  const strFunctionCall = returnValueFunctionCallMatch[1];
  return {
    insertionText: `${strFunctionCall}$0`,
    previewText: strFunctionCall,
  };
}
