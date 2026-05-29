// FileName: attrHandleFunc.ts

import { parse, printParseErrorCode, type ParseError } from "jsonc-parser";

export type SelectorJsonParseResult =
  | {
      success: true;
      data: unknown;
      mode: "json" | "json-compatible";
    }
  | {
      success: false;
      errorMessage: string;
    };

export const STR_SUFFIX_OMIT = "-omit";
export const STR_SUFFIX_REGEX = "-regex";

export function removeSuffix(originalText: string, suffix: string): string {
  if (originalText.endsWith(suffix)) {
    return originalText.slice(0, -suffix.length);
  }
  return originalText;
}

export function removePrefix(originalText: string, prefix: string): string {
  if (originalText.startsWith(prefix)) {
    return originalText.slice(prefix.length);
  }
  return originalText;
}

export function modifyKeyName(
  dictToModify: { [key: string]: unknown },
  originalKeyName: string,
  newKeyName: string
): void {
  // Modify the key's name and keep its order.
  for (const keyName of Object.keys(dictToModify)) {
    if (keyName === originalKeyName) {
      dictToModify[newKeyName] = dictToModify[keyName];
      delete dictToModify[keyName];
    } else {
      // Delete the key so it will after the newKeyName
      const valueCache: unknown = dictToModify[keyName];
      delete dictToModify[keyName];
      dictToModify[keyName] = valueCache;
    }
  }
}

function formatJsoncErrors(errors: ParseError[]): string {
  return errors.map((error) => printParseErrorCode(error.error)).join(", ");
}

export function parseSelectorJsonText(text: string): SelectorJsonParseResult {
  const strTrimmedText = text.trim();

  if (strTrimmedText === "") {
    return {
      success: false,
      errorMessage: "Selector JSON is empty.",
    };
  }

  try {
    return {
      success: true,
      data: JSON.parse(strTrimmedText),
      mode: "json",
    };
  } catch {
    // Continue to JSONC parsing for trailing commas.
  }

  const arrErrors: ParseError[] = [];
  const data: unknown = parse(strTrimmedText, arrErrors, {
    allowTrailingComma: true,
    disallowComments: true,
  });

  if (arrErrors.length === 0) {
    return {
      success: true,
      data,
      mode: "json-compatible",
    };
  }

  return {
    success: false,
    errorMessage:
      "Invalid selector JSON. Please use double quotes for keys and values. Trailing commas are allowed, but comments and Python literals are not supported. " +
      formatJsoncErrors(arrErrors),
  };
}
