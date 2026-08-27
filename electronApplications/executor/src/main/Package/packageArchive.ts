// FileName: packageArchive.ts

import fs from "fs";
import path from "path";
import AdmZip from "adm-zip";

const INT_MAX_ZIP_ENTRY_COUNT = 100_000;
const INT_MAX_UNCOMPRESSED_SIZE_BYTES = 16 * 1024 ** 3;
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

function getWindowsFolderNameError(name: string): string | undefined {
  if (name.length === 0 || name !== name.trim()) {
    return "Folder name cannot be empty or start/end with whitespace.";
  }
  if (REGEX_INVALID_WINDOWS_NAME_CHARACTER.test(name)) {
    return "Folder name contains Windows reserved characters.";
  }
  if ([...name].some((strCharacter) => strCharacter.charCodeAt(0) <= 0x1f)) {
    return "Folder name contains ASCII control characters.";
  }
  if (name.endsWith(".")) {
    return "Folder name cannot end with a period.";
  }
  const strBaseName = name.split(".", 1)[0]?.toUpperCase();
  if (strBaseName !== undefined && SET_RESERVED_WINDOWS_NAME.has(strBaseName)) {
    return `Folder name '${name}' is reserved by Windows.`;
  }
  if (name.length > 255) {
    return "Folder name cannot be longer than 255 characters.";
  }
  return undefined;
}

export function getTargetFolderName(name: string, version: string): string {
  const strFolderName = `${name}_${version}`;
  const strError = getWindowsFolderNameError(strFolderName);
  if (strError !== undefined) {
    throw new Error(`Cannot create the Executor Package folder: ${strError}`);
  }
  return strFolderName;
}

function getNormalizedZipEntryName(entryName: string): string {
  if (entryName.includes("\0")) {
    throw new Error(`ZIP entry contains a null character: ${entryName}`);
  }
  const strForwardSlashName = entryName.replace(/\\/g, "/");
  if (strForwardSlashName.startsWith("/") || /^[A-Za-z]:/.test(strForwardSlashName)) {
    throw new Error(`ZIP entry uses an absolute path: ${entryName}`);
  }

  const arrPart = strForwardSlashName.split("/");
  if (arrPart.at(-1) === "") {
    arrPart.pop();
  }
  if (
    arrPart.length === 0 ||
    arrPart.some((strPart) => strPart === "" || strPart === "." || strPart === "..")
  ) {
    throw new Error(`ZIP entry uses an invalid path: ${entryName}`);
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

function validateExtractedTree(rootPath: string): void {
  const arrPendingPath = [rootPath];
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

export function extractProjectPackageArchive(
  packageFilePath: string,
  stagedProjectPath: string,
): void {
  const zipObj = new AdmZip(packageFilePath);
  validateZipEntries(zipObj);
  zipObj.extractAllTo(stagedProjectPath, false);
  validateExtractedTree(stagedProjectPath);
}
