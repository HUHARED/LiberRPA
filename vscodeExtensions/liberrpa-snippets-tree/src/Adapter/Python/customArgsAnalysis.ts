// FileName: customArgsAnalysis.ts

import { execFile } from "node:child_process";
import * as path from "node:path";
import { isRecord } from "../../Common/typeCheck";

export type CustomArgsSource = { filePath: string; text: string };
export type CustomArgsAnalysisResult = {
  filePath: string;
  // null means invalid Python; the index retains the previous successful result.
  keyPaths: string[][] | null;
};

function isAnalysisResult(value: unknown): value is CustomArgsAnalysisResult {
  return (
    isRecord(value) &&
    typeof value.filePath === "string" &&
    (value.keyPaths === null ||
      (Array.isArray(value.keyPaths) &&
        value.keyPaths.every(
          (keyPath: unknown) =>
            Array.isArray(keyPath) &&
            keyPath.length > 0 &&
            keyPath.every((key: unknown) => typeof key === "string"),
        )))
  );
}

export async function analyzeCustomArgsSources(
  strHelperPath: string,
  arrSource: CustomArgsSource[],
  signal: AbortSignal,
): Promise<CustomArgsAnalysisResult[]> {
  if (arrSource.length === 0) {
    return [];
  }
  const strLiberRpaPath = process.env.LiberRPA;
  if (!strLiberRpaPath) {
    throw new Error(
      "LiberRPA is not initialized; nested CustomArgs completion is unavailable.",
    );
  }
  const strPythonPath = path.join(
    strLiberRpaPath,
    "envs",
    "pyenv",
    "default",
    "python.exe",
  );

  const strOutput = await new Promise<string>((resolve, reject) => {
    // Isolated mode and no site initialization prevent project/local modules or site hooks from being imported. Project source is data on stdin, not code.
    const processObj = execFile(
      strPythonPath,
      ["-I", "-S", "-X", "utf8", strHelperPath],
      {
        encoding: "utf8",
        windowsHide: true,
        timeout: 10000,
        maxBuffer: 16 * 1024 * 1024,
        signal,
      },
      (e, stdout) => {
        if (e) {
          reject(e instanceof Error ? e : new Error(e.message, { cause: e }));
        } else {
          resolve(stdout);
        }
      },
    );
    processObj.stdin?.on("error", reject);
    processObj.stdin?.end(
      JSON.stringify(arrSource.map(({ filePath, text }) => ({ filePath, text }))),
    );
  });
  const result: unknown = JSON.parse(strOutput);
  if (!Array.isArray(result) || !result.every(isAnalysisResult)) {
    throw new Error("Invalid CustomArgs source analysis response.");
  }
  return result;
}
