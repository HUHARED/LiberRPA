// FileName: commonFun.ts

import type { DictResultOriginal } from "./interface";
const INT_MAX_DISPLAY_STRING_LENGTH = 1024;
const STR_LONG_VALUE_PLACEHOLDER =
  "The value is too long (longer than 1024 characters), so it is hidden.";

type DictSanitizedDownloadItem = Record<string, unknown>;

function sanitizedDownloadItem(
  item: chrome.downloads.DownloadItem
): DictSanitizedDownloadItem {
  // Process results to truncate long attributes. The default incoming message size is 1,000,000 bytes. I didn't modify the size to avoid pingTimeout.

  const dictSanitizedItem: DictSanitizedDownloadItem = {};

  const arrKeys = Object.keys(item) as (keyof chrome.downloads.DownloadItem)[];
  for (const key of arrKeys) {
    const value = item[key];
    // Ensure type compatibility before assignment
    if (typeof value === "string" && value.length > INT_MAX_DISPLAY_STRING_LENGTH) {
      dictSanitizedItem[key] = STR_LONG_VALUE_PLACEHOLDER;
    } else {
      dictSanitizedItem[key] = value;
    }
  }
  return dictSanitizedItem;
}

export function getDownloadList(limit: number): Promise<DictResultOriginal> {
  console.log("--getDownloadList--");

  return new Promise((resolve, reject) => {
    chrome.downloads.search({ limit: limit, orderBy: ["-startTime"] }, (results) => {
      if (chrome.runtime.lastError) {
        reject(
          new Error(chrome.runtime.lastError.message ?? "Unknown Chrome runtime error.")
        );
        return;
      } else {
        const sanitizedResults = results.map((item) => sanitizedDownloadItem(item));

        console.log("List of downloaded files(after filtering):", sanitizedResults);

        resolve({
          boolSuccess: true,
          data: sanitizedResults,
        });
        return;
      }
    });
  });
}
