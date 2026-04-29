// FileName: icon.ts

type ExtensionIconState = "Normal" | "NoLink" | "Finding";

const ICONS: Record<ExtensionIconState, Record<string, string>> = {
  Normal: {
    "16": "/assets/LiberRPA_icon_v3_color_16px.png",
    "24": "/assets/LiberRPA_icon_v3_color_24px.png",
    "32": "/assets/LiberRPA_icon_v3_color_32px.png",
  },
  NoLink: {
    "16": "/assets/NoLink_16px.png",
    "24": "/assets/NoLink_24px.png",
    "32": "/assets/NoLink_32px.png",
  },
  Finding: {
    "16": "/assets/Finding_16px.png",
    "24": "/assets/Finding_24px.png",
    "32": "/assets/Finding_32px.png",
  },
};

const TITLES: Record<ExtensionIconState, string> = {
  Normal: "LiberRPA Chrome Extension",
  NoLink: "LiberRPA Local Server is not connected.",
  Finding: "LiberRPA is executing a content command.",
};

let boolSocketConnected = false;
let intRunningContentCount = 0;

const INT_FINDING_MIN_VISIBLE_MS = 150;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function getCurrentIconState(): ExtensionIconState {
  if (intRunningContentCount > 0) {
    return "Finding";
  }

  if (!boolSocketConnected) {
    return "NoLink";
  }

  return "Normal";
}

async function refreshExtensionIcon(): Promise<void> {
  const state = getCurrentIconState();

  await chrome.action.setIcon({ path: ICONS[state] });

  await chrome.action.setTitle({ title: TITLES[state] });
}

export async function setSocketConnected(connected: boolean): Promise<void> {
  boolSocketConnected = connected;
  await refreshExtensionIcon();
}

export async function runWithFindingIcon<T>(callback: () => Promise<T>): Promise<T> {
  intRunningContentCount += 1;
  const timeStart = Date.now();
  await refreshExtensionIcon();

  try {
    return await callback();
  } finally {
    const timeElapsed = Date.now() - timeStart;
    if (timeElapsed < INT_FINDING_MIN_VISIBLE_MS) {
      await sleep(INT_FINDING_MIN_VISIBLE_MS - timeElapsed);
    }

    intRunningContentCount = Math.max(0, intRunningContentCount - 1);
    await refreshExtensionIcon();
  }
}
