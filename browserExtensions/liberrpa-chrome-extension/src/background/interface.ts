// FileName: interface.ts

import type { DictCommandContent } from "../content/interface";

/* For Web Socket */

export interface DictNativeHostPortMessage {
  port: number;
  token: string;
}

/* Dict Type for the command executed in backgound */
interface DictCommandGetDownloadList {
  commandName: "getDownloadList";
  limit: number;
  timeout: number;
}

interface DictCommandGetState {
  commandName: "getState";
}

interface DictCommandGoBackward {
  commandName: "goBackward";
}

interface DictCommandGoForward {
  commandName: "goForward";
}

interface DictCommandRefresh {
  commandName: "refresh";
}

interface DictCommandWaitLoadCompleted {
  commandName: "waitLoadCompleted";
  timeout: number;
}

interface DictCommandNavigate {
  commandName: "navigate";
  url: string;
  waitLoadCompleted: boolean;
  timeout: number;
}

interface DictCommandOpenNewTab {
  commandName: "openNewTab";
  url: string;
  waitLoadCompleted: boolean;
  timeout: number;
}

interface DictCommandOpenNewWindow {
  commandName: "openNewWindow";
  url: string;
  waitLoadCompleted: boolean;
  timeout: number;
}

interface DictCommandSwitchTab {
  commandName: "switchTab";
  titleOrIndex: string | number;
}

interface DictCommandCloseCurrentTab {
  commandName: "closeCurrentTab";
}

interface DictCommandGetUrl {
  commandName: "getUrl";
}

interface DictCommandGetTitle {
  commandName: "getTitle";
}

interface DictCommandGetCookies {
  commandName: "getCookies";
}

interface DictCommandSetCookies {
  commandName: "setCookies";
  domain: string;
  name: string;
  path: string;
  value: string | null;
  expirationDate: number | null;
  httpOnly: boolean | null;
  secure: boolean | null;
  storeId: string | null;
  sameSite: chrome.cookies.SameSiteStatus | null;
}

type DictCommandBackground =
  | DictCommandGetDownloadList
  | DictCommandGetState
  | DictCommandGoBackward
  | DictCommandGoForward
  | DictCommandRefresh
  | DictCommandWaitLoadCompleted
  | DictCommandNavigate
  | DictCommandOpenNewTab
  | DictCommandOpenNewWindow
  | DictCommandSwitchTab
  | DictCommandCloseCurrentTab
  | DictCommandGetUrl
  | DictCommandGetTitle
  | DictCommandGetCookies
  | DictCommandSetCookies;

export type DictCommandFromFlaskWithoutId = DictCommandBackground | DictCommandContent;

export type DictCommandFromFlask<
  T extends DictCommandFromFlaskWithoutId = DictCommandFromFlaskWithoutId
> = T & {
  id: string;
};

/* The types for result */

export interface DictResultOriginal {
  boolSuccess: boolean;
  data: unknown;
}

export interface DictResultToFlask extends DictResultOriginal {
  id: string;
}
