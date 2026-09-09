// FileName: customArgsKeyIndex.ts

import * as fs from "node:fs/promises";
import type { Dirent } from "node:fs";
import * as path from "node:path";
import * as vscode from "vscode";
import { analyzeCustomArgsSources } from "../Python/customArgsAnalysis";
import { log } from "./output";

const INT_REFRESH_DELAY_MS = 350;
const INT_MAX_SOURCE_BYTES = 2 * 1024 * 1024;
const SET_EXCLUDED_DIRECTORY = new Set([
  "_components",
  "_snippets",
  "__pycache__",
  ".git",
  ".vscode",
  ".venv",
  "venv",
  "envs",
  "node_modules",
  ".tox",
  ".mypy_cache",
  ".pytest_cache",
  ".ruff_cache",
]);
const SET_PROJECT_MARKER = new Set(["project.flow", "flow.json", "component.json"]);

type IndexedSource = {
  revision: number;
  attemptedText?: string;
  keyPaths: string[][];
};

type ProjectKeyIndex = {
  folder: vscode.WorkspaceFolder;
  files: Map<string, IndexedSource>;
  children: Map<string, Set<string>>;
  pendingFiles: Set<string>;
  needsScan: boolean;
  initialized: boolean;
  disposed: boolean;
  abortController: AbortController;
  subscriptions: vscode.Disposable[];
  timer?: ReturnType<typeof setTimeout>;
  refreshPromise?: Promise<void>;
};

function normalizeSourcePath(strFilePath: string): string {
  const normalized = path.normalize(strFilePath);
  return process.platform === "win32" ? normalized.toLowerCase() : normalized;
}

function isWithinPath(strFilePath: string, strRootPath: string): boolean {
  const relative = path.relative(strRootPath, strFilePath);
  return (
    relative === "" ||
    (!relative.startsWith(`..${path.sep}`) &&
      relative !== ".." &&
      !path.isAbsolute(relative))
  );
}

function isIndexPath(strFilePath: string, strRootPath: string): boolean {
  return (
    isWithinPath(strFilePath, strRootPath) &&
    !path
      .relative(strRootPath, strFilePath)
      .split(path.sep)
      .some((segment) => SET_EXCLUDED_DIRECTORY.has(segment.toLowerCase()))
  );
}

function isSourcePath(strFilePath: string, strRootPath: string): boolean {
  return (
    isIndexPath(strFilePath, strRootPath) &&
    path.extname(strFilePath).toLowerCase() === ".py"
  );
}

async function hasProjectMarker(strDirectoryPath: string): Promise<boolean> {
  for (const name of SET_PROJECT_MARKER) {
    try {
      if ((await fs.stat(path.join(strDirectoryPath, name))).isFile()) {
        return true;
      }
    } catch {
      // A missing marker is normal for a source folder.
    }
  }
  return false;
}

async function isOwnedSource(strFilePath: string, strRootPath: string): Promise<boolean> {
  if (!isSourcePath(strFilePath, strRootPath)) {
    return false;
  }
  let strDirectoryPath = path.dirname(strFilePath);
  while (path.relative(strRootPath, strDirectoryPath) !== "") {
    if (
      (await fs.lstat(strDirectoryPath)).isSymbolicLink() ||
      (await hasProjectMarker(strDirectoryPath))
    ) {
      return false;
    }
    strDirectoryPath = path.dirname(strDirectoryPath);
  }
  return !(await fs.lstat(strFilePath)).isSymbolicLink();
}

async function listProjectSources(strRootPath: string): Promise<string[]> {
  const arrSourcePath: string[] = [];
  const visit = async (strDirectoryPath: string): Promise<void> => {
    let arrEntry: Dirent[];
    try {
      arrEntry = await fs.readdir(strDirectoryPath, { withFileTypes: true });
    } catch {
      return;
    }
    if (
      strDirectoryPath !== strRootPath &&
      arrEntry.some((entry) => SET_PROJECT_MARKER.has(entry.name))
    ) {
      return;
    }
    for (const entry of arrEntry) {
      const strEntryPath = path.join(strDirectoryPath, entry.name);
      if (entry.isDirectory() && !SET_EXCLUDED_DIRECTORY.has(entry.name.toLowerCase())) {
        await visit(strEntryPath);
      } else if (entry.isFile() && path.extname(entry.name).toLowerCase() === ".py") {
        arrSourcePath.push(strEntryPath);
      }
    }
  };
  await visit(strRootPath);
  return arrSourcePath;
}

function rebuildChildren(state: ProjectKeyIndex): void {
  state.children.clear();
  for (const source of state.files.values()) {
    for (const keyPath of source.keyPaths) {
      // First-level names are exclusively owned by project.flow.
      for (let intDepth = 1; intDepth < keyPath.length; intDepth += 1) {
        const parent = JSON.stringify(keyPath.slice(0, intDepth));
        let children = state.children.get(parent);
        if (!children) {
          children = new Set<string>();
          state.children.set(parent, children);
        }
        children.add(keyPath[intDepth]);
      }
    }
  }
}

/** Source observations only; this index does not model runtime execution order. */
export class CustomArgsKeyIndex implements vscode.Disposable {
  private readonly mapProject = new Map<string, ProjectKeyIndex>();
  private readonly subscriptions: vscode.Disposable[];
  private boolDisposed = false;

  constructor(private readonly strHelperPath: string) {
    const updateDocument = (document: vscode.TextDocument): void => {
      if (document.uri.scheme !== "file" || document.languageId !== "python") {
        return;
      }
      for (const state of this.mapProject.values()) {
        if (isSourcePath(document.uri.fsPath, state.folder.uri.fsPath)) {
          this.queueSource(state, document.uri.fsPath);
        }
      }
    };
    this.subscriptions = [
      vscode.workspace.onDidChangeTextDocument((event) => updateDocument(event.document)),
      vscode.workspace.onDidOpenTextDocument(updateDocument),
      vscode.workspace.onDidCloseTextDocument(updateDocument),
      vscode.workspace.onDidChangeWorkspaceFolders((event) => {
        for (const folder of event.added) {
          void this.primeFolder(folder);
        }
        for (const folder of event.removed) {
          const key = folder.uri.toString();
          const state = this.mapProject.get(key);
          if (state) {
            this.disposeProject(state);
            this.mapProject.delete(key);
          }
        }
      }),
      vscode.workspace.onDidGrantWorkspaceTrust(() => {
        for (const folder of vscode.workspace.workspaceFolders ?? []) {
          void this.primeFolder(folder);
        }
      }),
    ];
    for (const folder of vscode.workspace.workspaceFolders ?? []) {
      void this.primeFolder(folder);
    }
  }

  private async primeFolder(folder: vscode.WorkspaceFolder): Promise<void> {
    if (this.boolDisposed || !vscode.workspace.isTrusted || folder.uri.scheme !== "file") {
      return;
    }
    try {
      if ((await fs.stat(path.join(folder.uri.fsPath, "project.flow"))).isFile()) {
        // Prime valid definitions before the user begins an incomplete lookup.
        await this.getChildKeys(folder, []);
      }
    } catch {
      // A workspace folder need not be a Flow Project.
    }
  }

  async getChildKeys(folder: vscode.WorkspaceFolder, keyPath: string[]): Promise<string[]> {
    if (this.boolDisposed || !vscode.workspace.isTrusted || folder.uri.scheme !== "file") {
      return [];
    }
    const key = folder.uri.toString();
    if (
      !vscode.workspace.workspaceFolders?.some(
        (workspaceFolder) => workspaceFolder.uri.toString() === key,
      )
    ) {
      return [];
    }
    let state = this.mapProject.get(key);
    if (!state) {
      state = this.createProject(folder);
      this.mapProject.set(key, state);
    }
    if (!state.initialized) {
      await this.refresh(state);
    }
    // Once initialized, completion reads only the cache. Debounced source edits
    // are analyzed independently, never by scanning the project on each keypress.
    return state.disposed
      ? []
      : [...(state.children.get(JSON.stringify(keyPath)) ?? [])].sort();
  }

  private createProject(folder: vscode.WorkspaceFolder): ProjectKeyIndex {
    const state: ProjectKeyIndex = {
      folder,
      files: new Map(),
      children: new Map(),
      pendingFiles: new Set(),
      needsScan: true,
      initialized: false,
      disposed: false,
      abortController: new AbortController(),
      subscriptions: [],
    };
    const watcher = vscode.workspace.createFileSystemWatcher(
      new vscode.RelativePattern(folder, "**/*"),
    );
    const changed = (uri: vscode.Uri): void => {
      if (!isIndexPath(uri.fsPath, folder.uri.fsPath)) {
        return;
      }
      if (isSourcePath(uri.fsPath, folder.uri.fsPath)) {
        this.queueSource(state, uri.fsPath);
      } else if (SET_PROJECT_MARKER.has(path.basename(uri.fsPath))) {
        state.needsScan = true;
        this.schedule(state);
      }
    };
    state.subscriptions.push(
      watcher,
      watcher.onDidChange(changed),
      watcher.onDidCreate((uri) => {
        if (!isIndexPath(uri.fsPath, folder.uri.fsPath)) {
          return;
        }
        changed(uri);
        // Parent-folder moves may be reported without individual child events.
        void fs.stat(uri.fsPath).then(
          (stat) => {
            if (
              stat.isDirectory() &&
              !SET_EXCLUDED_DIRECTORY.has(path.basename(uri.fsPath).toLowerCase())
            ) {
              state.needsScan = true;
              this.schedule(state);
            }
          },
          () => undefined,
        );
      }),
      watcher.onDidDelete((uri) => {
        if (!isIndexPath(uri.fsPath, folder.uri.fsPath)) {
          return;
        }
        for (const strFilePath of state.files.keys()) {
          if (isWithinPath(strFilePath, uri.fsPath)) {
            state.files.delete(strFilePath);
            state.pendingFiles.delete(strFilePath);
          }
        }
        rebuildChildren(state);
        if (SET_PROJECT_MARKER.has(path.basename(uri.fsPath))) {
          state.needsScan = true;
          this.schedule(state);
        }
      }),
    );
    return state;
  }

  private queueSource(state: ProjectKeyIndex, strFilePath: string): void {
    strFilePath = normalizeSourcePath(strFilePath);
    if (state.disposed) {
      return;
    }
    const source = state.files.get(strFilePath);
    if (source) {
      source.revision += 1;
    }
    state.pendingFiles.add(strFilePath);
    this.schedule(state);
  }

  private schedule(state: ProjectKeyIndex): void {
    if (state.disposed) {
      return;
    }
    if (state.timer !== undefined) {
      clearTimeout(state.timer);
    }
    state.timer = setTimeout(() => {
      state.timer = undefined;
      void this.refresh(state);
    }, INT_REFRESH_DELAY_MS);
  }

  private refresh(state: ProjectKeyIndex): Promise<void> {
    if (state.refreshPromise) {
      return state.refreshPromise;
    }
    if (state.disposed) {
      return Promise.resolve();
    }
    if (state.timer !== undefined) {
      clearTimeout(state.timer);
      state.timer = undefined;
    }
    state.refreshPromise = this.updateSources(state)
      .catch((e: unknown) => {
        if (!state.disposed) {
          log.debug(
            `[CustomArgs] Source indexing unavailable: ${e instanceof Error ? e.message : String(e)}`,
          );
        }
      })
      .finally(() => {
        state.initialized = true;
        state.refreshPromise = undefined;
        if (!state.disposed && (state.needsScan || state.pendingFiles.size > 0)) {
          this.schedule(state);
        }
      });
    return state.refreshPromise;
  }

  private async updateSources(state: ProjectKeyIndex): Promise<void> {
    if (state.needsScan) {
      state.needsScan = false;
      const arrSourcePath = (await listProjectSources(state.folder.uri.fsPath)).map(
        normalizeSourcePath,
      );
      if (state.disposed) {
        return;
      }
      const setSourcePath = new Set(arrSourcePath);
      for (const strFilePath of state.files.keys()) {
        if (!setSourcePath.has(strFilePath)) {
          state.files.delete(strFilePath);
        }
      }
      for (const strFilePath of arrSourcePath) {
        state.pendingFiles.add(strFilePath);
      }
      rebuildChildren(state);
    }
    const arrPendingPath = [...state.pendingFiles];
    state.pendingFiles.clear();
    const arrSnapshot: {
      filePath: string;
      text: string;
      source: IndexedSource;
      revision: number;
    }[] = [];
    for (const strFilePath of arrPendingPath) {
      if (state.disposed) {
        return;
      }
      try {
        if (!(await isOwnedSource(strFilePath, state.folder.uri.fsPath))) {
          state.files.delete(strFilePath);
          continue;
        }
        let source = state.files.get(strFilePath);
        if (!source) {
          source = { revision: 0, keyPaths: [] };
          state.files.set(strFilePath, source);
        }
        const revision = source.revision;
        const document = vscode.workspace.textDocuments.find(
          (candidate) =>
            !candidate.isClosed &&
            candidate.uri.scheme === "file" &&
            normalizeSourcePath(candidate.uri.fsPath) === strFilePath,
        );
        let text: string | undefined;
        if (document) {
          text = document.getText();
        } else if ((await fs.stat(strFilePath)).size <= INT_MAX_SOURCE_BYTES) {
          text = await fs.readFile(strFilePath, "utf8");
        }
        if (text === undefined || Buffer.byteLength(text, "utf8") > INT_MAX_SOURCE_BYTES) {
          state.files.delete(strFilePath);
          continue;
        }
        if (text !== source.attemptedText) {
          arrSnapshot.push({ filePath: strFilePath, text, source, revision });
        }
      } catch {
        // Deleted/unreadable files must not contribute stale keys.
        state.files.delete(strFilePath);
      }
    }
    rebuildChildren(state);
    if (arrSnapshot.length === 0 || state.disposed) {
      return;
    }
    const arrResult = await analyzeCustomArgsSources(
      this.strHelperPath,
      arrSnapshot,
      state.abortController.signal,
    );
    if (state.disposed) {
      return;
    }
    const mapSnapshot = new Map(
      arrSnapshot.map((snapshot) => [snapshot.filePath, snapshot]),
    );
    for (const result of arrResult) {
      const snapshot = mapSnapshot.get(result.filePath);
      if (
        !snapshot ||
        state.files.get(result.filePath) !== snapshot.source ||
        snapshot.source.revision !== snapshot.revision
      ) {
        continue;
      }
      snapshot.source.attemptedText = snapshot.text;
      if (result.keyPaths !== null) {
        snapshot.source.keyPaths = result.keyPaths;
      }
    }
    rebuildChildren(state);
    log.trace(
      `[CustomArgs] Indexed ${arrSnapshot.length} changed Python file(s) in ${state.folder.name}.`,
    );
  }

  private disposeProject(state: ProjectKeyIndex): void {
    state.disposed = true;
    state.abortController.abort();
    if (state.timer !== undefined) {
      clearTimeout(state.timer);
    }
    for (const subscription of state.subscriptions) {
      subscription.dispose();
    }
    state.files.clear();
    state.children.clear();
    state.pendingFiles.clear();
  }

  dispose(): void {
    this.boolDisposed = true;
    for (const state of this.mapProject.values()) {
      this.disposeProject(state);
    }
    this.mapProject.clear();
    for (const subscription of this.subscriptions) {
      subscription.dispose();
    }
  }
}
