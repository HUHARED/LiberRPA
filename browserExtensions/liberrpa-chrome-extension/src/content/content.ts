// FileName: content.ts
console.log("This is content.js");
// console.log(new Date());

import type { DictResultOriginal } from "../background/interface";
import type { DictCommandContent } from "./interface";

import { getElementAttrByCoordinates, getElementAttrBySelector } from "./commonFunc";

import { withTimeout } from "./timeFunc";
import { clickMouseEvent } from "./mouseFunc";
import { setElementText } from "./keyboardFunc";
import {
  focusElement,
  getParentElementAttr,
  getChildrenElementAttr,
  setCheckState,
  getSelection,
  setSelection,
} from "./elementFunc";
import {
  getSourceCode,
  getAllText,
  getScrollPosition,
  setScrollPosition,
  executeJsCode,
} from "./pageFunc";

type SendResponse = (response: DictResultOriginal) => void;

chrome.runtime.onMessage.addListener(
  (dictCommand: DictCommandContent, _sender, sendResponse) => {
    console.log("Command received from background:", dictCommand);

    // NOTE: It throws an error "The message port closed before a response was received." if use async/await, so use then/catch.

    try {
      switch (dictCommand.commandName) {
        case "clickMouseEvent":
          handleAsyncResult(
            withTimeout(
              () =>
                clickMouseEvent(
                  dictCommand.htmlSelector,
                  dictCommand.button,
                  dictCommand.clickMode,
                  dictCommand.pressCtrl,
                  dictCommand.pressShift,
                  dictCommand.pressAlt,
                  dictCommand.pressWin,
                  dictCommand.preDelay,
                ),
              dictCommand.timeout,
            ),
            sendResponse,
          );

          break;

        case "setElementText":
          handleAsyncResult(
            withTimeout(
              () =>
                setElementText(
                  dictCommand.htmlSelector,
                  dictCommand.text,
                  dictCommand.clearBeforeWrite,
                  dictCommand.validateText,
                  dictCommand.preDelay,
                ),
              dictCommand.timeout,
            ),
            sendResponse,
          );

          break;

        case "focusElement":
          handleAsyncResult(
            withTimeout(
              () => focusElement(dictCommand.htmlSelector, dictCommand.preDelay),
              dictCommand.timeout,
            ),
            sendResponse,
          );
          break;

        case "getParentElementAttr":
          handleAsyncResult(
            withTimeout(
              () =>
                getParentElementAttr(
                  dictCommand.htmlSelector,
                  dictCommand.upwardLevel,
                  dictCommand.preDelay,
                ),
              dictCommand.timeout,
            ),
            sendResponse,
          );
          break;

        case "getChildrenElementAttr":
          handleAsyncResult(
            withTimeout(
              () => getChildrenElementAttr(dictCommand.htmlSelector, dictCommand.preDelay),
              dictCommand.timeout,
            ),
            sendResponse,
          );
          break;

        case "setCheckState":
          handleAsyncResult(
            withTimeout(
              () =>
                setCheckState(
                  dictCommand.htmlSelector,
                  dictCommand.checkAction,
                  dictCommand.preDelay,
                ),
              dictCommand.timeout,
            ),
            sendResponse,
          );
          break;

        case "getSelection":
          handleAsyncResult(
            withTimeout(
              () =>
                getSelection(
                  dictCommand.htmlSelector,
                  dictCommand.selectionType,
                  dictCommand.preDelay,
                ),
              dictCommand.timeout,
            ),
            sendResponse,
          );
          break;

        case "setSelection":
          handleAsyncResult(
            withTimeout(
              () =>
                setSelection(
                  dictCommand.htmlSelector,
                  dictCommand.text,
                  dictCommand.value,
                  dictCommand.index,
                  dictCommand.preDelay,
                ),
              dictCommand.timeout,
            ),
            sendResponse,
          );
          break;

        // More async cases will be added later...

        // Sync cases:
        case "getElementAttrByCoordinates":
          sendSuccess(
            getElementAttrByCoordinates(dictCommand.x, dictCommand.y, dictCommand.usePath),
            sendResponse,
          );
          return false;

        case "getElementAttrBySelector":
          sendSuccess(getElementAttrBySelector(dictCommand.htmlSelector), sendResponse);
          return false;

        case "getSourceCode":
          sendSuccess(getSourceCode(), sendResponse);
          return false;

        case "getAllText":
          sendSuccess(getAllText(), sendResponse);
          return false;

        case "getScrollPosition":
          sendSuccess(getScrollPosition(), sendResponse);
          return false;

        case "setScrollPosition":
          sendSuccess(setScrollPosition(dictCommand.x, dictCommand.y), sendResponse);
          return false;

        case "executeJsCode":
          sendSuccess(
            executeJsCode(dictCommand.jsCode, dictCommand.returnImmediately),
            sendResponse,
          );
          return false;

        // Unknown command:
        default:
          return assertNever(dictCommand);
      }
    } catch (e) {
      // The catch for sync and unknown command.
      // async functions use .catch() in handleAsyncResult().

      sendError(e, sendResponse);

      return false; // Close the messaging channel; response has been sent.
    }

    return true; // Return true to keep the response channel open due to it may have some async manipulation didn't resolve.
  },
);

function handleAsyncResult<T>(promise: Promise<T>, sendResponse: SendResponse): void {
  void promise
    .then((value) => {
      sendSuccess(value, sendResponse);
    })
    .catch((error: unknown) => {
      sendError(error, sendResponse);
    });
}

function sendSuccess(value: unknown, sendResponse: SendResponse): void {
  const result: DictResultOriginal = {
    boolSuccess: true,
    data: value === undefined ? null : value,
  };
  sendResponse(result);
  console.log("result", result);
}

function sendError(error: unknown, sendResponse: SendResponse): void {
  const result: DictResultOriginal = {
    boolSuccess: false,
    data: `${error instanceof Error ? error.message : String(error)}`,
  };
  sendResponse(result);
  console.log("result", result);
}

function assertNever(value: never): never {
  throw new Error(`Unhandled command: ${JSON.stringify(value)}`);
}
