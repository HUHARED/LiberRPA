// FileName: snippetImportEdits.ts
import * as vscode from "vscode";

export interface SnippetImportEditPlan {
  /** Text prepended to the primary snippet edit when a separate import edit would overlap it. */
  snippetPrefix: string;
  additionalTextEdits: vscode.TextEdit[];
}

function rangeContainsPosition(range: vscode.Range, position: vscode.Position): boolean {
  return !position.isBefore(range.start) && !position.isAfter(range.end);
}

function rangesOverlap(left: vscode.Range, right: vscode.Range): boolean {
  if (left.isEmpty) {
    return rangeContainsPosition(right, left.start);
  }
  if (right.isEmpty) {
    return rangeContainsPosition(left, right.start);
  }

  return left.start.isBefore(right.end) && right.start.isBefore(left.end);
}

/**
 * Prepare managed-import edits for a CompletionItem or DocumentDropEdit.
 *
 * VS Code rejects additional edits that overlap the primary snippet edit.
 * In an empty file both edits normally start at (0, 0), so the import block is prepended to the SnippetString instead.
 * Other overlap means the user is editing inside the managed block; no safe automatic edit is produced.
 */
export function planSnippetImportEdits(
  primaryRange: vscode.Range,
  importEdits: vscode.TextEdit[]
): SnippetImportEditPlan | undefined {
  if (importEdits.length === 0) {
    return { snippetPrefix: "", additionalTextEdits: [] };
  }

  if (
    importEdits.length === 1 &&
    importEdits[0].range.isEmpty &&
    importEdits[0].range.start.isEqual(primaryRange.start)
  ) {
    return {
      snippetPrefix: importEdits[0].newText,
      additionalTextEdits: [],
    };
  }

  if (importEdits.some((edit) => rangesOverlap(primaryRange, edit.range))) {
    return undefined;
  }

  return { snippetPrefix: "", additionalTextEdits: importEdits };
}

export function buildAdditionalWorkspaceEdit(
  document: vscode.TextDocument,
  edits: vscode.TextEdit[]
): vscode.WorkspaceEdit | undefined {
  if (edits.length === 0) {
    return undefined;
  }

  const workspaceEdit = new vscode.WorkspaceEdit();
  workspaceEdit.set(document.uri, edits);
  return workspaceEdit;
}
