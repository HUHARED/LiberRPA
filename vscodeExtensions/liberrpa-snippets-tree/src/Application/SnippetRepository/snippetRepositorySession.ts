// FileName: snippetRepositorySession.ts

import * as vscode from "vscode";

import { log } from "../../Adapter/VsCode/output";
import { reportError, reportWarning } from "../../Adapter/VsCode/errorHandling";
import {
  createEmptySnippetRepository,
  replaceSnippetRepository,
} from "../../Domain/Snippet/snippetRepository";
import type { Info_SnippetRepository } from "../../Domain/Snippet/snippetTypes";
import { loadSnippetRepository } from "./loadSnippetRepository";

const INT_REPOSITORY_RELOAD_DELAY_MS = 300;
const INT_MAX_COMPONENT_RELOAD_RETRY = 2;

function getSingleWorkspaceFolder(): vscode.WorkspaceFolder | undefined {
  const workspaceFolderList = vscode.workspace.workspaceFolders;
  return workspaceFolderList?.length === 1 ? workspaceFolderList[0] : undefined;
}

export class SnippetRepositorySession implements vscode.Disposable {
  private componentWatcherDisposable: vscode.Disposable | undefined;
  private workspaceChangeDisposable: vscode.Disposable | undefined;
  private refreshCommandDisposable: vscode.Disposable | undefined;
  private reloadTimer: ReturnType<typeof setTimeout> | undefined;
  private loadedWorkspaceUri: string | undefined;
  private boolStarted = false;

  constructor(
    private readonly extensionPath: string,
    private readonly repository: Info_SnippetRepository,
    private readonly refreshFeatures: () => void,
  ) {}

  start(): void {
    if (this.boolStarted) {
      return;
    }
    this.boolStarted = true;

    this.loadInitialRepository();
    this.updateComponentWatcher();

    this.workspaceChangeDisposable = vscode.workspace.onDidChangeWorkspaceFolders(() => {
      this.updateComponentWatcher();
      this.scheduleRepositoryReload(0);
    });
    this.refreshCommandDisposable = vscode.commands.registerCommand(
      "LiberRPA.refreshSnippetRepository",
      (): void => {
        this.scheduleRepositoryReload(0);
      },
    );
  }

  private loadInitialRepository(): void {
    const workspaceFolder = getSingleWorkspaceFolder();
    const workspaceUri = workspaceFolder?.uri.toString();

    try {
      const nextRepository = loadSnippetRepository(
        this.extensionPath,
        workspaceFolder?.uri.fsPath,
        true,
      );
      this.applyRepository(nextRepository, workspaceUri);
    } catch (e) {
      const fallbackRepository = loadSnippetRepository(
        this.extensionPath,
        undefined,
        false,
      );
      this.applyRepository(fallbackRepository, workspaceUri);
      reportWarning("Component snippets were skipped", e, true);
    }
  }

  private applyRepository(
    nextRepository: Info_SnippetRepository,
    workspaceUri: string | undefined,
  ): void {
    replaceSnippetRepository(this.repository, nextRepository);
    this.refreshFeatures();
    this.loadedWorkspaceUri = workspaceUri;
    log.info("LiberRPA snippet repository reloaded.");
  }

  private scheduleRepositoryReload(intRetry: number): void {
    if (this.reloadTimer !== undefined) {
      clearTimeout(this.reloadTimer);
    }

    this.reloadTimer = setTimeout(() => {
      this.reloadTimer = undefined;
      this.reloadRepository(intRetry);
    }, INT_REPOSITORY_RELOAD_DELAY_MS);
  }

  private reloadRepository(intRetry: number): void {
    const workspaceFolder = getSingleWorkspaceFolder();
    const workspaceUri = workspaceFolder?.uri.toString();
    const boolWorkspaceChanged = workspaceUri !== this.loadedWorkspaceUri;

    try {
      const nextRepository = loadSnippetRepository(
        this.extensionPath,
        workspaceFolder?.uri.fsPath,
        false,
      );
      this.applyRepository(nextRepository, workspaceUri);
      return;
    } catch (e) {
      if (!boolWorkspaceChanged && intRetry < INT_MAX_COMPONENT_RELOAD_RETRY) {
        log.debug(
          `[Catalog] Component reload attempt ${intRetry + 1} failed; ` +
            "retrying after the replacement window.",
        );
        this.scheduleRepositoryReload(intRetry + 1);
        return;
      }

      try {
        const fallbackRepository = loadSnippetRepository(
          this.extensionPath,
          undefined,
          false,
        );
        this.applyRepository(fallbackRepository, workspaceUri);
        reportWarning(
          boolWorkspaceChanged
            ? "Component snippets for the new workspace were skipped"
            : "Component snippets were cleared after reload failed",
          e,
          true,
        );
      } catch (fallbackError) {
        replaceSnippetRepository(this.repository, createEmptySnippetRepository());
        this.refreshFeatures();
        this.loadedWorkspaceUri = workspaceUri;
        reportError("Failed to load the built-in Snippet repository", fallbackError, true);
      }
    }
  }

  private updateComponentWatcher(): void {
    this.componentWatcherDisposable?.dispose();
    this.componentWatcherDisposable = undefined;

    const workspaceFolder = getSingleWorkspaceFolder();
    if (!workspaceFolder) {
      return;
    }

    const watcher = vscode.workspace.createFileSystemWatcher(
      new vscode.RelativePattern(
        workspaceFolder,
        "_Components/*.dist-info/snippets_catalog.json",
      ),
    );
    const scheduleReload = (): void => {
      this.scheduleRepositoryReload(0);
    };

    this.componentWatcherDisposable = vscode.Disposable.from(
      watcher,
      watcher.onDidCreate(scheduleReload),
      watcher.onDidChange(scheduleReload),
      watcher.onDidDelete(scheduleReload),
    );
  }

  dispose(): void {
    this.componentWatcherDisposable?.dispose();
    this.workspaceChangeDisposable?.dispose();
    this.refreshCommandDisposable?.dispose();
    if (this.reloadTimer !== undefined) {
      clearTimeout(this.reloadTimer);
      this.reloadTimer = undefined;
    }
  }
}
