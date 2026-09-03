// FileName: snippetTabNavigation.ts

import * as vscode from "vscode";

import { runAsyncBoundary } from "./errorHandling";
import { log } from "./output";

const SNIPPET_TAB_COMMAND = "LiberRPA.snippetsTree.navigateSnippetTab";
const CLOSING_CHARACTER_BY_OPENING: Readonly<Record<string, string>> = {
  "(": ")",
  "[": "]",
  "{": "}",
  '"': '"',
  "'": "'",
};

type AutoClosingPair = {
  openingOffset: number;
  closingOffset: number;
  openingCharacter: string;
  closingCharacter: string;
  confirmed: boolean;
  createdVersion: number;
};

type CursorSnapshot = {
  version: number;
  offset: number;
};

/** Register forward Tab navigation for all Python snippets, regardless of their source. */
export function registerSnippetTabNavigation(): vscode.Disposable {
  return new SnippetTabNavigation();
}

class SnippetTabNavigation implements vscode.Disposable {
  private readonly arrDisposable: vscode.Disposable[];
  private editor: vscode.TextEditor | undefined;
  private cursorSnapshot: CursorSnapshot | undefined;
  private pendingSelectionVersion: number | undefined;
  private expectedNavigationCursor: CursorSnapshot | undefined;
  private arrPair: AutoClosingPair[] = [];

  constructor() {
    this.resetEditor(vscode.window.activeTextEditor);
    this.arrDisposable = [
      vscode.window.onDidChangeActiveTextEditor((editor): void => {
        this.resetEditor(editor);
      }),
      vscode.window.onDidChangeWindowState((state): void => {
        if (!state.focused) {
          this.resetEditor(undefined);
        } else {
          this.resetEditor(vscode.window.activeTextEditor);
        }
      }),
      vscode.window.onDidChangeTextEditorSelection((event): void => {
        this.handleSelectionChange(event);
      }),
      vscode.workspace.onDidChangeTextDocument((event): void => {
        this.handleDocumentChange(event);
      }),
      vscode.workspace.onDidCloseTextDocument((document): void => {
        if (document === this.editor?.document) {
          this.resetEditor(undefined);
        }
      }),
      vscode.commands.registerCommand(SNIPPET_TAB_COMMAND, async (): Promise<void> => {
        await runAsyncBoundary(
          "Failed to navigate Python snippet",
          async (): Promise<void> => {
            const editor = vscode.window.activeTextEditor;
            if (editor?.document.languageId !== "python") {
              return;
            }

            // The hidden command's keybinding supplies the native snippet/choice/suggest guards.
            if (this.tryMovePastClosingCharacter(editor)) {
              return;
            }

            this.clearTracking();
            log.trace("[SnippetTab] Next placeholder.");
            await vscode.commands.executeCommand("jumpToNextSnippetPlaceholder");
          },
          false,
        );
      }),
    ];
  }

  dispose(): void {
    for (const disposable of this.arrDisposable) {
      disposable.dispose();
    }
    this.resetEditor(undefined);
  }

  private resetEditor(editor: vscode.TextEditor | undefined): void {
    this.clearTracking();
    this.editor = editor?.document.languageId === "python" ? editor : undefined;
    this.captureCursor();
  }

  private clearTracking(): void {
    this.arrPair = [];
    this.pendingSelectionVersion = undefined;
    this.expectedNavigationCursor = undefined;
    this.cursorSnapshot = undefined;
  }

  private captureCursor(): void {
    const editor = this.editor;
    this.cursorSnapshot =
      editor && editor.selections.length === 1 && editor.selection.isEmpty
        ? {
            version: editor.document.version,
            offset: editor.document.offsetAt(editor.selection.active),
          }
        : undefined;
  }

  private handleDocumentChange(event: vscode.TextDocumentChangeEvent): void {
    const editor = this.editor;
    if (
      !editor ||
      event.document !== editor.document ||
      event.contentChanges.length === 0
    ) {
      return;
    }

    this.expectedNavigationCursor = undefined;
    this.cursorSnapshot = undefined;
    this.pendingSelectionVersion = event.document.version;

    if (
      vscode.window.activeTextEditor !== editor ||
      event.document.languageId !== "python" ||
      event.reason !== undefined ||
      event.contentChanges.length !== 1
    ) {
      // Undo/redo and compound edits must not leave stale pair locations.
      this.arrPair = [];
      return;
    }

    const change = event.contentChanges[0];
    const openingCharacter = change.text[0];
    const closingCharacter = change.text[1];
    const isPairInsertion =
      change.rangeLength === 0 &&
      change.text.length === 2 &&
      CLOSING_CHARACTER_BY_OPENING[openingCharacter] === closingCharacter;

    this.updatePairsForDocumentChange(change, isPairInsertion, event.document.version);

    if (isPairInsertion) {
      // Confirmation normally comes from the following keyboard selection event.
      // If another typed character arrives first, updatePairsForDocumentChange confirms the pair instead.
      this.arrPair.push({
        openingOffset: change.rangeOffset,
        closingOffset: change.rangeOffset + 1,
        openingCharacter,
        closingCharacter,
        confirmed: false,
        createdVersion: event.document.version,
      });
    }
  }

  private updatePairsForDocumentChange(
    change: vscode.TextDocumentContentChangeEvent,
    isPairInsertion: boolean,
    documentVersion: number,
  ): void {
    const editStart = change.rangeOffset;
    const editEnd = change.rangeOffset + change.rangeLength;
    const offsetDelta = change.text.length - change.rangeLength;
    const isSingleCharacterTyping =
      change.rangeLength === 0 && (isPairInsertion || /^[^\r\n\t]$/u.test(change.text));
    const arrUpdatedPair: AutoClosingPair[] = [];

    for (const pair of this.arrPair) {
      if (editEnd <= pair.openingOffset) {
        arrUpdatedPair.push({
          ...pair,
          openingOffset: pair.openingOffset + offsetDelta,
          closingOffset: pair.closingOffset + offsetDelta,
        });
        continue;
      }

      if (editStart > pair.closingOffset) {
        arrUpdatedPair.push(pair);
        continue;
      }

      if (pair.openingOffset < editStart && editEnd <= pair.closingOffset) {
        const confirmsPair =
          !pair.confirmed &&
          isSingleCharacterTyping &&
          change.rangeOffset === pair.closingOffset &&
          pair.createdVersion === documentVersion - 1;
        arrUpdatedPair.push({
          ...pair,
          closingOffset: pair.closingOffset + offsetDelta,
          confirmed: pair.confirmed || confirmsPair,
        });
      }
      // Edits that touch either delimiter invalidate only that pair.
    }

    this.arrPair = arrUpdatedPair;
  }

  private handleSelectionChange(event: vscode.TextEditorSelectionChangeEvent): void {
    const editor = this.editor;
    if (!editor || event.textEditor !== editor) {
      return;
    }
    if (
      vscode.window.activeTextEditor !== editor ||
      editor.document.languageId !== "python" ||
      event.selections.length !== 1 ||
      !event.selections[0].isEmpty
    ) {
      this.clearTracking();
      return;
    }

    const currentCursor: CursorSnapshot = {
      version: editor.document.version,
      offset: editor.document.offsetAt(event.selections[0].active),
    };
    const previousCursor = this.cursorSnapshot;
    const expectedNavigationCursor = this.expectedNavigationCursor;

    if (this.pendingSelectionVersion === currentCursor.version) {
      this.arrPair = this.arrPair
        .map((pair): AutoClosingPair => {
          const confirmed =
            pair.confirmed ||
            (event.kind === vscode.TextEditorSelectionChangeKind.Keyboard &&
              pair.createdVersion === currentCursor.version &&
              currentCursor.offset === pair.closingOffset);
          return confirmed === pair.confirmed ? pair : { ...pair, confirmed };
        })
        .filter((pair): boolean => {
          if (!pair.confirmed) {
            return (
              pair.createdVersion === currentCursor.version &&
              currentCursor.offset === pair.closingOffset
            );
          }
          return (
            pair.openingOffset < currentCursor.offset &&
            currentCursor.offset <= pair.closingOffset
          );
        });
      this.pendingSelectionVersion = undefined;
    } else if (expectedNavigationCursor) {
      if (
        currentCursor.version !== expectedNavigationCursor.version ||
        currentCursor.offset !== expectedNavigationCursor.offset ||
        event.kind === vscode.TextEditorSelectionChangeKind.Mouse
      ) {
        this.arrPair = [];
      } else {
        this.arrPair = this.arrPair.filter(
          (pair): boolean =>
            pair.openingOffset < currentCursor.offset &&
            currentCursor.offset <= pair.closingOffset,
        );
      }
      this.expectedNavigationCursor = undefined;
    } else if (
      previousCursor?.version === currentCursor.version &&
      event.kind === vscode.TextEditorSelectionChangeKind.Keyboard &&
      currentCursor.offset === previousCursor.offset + 1 &&
      this.arrPair.some((pair) => pair.closingOffset === previousCursor.offset)
    ) {
      // Typing an existing auto-closed character can move the caret without a document edit.
      this.arrPair = this.arrPair.filter(
        (pair): boolean =>
          pair.closingOffset !== previousCursor.offset &&
          pair.openingOffset < currentCursor.offset &&
          currentCursor.offset <= pair.closingOffset,
      );
    } else if (
      event.kind !== vscode.TextEditorSelectionChangeKind.Keyboard ||
      previousCursor?.version !== currentCursor.version ||
      previousCursor.offset !== currentCursor.offset
    ) {
      // Mouse moves, placeholder navigation and unrelated commands start a new editing run.
      this.arrPair = [];
    }

    this.cursorSnapshot = currentCursor;
  }

  private tryMovePastClosingCharacter(editor: vscode.TextEditor): boolean {
    if (
      editor !== this.editor ||
      editor.selections.length !== 1 ||
      !editor.selection.isEmpty
    ) {
      return false;
    }

    const cursorOffset = editor.document.offsetAt(editor.selection.active);
    const pair = this.arrPair.find(
      (candidate): boolean =>
        candidate.confirmed && candidate.closingOffset === cursorOffset,
    );
    if (!pair || !this.isPairUnchanged(editor.document, pair)) {
      return false;
    }

    const nextOffset = pair.closingOffset + 1;
    const nextPosition = editor.document.positionAt(nextOffset);
    this.arrPair = this.arrPair.filter((candidate) => candidate !== pair);
    this.pendingSelectionVersion = undefined;
    this.expectedNavigationCursor = {
      version: editor.document.version,
      offset: nextOffset,
    };
    this.cursorSnapshot = this.expectedNavigationCursor;

    // Move this editor's caret, not its text. No synthetic typing, undo, or placeholder reconstruction.
    editor.selection = new vscode.Selection(nextPosition, nextPosition);
    log.trace(`[SnippetTab] Skip auto-closed ${JSON.stringify(pair.closingCharacter)}.`);
    return true;
  }

  private isPairUnchanged(document: vscode.TextDocument, pair: AutoClosingPair): boolean {
    const openingPosition = document.positionAt(pair.openingOffset);
    const closingPosition = document.positionAt(pair.closingOffset);
    if (
      document.getText(
        new vscode.Range(openingPosition, openingPosition.translate(0, 1)),
      ) !== pair.openingCharacter ||
      document.getText(
        new vscode.Range(closingPosition, closingPosition.translate(0, 1)),
      ) !== pair.closingCharacter
    ) {
      return false;
    }

    if (pair.closingCharacter === '"' || pair.closingCharacter === "'") {
      const linePrefix = document
        .lineAt(closingPosition.line)
        .text.slice(0, closingPosition.character);
      const backslashCount = /\\*$/.exec(linePrefix)?.[0].length ?? 0;
      if (backslashCount % 2 !== 0) {
        return false;
      }
    }
    return true;
  }
}
