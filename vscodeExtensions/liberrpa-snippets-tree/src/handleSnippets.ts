// FileName: handleSnippets.ts
import { log } from "./output";
import type {
  DictSnippetFavoriteFile,
  DictImportsInfo,
  DictSnippetCatalogFile,
  DictSnippetRepository,
  DictSnippetTotalInfo,
  SnippetInsertionMode,
} from "./interface";
import { isFavoriteSnippetsFile, isSnippetCatalog } from "./typeCheck";
import { reportWarning } from "./errorHandling";

import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import * as jsoncParser from "jsonc-parser";
import * as vscode from "vscode";

const STR_FAVORITE_CATEGORY = "Favorite";

function normalizeSnippetBody(body: string[] | string): string[] {
  const lines = Array.isArray(body) ? body : body.split(/\r?\n/);
  return lines.map((line) => line.replace(/\t/g, "    "));
}

function loadDefaultCatalog(): DictSnippetCatalogFile {
  const strCatalogPath = path.join(__dirname, "../assets/snippets_catalog.json");

  if (!fs.existsSync(strCatalogPath)) {
    throw new Error(`snippets_catalog.json was not found: ${strCatalogPath}`);
  }

  const value: unknown = JSON.parse(fs.readFileSync(strCatalogPath, "utf-8"));
  if (!isSnippetCatalog(value)) {
    throw new Error(`Invalid snippets_catalog.json: ${strCatalogPath}`);
  }

  log.debug(
    `[Catalog] Loaded ${Object.keys(value.snippets).length} snippets from ${strCatalogPath}.`
  );

  return value;
}

function loadFavoriteSnippets(): DictSnippetFavoriteFile {
  const strFavoritePath = path.join(
    os.homedir(),
    "Documents/LiberRPA/snippets_favorite.jsonc"
  );

  const strTargetFolderPath = path.dirname(strFavoritePath);
  if (
    !fs.existsSync(strTargetFolderPath) ||
    !fs.statSync(strTargetFolderPath).isDirectory()
  ) {
    throw new Error(
      `${strTargetFolderPath} was not found. Please run InitLiberRPA.exe to initialize or update LiberRPA.`
    );
  }

  if (!fs.existsSync(strFavoritePath)) {
    const strTemplatePath = path.join(
      __dirname,
      "../assets/snippets_favorite_template.jsonc"
    );
    fs.copyFileSync(strTemplatePath, strFavoritePath);

    log.info(`[Favorite] Created favorite snippets file: ${strFavoritePath}.`);
  }

  const strFileContent = fs.readFileSync(strFavoritePath, "utf-8");
  const arrParseErrors: jsoncParser.ParseError[] = [];
  const value: unknown = jsoncParser.parse(strFileContent, arrParseErrors, {
    allowTrailingComma: true,
  });

  if (arrParseErrors.length > 0) {
    const firstError = arrParseErrors[0];
    const strBeforeError = strFileContent.slice(0, firstError.offset);
    const intLine = strBeforeError.split(/\r?\n/).length;
    const intLastLineBreak = Math.max(
      strBeforeError.lastIndexOf("\n"),
      strBeforeError.lastIndexOf("\r")
    );
    const intColumn = firstError.offset - intLastLineBreak;

    throw new Error(
      `Invalid JSONC in ${strFavoritePath} at line ${intLine}, column ${intColumn}: ` +
        jsoncParser.printParseErrorCode(firstError.error)
    );
  }

  if (!isFavoriteSnippetsFile(value)) {
    throw new Error(`Invalid favorite snippets file: ${strFavoritePath}`);
  }

  log.debug(
    `[Favorite] Loaded ${Object.keys(value.snippets).length} snippets from ${strFavoritePath}.`
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

function validateSnippetImports(
  snippetTotalInfo: DictSnippetTotalInfo,
  knownImportSources: ReadonlySet<string>
): void {
  const unknownSources = Object.keys(snippetTotalInfo.imports).filter(
    (source) => !knownImportSources.has(source)
  );

  if (unknownSources.length > 0) {
    log.warn(
      `[Catalog] Snippet ${snippetTotalInfo.title} uses import sources without an order configuration: ${unknownSources.join(", ")}.`
    );
    // The source is still preserved by managed import handling,
    // but its names will use alphabetical order.
  }
}

export function loadSnippetRepository(): DictSnippetRepository {
  let dictFavorites: DictSnippetFavoriteFile;

  try {
    dictFavorites = loadFavoriteSnippets();
  } catch (e) {
    // Favorites are user-maintained and optional. A malformed file should not
    // disable the generated built-in TreeView and IntelliSense catalog.
    reportWarning("Favorite snippets were skipped", e, true);
    dictFavorites = { schemaVersion: 1, snippets: {} };
  }

  const dictCatalog = loadDefaultCatalog();
  const dictCategories: Record<string, DictSnippetTotalInfo[]> = {};
  const setKnownImportSources = new Set(Object.keys(dictCatalog.importSources));

  for (const [strTitle, dictDefinition] of Object.entries(dictFavorites.snippets)) {
    const dictSnippetTemp = {
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

    validateSnippetImports(dictSnippetTemp, setKnownImportSources);

    dictCategories[dictSnippetTemp.category] ??= [];
    dictCategories[dictSnippetTemp.category].push(dictSnippetTemp);
  }

  for (const [strTitle, dictDefinition] of Object.entries(dictCatalog.snippets)) {
    const dictSnippetTemp = {
      id: `builtin:${strTitle}`,
      title: strTitle,
      category: dictDefinition.category,
      label: dictDefinition.label,
      prefix: dictDefinition.prefix,
      body: normalizeSnippetBody(dictDefinition.body),
      description: dictDefinition.description,
      imports: normalizeImports(dictDefinition.imports),
      insertionMode: dictDefinition.insertionMode,
    };

    validateSnippetImports(dictSnippetTemp, setKnownImportSources);

    dictCategories[dictSnippetTemp.category] ??= [];
    dictCategories[dictSnippetTemp.category].push(dictSnippetTemp);
  }

  const arrCategoryOrder: string[] = [];

  if ((dictCategories[STR_FAVORITE_CATEGORY]?.length ?? 0) > 0) {
    arrCategoryOrder.push(STR_FAVORITE_CATEGORY);
  }

  for (const category of dictCatalog.categoryOrder) {
    if ((dictCategories[category]?.length ?? 0) > 0) {
      arrCategoryOrder.push(category);
    }
  }

  const arrUnknownCategories = Object.keys(dictCategories)
    .filter((category) => !arrCategoryOrder.includes(category))
    .sort();
  arrCategoryOrder.push(...arrUnknownCategories);

  return {
    categoryOrder: arrCategoryOrder,
    categories: dictCategories,
    importSources: dictCatalog.importSources,
  };
}

export async function insertSnippetFromTreeNode(
  editor: vscode.TextEditor,
  arrSnippetsLines: string[],
  insertionMode: SnippetInsertionMode
): Promise<boolean> {
  const snippetObj = new vscode.SnippetString(arrSnippetsLines.join("\n"));

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

  if (arrSnippetsLines[0].startsWith(" # type: ignore")) {
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
      "\n" + strCurrentLineIndent
    );
  });

  if (!boolEdited) {
    throw new Error("Failed to create a new line for the snippet.");
  }

  // Add the snippet at the new empty line.
  const positionNextLine = new vscode.Position(
    intLineNumberCurrent + 1,
    strCurrentLineIndent.length
  );
  editor.selection = new vscode.Selection(positionNextLine, positionNextLine);
  return await editor.insertSnippet(snippetObj);
}
