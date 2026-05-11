// FileName: keyboardFunc.ts

import type { DictLayerHtml } from "./interface";
import { findElementWithPredelay } from "./timeFunc";

export async function setElementText(
  selector: DictLayerHtml[],
  text: string,
  emptyOriginalText: boolean = false,
  validateWrittenText: boolean = false,
  preExecutionDelay: number = 300
): Promise<void> {
  console.log("--setElementText--");

  const element: HTMLElement = await findElementWithPredelay(selector, preExecutionDelay);

  let strWrittenText: string;

  if (isTextInputOrTextare(element)) {
    if (emptyOriginalText) {
      element.value = text;
    } else {
      element.value += text;
    }
    strWrittenText = element.value;
    console.log("element.value", element.value);
  } else if (element.isContentEditable) {
    if (emptyOriginalText) {
      element.innerText = text;
    } else {
      element.innerText += text;
    }
    strWrittenText = element.innerText;
    console.log("element.innerText", element.innerText);
  } else {
    throw new Error("The element's content is not editable.");
  }

  if (
    validateWrittenText &&
    strWrittenText.replace("\r\n", "\n") !== text.replace("\r\n", "\n")
  ) {
    throw new Error(
      `The written text (${JSON.stringify(
        strWrittenText
      )}) is not equals with the argument text(${JSON.stringify(text)}).`
    );
  }
}

function isTextInputOrTextare(
  element: HTMLElement
): element is HTMLInputElement | HTMLTextAreaElement {
  return (
    element instanceof HTMLTextAreaElement ||
    (element instanceof HTMLInputElement && element.type === "text")
  );
}
