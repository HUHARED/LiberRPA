// FileName: loadSnippetRepository.ts

import { log } from "../../Adapter/VsCode/output";
import { reportWarning } from "../../Adapter/VsCode/errorHandling";
import { loadFavoriteSnippetFile } from "../../Adapter/FileSystem/favoriteSnippetFile";
import {
  loadBuiltInSnippetCatalog,
  loadComponentSnippetCatalogs,
} from "../../Adapter/FileSystem/snippetCatalogFiles";
import { buildSnippetRepository } from "../../Domain/Snippet/snippetRepository";
import type {
  DictSnippetFavoriteFile,
  Info_SnippetRepository,
} from "../../Domain/Snippet/snippetTypes";

const EMPTY_FAVORITE_FILE: DictSnippetFavoriteFile = {
  schemaVersion: 1,
  snippets: {},
};

export function loadSnippetRepository(
  extensionPath: string,
  projectFolderPath: string | undefined,
  notifyFavoriteError: boolean,
): Info_SnippetRepository {
  let favoriteFile: DictSnippetFavoriteFile;
  try {
    favoriteFile = loadFavoriteSnippetFile(extensionPath);
  } catch (e) {
    reportWarning("Favorite snippets were skipped", e, notifyFavoriteError);
    favoriteFile = EMPTY_FAVORITE_FILE;
  }

  const loadedCatalogList = [
    loadBuiltInSnippetCatalog(extensionPath),
    ...loadComponentSnippetCatalogs(projectFolderPath),
  ];
  const buildResult = buildSnippetRepository(loadedCatalogList, favoriteFile);

  for (const warning of buildResult.warnings) {
    log.warn(`[Catalog] ${warning}`);
  }

  const intSnippetCount = Object.keys(buildResult.repository.snippetById).length;
  log.debug(
    `[Catalog] Loaded ${intSnippetCount} snippets from ${loadedCatalogList.length} catalog(s).`,
  );
  return buildResult.repository;
}
