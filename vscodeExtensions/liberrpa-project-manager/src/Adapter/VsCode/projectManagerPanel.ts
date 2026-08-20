// FileName: projectManagerPanel.ts

import * as vscode from "vscode";
import * as fs from "node:fs";

import { log, showErrorMessageWithLogs } from "./output";
import { getErrorMessage } from "../../Common/utils";
import {
  type ProjectManagerOperation,
  type DictMessage_ExtensionToWebview,
  isMessage_WebviewToExtension,
} from "../Webview/projectManagerMessages";
import {
  type ProjectManagerSessionHost,
  ProjectManagerSession,
} from "../../Application/projectManagerSession";

export class ProjectManagerPanel implements ProjectManagerSessionHost {
  private static currentPanel: ProjectManagerPanel | undefined;

  private readonly panel: vscode.WebviewPanel;
  private disposed = false;
  private readonly disposables: vscode.Disposable[] = [];
  private readonly session: ProjectManagerSession;

  private constructor(
    private readonly context: vscode.ExtensionContext,
    operation: ProjectManagerOperation,
  ) {
    const webviewDistUri = vscode.Uri.joinPath(context.extensionUri, "webview-ui", "dist");

    this.panel = vscode.window.createWebviewPanel(
      "liberrpa-project-manager",
      "Project Manager - LiberRPA",
      vscode.ViewColumn.Active,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [webviewDistUri],
      },
    );
    this.session = new ProjectManagerSession(this, operation);

    try {
      this.panel.webview.html = this.getWebviewContent(this.panel.webview);
    } catch (e: unknown) {
      this.panel.dispose();
      throw e;
    }

    this.panel.onDidDispose(
      () => {
        this.disposeResources();
      },
      undefined,
      this.disposables,
    );

    this.panel.webview.onDidReceiveMessage(
      (value: unknown) => {
        if (!isMessage_WebviewToExtension(value)) {
          log.warn("Ignored invalid Project Manager Webview message.");
          return;
        }

        void this.session.handleMessage(value).catch(async (e: unknown) => {
          try {
            await this.session.sendError(e);
          } catch (sendError: unknown) {
            const strMessage =
              "Failed to send error to Project Manager Webview: " +
              getErrorMessage(sendError);
            log.error(strMessage);
            void showErrorMessageWithLogs(strMessage);
          }
        });
      },
      undefined,
      this.disposables,
    );

    vscode.window.onDidChangeActiveColorTheme(
      (theme) => {
        void this.session.handleThemeChanged(theme).catch((e: unknown) => {
          log.warn(`Failed to update Project Manager theme: ${getErrorMessage(e)}`);
        });
      },
      undefined,
      this.disposables,
    );
  }

  private getWebviewContent(webview: vscode.Webview): string {
    const indexHtmlUri = vscode.Uri.joinPath(
      this.context.extensionUri,
      "webview-ui",
      "dist",
      "index.html",
    );
    if (!fs.existsSync(indexHtmlUri.fsPath)) {
      throw new Error(
        "Project Manager Webview has not been built. Run npm run build in " +
          "webview-ui first.",
      );
    }

    let html = fs.readFileSync(indexHtmlUri.fsPath, { encoding: "utf-8" });
    const assetsUri = vscode.Uri.joinPath(
      this.context.extensionUri,
      "webview-ui",
      "dist",
      "assets",
    );
    const strWebviewAssetsUri = webview.asWebviewUri(assetsUri).toString();

    html = html.replaceAll('"/assets/', `"${strWebviewAssetsUri}/`);
    html = html.replaceAll("'/assets/", `'${strWebviewAssetsUri}/`);
    html = html.replaceAll('"./assets/', `"${strWebviewAssetsUri}/`);
    html = html.replaceAll("'./assets/", `'${strWebviewAssetsUri}/`);
    html = html.replace(/\scrossorigin\b/g, "");
    html = html.replaceAll("{{WEBVIEW_CSP_SOURCE}}", webview.cspSource);

    return html;
  }

  public async postMessage(message: DictMessage_ExtensionToWebview): Promise<void> {
    if (this.disposed) {
      return;
    }

    try {
      const boolMessagePosted = await this.panel.webview.postMessage(message);
      if (!boolMessagePosted && !this.disposed) {
        throw new Error("Project Manager Webview is not available.");
      }
    } catch (e: unknown) {
      if (this.disposed) {
        log.debug(
          `Skipped Project Manager Webview message after disposal: ${message.command}.`,
        );
        return;
      }
      throw e;
    }
  }

  public dispose(): void {
    if (this.disposed) {
      return;
    }
    this.disposed = true;
    this.panel.dispose();
  }

  private disposeResources(): void {
    this.disposed = true;

    if (ProjectManagerPanel.currentPanel === this) {
      ProjectManagerPanel.currentPanel = undefined;
    }

    while (this.disposables.length > 0) {
      this.disposables.pop()?.dispose();
    }
  }

  public static show(
    context: vscode.ExtensionContext,
    operation: ProjectManagerOperation,
  ): void {
    try {
      const currentPanel = ProjectManagerPanel.currentPanel;
      if (currentPanel === undefined) {
        ProjectManagerPanel.currentPanel = new ProjectManagerPanel(context, operation);
        return;
      }

      currentPanel.panel.reveal(vscode.ViewColumn.Active);
      if (currentPanel.session.currentOperation === operation) {
        return;
      }
      if (currentPanel.session.isBusy) {
        void vscode.window.showInformationMessage(
          "Project Manager cannot switch operations while the current operation is running.",
        );
        return;
      }

      void currentPanel.session.switchOperation(operation).catch(async (e: unknown) => {
        try {
          await currentPanel.session.sendError(e);
        } catch (sendError: unknown) {
          const strMessage =
            "Failed to send Project Manager error: " + getErrorMessage(sendError);
          log.error(strMessage);
          void showErrorMessageWithLogs(strMessage);
        }
      });
    } catch (e: unknown) {
      const strMessage = `Failed to open Project Manager: ${getErrorMessage(e)}`;
      log.error(strMessage);
      void showErrorMessageWithLogs(strMessage);
    }
  }
}
