// FileName: handleSnippets.ts
import { DictSnippetsItem, DictSnippetNodeInfo } from "./interface";
import { outputChannel } from "./output";
import * as vscode from "vscode";
import * as path from "path";
import * as fs from "fs";
import * as os from "os";
import * as jsoncParser from "jsonc-parser";

export function getSnippets(): {
  [key: string]: { [key: string]: DictSnippetNodeInfo };
} {
  // outputChannel.appendLine("--getSnippets--");
  return { ...getFavoriteSnippets(), ...getDefaultSnippets() };
}

function getFavoriteSnippets(): {
  [key: string]: { [key: string]: DictSnippetNodeInfo };
} {
  // outputChannel.appendLine("--getFavoriteSnippets--");
  const strFilePath = path.join(os.homedir(), "Documents/LiberRPA/snippets_favorite.jsonc");

  if (!fs.existsSync(strFilePath)) {
    outputChannel.appendLine(`${strFilePath} doesn't exist, create it.`);

    const strFileContent = fs.readFileSync(
      path.join(__dirname, "../assets/snippets_favorite_template.jsonc"),
      "utf-8"
    );
    fs.writeFileSync(strFilePath, strFileContent, { encoding: "utf-8" });
    // return {};
  }

  const strFileContent = fs.readFileSync(strFilePath, "utf-8");
  return generateTreeItemFromSnippets(strFileContent, true);
}

function addDynamicPart(fileContent: string): string {
  // Get .py files in ./Utils and ./Selector, add them in snippets text. Not including the subfolders.

  const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
  if (!workspaceFolder) {
    outputChannel.appendLine("No workspace folder is open.");
    return fileContent;
  }

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

  // Define target folders
  const utilsPath = path.join(workspaceFolder.uri.fsPath, "Utils");
  const selectorPath = path.join(workspaceFolder.uri.fsPath, "Selector");

  const utilsModules = getPythonModules(utilsPath);
  const selectorModules = getPythonModules(selectorPath);
  const modulesText = [
    ...utilsModules.map((mod) => `"from Utils.${mod} import *",`),
    ...selectorModules.map((mod) => `"from Selector.${mod} import *",`),
  ];

  const strAnchorText = 'Import all from liberrpa",';
  return fileContent.replace(strAnchorText, strAnchorText + modulesText.join(""));
}

function getDefaultSnippets(): {
  [key: string]: { [key: string]: DictSnippetNodeInfo };
} {
  // outputChannel.appendLine("--getDefaultSnippets--");
  const strFileContent = fs.readFileSync(
    path.join(__dirname, "../assets/snippets_final.snippets"),
    "utf-8"
  );
  // outputChannel.appendLine("strFileContent", strFileContent);

  return generateTreeItemFromSnippets(addDynamicPart(strFileContent), false);
}

function generateTreeItemFromSnippets(
  fileContent: string,
  isFavorite: boolean
): {
  [key: string]: { [key: string]: DictSnippetNodeInfo };
} {
  // outputChannel.appendLine("--generateTreeItemFromSnippets--");
  const dictTree: { [key: string]: { [key: string]: DictSnippetNodeInfo } } = {};
  try {
    // Replace \t in snippets to 4 space.(\t in description will also be replaced.)
    fileContent = fileContent.replace("\t", '"    ');
    const dictSnippets: {
      [key: string]: DictSnippetsItem;
    } = jsoncParser.parse(fileContent);

    for (const [strTitle, dictSnippet] of Object.entries(dictSnippets)) {
      // Split Category name and Snippet name if it is not favorite snippets.

      let strCategoryName: string;
      let strSnippetName: string;
      if (isFavorite) {
        strCategoryName = "Favorite";
        strSnippetName = strTitle;
      } else {
        const intDotIndex = strTitle.indexOf(".");
        strCategoryName =
          intDotIndex !== -1 ? strTitle.substring(0, intDotIndex) : strTitle;
        strSnippetName =
          intDotIndex !== -1
            ? strTitle.substring(intDotIndex + 1, strTitle.length)
            : strTitle;
      }

      if (!dictTree[strCategoryName]) {
        dictTree[strCategoryName] = {};
      }

      dictTree[strCategoryName][strSnippetName] = {
        body: dictSnippet.body,
        description:
          dictSnippet.description ??
          "There is no description. Maybe it's enough to see the name of the function?",
      };
    }

    return dictTree;
  } catch (e) {
    console.error("An error occured:", e);
    return {};
  }
}
