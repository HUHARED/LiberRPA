// FileName: tabFunc.ts

import { DictResultToFlask } from "./interface";

export async function getActiveTab(): Promise<chrome.tabs.Tab> {
  console.log("--getActiveTab--");

  const tabs = await chrome.tabs.query({
    active: true,
    lastFocusedWindow: true,
  });
  console.log("tabs", tabs);

  if (tabs.length === 0) {
    throw new Error(
      "Failed to locate the active tab, maybe it's a Chrome built-in page so LiberRPA extension has no permission?"
    );
  }
  return tabs[0];
}

export async function getActiveTabId(): Promise<number> {
  console.log("--getActiveTabId--");

  let tabId: number;

  // Confirmed there is an active tab and it has an ID
  const tab = await getActiveTab();

  if (!tab.id) {
    const fallbackTabs = await chrome.tabs.query({
      active: true,
    });
    console.log("fallbackTabs", fallbackTabs);
    if (fallbackTabs.length === 0 || !fallbackTabs[0].id) {
      throw new Error(
        "Failed to locate the active tab, maybe it's a Chrome built-in page so LiberRPA extension has no permission?"
      );
    } else {
      tabId = fallbackTabs[0].id;
    }
  } else {
    tabId = tab.id;
  }

  return tabId;
}

export async function getState(): Promise<DictResultToFlask> {
  console.log("--getState--");

  const tab = await getActiveTab();

  const result: DictResultToFlask = {
    boolSuccess: true,
    boolNeedResponse: true,
    data: tab.status as "unloaded" | "loading" | "complete" | undefined,
  };
  return result;
}

export async function goBackward(): Promise<DictResultToFlask> {
  console.log("--goBackward--");

  const tabId = await getActiveTabId();
  await chrome.tabs.goBack(tabId);

  const result: DictResultToFlask = {
    boolSuccess: true,
    boolNeedResponse: true,
    data: null,
  };
  return result;
}

export async function goForward(): Promise<DictResultToFlask> {
  console.log("--goForward--");

  const tabId = await getActiveTabId();
  await chrome.tabs.goForward(tabId);

  const result: DictResultToFlask = {
    boolSuccess: true,
    boolNeedResponse: true,
    data: null,
  };
  return result;
}

export async function refresh(): Promise<DictResultToFlask> {
  console.log("--refresh--");

  const tabId = await getActiveTabId();
  await chrome.tabs.reload(tabId);

  const result: DictResultToFlask = {
    boolSuccess: true,
    boolNeedResponse: true,
    data: null,
  };
  return result;
}

export async function waitLoadCompleted(
  timeout: number
): Promise<DictResultToFlask> {
  console.log("--waitLoadCompleted--");

  return new Promise<DictResultToFlask>((resolve, reject) => {
    let timeUsed = 0;
    const checkTabStatus = () => {
      getState().then((dictTemp) => {
        // If the tab status is 'complete', resolve the promise
        if (dictTemp.data === "complete") {
          console.log(`Tab has completed loading.`);
          const result: DictResultToFlask = {
            boolSuccess: true,
            boolNeedResponse: true,
            data: null,
          };
          resolve(result);
          return;
        } else {
          // Otherwise, check again after a delay
          console.log(`Tab is still loading. Checking again...`);
          timeUsed += 1000;
          if (timeUsed >= timeout) {
            reject(
              `The active tab doesn't load completed after ${timeout} milliseconds.`
            );
            return;
          }
          setTimeout(checkTabStatus, 1000);
        }
      });
    };

    // Start checking the tab's status
    checkTabStatus();
  });
}

export async function navigate(
  url: string,
  shouldWaitLoadCompleted: boolean,
  timeout: number
): Promise<DictResultToFlask> {
  console.log("--navigate--");

  const tabId = await getActiveTabId();
  await chrome.tabs.update(tabId, { url: url });

  if (shouldWaitLoadCompleted) {
    await waitLoadCompleted(timeout);
  }

  const result: DictResultToFlask = {
    boolSuccess: true,
    boolNeedResponse: true,
    data: null,
  };
  return result;
}

export async function openNewTab(
  url: string,
  shouldWaitLoadCompleted: boolean,
  timeout: number
): Promise<DictResultToFlask> {
  console.log("--openNewTab--");

  await chrome.tabs.create({ url: url });

  if (shouldWaitLoadCompleted) {
    await waitLoadCompleted(timeout);
  }

  const result: DictResultToFlask = {
    boolSuccess: true,
    boolNeedResponse: true,
    data: null,
  };
  return result;
}

export async function openNewWindow(
  url: string,
  shouldWaitLoadCompleted: boolean,
  timeout: number
): Promise<DictResultToFlask> {
  console.log("--openNewWindow--");

  chrome.windows.create({ url: url });

  if (shouldWaitLoadCompleted) {
    await waitLoadCompleted(timeout);
  }

  const result: DictResultToFlask = {
    boolSuccess: true,
    boolNeedResponse: true,
    data: null,
  };
  return result;
}

export async function switchTab(
  titleOrIndex: string | number
): Promise<DictResultToFlask> {
  console.log("--switchTab--");

  const tabs = await chrome.tabs.query({ currentWindow: true });

  if (typeof titleOrIndex === "number") {
    if (tabs.length <= titleOrIndex) {
      throw new Error(
        `The count of current tabs is ${
          tabs.length
        }, so the argument titleOrIndex should be an integer between 0 and ${
          tabs.length - 1
        }, instead of ${titleOrIndex}`
      );
    }
    const tabId = tabs[titleOrIndex].id;
    if (!tabId) {
      throw new Error(
        `Failed to locate the target tab (index = ${titleOrIndex}), maybe it's a Chrome built-in page so LiberRPA extension has no permission?`
      );
    }

    await chrome.tabs.update(tabId, { active: true });
  } else {
    const tabToSwitch = tabs.find((tab) => tab.title === titleOrIndex);
    if (!tabToSwitch || !tabToSwitch.id) {
      throw new Error(
        `Failed to locate the target tab (title=${titleOrIndex}), maybe it's a Chrome built-in page so LiberRPA extension has no permission?`
      );
    }
    await chrome.tabs.update(tabToSwitch.id, { active: true });
  }

  const result: DictResultToFlask = {
    boolSuccess: true,
    boolNeedResponse: true,
    data: null,
  };
  return result;
}

export async function closeCurrentTab(): Promise<DictResultToFlask> {
  console.log("--closeCurrentTab--");

  const tabId = await getActiveTabId();
  await chrome.tabs.remove(tabId);

  const result: DictResultToFlask = {
    boolSuccess: true,
    boolNeedResponse: true,
    data: null,
  };
  return result;
}

export async function getUrl(): Promise<DictResultToFlask> {
  console.log("--getUrl--");

  const tab = await getActiveTab();

  if (!tab.url) {
    throw new Error(
      `Failed to get the url, maybe it's a Chrome built-in page so LiberRPA extension has no permission?`
    );
  }

  const result: DictResultToFlask = {
    boolSuccess: true,
    boolNeedResponse: true,
    data: tab.url,
  };
  return result;
}

export async function getTitle(): Promise<DictResultToFlask> {
  console.log("--getTitle--");

  const tab = await getActiveTab();

  if (!tab.title) {
    throw new Error(
      `Failed to get the title, maybe it's a Chrome built-in page so LiberRPA extension has no permission?`
    );
  }

  const result: DictResultToFlask = {
    boolSuccess: true,
    boolNeedResponse: true,
    data: tab.title,
  };
  return result;
}

export async function getCookies(): Promise<DictResultToFlask> {
  console.log("--getCookies--");

  const tab = await getActiveTab();

  if (!tab.url) {
    throw new Error(
      `Failed to locate the target tab, maybe it's a Chrome built-in page so LiberRPA extension has no permission?`
    );
  }

  const url = new URL(tab.url);
  const domain = url.hostname;

  const cookies = await new Promise<chrome.cookies.Cookie[]>((resolve, reject) => {
    chrome.cookies.getAll({ domain: domain }, function (temp) {
      if (chrome.runtime.lastError) {
        reject(chrome.runtime.lastError);
        return;
      } else {
        resolve(temp);
        return;
      }
    });
  });

  const result: DictResultToFlask = {
    boolSuccess: true,
    boolNeedResponse: true,
    data: cookies,
  };
  return result;
}

export async function setCookies(
  domain: string,
  name: string,
  path: string,
  value: string | null,
  expirationDate: number | null,
  httpOnly: boolean | null,
  secure: boolean | null,
  storeId: string | null,
  sameSite: "no_restriction" | "lax" | "strict" | "unspecified" | null
): Promise<DictResultToFlask> {
  console.log("--setCookies--");

  const tab = await getActiveTab();

  if (!tab.url) {
    throw new Error(
      `Failed to locate the target tab, maybe it's a Chrome built-in page so LiberRPA extension has no permission?`
    );
  }

  const url = new URL(tab.url);
  const domainTemp = url.hostname;

  const arrCookiesOriginal = await new Promise<chrome.cookies.Cookie[]>(
    (resolve, reject) => {
      chrome.cookies.getAll({ domain: domainTemp }, function (temp) {
        if (chrome.runtime.lastError) {
          reject(chrome.runtime.lastError);
          return;
        } else {
          resolve(temp);
          return;
        }
      });
    }
  );

  console.log(arrCookiesOriginal);

  const cookiesOriginal = arrCookiesOriginal.find(
    (cookie) =>
      cookie.domain === domain && cookie.name === name && cookie.path === path
  );

  if (!cookiesOriginal) {
    throw new Error(
      `Not found a existing cookie to set, domain='${domain}' name='${name}' path='${path}'`
    );
  }

  const cookieDetails = {
    url: url.href,
    domain: domain,
    name: name,
    path: path,
    // Use !== null to make sure false and "" will not trigger the fallback.
    value: value !== null ? value : cookiesOriginal.value,
    expirationDate:
      expirationDate !== null ? expirationDate : cookiesOriginal.expirationDate,
    httpOnly: httpOnly !== null ? httpOnly : cookiesOriginal.httpOnly,
    secure: secure !== null ? secure : cookiesOriginal.secure,
    storeId: storeId !== null ? storeId : cookiesOriginal.storeId,
    sameSite: sameSite !== null ? sameSite : cookiesOriginal.sameSite,
  };

  // Set the cookie
  const newCookies = await chrome.cookies.set(cookieDetails);

  const result: DictResultToFlask = {
    boolSuccess: true,
    boolNeedResponse: true,
    data: newCookies,
  };
  return result;
}
