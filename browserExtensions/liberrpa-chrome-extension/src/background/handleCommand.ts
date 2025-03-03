// FileName: handleCommand.ts

import { DictResultToFlask } from "./interface";
import { getDownloadList } from "./commonFun";
import {
  getActiveTabId,
  getState,
  goBackward,
  goForward,
  refresh,
  waitLoadCompleted,
  navigate,
  openNewTab,
  openNewWindow,
  switchTab,
  closeCurrentTab,
  getUrl,
  getTitle,
  getCookies,
  setCookies,
} from "./tabFunc";

export async function handleCommand(dictCommand: {
  [key: string]: any;
}): Promise<DictResultToFlask> {
  console.log("--handleCommand--");

  let result: DictResultToFlask;

  try {
    switch (dictCommand.commandName as string) {
      case "confirmConnection":
        console.log("Confirm connection from server.");
        result = {
          boolSuccess: true,
          boolNeedResponse: false,
          data: null,
        };
        break;

      // Some command that background can handle.
      case "getDownloadList":
        try {
          result = await getDownloadList(dictCommand.limit);
        } catch (e) {
          result = handleCatch(e as Error);
        }
        break;

      case "getState":
        try {
          result = await getState();
        } catch (e) {
          result = handleCatch(e as Error);
        }
        break;

      case "goBackward":
        try {
          result = await goBackward();
        } catch (e) {
          result = handleCatch(e as Error);
        }
        break;

      case "goForward":
        try {
          result = await goForward();
        } catch (e) {
          result = handleCatch(e as Error);
        }
        break;

      case "refresh":
        try {
          result = await refresh();
        } catch (e) {
          result = handleCatch(e as Error);
        }
        break;

      case "waitLoadCompleted":
        try {
          result = await waitLoadCompleted(dictCommand.timeout);
        } catch (e) {
          result = handleCatch(e as Error);
        }
        break;

      case "navigate":
        try {
          result = await navigate(
            dictCommand.url,
            dictCommand.waitLoadCompleted,
            dictCommand.timeout
          );
        } catch (e) {
          result = handleCatch(e as Error);
        }
        break;

      case "openNewTab":
        try {
          result = await openNewTab(
            dictCommand.url,
            dictCommand.waitLoadCompleted,
            dictCommand.timeout
          );
        } catch (e) {
          result = handleCatch(e as Error);
        }
        break;

      case "openNewWindow":
        try {
          result = await openNewWindow(
            dictCommand.url,
            dictCommand.waitLoadCompleted,
            dictCommand.timeout
          );
        } catch (e) {
          result = handleCatch(e as Error);
        }
        break;

      case "switchTab":
        try {
          result = await switchTab(dictCommand.titleOrIndex);
        } catch (e) {
          result = handleCatch(e as Error);
        }
        break;

      case "closeCurrentTab":
        try {
          result = await closeCurrentTab();
        } catch (e) {
          result = handleCatch(e as Error);
        }
        break;

      case "getUrl":
        try {
          result = await getUrl();
        } catch (e) {
          result = handleCatch(e as Error);
        }
        break;

      case "getTitle":
        try {
          result = await getTitle();
        } catch (e) {
          result = handleCatch(e as Error);
        }
        break;

      case "getCookies":
        try {
          result = await getCookies();
        } catch (e) {
          result = handleCatch(e as Error);
        }
        break;

      case "setCookies":
        try {
          result = await setCookies(
            dictCommand.domain,
            dictCommand.name,
            dictCommand.path,
            dictCommand.value,
            dictCommand.expirationDate,
            dictCommand.httpOnly,
            dictCommand.secure,
            dictCommand.storeId,
            dictCommand.sameSite
          );
        } catch (e) {
          result = handleCatch(e as Error);
        }
        break;

      // Send all other command to content.
      default:
        // The result is assigned in content.ts with the same format, so just use it.
        result = await sendCommandToContent(dictCommand);

        break;
    }
  } catch (e) {
    // The catch clause handles non-default case of the swtich, due to the default case has try-catch inside.
    result = {
      boolSuccess: false,
      boolNeedResponse: true,
      data: `${(e as Error).message}`,
    };
  }

  // Add id. for return the result to the corresponding Python process.
  if (dictCommand.id) {
    result = { id: dictCommand.id, ...result };
  }

  // If the JSON stringify is fault, it must cause by the 'data' value.
  try {
    const strTemp = JSON.stringify(result, null, 2);
    console.log(`result = ${strTemp}`);
  } catch (e) {
    console.error(
      `Failed to stringify the object: ${result}, convert data into string.`
    );
    result.data = String(result.data);
  }

  return result;
}

// The interaction with content.ts
async function sendCommandToContent(dictCommand: {
  [key: string]: any;
}): Promise<DictResultToFlask> {
  // Define the error result in case of failure.
  const resultError: DictResultToFlask = {
    boolSuccess: false,
    boolNeedResponse: true,
    data: undefined,
  };

  try {
    const tabs = await chrome.tabs.query({
      active: true,
      lastFocusedWindow: true,
    });
    console.log("tabs", tabs);

    const tabId = await getActiveTabId();

    return new Promise((resolve, _) => {
      chrome.tabs.sendMessage(tabId, dictCommand, (response: DictResultToFlask) => {
        if (chrome.runtime.lastError) {
          resultError.data = chrome.runtime.lastError.message;
          resolve(resultError);
          return;
        } else {
          resolve(response);
          return;
        }
      });
    });
  } catch (e) {
    resultError.data = `Error sending command to Chrome content script: ${
      (e as Error).message
    }`;
    return resultError;
  }
}

function handleCatch(e: Error): DictResultToFlask {
  const result: DictResultToFlask = {
    boolSuccess: false,
    boolNeedResponse: true,
    data: `${e instanceof Error ? e.message : e}`,
  };
  return result;
}
