// FileName: handleCommand.ts

/*
Browser.py / _Chrome.py
Python API Layer：Create dictCommand

_WebSocket.py
Python Client Layer：Send command to Local Server and wait the result

_ListenerSocketChrome.py
Local Server Layer：Add an id in command，transfer it to Chrome extension, then wait the result with id.

Chrome extension
socketFun.ts -> handleCommand.ts -> tabFunc.ts(backgound) / content

content: DOM/page manipulation -> return DictResultToFlask -> socketFun.ts sends "result_chrome_to_flask" -> Local Server -> Python Client

*/

import type {
  DictCommandFromFlask,
  DictCommandFromFlaskWithoutId,
  DictResultOriginal,
  DictResultToFlask,
} from "./interface";
import type { DictCommandContent } from "../content/interface";

import { getDownloadList } from "./commonFun";
import {
  getActiveCommonWebPageTabId,
  getState,
  goBackward,
  goForward,
  refresh,
  waitForLoad,
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
import { runWithFindingIcon } from "./icon";

export async function handleCommand(
  dictCommand: DictCommandFromFlask,
): Promise<DictResultToFlask> {
  console.log("--handleCommand--");

  const { ServerWaitId, ...dictCommandWithoutId } = dictCommand;

  try {
    const result: DictResultOriginal = await handleCommandCore(dictCommandWithoutId);

    // If the JSON stringify is fault, it must cause by the 'data' value.
    try {
      const strTemp = JSON.stringify(result, null, 2);
      console.log(`result = ${strTemp}`);
    } catch (e) {
      console.error(`Failed to stringify the result, convert data into string.`);
      result.data = String(result.data);
    }

    return {
      ServerWaitId,
      ...result,
    };
  } catch (e) {
    return {
      ServerWaitId,
      boolSuccess: false,
      data: `${e instanceof Error ? e.message : String(e)}`,
    };
  }
}

async function handleCommandCore(
  dictCommand: DictCommandFromFlaskWithoutId,
): Promise<DictResultOriginal> {
  console.log("--handleCommandCore--");

  switch (dictCommand.commandName) {
    // Some command that background can handle.
    case "getDownloadList":
      return await getDownloadList(dictCommand.limit);

    case "getState":
      return await getState();

    case "goBackward":
      return await goBackward();

    case "goForward":
      return await goForward();

    case "refresh":
      return await refresh();

    case "waitForLoad":
      return await waitForLoad(dictCommand.timeout);

    case "navigate":
      return await navigate(dictCommand.url, dictCommand.waitForLoad, dictCommand.timeout);

    case "openNewTab":
      return await openNewTab(
        dictCommand.url,
        dictCommand.waitForLoad,
        dictCommand.timeout,
      );

    case "openNewWindow":
      return await openNewWindow(
        dictCommand.url,
        dictCommand.waitForLoad,
        dictCommand.timeout,
      );

    case "switchTab":
      return await switchTab(dictCommand.titleOrIndex);

    case "closeCurrentTab":
      return await closeCurrentTab();

    case "getUrl":
      return await getUrl();

    case "getTitle":
      return await getTitle();

    case "getCookies":
      return await getCookies();

    case "setCookies":
      return await setCookies(
        dictCommand.domain,
        dictCommand.name,
        dictCommand.path,
        dictCommand.value,
        dictCommand.expirationDate,
        dictCommand.httpOnly,
        dictCommand.secure,
        dictCommand.storeId,
        dictCommand.sameSite,
      );

    // Send all other command to content.
    default:
      // The result is assigned in content.ts with the same format, so just use it.
      return await runWithFindingIcon(() => sendCommandToContent(dictCommand));
  }
}

// The interaction with content.ts
async function sendCommandToContent(
  dictCommand: DictCommandContent,
): Promise<DictResultOriginal> {
  const tabId = await getActiveCommonWebPageTabId();

  return new Promise<DictResultOriginal>((resolve) => {
    chrome.tabs.sendMessage(
      tabId,
      dictCommand,
      (response: DictResultOriginal | undefined) => {
        if (chrome.runtime.lastError) {
          resolve({
            boolSuccess: false,
            data: chrome.runtime.lastError.message ?? "Unknown Chrome runtime error.",
          });
          return;
        }
        if (response === undefined) {
          resolve({
            boolSuccess: false,
            data: "No response received from content script.",
          });
          return;
        }

        resolve(response);
      },
    );
  });
}
