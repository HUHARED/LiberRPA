// FileName: environment.ts

import { app } from "electron";
import fs from "fs";
import path from "path";

export const strDocumentsFolderPath = app.getPath("documents");
app.setPath("userData", path.join(strDocumentsFolderPath, "LiberRPA/AppData/executor/"));

const strLiberRPAEnvPathValue = process.env.LiberRPA;
if (strLiberRPAEnvPathValue === undefined || strLiberRPAEnvPathValue === "") {
  throw new Error(
    "Not found 'LiberRPA' in User Environment Variables, you should add it before using LiberRPA Executor.",
  );
}
export const strLiberRPAEnvPath = strLiberRPAEnvPathValue;

export const STR_DEFAULT_PYTHON_ENVIRONMENT_NAME = "default";
const strPythonEnvironmentRootPath = path.join(strLiberRPAEnvPath, "envs/pyenv");
export const strDefaultPythonEnvironmentPath = path.join(
  strPythonEnvironmentRootPath,
  STR_DEFAULT_PYTHON_ENVIRONMENT_NAME,
);

export function getPythonEnvironmentNames(): string[] {
  if (
    !fs.existsSync(strPythonEnvironmentRootPath) ||
    !fs.statSync(strPythonEnvironmentRootPath).isDirectory()
  ) {
    throw new Error(
      `Python environment folder does not exist: ${strPythonEnvironmentRootPath}`,
    );
  }

  const arrEnvironmentName = fs
    .readdirSync(strPythonEnvironmentRootPath, { withFileTypes: true })
    .filter((entryObj) => {
      if (!entryObj.isDirectory()) {
        return false;
      }

      const strPythonPath = path.join(
        strPythonEnvironmentRootPath,
        entryObj.name,
        "python.exe",
      );
      return fs.existsSync(strPythonPath) && fs.statSync(strPythonPath).isFile();
    })
    .map((entryObj) => entryObj.name);

  if (!arrEnvironmentName.includes(STR_DEFAULT_PYTHON_ENVIRONMENT_NAME)) {
    throw new Error(
      `Default Python environment does not exist: ${strDefaultPythonEnvironmentPath}`,
    );
  }

  return arrEnvironmentName.sort((strLeft, strRight) => {
    if (strLeft === STR_DEFAULT_PYTHON_ENVIRONMENT_NAME) {
      return -1;
    }
    if (strRight === STR_DEFAULT_PYTHON_ENVIRONMENT_NAME) {
      return 1;
    }
    return strLeft.localeCompare(strRight);
  });
}

export function getPythonEnvironmentPath(strEnvironmentName: string): string {
  if (
    strEnvironmentName.trim() === "" ||
    strEnvironmentName !== strEnvironmentName.trim() ||
    strEnvironmentName === "." ||
    strEnvironmentName === ".." ||
    path.basename(strEnvironmentName) !== strEnvironmentName
  ) {
    throw new Error(`Invalid Python environment name: ${strEnvironmentName}`);
  }

  const strEnvironmentPath = path.join(strPythonEnvironmentRootPath, strEnvironmentName);
  const strPythonPath = path.join(strEnvironmentPath, "python.exe");
  if (!fs.existsSync(strPythonPath) || !fs.statSync(strPythonPath).isFile()) {
    throw new Error(
      `Python environment '${strEnvironmentName}' does not contain python.exe: ${strEnvironmentPath}`,
    );
  }

  return strEnvironmentPath;
}

// Windows environment variable names are case-insensitive, while process.env preserves the original key casing.
function getProcessEnvironmentVariable(name: string): string | undefined {
  const strNameLower = name.toLowerCase();
  for (const [strKey, strValue] of Object.entries(process.env)) {
    if (strKey.toLowerCase() === strNameLower) {
      return strValue;
    }
  }
  return undefined;
}

function mergeProcessEnvironment(
  overrideDict: Record<string, string | undefined>,
): NodeJS.ProcessEnv {
  const setOverrideKey = new Set(
    Object.keys(overrideDict).map((strKey) => strKey.toLowerCase()),
  );
  const dictEnvironment: NodeJS.ProcessEnv = {};

  for (const [strKey, strValue] of Object.entries(process.env)) {
    if (!setOverrideKey.has(strKey.toLowerCase()) && strValue !== undefined) {
      dictEnvironment[strKey] = strValue;
    }
  }

  for (const [strKey, strValue] of Object.entries(overrideDict)) {
    if (strValue !== undefined) {
      dictEnvironment[strKey] = strValue;
    }
  }

  return dictEnvironment;
}

function getPythonEnvironmentPathEntries(pythonEnvironmentPath: string): string[] {
  return [
    pythonEnvironmentPath,
    path.join(pythonEnvironmentPath, "Library", "mingw-w64", "bin"),
    path.join(pythonEnvironmentPath, "Library", "usr", "bin"),
    path.join(pythonEnvironmentPath, "Library", "bin"),
    path.join(pythonEnvironmentPath, "Scripts"),
    path.join(pythonEnvironmentPath, "bin"),
  ];
}

export function buildPythonProcessEnvironment({
  pythonEnvironmentPath,
  pythonPathEntries = [],
  additionalVariables = {},
}: {
  pythonEnvironmentPath: string;
  pythonPathEntries?: string[];
  additionalVariables?: Record<string, string | undefined>;
}): NodeJS.ProcessEnv {
  // Put the selected environment before the inherited PATH so its DLLs and tools win.
  const arrPathEntry = getPythonEnvironmentPathEntries(pythonEnvironmentPath);
  const strParentPath = getProcessEnvironmentVariable("PATH");
  if (strParentPath !== undefined && strParentPath.length > 0) {
    arrPathEntry.push(strParentPath);
  }

  // Do not inherit PYTHONHOME or PYTHONPATH because they can redirect the selected environment or shadow modules from the installed Project Package.
  return mergeProcessEnvironment({
    ...additionalVariables,
    PATH: arrPathEntry.join(path.delimiter),
    PYTHONHOME: undefined,
    PYTHONPATH:
      pythonPathEntries.length === 0 ? undefined : pythonPathEntries.join(path.delimiter),
  });
}
