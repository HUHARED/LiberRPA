// FileName: managedImportAnalysis.ts

import { execFile } from "node:child_process";
import * as path from "node:path";

import { isRecord } from "../../Common/typeCheck";

interface ManagedImportAnalysisResponse {
  // null means the complete Python source is currently invalid.
  referencedNames: string[] | null;
}

function isManagedImportAnalysisResponse(
  value: unknown,
): value is ManagedImportAnalysisResponse {
  return (
    isRecord(value) &&
    (value.referencedNames === null ||
      (Array.isArray(value.referencedNames) &&
        value.referencedNames.every((name: unknown) => typeof name === "string")))
  );
}

export async function analyzeManagedImportNames(
  strHelperPath: string,
  strSource: string,
  arrKnownName: string[],
): Promise<string[] | null> {
  if (arrKnownName.length === 0) {
    return [];
  }

  const strLiberRpaPath = process.env.LiberRPA;
  if (!strLiberRpaPath) {
    throw new Error(
      "LiberRPA is not initialized; paste-time managed import analysis is unavailable.",
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
    const processObj = execFile(
      strPythonPath,
      ["-I", "-S", "-X", "utf8", strHelperPath],
      {
        encoding: "utf8",
        windowsHide: true,
        timeout: 10000,
        maxBuffer: 4 * 1024 * 1024,
      },
      (e, stdout) => {
        if (e) {
          reject(e instanceof Error ? e : new Error(e.message, { cause: e }));
        } else {
          resolve(stdout);
        }
      },
    );

    processObj.stdin?.on("error", (e: Error) => {
      reject(e);
    });
    processObj.stdin?.end(
      JSON.stringify({
        source: strSource,
        knownNames: arrKnownName,
      }),
    );
  });

  const result: unknown = JSON.parse(strOutput);
  if (!isManagedImportAnalysisResponse(result)) {
    throw new Error("Invalid paste-time managed import analysis response.");
  }

  return result.referencedNames;
}
