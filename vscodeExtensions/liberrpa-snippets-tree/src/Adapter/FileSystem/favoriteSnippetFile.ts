// FileName: favoriteSnippetFile.ts

import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import * as jsoncParser from "jsonc-parser";

import type { DictSnippetFavoriteFile } from "../../Domain/Snippet/snippetTypes";
import { isFavoriteSnippetFile } from "../../Domain/Snippet/snippetValidation";

const STR_FAVORITE_RELATIVE_PATH = "Documents/LiberRPA/snippets_favorite.jsonc";

export function getFavoriteSnippetFilePath(): string {
  return path.join(os.homedir(), STR_FAVORITE_RELATIVE_PATH);
}

export function loadFavoriteSnippetFile(extensionPath: string): DictSnippetFavoriteFile {
  const favoriteFilePath = getFavoriteSnippetFilePath();
  const favoriteFolderPath = path.dirname(favoriteFilePath);

  let favoriteFolderStat: fs.Stats;
  try {
    favoriteFolderStat = fs.statSync(favoriteFolderPath);
  } catch (e) {
    throw new Error(
      `${favoriteFolderPath} was not found. Run InitLiberRPA.exe to ` +
        "initialize or update LiberRPA.",
      { cause: e },
    );
  }

  if (!favoriteFolderStat.isDirectory()) {
    throw new Error(`Favorite snippet path is not a folder: ${favoriteFolderPath}`);
  }

  if (!fs.existsSync(favoriteFilePath)) {
    const templateFilePath = path.join(
      extensionPath,
      "assets",
      "snippets_favorite.jsonc.template",
    );
    fs.copyFileSync(templateFilePath, favoriteFilePath);
  }

  const fileContent = fs.readFileSync(favoriteFilePath, "utf-8");
  const parseErrorList: jsoncParser.ParseError[] = [];
  const value: unknown = jsoncParser.parse(fileContent, parseErrorList, {
    allowTrailingComma: true,
  });

  if (parseErrorList.length > 0) {
    const firstError = parseErrorList[0];
    const beforeError = fileContent.slice(0, firstError.offset);
    const intLine = beforeError.split(/\r?\n/).length;
    const intLastLineBreak = Math.max(
      beforeError.lastIndexOf("\n"),
      beforeError.lastIndexOf("\r"),
    );
    const intColumn = firstError.offset - intLastLineBreak;

    throw new Error(
      `Invalid JSONC in ${favoriteFilePath} at line ${intLine}, ` +
        `column ${intColumn}: ` +
        jsoncParser.printParseErrorCode(firstError.error),
    );
  }

  if (!isFavoriteSnippetFile(value)) {
    throw new Error(`Invalid favorite snippets file: ${favoriteFilePath}`);
  }

  return value;
}
