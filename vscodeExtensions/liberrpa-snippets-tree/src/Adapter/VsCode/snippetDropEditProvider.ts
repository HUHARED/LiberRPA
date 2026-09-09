// FileName: snippetDropEditProvider.ts
import * as vscode from "vscode";

import { log } from "./output";
import { STR_SNIPPET_DRAG_MIME } from "./snippetTreeDataProvider";
import { buildManagedImportTextEdits } from "../../Application/SnippetInsertion/managedImports";
import {
  getSnippetTextForInsertion,
  hasNonWhitespaceTextBefore,
} from "../../Application/SnippetInsertion/snippetInsertionText";
import {
  planSnippetImportEdits,
  buildAdditionalWorkspaceEdit,
} from "../../Application/SnippetInsertion/snippetImportEdits";
import type { Info_SnippetRepository } from "../../Domain/Snippet/snippetTypes";

export class SnippetDropEditProvider implements vscode.DocumentDropEditProvider {
  constructor(
    private readonly repository: Info_SnippetRepository,
    private readonly finishTreeDrag: () => void,
  ) {}

  async provideDocumentDropEdits(
    document: vscode.TextDocument,
    position: vscode.Position,
    dataTransfer: vscode.DataTransfer,
  ): Promise<vscode.DocumentDropEdit | undefined> {
    if (document.languageId !== "python") {
      return undefined;
    }

    const transferItem = dataTransfer.get(STR_SNIPPET_DRAG_MIME);
    if (transferItem === undefined) {
      return undefined;
    }

    try {
      const snippetId = (await transferItem.asString()).trim();
      if (snippetId === "") {
        return undefined;
      }

      const draggedSnippet = this.repository.snippetById[snippetId];
      if (draggedSnippet === undefined) {
        return undefined;
      }

      const primaryRange = new vscode.Range(position, position);
      const snippetText = getSnippetTextForInsertion(
        draggedSnippet,
        hasNonWhitespaceTextBefore(document.lineAt(position.line).text, position.character),
      );
      const importEdits = buildManagedImportTextEdits(
        document,
        this.repository.importSource,
        draggedSnippet.imports,
      );
      const importPlan = planSnippetImportEdits(primaryRange, importEdits);

      if (importPlan === undefined) {
        return undefined;
      }

      const dropEdit = new vscode.DocumentDropEdit(
        new vscode.SnippetString(importPlan.snippetPrefix + snippetText.insertionText),
      );
      dropEdit.title = `Insert LiberRPA snippet: ${draggedSnippet.title}`;
      dropEdit.additionalEdit = buildAdditionalWorkspaceEdit(
        document,
        importPlan.additionalTextEdits,
      );

      log.debug(`[Drop] Prepared snippet: ${draggedSnippet.title}.`);
      return dropEdit;
    } finally {
      this.finishTreeDrag();
    }
  }
}
