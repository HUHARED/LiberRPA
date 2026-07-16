// FileName: documentDropProvider.ts
import { log } from "./output";
import type { DictSnippetTotalInfo, DictSnippetRepository } from "./interface";
import { buildManagedImportTextEdits } from "./managedImports";
import { buildAdditionalWorkspaceEdit, planSnippetImportEdits } from "./snippetImportEdits";
import { STR_SNIPPET_DRAG_MIME } from "./treeViewProvider";

import * as vscode from "vscode";

export class DropEditProvider implements vscode.DocumentDropEditProvider {
  constructor(
    private readonly repository: DictSnippetRepository,
    private readonly finishTreeDrag: () => void
  ) {}

  async provideDocumentDropEdits(
    document: vscode.TextDocument,
    position: vscode.Position,
    dataTransfer: vscode.DataTransfer
  ): Promise<vscode.DocumentDropEdit | undefined> {
    if (document.languageId !== "python") {
      return undefined;
    }

    const transferItem = dataTransfer.get(STR_SNIPPET_DRAG_MIME);
    if (!transferItem) {
      return undefined;
    }

    try {
      const strSnippetId = (await transferItem.asString()).trim();
      if (!strSnippetId) {
        return undefined;
      }

      const draggedSnippet: DictSnippetTotalInfo | undefined = Object.values(
        this.repository.categories
      )
        .flat()
        .find((dictSnippet) => dictSnippet.id === strSnippetId);

      if (!draggedSnippet) {
        return undefined;
      }

      const primaryRange = new vscode.Range(position, position);
      const importEdits = buildManagedImportTextEdits(
        document,
        this.repository.importSources,
        draggedSnippet.imports
      );
      const importPlan = planSnippetImportEdits(primaryRange, importEdits);

      if (!importPlan) {
        return undefined;
      }

      const dropEdit = new vscode.DocumentDropEdit(
        new vscode.SnippetString(importPlan.snippetPrefix + draggedSnippet.body.join("\n"))
      );
      dropEdit.title = `Insert LiberRPA snippet: ${draggedSnippet.title}`;
      dropEdit.additionalEdit = buildAdditionalWorkspaceEdit(
        document,
        importPlan.additionalTextEdits
      );

      log.debug(`[Drop] Prepared snippet: ${draggedSnippet.title}.`);
      return dropEdit;
    } finally {
      this.finishTreeDrag();
    }
  }
}
