// FileName: jsonc.ts

import * as jsoncParser from "jsonc-parser";

export function parseJsonc(content: string, sourceName: string): unknown {
  const arrError: jsoncParser.ParseError[] = [];
  const value = jsoncParser.parse(content, arrError);
  if (arrError.length !== 0) {
    const firstError = arrError[0];
    throw new Error(
      `${sourceName} contains invalid JSONC at offset ${String(firstError.offset)}.`,
    );
  }
  return value;
}
