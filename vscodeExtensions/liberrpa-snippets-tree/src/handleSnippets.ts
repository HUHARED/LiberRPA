// FileName: handleSnippets.ts
import { log } from "./output";
import type {
  SnippetInsertionMode,
  DictImportsInfo,
  DictImportSourceConfig,
  DictSnippetCatalogFile,
  DictSnippetFavoriteFile,
  DictSnippetRepository,
  DictSnippetTotalInfo,
} from "./interface";
import { isFavoriteSnippetsFile, isSnippetCatalog } from "./typeCheck";
import { reportWarning } from "./errorHandling";

import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import * as jsoncParser from "jsonc-parser";
import * as vscode from "vscode";

const STR_FAVORITE_CATEGORY = "Favorite";
const STR_COMPONENTS_FOLDER = "_Components";
const STR_COMPONENT_CATALOG_RELATIVE_PATH = "snippets_catalog.json";

interface DictLoadedSnippetCatalog {
  idPrefix: string;
  displayPath: string;
  catalog: DictSnippetCatalogFile;
}

function normalizeSnippetBody(body: string[] | string): string[] {
  const arrLine = Array.isArray(body) ? body : body.split(/\r?\n/);
  return arrLine.map((line) => line.replace(/\t/g, "    "));
}

function loadSnippetCatalogFile(catalogPath: string): DictSnippetCatalogFile {
  if (!fs.existsSync(catalogPath) || !fs.statSync(catalogPath).isFile()) {
    throw new Error(`Snippet catalog was not found: ${catalogPath}`);
  }

  const value: unknown = JSON.parse(fs.readFileSync(catalogPath, "utf-8"));
  if (!isSnippetCatalog(value)) {
    throw new Error(`Invalid snippet catalog: ${catalogPath}`);
  }

  log.debug(
    `[Catalog] Loaded ${Object.keys(value.snippets).length} snippets from ${catalogPath}.`,
  );

  return value;
}

function loadDefaultCatalog(): DictLoadedSnippetCatalog {
  const strCatalogPath = path.join(__dirname, "../assets/snippets_catalog.json");

  return {
    idPrefix: "builtin",
    displayPath: strCatalogPath,
    catalog: loadSnippetCatalogFile(strCatalogPath),
  };
}

function compareFileNames(firstName: string, secondName: string): number {
  const intInsensitiveComparison = firstName
    .toLowerCase()
    .localeCompare(secondName.toLowerCase());

  if (intInsensitiveComparison !== 0) {
    return intInsensitiveComparison;
  }

  return firstName.localeCompare(secondName);
}

function loadComponentCatalogs(
  workspaceFolder: vscode.WorkspaceFolder | undefined,
): DictLoadedSnippetCatalog[] {
  if (!workspaceFolder) {
    return [];
  }

  const strComponentsPath = path.join(workspaceFolder.uri.fsPath, STR_COMPONENTS_FOLDER);
  if (!fs.existsSync(strComponentsPath)) {
    return [];
  }

  if (!fs.statSync(strComponentsPath).isDirectory()) {
    throw new Error(`Component folder is not a directory: ${strComponentsPath}`);
  }

  const arrDistInfoFolder = fs
    .readdirSync(strComponentsPath, { withFileTypes: true })
    .filter(
      (entry) => entry.isDirectory() && entry.name.toLowerCase().endsWith(".dist-info"),
    )
    .sort((first, second) => compareFileNames(first.name, second.name));

  return arrDistInfoFolder.map((entry) => {
    const strCatalogPath = path.join(
      strComponentsPath,
      entry.name,
      ...STR_COMPONENT_CATALOG_RELATIVE_PATH.split("/"),
    );
    const strDisplayPath = path
      .relative(workspaceFolder.uri.fsPath, strCatalogPath)
      .split(path.sep)
      .join("/");

    return {
      idPrefix: `component:${entry.name}`,
      displayPath: strDisplayPath,
      catalog: loadSnippetCatalogFile(strCatalogPath),
    };
  });
}

function loadFavoriteSnippets(): DictSnippetFavoriteFile {
  const strFavoritePath = path.join(
    os.homedir(),
    "Documents/LiberRPA/snippets_favorite.jsonc",
  );

  const strTargetFolderPath = path.dirname(strFavoritePath);
  if (
    !fs.existsSync(strTargetFolderPath) ||
    !fs.statSync(strTargetFolderPath).isDirectory()
  ) {
    throw new Error(
      `${strTargetFolderPath} was not found. Please run InitLiberRPA.exe to initialize or update LiberRPA.`,
    );
  }

  if (!fs.existsSync(strFavoritePath)) {
    const strTemplatePath = path.join(
      __dirname,
      "../assets/snippets_favorite.jsonc.template",
    );
    fs.copyFileSync(strTemplatePath, strFavoritePath);

    log.info(`[Favorite] Created favorite snippets file: ${strFavoritePath}.`);
  }

  const strFileContent = fs.readFileSync(strFavoritePath, "utf-8");
  const arrParseError: jsoncParser.ParseError[] = [];
  const value: unknown = jsoncParser.parse(strFileContent, arrParseError, {
    allowTrailingComma: true,
  });

  if (arrParseError.length > 0) {
    const firstError = arrParseError[0];
    const strBeforeError = strFileContent.slice(0, firstError.offset);
    const intLine = strBeforeError.split(/\r?\n/).length;
    const intLastLineBreak = Math.max(
      strBeforeError.lastIndexOf("\n"),
      strBeforeError.lastIndexOf("\r"),
    );
    const intColumn = firstError.offset - intLastLineBreak;

    throw new Error(
      `Invalid JSONC in ${strFavoritePath} at line ${intLine}, column ${intColumn}: ` +
        jsoncParser.printParseErrorCode(firstError.error),
    );
  }

  if (!isFavoriteSnippetsFile(value)) {
    throw new Error(`Invalid favorite snippets file: ${strFavoritePath}`);
  }

  log.debug(
    `[Favorite] Loaded ${Object.keys(value.snippets).length} snippets from ${strFavoritePath}.`,
  );

  return value;
}

function normalizeImports(imports: DictImportsInfo | undefined): DictImportsInfo {
  if (!imports) {
    return {};
  }

  const dictResult: DictImportsInfo = {};

  for (const [importSource, importNames] of Object.entries(imports)) {
    dictResult[importSource] = [...new Set(importNames)];
  }

  return dictResult;
}

function cloneImportSourceConfig(config: DictImportSourceConfig): DictImportSourceConfig {
  return {
    order: [...config.order],
    ...(config.aliasMode === undefined ? {} : { aliasMode: config.aliasMode }),
  };
}

function validateSnippetImports(
  snippetTotalInfo: DictSnippetTotalInfo,
  knownImportSources: ReadonlySet<string>,
): void {
  const arrUnknownSource = Object.keys(snippetTotalInfo.imports).filter(
    (source) => !knownImportSources.has(source),
  );

  if (arrUnknownSource.length > 0) {
    log.warn(
      `[Catalog] Snippet ${snippetTotalInfo.title} uses import sources without an order configuration: ${arrUnknownSource.join(", ")}.`,
    );
    // The source is still preserved by managed import handling,
    // but its names will use alphabetical order.
  }
}

function addCatalogToRepository(
  loadedCatalogDict: DictLoadedSnippetCatalog,
  categoryDict: Record<string, DictSnippetTotalInfo[]>,
  importSourceDict: Record<string, DictImportSourceConfig>,
  catalogCategoryOrderArr: string[],
  snippetOwnerMap: Map<string, string>,
  importSourceOwnerMap: Map<string, string>,
): void {
  for (const [strImportSource, dictConfig] of Object.entries(
    loadedCatalogDict.catalog.importSources,
  )) {
    const strExistingOwner = importSourceOwnerMap.get(strImportSource);
    if (strExistingOwner !== undefined) {
      throw new Error(
        `Duplicate import source "${strImportSource}" in ${loadedCatalogDict.displayPath}; it is already provided by ${strExistingOwner}.`,
      );
    }

    importSourceOwnerMap.set(strImportSource, loadedCatalogDict.displayPath);
    importSourceDict[strImportSource] = cloneImportSourceConfig(dictConfig);
  }

  for (const strCategory of loadedCatalogDict.catalog.categoryOrder) {
    if (!catalogCategoryOrderArr.includes(strCategory)) {
      catalogCategoryOrderArr.push(strCategory);
    }
  }

  for (const [strTitle, dictDefinition] of Object.entries(
    loadedCatalogDict.catalog.snippets,
  )) {
    const strExistingOwner = snippetOwnerMap.get(strTitle);
    if (strExistingOwner !== undefined) {
      throw new Error(
        `Duplicate snippet key "${strTitle}" in ${loadedCatalogDict.displayPath}; it is already provided by ${strExistingOwner}.`,
      );
    }

    snippetOwnerMap.set(strTitle, loadedCatalogDict.displayPath);

    const dictSnippetTemp: DictSnippetTotalInfo = {
      id: `${loadedCatalogDict.idPrefix}:${strTitle}`,
      title: strTitle,
      category: dictDefinition.category,
      label: dictDefinition.label,
      prefix: dictDefinition.prefix,
      body: normalizeSnippetBody(dictDefinition.body),
      description: dictDefinition.description,
      imports: normalizeImports(dictDefinition.imports),
      insertionMode: dictDefinition.insertionMode,
    };

    categoryDict[dictSnippetTemp.category] ??= [];
    categoryDict[dictSnippetTemp.category].push(dictSnippetTemp);
  }
}

function replaceRecord<T>(
  targetDict: Record<string, T>,
  sourceDict: Record<string, T>,
): void {
  for (const strKey of Object.keys(targetDict)) {
    delete targetDict[strKey];
  }

  Object.assign(targetDict, sourceDict);
}

export function replaceSnippetRepository(
  repository: DictSnippetRepository,
  nextRepository: DictSnippetRepository,
): void {
  repository.categoryOrder.splice(
    0,
    repository.categoryOrder.length,
    ...nextRepository.categoryOrder,
  );
  replaceRecord(repository.categories, nextRepository.categories);
  replaceRecord(repository.importSources, nextRepository.importSources);
}

export function loadSnippetRepository(
  workspaceFolder?: vscode.WorkspaceFolder,
): DictSnippetRepository {
  let dictFavorites: DictSnippetFavoriteFile;

  try {
    dictFavorites = loadFavoriteSnippets();
  } catch (e) {
    // Favorites are user-maintained and optional. A malformed file should not
    // disable the generated built-in TreeView and IntelliSense catalog.
    reportWarning("Favorite snippets were skipped", e, true);
    dictFavorites = { schemaVersion: 1, snippets: {} };
  }

  const arrLoadedCatalogs = [
    loadDefaultCatalog(),
    ...loadComponentCatalogs(workspaceFolder),
  ];
  const dictCategory: Record<string, DictSnippetTotalInfo[]> = {};
  const dictImportSource: Record<string, DictImportSourceConfig> = {};
  const arrCatalogCategoryOrder: string[] = [];
  const mapSnippetOwner = new Map<string, string>();
  const mapImportSourceOwner = new Map<string, string>();

  for (const loadedCatalog of arrLoadedCatalogs) {
    addCatalogToRepository(
      loadedCatalog,
      dictCategory,
      dictImportSource,
      arrCatalogCategoryOrder,
      mapSnippetOwner,
      mapImportSourceOwner,
    );
  }

  const setKnownImportSource = new Set(Object.keys(dictImportSource));

  for (const arrSnippet of Object.values(dictCategory)) {
    for (const snippetTotalInfo of arrSnippet) {
      validateSnippetImports(snippetTotalInfo, setKnownImportSource);
    }
  }

  for (const [strTitle, dictDefinition] of Object.entries(dictFavorites.snippets)) {
    const dictSnippetTemp: DictSnippetTotalInfo = {
      id: `favorite:${strTitle}`,
      title: strTitle,
      category: STR_FAVORITE_CATEGORY,
      label: dictDefinition.label ?? strTitle,
      prefix: dictDefinition.prefix,
      body: normalizeSnippetBody(dictDefinition.body),
      description:
        dictDefinition.description ?? "No description is available for this snippet.",
      imports: normalizeImports(dictDefinition.imports),
      insertionMode: dictDefinition.insertionMode ?? "line",
    };

    validateSnippetImports(dictSnippetTemp, setKnownImportSource);

    dictCategory[dictSnippetTemp.category] ??= [];
    dictCategory[dictSnippetTemp.category].push(dictSnippetTemp);
  }

  const arrCategoryOrder: string[] = [];

  if ((dictCategory[STR_FAVORITE_CATEGORY]?.length ?? 0) > 0) {
    arrCategoryOrder.push(STR_FAVORITE_CATEGORY);
  }

  for (const strCategory of arrCatalogCategoryOrder) {
    if (
      (dictCategory[strCategory]?.length ?? 0) > 0 &&
      !arrCategoryOrder.includes(strCategory)
    ) {
      arrCategoryOrder.push(strCategory);
    }
  }

  const arrUnknownCategories = Object.keys(dictCategory)
    .filter((category) => !arrCategoryOrder.includes(category))
    .sort(compareFileNames);
  arrCategoryOrder.push(...arrUnknownCategories);

  return {
    categoryOrder: arrCategoryOrder,
    categories: dictCategory,
    importSources: dictImportSource,
  };
}

export async function insertSnippetFromTreeNode(
  editor: vscode.TextEditor,
  arrSnippetsLine: string[],
  insertionMode: SnippetInsertionMode,
): Promise<boolean> {
  const snippetObj = new vscode.SnippetString(arrSnippetsLine.join("\n"));

  /*
   * Expression-like snippets, such as PrjArgs.projectPath, should be
   * inserted exactly at the current cursor or replace the current selection.
   */
  if (insertionMode === "cursor") {
    return await editor.insertSnippet(snippetObj);
  }

  const positionCurrent = editor.selection.active;
  const intLineNumberCurrent = positionCurrent.line;
  const lineCurrent = editor.document.lineAt(intLineNumberCurrent);

  if (lineCurrent.isEmptyOrWhitespace) {
    // It's a empty line, add the snippet directly.
    return await editor.insertSnippet(snippetObj);
  }

  if (arrSnippetsLine[0].startsWith(" # type: ignore")) {
    // For type ignore, add it at the line's end.
    const positionEnd = new vscode.Position(intLineNumberCurrent, lineCurrent.text.length);
    editor.selection = new vscode.Selection(positionEnd, positionEnd);
    return await editor.insertSnippet(snippetObj);
  }

  // Keep the current indent by insert spaces.
  const strCurrentLineIndent = lineCurrent.text.match(/^\s*/)?.[0] || "";
  const boolEdited = await editor.edit((editBuilder) => {
    editBuilder.insert(
      positionCurrent.with(intLineNumberCurrent, lineCurrent.text.length),
      "\n" + strCurrentLineIndent,
    );
  });

  if (!boolEdited) {
    throw new Error("Failed to create a new line for the snippet.");
  }

  // Add the snippet at the new empty line.
  const positionNextLine = new vscode.Position(
    intLineNumberCurrent + 1,
    strCurrentLineIndent.length,
  );
  editor.selection = new vscode.Selection(positionNextLine, positionNextLine);
  return await editor.insertSnippet(snippetObj);
}
