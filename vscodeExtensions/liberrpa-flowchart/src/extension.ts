// FileName: extension.ts
import * as vscode from "vscode";
import * as path from "path";
import * as fs from "fs";

const outputChannel = vscode.window.createOutputChannel("liberrpa-flowchart");
outputChannel.show(true);

export function activate(context: vscode.ExtensionContext) {
  outputChannel.appendLine('"liberrpa-flowchart" is now active.');

  context.subscriptions.push(FlowchartEditorProvider.register(context));

  const provider = vscode.languages.registerCompletionItemProvider(
    { language: "python" },
    {
      provideCompletionItems(document: vscode.TextDocument, position: vscode.Position) {
        const linePrefix = document.lineAt(position).text.substring(0, position.character);

        // outputChannel.appendLine(`linePrefix: "${linePrefix}"`);
        let intOffset: number = 0;

        // Show suggestions if the line ends with CustomArgs, CustomArgs[ or CustomArgs["
        if (linePrefix.endsWith("CustomArgs")) {
          intOffset = 0;
        } else if (linePrefix.endsWith("CustomArgs[")) {
          intOffset = 1;
        } else if (linePrefix.endsWith('CustomArgs["')) {
          intOffset = 2;
        } else if (linePrefix.endsWith("CustomArgs['")) {
          intOffset = 2;
        } else {
          // outputChannel.appendLine(`${linePrefix}`);
          return undefined;
        }

        // outputChannel.appendLine(`Go on: ${linePrefix}`);

        const customArgNames = getCustomArgNames();
        if (!customArgNames || customArgNames.length === 0) {
          // outputChannel.appendLine(`!customArgNames || customArgNames.length === 0`);
          return undefined;
        }

        // Build completion items
        const completionItems: vscode.CompletionItem[] = [];
        for (const argName of customArgNames) {
          let strSnippets: string = "";
          if (intOffset === 0) {
            strSnippets = `["${argName}"]`;
          } else if (intOffset === 1) {
            strSnippets = `"${argName}"`;
          } else if (intOffset === 2) {
            strSnippets = `${argName}`;
          }
          const item = new vscode.CompletionItem(
            strSnippets,
            vscode.CompletionItemKind.Snippet
          );
          item.insertText = strSnippets;
          item.range = new vscode.Range(position, position);
          // outputChannel.appendLine(`item: ["${argName}"]`);

          completionItems.push(item);
        }

        return completionItems;
      },
    },
    "[",
    '"',
    "'"
  );

  // outputChannel.appendLine("push CompletionItemProvider.");

  context.subscriptions.push(provider);
}

export function deactivate() {
  outputChannel.appendLine('"liberrpa-flowchart" is now deactivated.');
}

class FlowchartEditorProvider implements vscode.CustomTextEditorProvider {
  constructor(private readonly context: vscode.ExtensionContext) {}

  // Register the custom editor for `.flow` files
  public static register(context: vscode.ExtensionContext): vscode.Disposable {
    const providerRegistration = vscode.window.registerCustomEditorProvider(
      "liberrpa-flowchart.editor",
      new FlowchartEditorProvider(context),
      {
        webviewOptions: {
          retainContextWhenHidden: true,
        },
      }
    );
    return providerRegistration;
  }

  // Called when the custom editor is opened.
  public async resolveCustomTextEditor(
    document: vscode.TextDocument,
    webviewPanel: vscode.WebviewPanel,
    _token: vscode.CancellationToken
  ): Promise<void> {
    webviewPanel.webview.options = {
      enableScripts: true,
    };

    webviewPanel.webview.html = this.getWebviewContent(webviewPanel.webview);

    // Receive message from webview.
    webviewPanel.webview.onDidReceiveMessage((message) => {
      const workspaceFolder = vscode.workspace.workspaceFolders?.[0];

      switch (message.command) {
        case "update":
          this.updateDocument(document, message.data);
          break;

        case "open": {
          outputChannel.appendLine(`Open ${message.path}`);

          if (!workspaceFolder) {
            vscode.window.showErrorMessage("No workspace folder is open.");
            break;
          }

          const strFilePath = vscode.Uri.joinPath(workspaceFolder.uri, message.path);
          const strFileSystemPath = strFilePath.fsPath;

          // If the path doesn't exist, create it and write the default script.
          if (
            !fs.existsSync(strFileSystemPath) ||
            !fs.statSync(strFileSystemPath).isFile()
          ) {
            const strFolderPath = path.dirname(strFileSystemPath);
            if (!fs.existsSync(strFolderPath)) {
              fs.mkdirSync(strFolderPath, { recursive: true });
            }

            // Follow liberrpa-snippets-tree, add modules in Utils and selector.
            function getPythonModules(folderPath: string): string[] {
              if (!fs.existsSync(folderPath)) {
                return [];
              }

              return (
                fs
                  .readdirSync(folderPath)
                  .filter((file) => file.endsWith(".py"))
                  // Remove .py extension
                  .map((file) => path.parse(file).name)
              );
            }

            const utilsPath = path.join(workspaceFolder.uri.fsPath, "Utils");
            const selectorPath = path.join(workspaceFolder.uri.fsPath, "Selector");

            const utilsModules = getPythonModules(utilsPath);
            const selectorModules = getPythonModules(selectorPath);
            const modulesText = [
              ...utilsModules.map((mod) => `from Utils.${mod} import *\n`),
              ...selectorModules.map((mod) => `from Selector.${mod} import *\n`),
            ];

            const strNewPython = `# FileName: ${path.basename(strFileSystemPath)}
from liberrpa.Modules import *  # type: ignore - Import all from liberrpa
${modulesText.join("")}

def main() -> None:
    raise NotImplementedError()


if __name__ == "__main__":
    main()
`;

            fs.writeFileSync(strFileSystemPath, strNewPython, { encoding: "utf-8" });
          }

          vscode.workspace.openTextDocument(strFilePath).then(
            (document) => {
              // Open it in a new tab.
              vscode.window.showTextDocument(document, {
                viewColumn: vscode.ViewColumn.Active,
                preview: false,
                preserveFocus: false,
              });
            },
            (error) => {
              vscode.window.showErrorMessage(
                `Could not open or create file: ${strFilePath.fsPath}`
              );
              console.error(error);
            }
          );

          break;
        }

        case "execute": {
          outputChannel.appendLine(
            `Execute ${message.data.pyFile} in ${message.data.executeMode} mode.`
          );
          if (!workspaceFolder) {
            vscode.window.showErrorMessage("No workspace folder is open.");
            break;
          }

          // Ensure the file exists
          const strFilePath = vscode.Uri.joinPath(workspaceFolder.uri, message.data.pyFile);
          const strFileSystemPath = strFilePath.fsPath;
          if (
            !fs.existsSync(strFileSystemPath) ||
            !fs.statSync(strFileSystemPath).isFile()
          ) {
            vscode.window.showErrorMessage(
              `File does not exist: ${strFileSystemPath}, you should create it manually or click "open" button in Block to create it.`
            );
            break;
          }

          // Save files before running.
          vscode.workspace.saveAll().then(() => {
            // Run or debug it.
            const config = {
              type: "debugpy",
              request: "launch",
              name: "Python Debugger: block file",
              program: strFileSystemPath,
              console: "integratedTerminal",
              cwd: workspaceFolder.uri.fsPath,
              env: {
                PYTHONPATH: "${workspaceFolder}",
              },
            };
            if (message.data.executeMode === "Run") {
              vscode.debug.startDebugging(workspaceFolder, config, { noDebug: true });
            } else {
              vscode.debug.startDebugging(workspaceFolder, config, { noDebug: false });
            }
          });

          break;
        }

        case "executeProject":
          outputChannel.appendLine(`Execute Project in ${message.data.executeMode} mode.`);
          if (!workspaceFolder) {
            vscode.window.showErrorMessage("No workspace folder is open.");
            break;
          }

          // Save files before running.
          vscode.workspace.saveAll().then(() => {
            const strLiberRPAEnvPath = process.env.LiberRPA;
            if (!strLiberRPAEnvPath) {
              throw new Error("Not found 'LiberRPA' in User Envirnment Variables.");
            }

            const strProgramTemp = path.join(
              strLiberRPAEnvPath,
              "envs/pyenv/Lib/site-packages/liberrpa/FlowControl/Run.py"
            );

            if (!strProgramTemp) {
              throw new Error("The Python module 'liberrpa' didn't install correctly.");
            }

            // Run or debug it.
            const config = {
              type: "debugpy",
              request: "launch",
              name: "Python Debugger: project",
              program: strProgramTemp,
              console: "integratedTerminal",
              cwd: workspaceFolder.uri.fsPath,
              env: {
                PYTHONPATH: "${workspaceFolder}",
              },
            };
            if (message.data.executeMode === "Run") {
              vscode.debug.startDebugging(workspaceFolder, config, { noDebug: true });
            } else {
              vscode.debug.startDebugging(workspaceFolder, config, { noDebug: false });
            }
          });

          break;

        default:
          break;
      }
    });

    this.loadWebviewData(document, webviewPanel.webview);

    // Update webview when text changed.
    // (It is useless now, always webview changed then update text.)
    /* const changeDocumentsSubscription = vscode.workspace.onDidChangeTextDocument(
      (event) => {
        if (event.document.uri.toString() === document.uri.toString()) {
          this.loadWebviewData(document, webviewPanel.webview);
        }
      }
    ); */

    webviewPanel.onDidDispose(() => {
      // changeDocumentsSubscription.dispose();
    });
  }

  // Get the static html used for the editor webviews.
  private getWebviewContent(webview: vscode.Webview): string {
    // Path to the dist folder
    const distPath = vscode.Uri.file(
      path.join(this.context.extensionPath, "webview-ui", "dist")
    );

    // Convert the dist folder to a webview URI
    const baseUri = webview.asWebviewUri(distPath);

    // Read the built index.html file from the dist folder
    const indexPath = path.join(distPath.fsPath, "index.html");
    let html = fs.readFileSync(indexPath, "utf8");

    // Update the paths in the HTML to use the webview URIs for assets
    html = html.replace(/(href|src)="([^"]*)"/g, (_, tag, src) => {
      if (src.startsWith("http") || src.startsWith("//")) {
        return `${tag}="${src}"`;
      }
      return `${tag}="${baseUri}/${src.replace(/^\//, "")}"`;
    });

    // Remove crossorigin attributes
    html = html.replace(/\scrossorigin/g, "");

    // Dynamically rewrite font URLs in the CSS file
    const cssPath = path.join(distPath.fsPath, "assets", "index.css");
    let cssContent = fs.readFileSync(cssPath, "utf8");

    cssContent = cssContent.replace(
      /url\(["']?(\/?assets\/.*?\.(woff2?|woff|ttf|eot)(\?.*?)?)["']?\)/g,
      (_, src) => {
        return `url(${baseUri}/${src.replace(/^\//, "")})`;
      }
    );

    // Inject the modified CSS directly into the HTML
    html = html.replace(
      /<link rel="stylesheet" href="[^"]*">/,
      `<style>${cssContent}</style>`
    );

    // outputChannel.appendLine("html", html);

    return html;
  }

  // Send the file content to webview.
  private loadWebviewData(document: vscode.TextDocument, webview: vscode.Webview): void {
    const strDocumentContent = document.getText();
    // Init color theme of flowchart. "Light" for Light and HighContrast.
    const dictData = {
      ...JSON.parse(strDocumentContent),
      ...{
        theme:
          vscode.ColorThemeKind[vscode.window.activeColorTheme.kind] === "Dark"
            ? "dark"
            : "light",
      },
    };
    webview.postMessage({ command: "load", data: dictData });
  }

  // Write out the json to a given document.
  private updateDocument(document: vscode.TextDocument, data: string): void {
    const edit = new vscode.WorkspaceEdit();
    // Replace the entire document every time.
    edit.replace(document.uri, new vscode.Range(0, 0, document.lineCount, 0), data);
    // update it in editor but not automatically saved to disk.
    vscode.workspace.applyEdit(edit);
  }
}

function getCustomArgNames(): string[] {
  // outputChannel.appendLine("--getCustomArgNames--");

  const workspaceFolder = vscode.workspace.workspaceFolders?.[0];

  if (!workspaceFolder) {
    return [];
  }

  const projectFlowPath = path.join(workspaceFolder.uri.fsPath, "project.flow");

  // Try to get the open "project.flow" document
  const openDocument = vscode.workspace.textDocuments.find(
    (doc) => doc.uri.fsPath === projectFlowPath
  );

  let content: string | undefined;

  if (openDocument) {
    // Read the latest unsaved content from the open document
    content = openDocument.getText();
    // outputChannel.appendLine("Using unsaved project.flow content.");
  } else {
    // Fallback: read from disk if the file is not open in the editor

    if (!fs.existsSync(projectFlowPath)) {
      // outputChannel.appendLine("Not found project.flow.");
      return [];
    }

    try {
      content = fs.readFileSync(projectFlowPath, "utf-8");
      // outputChannel.appendLine("Using saved project.flow content from disk.");
    } catch (e) {
      outputChannel.appendLine(`Error reading project.flow: ${e}`);
      return [];
    }
  }

  // Parse JSON and extract customPrjArgs
  try {
    const jsonData = JSON.parse(content);

    if (Array.isArray(jsonData.customPrjArgs)) {
      const result: string[] = jsonData.customPrjArgs.map((item: string[]) => item[0]);
      // outputChannel.appendLine("customPrjArgs result" + result);

      return result;
    }
  } catch (e) {
    outputChannel.appendLine(`parsing project.flow JSON: ${e}`);
  }

  return [];
}
