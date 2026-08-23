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

export const DEFAULT_PYTHON_ENVIRONMENT_NAME = "default";
export const strPythonEnvironmentRootPath = path.join(strLiberRPAEnvPath, "envs/pyenv");
export const strDefaultPythonEnvironmentPath = path.join(
  strPythonEnvironmentRootPath,
  DEFAULT_PYTHON_ENVIRONMENT_NAME,
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

  if (!arrEnvironmentName.includes(DEFAULT_PYTHON_ENVIRONMENT_NAME)) {
    throw new Error(
      `Default Python environment does not exist: ${strDefaultPythonEnvironmentPath}`,
    );
  }

  return arrEnvironmentName.sort((strLeft, strRight) => {
    if (strLeft === DEFAULT_PYTHON_ENVIRONMENT_NAME) {
      return -1;
    }
    if (strRight === DEFAULT_PYTHON_ENVIRONMENT_NAME) {
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

function getInheritedEnvironmentVariable(strName: string): string {
  const strNameLower = strName.toLowerCase();
  for (const [strKey, strValue] of Object.entries(process.env)) {
    if (strKey.toLowerCase() === strNameLower) {
      return strValue ?? "";
    }
  }
  return "";
}

function mergeProcessEnvironment(
  dictOverride: Record<string, string | undefined>,
): NodeJS.ProcessEnv {
  const setOverrideKey = new Set(
    Object.keys(dictOverride).map((strKey) => strKey.toLowerCase()),
  );
  const dictEnvironment: NodeJS.ProcessEnv = {};

  for (const [strKey, strValue] of Object.entries(process.env)) {
    if (!setOverrideKey.has(strKey.toLowerCase()) && strValue !== undefined) {
      dictEnvironment[strKey] = strValue;
    }
  }

  for (const [strKey, strValue] of Object.entries(dictOverride)) {
    if (strValue !== undefined) {
      dictEnvironment[strKey] = strValue;
    }
  }

  return dictEnvironment;
}

export function getPythonProcessEnvironment({
  pythonEnvironmentPath,
  pythonPathEntries = [],
  variables = {},
}: {
  pythonEnvironmentPath: string;
  pythonPathEntries?: string[];
  variables?: Record<string, string | undefined>;
}): NodeJS.ProcessEnv {
  const strInheritedPath = getInheritedEnvironmentVariable("PATH");
  const strInheritedPythonPath = getInheritedEnvironmentVariable("PYTHONPATH");

  const strPath = [
    pythonEnvironmentPath,
    path.join(pythonEnvironmentPath, "Library", "mingw-w64", "bin"),
    path.join(pythonEnvironmentPath, "Library", "usr", "bin"),
    path.join(pythonEnvironmentPath, "Library", "bin"),
    path.join(pythonEnvironmentPath, "Scripts"),
    path.join(pythonEnvironmentPath, "bin"),
    strInheritedPath,
  ]
    .filter((strItem) => strItem.length > 0)
    .join(path.delimiter);

  const arrPythonPath = [...pythonPathEntries];
  if (strInheritedPythonPath.length > 0) {
    arrPythonPath.push(strInheritedPythonPath);
  }

  return mergeProcessEnvironment({
    ...variables,
    PATH: strPath,
    ...(arrPythonPath.length === 0
      ? {}
      : { PYTHONPATH: arrPythonPath.join(path.delimiter) }),
  });
}
