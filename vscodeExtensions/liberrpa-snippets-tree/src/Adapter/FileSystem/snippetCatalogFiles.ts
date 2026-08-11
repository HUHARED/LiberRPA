// FileName: snippetCatalogFiles.ts

import * as fs from "node:fs";
import * as path from "node:path";

import { isSnippetCatalogFile } from "../../Domain/Snippet/snippetValidation";
import type {
  DictSnippetCatalogFile,
  Info_LoadedSnippetCatalog,
} from "../../Domain/Snippet/snippetTypes";

const STR_COMPONENTS_FOLDER_NAME = "_Components";
const STR_COMPONENT_CATALOG_FILE_NAME = "snippets_catalog.json";

function compareFileNames(firstName: string, secondName: string): number {
  const intInsensitiveComparison = firstName
    .toLowerCase()
    .localeCompare(secondName.toLowerCase());

  return intInsensitiveComparison !== 0
    ? intInsensitiveComparison
    : firstName.localeCompare(secondName);
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
  if (!fs.existsSync(componentsFolderPath)) {
    return [];
  }

  const componentsFolderStat = fs.lstatSync(componentsFolderPath);
  if (!componentsFolderStat.isDirectory() || componentsFolderStat.isSymbolicLink()) {
    throw new Error(`_Components is not a normal folder: ${componentsFolderPath}`);
  }

  const distInfoEntryList = fs
    .readdirSync(componentsFolderPath, { withFileTypes: true })
    .filter((entry) => entry.name.toLowerCase().endsWith(".dist-info"))
    .sort((first, second) => compareFileNames(first.name, second.name));

  return distInfoEntryList.map((entry) => {
    if (!entry.isDirectory() || entry.isSymbolicLink()) {
      throw new Error(
        `Component dist-info path is not a normal folder: ` +
          path.join(componentsFolderPath, entry.name),
      );
    }

    const catalogFilePath = path.join(
      componentsFolderPath,
      entry.name,
      STR_COMPONENT_CATALOG_FILE_NAME,
    );
    const displayPath = path
      .relative(projectFolderPath, catalogFilePath)
      .split(path.sep)
      .join("/");

    return {
      idPrefix: `component:${entry.name}`,
      displayPath,
      catalog: loadSnippetCatalogFile(catalogFilePath),
    };
  });
}
