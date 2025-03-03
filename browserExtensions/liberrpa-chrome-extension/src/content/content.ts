// FileName: content.ts
console.log("This is content.js");
console.log(new Date());

import { DictResultToFlask } from "../background/interface";
import {
  getElementAttrByCoordinates,
  getElementAttrBySelector,
} from "./commonFunc";

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

chrome.runtime.onMessage.addListener(
  (dictCommand: { [key: string]: any }, _, sendResponse) => {
    console.log("Command received from background:", dictCommand);

    // NOTE: It throws an error "The message port closed before a response was received." if use async/await, so use then/catch.

    let result: DictResultToFlask;
    try {
      switch (dictCommand.commandName) {
        case "clickMouseEvent":
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
                dictCommand.preExecutionDelay
              ),
            dictCommand.timeout
          )
            .then((temp) => handleThen(temp, sendResponse))
            .catch((e) => handleCatch(e, sendResponse));
          break;

        case "setElementText":
          withTimeout(
            () =>
              setElementText(
                dictCommand.htmlSelector,
                dictCommand.text,
                dictCommand.emptyOriginalText,
                dictCommand.validateWrittenText,
                dictCommand.preExecutionDelay
              ),
            dictCommand.timeout
          )
            .then((temp) => handleThen(temp, sendResponse))
            .catch((e) => handleCatch(e, sendResponse));
          break;

        case "focusElement":
          withTimeout(
            () =>
              focusElement(dictCommand.htmlSelector, dictCommand.preExecutionDelay),
            dictCommand.timeout
          )
            .then((temp) => handleThen(temp, sendResponse))
            .catch((e) => handleCatch(e, sendResponse));
          break;

        case "getParentElementAttr":
          withTimeout(
            () =>
              getParentElementAttr(
                dictCommand.htmlSelector,
                dictCommand.upwardLevel,
                dictCommand.preExecutionDelay
              ),
            dictCommand.timeout
          )
            .then((temp) => handleThen(temp, sendResponse))
            .catch((e) => handleCatch(e, sendResponse));
          break;

        case "getChildrenElementAttr":
          withTimeout(
            () =>
              getChildrenElementAttr(
                dictCommand.htmlSelector,
                dictCommand.preExecutionDelay
              ),
            dictCommand.timeout
          )
            .then((temp) => handleThen(temp, sendResponse))
            .catch((e) => handleCatch(e, sendResponse));
          break;

        case "setCheckState":
          withTimeout(
            () =>
              setCheckState(
                dictCommand.htmlSelector,
                dictCommand.checkAction,
                dictCommand.preExecutionDelay
              ),
            dictCommand.timeout
          )
            .then((temp) => handleThen(temp, sendResponse))
            .catch((e) => handleCatch(e, sendResponse));
          break;

        case "getSelection":
          withTimeout(
            () =>
              getSelection(
                dictCommand.htmlSelector,
                dictCommand.selectionType,
                dictCommand.preExecutionDelay
              ),
            dictCommand.timeout
          )
            .then((temp) => handleThen(temp, sendResponse))
            .catch((e) => handleCatch(e, sendResponse));
          break;

        case "setSelection":
          withTimeout(
            () =>
              setSelection(
                dictCommand.htmlSelector,
                dictCommand.text,
                dictCommand.value,
                dictCommand.index,
                dictCommand.preExecutionDelay
              ),
            dictCommand.timeout
          )
            .then((temp) => handleThen(temp, sendResponse))
            .catch((e) => handleCatch(e, sendResponse));
          break;

        // More async cases will be added later...

        // Sync cases:
        case "getElementAttrByCoordinates":
          handleSyncAndUnknownCommand(
            getElementAttrByCoordinates(
              dictCommand.x,
              dictCommand.y,
              dictCommand.usePath
            ),
            sendResponse
          );
          break;

        case "getElementAttrBySelector":
          handleSyncAndUnknownCommand(
            getElementAttrBySelector(dictCommand.htmlSelector),
            sendResponse
          );
          break;

        case "getSourceCode":
          handleSyncAndUnknownCommand(getSourceCode(), sendResponse);
          break;

        case "getAllText":
          handleSyncAndUnknownCommand(getAllText(), sendResponse);
          break;

        case "getScrollPosition":
          handleSyncAndUnknownCommand(getScrollPosition(), sendResponse);
          break;

        case "setScrollPosition":
          handleSyncAndUnknownCommand(
            setScrollPosition(dictCommand.x, dictCommand.y),
            sendResponse
          );
          break;

        case "executeJsCode":
          handleSyncAndUnknownCommand(
            executeJsCode(dictCommand.jsCode, dictCommand.returnImmediately),
            sendResponse
          );
          break;

        // Unknown command:
        default:
          result = {
            boolSuccess: false,
            boolNeedResponse: true,
            data: `Unknown command: [${dictCommand.commandName}]`,
          };
          sendResponse(result);
          console.log("result", result);
          return false; // Close the messaging channel; response has been sent.
      }
    } catch (e) {
      // The catch for sync and unknown command.
      result = {
        boolSuccess: false,
        boolNeedResponse: true,
        data: `${(e as Error).message}`,
      };
      sendResponse(result);
      console.log("result", result);
      return false; // Close the messaging channel; response has been sent.
    }

    return true; // Return true to keep the response channel open due to it may have some async manipulation didn't resolve.
  }
);

function handleThen(value: any, sendResponse: CallableFunction): void {
  const result: DictResultToFlask = {
    boolSuccess: true,
    boolNeedResponse: true,
    data: value,
  };
  sendResponse(result);
  console.log("result", result);
}

function handleCatch(e: Error, sendResponse: CallableFunction): void {
  const result: DictResultToFlask = {
    boolSuccess: false,
    boolNeedResponse: true,
    data: `${e instanceof Error ? e.message : e}`,
  };
  sendResponse(result);
  console.log("result", result);
}

function handleSyncAndUnknownCommand(
  value: any,
  sendResponse: CallableFunction
): void {
  const result: DictResultToFlask = {
    boolSuccess: true,
    boolNeedResponse: true,
    data: value,
  };
  sendResponse(result);
  console.log("result", result);
}
