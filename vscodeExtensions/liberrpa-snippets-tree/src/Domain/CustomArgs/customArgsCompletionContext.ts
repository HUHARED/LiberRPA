// FileName: customArgsCompletionContext.ts

export type CustomArgsContextKind =
  | "afterCustomArgs"
  | "afterBracket"
  | "insideDoubleQuote"
  | "insideSingleQuote";

export type CustomArgsCompletionContext = {
  kind: CustomArgsContextKind;
  keyPath: string[];
  startOffset: number;
  endOffset: number;
};

/** Ignore comments and strings, including multiline strings and their prefixes. */
export function isPythonCodeAtOffset(text: string, intOffset: number): boolean {
  let intIndex = 0;
  while (intIndex < intOffset) {
    const character = text[intIndex];
    if (character === "#") {
      const intEnd = text.indexOf("\n", intIndex);
      if (intEnd === -1 || intEnd >= intOffset) {
        return false;
      }
      intIndex = intEnd + 1;
    } else if (character === '"' || character === "'") {
      const delimiter = text.startsWith(character.repeat(3), intIndex)
        ? character.repeat(3)
        : character;
      intIndex += delimiter.length;
      let boolClosed = false;
      while (intIndex < intOffset) {
        if (text[intIndex] === "\\") {
          intIndex += 2;
        } else if (text.startsWith(delimiter, intIndex)) {
          intIndex += delimiter.length;
          boolClosed = true;
          break;
        } else {
          intIndex += 1;
        }
      }
      if (!boolClosed || intIndex > intOffset) {
        return false;
      }
    } else {
      intIndex += 1;
    }
  }
  return true;
}

function decodePythonStringContent(content: string): string | undefined {
  let result = "";
  const mapEscape: Readonly<Record<string, string>> = {
    "\\": "\\",
    '"': '"',
    "'": "'",
    n: "\n",
    r: "\r",
    t: "\t",
    b: "\b",
    f: "\f",
    a: "\x07",
    v: "\v",
  };
  for (let intIndex = 0; intIndex < content.length; intIndex += 1) {
    if (content[intIndex] !== "\\") {
      result += content[intIndex];
      continue;
    }
    intIndex += 1;
    const character = content[intIndex];
    if (character === undefined) {
      return undefined;
    }
    if (Object.hasOwn(mapEscape, character)) {
      result += mapEscape[character];
    } else if (character === "x" || character === "u" || character === "U") {
      const intLength = character === "x" ? 2 : character === "u" ? 4 : 8;
      const strHex = content.slice(intIndex + 1, intIndex + 1 + intLength);
      if (strHex.length !== intLength || !/^[0-9a-f]+$/i.test(strHex)) {
        return undefined;
      }
      const intCodePoint = Number.parseInt(strHex, 16);
      if (intCodePoint > 0x10ffff) {
        return undefined;
      }
      result += String.fromCodePoint(intCodePoint);
      intIndex += intLength;
    } else if (/[0-7]/.test(character)) {
      const strOctal = /^[0-7]{1,3}/.exec(content.slice(intIndex))![0];
      result += String.fromCodePoint(Number.parseInt(strOctal, 8));
      intIndex += strOctal.length - 1;
    } else {
      // Named Unicode escapes and nonstandard literal forms are not inferred.
      return undefined;
    }
  }
  return result;
}

function skipSpace(text: string, intIndex: number): number {
  while (text[intIndex] === " " || text[intIndex] === "\t") {
    intIndex += 1;
  }
  return intIndex;
}

function parseAccess(
  line: string,
  intStart: number,
  intCursor: number,
): CustomArgsCompletionContext | undefined {
  let intIndex = intStart + "CustomArgs".length;
  const arrKeyPath: string[] = [];
  while (intIndex <= intCursor) {
    intIndex = skipSpace(line, intIndex);
    if (intIndex === intCursor) {
      return {
        kind: "afterCustomArgs",
        keyPath: arrKeyPath,
        startOffset: intCursor,
        endOffset: intCursor,
      };
    }
    if (line[intIndex] !== "[") {
      return undefined;
    }
    intIndex = skipSpace(line, intIndex + 1);
    if (intIndex === intCursor) {
      // Keep the existing permissive first-level entry points.
      // Nested lookups require the closing bracket already present (normally auto-inserted).
      if (arrKeyPath.length > 0 && line[skipSpace(line, intIndex)] !== "]") {
        return undefined;
      }
      return {
        kind: "afterBracket",
        keyPath: arrKeyPath,
        startOffset: intCursor,
        endOffset: intCursor,
      };
    }
    const quote = line[intIndex];
    if (quote !== '"' && quote !== "'") {
      return undefined;
    }
    const intContentStart = intIndex + 1;
    let intQuoteEnd = intContentStart;
    while (intQuoteEnd < line.length && line[intQuoteEnd] !== quote) {
      intQuoteEnd += line[intQuoteEnd] === "\\" ? 2 : 1;
    }
    const boolClosed = line[intQuoteEnd] === quote;
    const intBracketEnd = skipSpace(line, intQuoteEnd + 1);
    if (intCursor >= intContentStart && intCursor <= intQuoteEnd) {
      if (arrKeyPath.length > 0 && (!boolClosed || line[intBracketEnd] !== "]")) {
        return undefined;
      }
      return {
        kind: quote === '"' ? "insideDoubleQuote" : "insideSingleQuote",
        keyPath: arrKeyPath,
        startOffset: intContentStart,
        endOffset: boolClosed ? intQuoteEnd : intCursor,
      };
    }
    if (!boolClosed || line[intBracketEnd] !== "]" || intBracketEnd >= intCursor) {
      return undefined;
    }
    const key = decodePythonStringContent(line.slice(intContentStart, intQuoteEnd));
    if (key === undefined) {
      return undefined;
    }
    arrKeyPath.push(key);
    intIndex = intBracketEnd + 1;
  }
  return undefined;
}

/** Parse one same-line lookup; do not repair incomplete nested expressions. */
export function getCustomArgsCompletionContext(
  text: string,
  intOffset: number,
): CustomArgsCompletionContext | undefined {
  const intLineStart = intOffset === 0 ? 0 : text.lastIndexOf("\n", intOffset - 1) + 1;
  const intLineEnd = text.indexOf("\n", intOffset);
  const line = text.slice(intLineStart, intLineEnd === -1 ? undefined : intLineEnd);
  const intCursor = intOffset - intLineStart;
  const arrMatch = [...line.slice(0, intCursor).matchAll(/\bCustomArgs\b/g)];
  for (const match of arrMatch.reverse()) {
    const intStart = match.index;
    const before = line.slice(0, intStart);
    if (/[\p{ID_Continue}.]$/u.test(before) || before.trimEnd().endsWith(".")) {
      continue;
    }
    const context = parseAccess(line, intStart, intCursor);
    if (context && isPythonCodeAtOffset(text, intLineStart + intStart)) {
      return {
        ...context,
        startOffset: intLineStart + context.startOffset,
        endOffset: intLineStart + context.endOffset,
      };
    }
  }
  return undefined;
}
