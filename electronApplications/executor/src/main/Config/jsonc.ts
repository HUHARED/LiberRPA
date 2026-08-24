import * as jsoncParser from "jsonc-parser";

export function parseJsonc(strContent: string, strSourceName: string): unknown {
  const arrError: jsoncParser.ParseError[] = [];
  const value = jsoncParser.parse(strContent, arrError);
  if (arrError.length !== 0) {
    const firstError = arrError[0];
    throw new Error(
      `${strSourceName} contains invalid JSONC at offset ${String(firstError.offset)}.`,
    );
  }
  return value;
}
