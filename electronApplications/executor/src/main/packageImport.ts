// FileName: packageImport.ts

import { randomUUID } from "crypto";
import { dialog } from "electron";
import fs from "fs";
import path from "path";
import AdmZip from "adm-zip";

import { DEFAULT_PYTHON_ENVIRONMENT_NAME } from "./commonFunc";
import { validatePackagedFlowProject } from "./componentManagementProcess";
import { dbInsertProjectDetail, dbSelectProjectDetail } from "./database";
import { getExecutorPackageFolderPath, strExecutorPackageFolderPath } from "./fileFunc";
import { loggerMain } from "./logger";
import { ensureLogLevel, isRecord } from "./validation";
import type {
  DictColumns_Project_Detail_ToInsert,
  DictProjectPackageImportResult,
  TypeColumns_LogLevel,
  TypeCustomProjectArgs,
} from "../shared/interface";

interface DictFlowManifest {
  schemaVersion: 1;
  name: string;
  version: string;
  description: string;
  requiresLiberrpa: string;
  componentDependencies: Record<string, string>;
}

interface DictPackageManifest {
  schemaVersion: 1;
  versionSummary: string;
}

interface DictProjectFlowRuntimeSettings {
  logLevel: TypeColumns_LogLevel;
  recordVideo: boolean;
  stopShortcut: boolean;
  highlightUi: boolean;
  customPrjArgs: TypeCustomProjectArgs;
}

interface DictPackageImportTransaction {
  schemaVersion: 1;
  state: "prepared";
  projectName: string;
  projectVersion: string;
  targetFolderName: string;
}

const STR_STAGING_FOLDER_NAME = ".staging";
const INT_MAX_ZIP_ENTRY_COUNT = 100_000;
const INT_MAX_UNCOMPRESSED_SIZE_BYTES = 16 * 1024 ** 3;
const STR_TRANSACTION_FILE_NAME = "transaction.json";
const STR_STAGED_PROJECT_FOLDER_NAME = "project";
const STR_FLOW_MANIFEST_FILE_NAME = "flow.json";
const STR_PACKAGE_MANIFEST_FILE_NAME = ".liberrpa-package.json";
const STR_PROJECT_FLOW_FILE_NAME = "project.flow";
const STR_LEGACY_PROJECT_FILE_NAME = "project.json";
const SET_FLOW_MANIFEST_KEYS = new Set([
  "schemaVersion",
  "name",
  "version",
  "description",
  "requiresLiberrpa",
  "componentDependencies",
]);
const SET_PACKAGE_MANIFEST_KEYS = new Set(["schemaVersion", "versionSummary"]);
const SET_PROJECT_FLOW_KEYS = new Set([
  "nodes",
  "edges",
  "executeMode",
  "logLevel",
  "recordVideo",
  "stopShortcut",
  "highlightUi",
  "customPrjArgs",
]);
const SET_RESERVED_WINDOWS_NAME = new Set([
  "CON",
  "PRN",
  "AUX",
  "NUL",
  "COM1",
  "COM2",
  "COM3",
  "COM4",
  "COM5",
  "COM6",
  "COM7",
  "COM8",
  "COM9",
  "LPT1",
  "LPT2",
  "LPT3",
  "LPT4",
  "LPT5",
  "LPT6",
  "LPT7",
  "LPT8",
  "LPT9",
]);
const REGEX_INVALID_WINDOWS_NAME_CHARACTER = /[<>:"/\\|?*]/;

let boolPackageImportRunning = false;

function hasExactKeys(
  value: Record<string, unknown>,
  setExpectedKey: Set<string>,
): boolean {
  const arrKey = Object.keys(value);
  return (
    arrKey.length === setExpectedKey.size &&
    arrKey.every((strKey) => setExpectedKey.has(strKey))
  );
}

function readJsonFile(strFilePath: string): unknown {
  try {
    return JSON.parse(fs.readFileSync(strFilePath, { encoding: "utf-8" }));
  } catch (e: unknown) {
    throw new Error(`Failed to read JSON file: ${strFilePath}`, { cause: e });
  }
}

function writeJsonFileAtomic(strFilePath: string, value: unknown): void {
  const strTempPath = `${strFilePath}.tmp`;
  fs.rmSync(strTempPath, { force: true });
  fs.writeFileSync(strTempPath, `${JSON.stringify(value, null, 2)}\n`, {
    encoding: "utf-8",
  });
  fs.renameSync(strTempPath, strFilePath);
}

function validateTrimmedSingleLine(
  value: unknown,
  strFieldName: string,
  boolAllowEmpty: boolean,
): string {
  if (typeof value !== "string") {
    throw new Error(`${strFieldName} must be a string.`);
  }
  if ((!boolAllowEmpty && value.length === 0) || value !== value.trim()) {
    throw new Error(
      boolAllowEmpty
        ? `${strFieldName} cannot start or end with whitespace.`
        : `${strFieldName} must be a non-empty trimmed string.`,
    );
  }
  if (value.includes("\r") || value.includes("\n")) {
    throw new Error(`${strFieldName} must be a single line.`);
  }
  return value;
}

function parseFlowManifest(value: unknown): DictFlowManifest {
  if (!isRecord(value) || !hasExactKeys(value, SET_FLOW_MANIFEST_KEYS)) {
    throw new Error("flow.json contains missing or unknown fields.");
  }
  if (value.schemaVersion !== 1) {
    throw new Error("Only flow.json schemaVersion 1 is supported.");
  }
  if (!isRecord(value.componentDependencies)) {
    throw new Error("flow.json componentDependencies must be an object.");
  }
  const dictDependency: Record<string, string> = {};
  for (const [strComponentId, dependencyValue] of Object.entries(
    value.componentDependencies,
  )) {
    if (typeof dependencyValue !== "string") {
      throw new Error(
        `flow.json componentDependencies.${strComponentId} must be a string.`,
      );
    }
    dictDependency[strComponentId] = dependencyValue;
  }

  if (typeof value.description !== "string") {
    throw new Error("flow.json description must be a string.");
  }

  return {
    schemaVersion: 1,
    name: validateTrimmedSingleLine(value.name, "flow.json name", false),
    version: validateTrimmedSingleLine(value.version, "flow.json version", false),
    description: value.description,
    requiresLiberrpa: validateTrimmedSingleLine(
      value.requiresLiberrpa,
      "flow.json requiresLiberrpa",
      false,
    ),
    componentDependencies: dictDependency,
  };
}

function parsePackageManifest(value: unknown): DictPackageManifest {
  if (!isRecord(value) || !hasExactKeys(value, SET_PACKAGE_MANIFEST_KEYS)) {
    throw new Error(".liberrpa-package.json contains missing or unknown fields.");
  }
  if (value.schemaVersion !== 1) {
    throw new Error("Only Package manifest schemaVersion 1 is supported.");
  }
  return {
    schemaVersion: 1,
    versionSummary: validateTrimmedSingleLine(
      value.versionSummary,
      ".liberrpa-package.json versionSummary",
      true,
    ),
  };
}

function parseCustomProjectArguments(value: unknown): TypeCustomProjectArgs {
  if (!Array.isArray(value)) {
    throw new Error("project.flow customPrjArgs must be an array.");
  }

  const setKey = new Set<string>();
  return value.map((item, intIndex) => {
    if (!Array.isArray(item) || item.length !== 2) {
      throw new Error(
        `project.flow customPrjArgs[${String(intIndex)}] must contain a key and value.`,
      );
    }
    const strKey = validateTrimmedSingleLine(
      item[0],
      `project.flow customPrjArgs[${String(intIndex)}][0]`,
      false,
    );
    if (setKey.has(strKey)) {
      throw new Error(`Duplicate Custom Project Argument key: ${strKey}`);
    }
    setKey.add(strKey);
    return [strKey, item[1]];
  });
}

function parseProjectFlowRuntimeSettings(value: unknown): DictProjectFlowRuntimeSettings {
  if (!isRecord(value) || !hasExactKeys(value, SET_PROJECT_FLOW_KEYS)) {
    throw new Error("project.flow contains missing or unknown root fields.");
  }
  if (!Array.isArray(value.nodes) || !Array.isArray(value.edges)) {
    throw new Error("project.flow nodes and edges must be arrays.");
  }
  if (value.executeMode !== "Run" && value.executeMode !== "Debug") {
    throw new Error("project.flow executeMode must be Run or Debug.");
  }
  const strLogLevel = ensureLogLevel(value.logLevel, "project.flow logLevel");
  if (
    typeof value.recordVideo !== "boolean" ||
    typeof value.stopShortcut !== "boolean" ||
    typeof value.highlightUi !== "boolean"
  ) {
    throw new Error(
      "project.flow recordVideo, stopShortcut and highlightUi must be Boolean values.",
    );
  }

  return {
    logLevel: strLogLevel,
    recordVideo: value.recordVideo,
    stopShortcut: value.stopShortcut,
    highlightUi: value.highlightUi,
    customPrjArgs: parseCustomProjectArguments(value.customPrjArgs),
  };
}

function getWindowsFolderNameError(strName: string): string | undefined {
  if (strName.length === 0 || strName !== strName.trim()) {
    return "Folder name cannot be empty or start/end with whitespace.";
  }
  if (REGEX_INVALID_WINDOWS_NAME_CHARACTER.test(strName)) {
    return "Folder name contains Windows reserved characters.";
  }
  if ([...strName].some((strCharacter) => strCharacter.charCodeAt(0) <= 0x1f)) {
    return "Folder name contains ASCII control characters.";
  }
  if (strName.endsWith(".")) {
    return "Folder name cannot end with a period.";
  }
  const strBaseName = strName.split(".", 1)[0]?.toUpperCase();
  if (strBaseName !== undefined && SET_RESERVED_WINDOWS_NAME.has(strBaseName)) {
    return `Folder name '${strName}' is reserved by Windows.`;
  }
  if (strName.length > 255) {
    return "Folder name cannot be longer than 255 characters.";
  }
  return undefined;
}

function getTargetFolderName(strName: string, strVersion: string): string {
  const strFolderName = `${strName}_${strVersion}`;
  const strError = getWindowsFolderNameError(strFolderName);
  if (strError !== undefined) {
    throw new Error(`Cannot create the Executor Package folder: ${strError}`);
  }
  return strFolderName;
}

function getNormalizedZipEntryName(strEntryName: string): string {
  if (strEntryName.includes("\0")) {
    throw new Error(`ZIP entry contains a null character: ${strEntryName}`);
  }
  const strForwardSlashName = strEntryName.replace(/\\/g, "/");
  if (strForwardSlashName.startsWith("/") || /^[A-Za-z]:/.test(strForwardSlashName)) {
    throw new Error(`ZIP entry uses an absolute path: ${strEntryName}`);
  }

  const arrPart = strForwardSlashName.split("/");
  if (arrPart.at(-1) === "") {
    arrPart.pop();
  }
  if (
    arrPart.length === 0 ||
    arrPart.some((strPart) => strPart === "" || strPart === "." || strPart === "..")
  ) {
    throw new Error(`ZIP entry uses an invalid path: ${strEntryName}`);
  }
  for (const strPart of arrPart) {
    const strError = getWindowsFolderNameError(strPart);
    if (strError !== undefined) {
      throw new Error(
        `ZIP entry contains an invalid Windows path segment '${strPart}': ${strError}`,
      );
    }
  }
  return arrPart.join("/");
}

function validateZipEntries(zipObj: AdmZip): void {
  const arrEntry = zipObj.getEntries();
  if (arrEntry.length > INT_MAX_ZIP_ENTRY_COUNT) {
    throw new Error(`ZIP contains too many entries: ${String(arrEntry.length)}.`);
  }

  const mapPathByLowercase = new Map<string, string>();
  const mapPathIsDirectory = new Map<string, boolean>();
  const setRequiredDirectoryPath = new Set<string>();
  let intUncompressedSizeBytes = 0;

  for (const entryObj of arrEntry) {
    const strNormalizedName = getNormalizedZipEntryName(entryObj.entryName);
    const strLowercaseName = strNormalizedName.toLowerCase();
    const strExistingName = mapPathByLowercase.get(strLowercaseName);
    if (strExistingName !== undefined) {
      if (strExistingName === strNormalizedName) {
        throw new Error(`ZIP contains a duplicate entry: ${strNormalizedName}`);
      }
      throw new Error(
        `ZIP contains paths that differ only by case: ${strExistingName}, ${strNormalizedName}`,
      );
    }
    const arrPathPart = strLowercaseName.split("/");
    for (let intIndex = 1; intIndex < arrPathPart.length; intIndex++) {
      const strParentPath = arrPathPart.slice(0, intIndex).join("/");
      if (mapPathIsDirectory.get(strParentPath) === false) {
        throw new Error(
          `ZIP file entry is used as a directory: ${mapPathByLowercase.get(strParentPath)}`,
        );
      }
      setRequiredDirectoryPath.add(strParentPath);
    }
    if (!entryObj.isDirectory && setRequiredDirectoryPath.has(strLowercaseName)) {
      throw new Error(`ZIP directory path is also a file: ${strNormalizedName}`);
    }

    mapPathByLowercase.set(strLowercaseName, strNormalizedName);
    mapPathIsDirectory.set(strLowercaseName, entryObj.isDirectory);

    if (entryObj.header.encrypted) {
      throw new Error(`ZIP contains an encrypted entry: ${strNormalizedName}`);
    }
    if (!Number.isSafeInteger(entryObj.header.size) || entryObj.header.size < 0) {
      throw new Error(`ZIP entry has an invalid size: ${strNormalizedName}`);
    }
    intUncompressedSizeBytes += entryObj.header.size;
    if (intUncompressedSizeBytes > INT_MAX_UNCOMPRESSED_SIZE_BYTES) {
      throw new Error("ZIP uncompressed content is larger than 16 GiB.");
    }

    const intUnixMode = (entryObj.header.attr >>> 16) & 0xffff;
    const intFileType = intUnixMode & 0o170000;
    if (intFileType !== 0 && intFileType !== 0o040000 && intFileType !== 0o100000) {
      throw new Error(`ZIP contains an unsupported special entry: ${strNormalizedName}`);
    }
  }
}

function validateExtractedTree(strRootPath: string): void {
  const arrPendingPath = [strRootPath];
  while (arrPendingPath.length > 0) {
    const strCurrentPath = arrPendingPath.pop();
    if (strCurrentPath === undefined) {
      continue;
    }
    for (const entryObj of fs.readdirSync(strCurrentPath, { withFileTypes: true })) {
      const strEntryPath = path.join(strCurrentPath, entryObj.name);
      const statObj = fs.lstatSync(strEntryPath);
      if (statObj.isSymbolicLink()) {
        throw new Error(`Extracted Package contains a symbolic link: ${strEntryPath}`);
      }
      if (statObj.isDirectory()) {
        arrPendingPath.push(strEntryPath);
      } else if (!statObj.isFile()) {
        throw new Error(`Extracted Package contains a special entry: ${strEntryPath}`);
      }
    }
  }
}

function readRequiredRootJson(strProjectPath: string, strFileName: string): unknown {
  const strFilePath = path.join(strProjectPath, strFileName);
  if (!fs.existsSync(strFilePath) || !fs.statSync(strFilePath).isFile()) {
    throw new Error(`The Package does not contain ${strFileName} at its root.`);
  }
  return readJsonFile(strFilePath);
}

function buildProjectDetail(
  flowManifest: DictFlowManifest,
  packageManifest: DictPackageManifest,
  runtimeSettings: DictProjectFlowRuntimeSettings,
): DictColumns_Project_Detail_ToInsert {
  return {
    name: flowManifest.name,
    version: flowManifest.version,
    description: flowManifest.description,
    version_summary: packageManifest.versionSummary,
    python_environment_name: DEFAULT_PYTHON_ENVIRONMENT_NAME,
    timeout_min: 0,
    builtin_log_level: runtimeSettings.logLevel,
    builtin_record_video: runtimeSettings.recordVideo ? 1 : 0,
    builtin_stop_shortcut: runtimeSettings.stopShortcut ? 1 : 0,
    builtin_highlight_ui: runtimeSettings.highlightUi ? 1 : 0,
    custom_prj_args: JSON.stringify(runtimeSettings.customPrjArgs),
  };
}

function parseTransaction(strTransactionPath: string): DictPackageImportTransaction {
  const value = readJsonFile(strTransactionPath);
  const setKey = new Set([
    "schemaVersion",
    "state",
    "projectName",
    "projectVersion",
    "targetFolderName",
  ]);
  if (
    !isRecord(value) ||
    !hasExactKeys(value, setKey) ||
    value.schemaVersion !== 1 ||
    value.state !== "prepared" ||
    typeof value.projectName !== "string" ||
    typeof value.projectVersion !== "string" ||
    typeof value.targetFolderName !== "string"
  ) {
    throw new Error(`Invalid Package import transaction: ${strTransactionPath}`);
  }
  if (
    getTargetFolderName(value.projectName, value.projectVersion) !== value.targetFolderName
  ) {
    throw new Error(
      `Package import transaction target is inconsistent: ${strTransactionPath}`,
    );
  }
  return {
    schemaVersion: 1,
    state: value.state,
    projectName: value.projectName,
    projectVersion: value.projectVersion,
    targetFolderName: value.targetFolderName,
  };
}

function removeFolder(strFolderPath: string): void {
  fs.rmSync(strFolderPath, { recursive: true, force: true });
}

function tryRemoveFolder(strFolderPath: string, strContext: string): void {
  try {
    removeFolder(strFolderPath);
  } catch (e: unknown) {
    loggerMain.warn(`${strContext}: ${e instanceof Error ? e.message : String(e)}`);
  }
}

export function recoverProjectPackageImports(): void {
  const strStagingRootPath = path.join(
    strExecutorPackageFolderPath,
    STR_STAGING_FOLDER_NAME,
  );
  if (!fs.existsSync(strStagingRootPath)) {
    return;
  }

  for (const entryObj of fs.readdirSync(strStagingRootPath, { withFileTypes: true })) {
    const strTransactionFolderPath = path.join(strStagingRootPath, entryObj.name);
    if (!entryObj.isDirectory()) {
      tryRemoveFolder(
        strTransactionFolderPath,
        "Failed to remove an invalid Package import staging entry",
      );
      continue;
    }

    const strTransactionPath = path.join(
      strTransactionFolderPath,
      STR_TRANSACTION_FILE_NAME,
    );
    if (!fs.existsSync(strTransactionPath)) {
      tryRemoveFolder(
        strTransactionFolderPath,
        "Failed to remove a Package staging folder without a transaction",
      );
      continue;
    }

    try {
      const transaction = parseTransaction(strTransactionPath);
      const strTargetPath = path.join(
        strExecutorPackageFolderPath,
        transaction.targetFolderName,
      );
      const projectRecord = dbSelectProjectDetail(
        transaction.projectName,
        transaction.projectVersion,
      );

      if (fs.existsSync(strTargetPath) && projectRecord === undefined) {
        loggerMain.warn(
          `Roll back an incomplete Package import: ${transaction.projectName}-${transaction.projectVersion}`,
        );
        tryRemoveFolder(strTargetPath, "Failed to roll back an incomplete Package import");
      } else if (!fs.existsSync(strTargetPath) && projectRecord !== undefined) {
        loggerMain.error(
          "Installed Package folder is missing for database record: " +
            `${transaction.projectName}-${transaction.projectVersion}`,
        );
      }
    } catch (e: unknown) {
      loggerMain.error(
        `Failed to inspect Package import transaction ${strTransactionFolderPath}: ${String(e)}`,
      );
    } finally {
      tryRemoveFolder(
        strTransactionFolderPath,
        "Failed to clean a recovered Package import transaction",
      );
    }
  }
}

async function _importProjectPackage(): Promise<DictProjectPackageImportResult> {
  const dialogResult = await dialog.showOpenDialog({
    properties: ["openFile"],
    title: "Select a Flow Project Package",
    filters: [{ name: "LiberRPA Flow Project Package", extensions: ["rpa.zip"] }],
  });
  if (dialogResult.canceled) {
    return { status: "canceled" };
  }
  if (dialogResult.filePaths.length !== 1) {
    throw new Error("Exactly one Flow Project Package must be selected.");
  }

  const strPackageFilePath = dialogResult.filePaths[0];
  fs.mkdirSync(strExecutorPackageFolderPath, { recursive: true });
  const strTransactionFolderPath = path.join(
    strExecutorPackageFolderPath,
    STR_STAGING_FOLDER_NAME,
    randomUUID(),
  );
  const strStagedProjectPath = path.join(
    strTransactionFolderPath,
    STR_STAGED_PROJECT_FOLDER_NAME,
  );
  fs.mkdirSync(strStagedProjectPath, { recursive: true });

  let strTargetPath: string | undefined;
  let boolDatabaseCommitted = false;
  try {
    const zipObj = new AdmZip(strPackageFilePath);
    validateZipEntries(zipObj);
    zipObj.extractAllTo(strStagedProjectPath, false);
    validateExtractedTree(strStagedProjectPath);

    const strLegacyProjectPath = path.join(
      strStagedProjectPath,
      STR_LEGACY_PROJECT_FILE_NAME,
    );
    if (fs.existsSync(strLegacyProjectPath)) {
      throw new Error(
        "This is a legacy project.json Package. Create a new Package with the current Project Manager.",
      );
    }

    const flowManifest = parseFlowManifest(
      readRequiredRootJson(strStagedProjectPath, STR_FLOW_MANIFEST_FILE_NAME),
    );
    const packageManifest = parsePackageManifest(
      readRequiredRootJson(strStagedProjectPath, STR_PACKAGE_MANIFEST_FILE_NAME),
    );
    const runtimeSettings = parseProjectFlowRuntimeSettings(
      readRequiredRootJson(strStagedProjectPath, STR_PROJECT_FLOW_FILE_NAME),
    );

    await validatePackagedFlowProject(strStagedProjectPath);

    if (dbSelectProjectDetail(flowManifest.name, flowManifest.version) !== undefined) {
      throw new Error(
        `Project Package ${flowManifest.name}-${flowManifest.version} is already installed.`,
      );
    }

    const strTargetFolderName = getTargetFolderName(
      flowManifest.name,
      flowManifest.version,
    );
    strTargetPath = getExecutorPackageFolderPath(flowManifest.name, flowManifest.version);
    if (fs.existsSync(strTargetPath)) {
      throw new Error(`The target Package folder already exists: ${strTargetPath}`);
    }

    const strTransactionPath = path.join(
      strTransactionFolderPath,
      STR_TRANSACTION_FILE_NAME,
    );
    const transaction: DictPackageImportTransaction = {
      schemaVersion: 1,
      state: "prepared",
      projectName: flowManifest.name,
      projectVersion: flowManifest.version,
      targetFolderName: strTargetFolderName,
    };
    writeJsonFileAtomic(strTransactionPath, transaction);

    fs.renameSync(strStagedProjectPath, strTargetPath);

    dbInsertProjectDetail(
      buildProjectDetail(flowManifest, packageManifest, runtimeSettings),
    );
    boolDatabaseCommitted = true;

    tryRemoveFolder(
      strTransactionFolderPath,
      "Failed to clean the completed Package import transaction",
    );
    loggerMain.info(
      `Imported Flow Project Package: ${flowManifest.name}-${flowManifest.version}`,
    );
    return {
      status: "projectPackageImported",
      name: flowManifest.name,
      version: flowManifest.version,
      packageFilePath: strPackageFilePath,
      installedFolderPath: strTargetPath,
    };
  } catch (e: unknown) {
    if (
      strTargetPath !== undefined &&
      fs.existsSync(strTargetPath) &&
      !boolDatabaseCommitted
    ) {
      tryRemoveFolder(strTargetPath, "Failed to roll back the installed Package folder");
    }
    tryRemoveFolder(
      strTransactionFolderPath,
      "Failed to clean the failed Package import transaction",
    );
    throw e;
  }
}

export async function importProjectPackage(): Promise<DictProjectPackageImportResult> {
  if (boolPackageImportRunning) {
    throw new Error("Another Project Package import is already running.");
  }

  boolPackageImportRunning = true;
  try {
    return await _importProjectPackage();
  } finally {
    boolPackageImportRunning = false;
  }
}
