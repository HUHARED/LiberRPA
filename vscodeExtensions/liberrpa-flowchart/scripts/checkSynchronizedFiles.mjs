// FileName: checkSynchronizedFiles.mjs

import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const rootFolderPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

const arrSynchronizedFilePair = [
  ["src/interface.ts", "webview-ui/src/interface.ts"],
  ["src/riskyPyModuleNames.ts", "webview-ui/src/riskyPyModuleNames.ts"],
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
