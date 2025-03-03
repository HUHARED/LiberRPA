// FileName: commonFun.ts

import { DictResultToFlask } from "./interface";

export function getDownloadList(limit: number): Promise<DictResultToFlask> {
  console.log("--getDownloadList--");

  return new Promise((resolve, reject) => {
    chrome.downloads.search({ limit: limit, orderBy: ["-startTime"] }, (results) => {
      if (chrome.runtime.lastError) {
        reject(chrome.runtime.lastError.message);
        return;
      } else {
        // Process results to truncate long attributes
        const sanitizedResults = results.map((item) => {
          // Partial makes it a valid type without requiring all properties
          const sanitizedItem: Partial<chrome.downloads.DownloadItem> = {};

          (Object.keys(item) as Array<keyof chrome.downloads.DownloadItem>).forEach(
            (key) => {
              const value = item[key];

              // Ensure type compatibility before assignment
              if (typeof value === "string" && value.length > 1024) {
                sanitizedItem[key] =
                  "The value is too long (longer than 1024 characters), so not show it." as any;
              } else {
                sanitizedItem[key] = value as any; // Explicit type assertion
              }
            }
          );

          return sanitizedItem;
        });
        console.log("List of downloaded files(after filtering):", sanitizedResults);

        const result: DictResultToFlask = {
          boolSuccess: true,
          boolNeedResponse: true,
          data: sanitizedResults,
        };
        resolve(result);
        return;
      }
    });
  });
}
