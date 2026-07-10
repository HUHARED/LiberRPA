// FileName: handleSnippets.ts
import { log } from "./output";
import type { ImportManifest, SnippetTotalInfo } from "./interface";
import { isSnippetsRecord, isImportManifest } from "./typeCheck";

import * as path from "path";
import * as fs from "fs";
import * as os from "os";
import * as jsoncParser from "jsonc-parser";

function normalizeSnippetBody(body: string[] | string): string[] {
  if (Array.isArray(body)) {
    return body;
  }

  return body.split(/\r?\n/);
}

function generateTreeItemFromSnippets(
  fileContent: string,
  isFavorite: boolean,
  importManifest: ImportManifest,
): Record<string, Record<string, SnippetTotalInfo>> {
  const dictTree: Record<string, Record<string, SnippetTotalInfo>> = {};

  fileContent = fileContent.replace(/\t/g, "    ");

  const parsedSnippets: unknown = jsoncParser.parse(fileContent);

  if (!isSnippetsRecord(parsedSnippets)) {
    throw new Error("Invalid snippets file structure.");
  }

  const dictSnippets = parsedSnippets;

  for (const [strKey, dictSnippetDetail] of Object.entries(dictSnippets)) {
    let strCategoryName: string;
    let strSnippetLabel: string;

    if (isFavorite) {
      strCategoryName = "Favorite";
      // Keep the original key as the label for favorite snippets.
      strSnippetLabel = strKey;
    } else {
      // Use the text before "." as the category's name. Use the text after "." as the children node's name.
      const intDotIndex = strKey.indexOf(".");

      strCategoryName = intDotIndex !== -1 ? strKey.substring(0, intDotIndex) : strKey;
      strSnippetLabel = intDotIndex !== -1 ? strKey.substring(intDotIndex + 1) : strKey;
    }

    // Create the category group.
    if (!dictTree[strCategoryName]) {
      dictTree[strCategoryName] = {};
    }

    // Add children into the category group.
    dictTree[strCategoryName][strSnippetLabel] = {
      // Store all metadata needed by TreeView, IntelliSense, and import management.
      title: strKey,
      prefix: dictSnippetDetail.prefix,
      body: normalizeSnippetBody(dictSnippetDetail.body),
      description:
        dictSnippetDetail.description ??
        "There is no description. Maybe it's enough to see the name of the function?",
      importNames: importManifest.items[strKey] ?? [],
    };
  }

  log.debug(
    `[Snippets]Loaded ${Object.values(dictTree).reduce((total, category) => total + Object.keys(category).length, 0)} snippets from ${isFavorite ? "favorite" : "default"} snippets.`,
  );

  return dictTree;
}

function getFavoriteSnippets(importManifest: ImportManifest): {
  [key: string]: { [key: string]: SnippetTotalInfo };
} {
  const strFilePath = path.join(os.homedir(), "Documents/LiberRPA/snippets_favorite.jsonc");

  if (!fs.existsSync(strFilePath)) {
    log.info(`${strFilePath} doesn't exist, create it.`);

    const strFileContent = fs.readFileSync(
      path.join(__dirname, "../assets/snippets_favorite_template.jsonc"),
      "utf-8",
    );
    fs.writeFileSync(strFilePath, strFileContent, { encoding: "utf-8" });
  }

  const strFileContent = fs.readFileSync(strFilePath, "utf-8");
  return generateTreeItemFromSnippets(strFileContent, true, importManifest);
}

function getDefaultSnippets(importManifest: ImportManifest): {
  [key: string]: { [key: string]: SnippetTotalInfo };
} {
  const strFileContent = fs.readFileSync(
    path.join(__dirname, "../assets/snippets_final.snippets"),
    "utf-8",
  );

  return generateTreeItemFromSnippets(strFileContent, false, importManifest);
}

export function getSnippets(): {
  [key: string]: { [key: string]: SnippetTotalInfo };
} {
  const importManifest = getImportManifest();
  return {
    ...getFavoriteSnippets(importManifest),
    ...getDefaultSnippets(importManifest),
  };
}

export function getImportManifest(): ImportManifest {
  const manifestPath = path.join(__dirname, "../assets/import_manifest.json");

  if (!fs.existsSync(manifestPath)) {
    log.error(
      `import_manifest.json was not found: ${manifestPath}. Managed imports will be disabled.`,
    );

    return {
      importSource: "liberrpa.Modules",
      importOrder: [],
      items: {},
    };
  }

  const value: unknown = JSON.parse(fs.readFileSync(manifestPath, "utf-8"));

  if (!isImportManifest(value)) {
    throw new Error(`Invalid import_manifest.json: ${manifestPath}`);
  }

  // TODO: More "import_manifest.json" would be used after LiberRPA Component feature completed.
  log.trace(
    `[Manifest] Loaded import manifest: ${manifestPath}, items=${Object.keys(value.items).length}.`,
  );

  return value;
}
