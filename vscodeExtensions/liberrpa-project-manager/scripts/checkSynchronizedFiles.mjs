// FileName: checkSynchronizedFiles.mjs

import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const rootFolderPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

const arrSynchronizedFilePair = [
  ["src/Common/typeCheck.ts", "webview-ui/src/Common/typeCheck.ts"],
  ["src/Domain/Project/projectTypes.ts", "webview-ui/src/Domain/Project/projectTypes.ts"],
  [
    "src/Domain/Project/projectValidation.ts",
    "webview-ui/src/Domain/Project/projectValidation.ts",
  ],
  [
    "src/Domain/Project/riskyComponentPackageNames.ts",
    "webview-ui/src/Domain/Project/riskyComponentPackageNames.ts",
  ],
  [
    "src/Domain/ComponentManagement/componentManagementTypes.ts",
    "src/Domain/ComponentManagement/componentManagementTypes.ts",
  ],
  [
    "src/Adapter/Webview/projectManagerMessages.ts",
    "webview-ui/src/Adapter/Extension/projectManagerMessages.ts",
  ],
];

function normalizeText(value) {
  return value.replaceAll("\r\n", "\n");
}

const arrMismatch = [];
for (const [extensionRelativePath, webviewRelativePath] of arrSynchronizedFilePair) {
  const [extensionText, webviewText] = await Promise.all([
    readFile(path.join(rootFolderPath, extensionRelativePath), "utf-8"),
    readFile(path.join(rootFolderPath, webviewRelativePath), "utf-8"),
  ]);

  if (normalizeText(extensionText) !== normalizeText(webviewText)) {
    arrMismatch.push(`${extensionRelativePath} != ${webviewRelativePath}`);
  }
}

if (arrMismatch.length > 0) {
  throw new Error(
    "Synchronized Extension/Webview files differ:\n" + arrMismatch.join("\n"),
  );
}

console.log("Synchronized Extension/Webview files match.");
