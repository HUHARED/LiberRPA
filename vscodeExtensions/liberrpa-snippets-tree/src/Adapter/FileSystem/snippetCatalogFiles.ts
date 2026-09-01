// FileName: snippetCatalogFiles.ts

import * as fs from "node:fs";
import * as path from "node:path";

import { isRecord } from "../../Common/typeCheck";
import { isSnippetCatalogFile } from "../../Domain/Snippet/snippetValidation";
import type {
  DictSnippetCatalogFile,
  Info_LoadedSnippetCatalog,
} from "../../Domain/Snippet/snippetTypes";

const STR_COMPONENTS_FOLDER_NAME = "_Components";
const STR_COMPONENT_LOCK_FILE_NAME = "components.lock.json";
const STR_COMPONENT_CATALOG_FILE_NAME = "snippets_catalog.json";

interface DictLockedComponent {
  packageName: string;
  wheelFileName: string;
}

interface DictComponentsLockFile {
  schemaVersion: 1;
  root: {
    componentDependencies: Record<string, string>;
  };
  components: Record<string, DictLockedComponent>;
}

function compareFileNames(firstName: string, secondName: string): number {
  const intInsensitiveComparison = firstName
    .toLowerCase()
    .localeCompare(secondName.toLowerCase());

  return intInsensitiveComparison !== 0
    ? intInsensitiveComparison
    : firstName.localeCompare(secondName);
}

function isStringRecord(value: unknown): value is Record<string, string> {
  return (
    isRecord(value) &&
    Object.values(value).every((recordValue) => typeof recordValue === "string")
  );
}

function isLockedComponent(value: unknown): value is DictLockedComponent {
  return (
    isRecord(value) &&
    typeof value.packageName === "string" &&
    typeof value.wheelFileName === "string"
  );
}

function isComponentsLockFile(value: unknown): value is DictComponentsLockFile {
  return (
    isRecord(value) &&
    value.schemaVersion === 1 &&
    isRecord(value.root) &&
    isStringRecord(value.root.componentDependencies) &&
    isRecord(value.components) &&
    Object.values(value.components).every(isLockedComponent)
  );
}

function loadComponentsLockFile(lockFilePath: string): DictComponentsLockFile {
  let lockFileStat: fs.Stats;
  try {
    lockFileStat = fs.lstatSync(lockFilePath);
  } catch (e) {
    throw new Error(`Component lock file was not found: ${lockFilePath}`, {
      cause: e,
    });
  }

  if (!lockFileStat.isFile() || lockFileStat.isSymbolicLink()) {
    throw new Error(`Component lock file is not a normal file: ${lockFilePath}`);
  }

  const value: unknown = JSON.parse(fs.readFileSync(lockFilePath, "utf-8"));
  if (!isComponentsLockFile(value)) {
    throw new Error(`Invalid component lock file: ${lockFilePath}`);
  }

  return value;
}

function getDistInfoFolderName(wheelFileName: string): string {
  const fileName = path.basename(wheelFileName);
  if (fileName !== wheelFileName || !fileName.toLowerCase().endsWith(".whl")) {
    throw new Error(`Invalid component wheel file name: ${wheelFileName}`);
  }

  const arrWheelNamePart = fileName.slice(0, -4).split("-");
  if (
    arrWheelNamePart.length < 5 ||
    arrWheelNamePart[0].length === 0 ||
    arrWheelNamePart[1].length === 0
  ) {
    throw new Error(`Invalid component wheel file name: ${wheelFileName}`);
  }

  return `${arrWheelNamePart[0]}-${arrWheelNamePart[1]}.dist-info`;
}

function loadSnippetCatalogFile(catalogFilePath: string): DictSnippetCatalogFile {
  let catalogFileStat: fs.Stats;
  try {
    catalogFileStat = fs.lstatSync(catalogFilePath);
  } catch (e) {
    throw new Error(`Snippet catalog was not found: ${catalogFilePath}`, {
      cause: e,
    });
  }

  if (!catalogFileStat.isFile() || catalogFileStat.isSymbolicLink()) {
    throw new Error(`Snippet catalog is not a normal file: ${catalogFilePath}`);
  }

  const value: unknown = JSON.parse(fs.readFileSync(catalogFilePath, "utf-8"));
  if (!isSnippetCatalogFile(value)) {
    throw new Error(`Invalid snippet catalog: ${catalogFilePath}`);
  }

  return value;
}

export function loadBuiltInSnippetCatalog(
  extensionPath: string,
): Info_LoadedSnippetCatalog {
  const catalogFilePath = path.join(
    extensionPath,
    "assets",
    STR_COMPONENT_CATALOG_FILE_NAME,
  );

  return {
    idPrefix: "builtin",
    displayPath: catalogFilePath,
    catalog: loadSnippetCatalogFile(catalogFilePath),
  };
}

export function loadComponentSnippetCatalogs(
  projectFolderPath: string | undefined,
): Info_LoadedSnippetCatalog[] {
  if (projectFolderPath === undefined) {
    return [];
  }

  const componentsFolderPath = path.join(projectFolderPath, STR_COMPONENTS_FOLDER_NAME);
  const lockFilePath = path.join(projectFolderPath, STR_COMPONENT_LOCK_FILE_NAME);
  const boolComponentsFolderExists = fs.existsSync(componentsFolderPath);
  const boolLockFileExists = fs.existsSync(lockFilePath);

  if (!boolLockFileExists) {
    if (boolComponentsFolderExists) {
      throw new Error(`Component lock file was not found for _Components: ${lockFilePath}`);
    }
    return [];
  }

  const lockFile = loadComponentsLockFile(lockFilePath);
  const arrDirectComponentId = Object.keys(lockFile.root.componentDependencies);
  if (arrDirectComponentId.length === 0) {
    return [];
  }

  if (!boolComponentsFolderExists) {
    throw new Error(`_Components folder was not found: ${componentsFolderPath}`);
  }

  const componentsFolderStat = fs.lstatSync(componentsFolderPath);
  if (!componentsFolderStat.isDirectory() || componentsFolderStat.isSymbolicLink()) {
    throw new Error(`_Components is not a normal folder: ${componentsFolderPath}`);
  }

  const directComponentInfoList = arrDirectComponentId.map((componentId) => {
    const lockedComponent = lockFile.components[componentId];
    if (lockedComponent === undefined) {
      throw new Error(
        `Direct component ${componentId} is missing from components.lock.json components.`,
      );
    }

    return {
      componentId,
      packageName: lockedComponent.packageName,
      distInfoFolderName: getDistInfoFolderName(lockedComponent.wheelFileName),
    };
  });

  directComponentInfoList.sort((first, second) =>
    compareFileNames(first.distInfoFolderName, second.distInfoFolderName),
  );

  return directComponentInfoList.map((componentInfo) => {
    const distInfoFolderPath = path.join(
      componentsFolderPath,
      componentInfo.distInfoFolderName,
    );

    let distInfoFolderStat: fs.Stats;
    try {
      distInfoFolderStat = fs.lstatSync(distInfoFolderPath);
    } catch (e) {
      throw new Error(
        `Direct component dist-info folder was not found for ${componentInfo.packageName}: ` +
          distInfoFolderPath,
        { cause: e },
      );
    }

    if (!distInfoFolderStat.isDirectory() || distInfoFolderStat.isSymbolicLink()) {
      throw new Error(
        `Direct component dist-info path is not a normal folder: ${distInfoFolderPath}`,
      );
    }

    const catalogFilePath = path.join(distInfoFolderPath, STR_COMPONENT_CATALOG_FILE_NAME);
    const displayPath = path
      .relative(projectFolderPath, catalogFilePath)
      .split(path.sep)
      .join("/");

    return {
      idPrefix: `component:${componentInfo.distInfoFolderName}`,
      displayPath,
      catalog: loadSnippetCatalogFile(catalogFilePath),
    };
  });
}
