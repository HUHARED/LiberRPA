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
  let strOriginal: string;
  let strExpected: string;

  if (isTextInputOrTextarea(element)) {
    strOriginal = element.value;

    strExpected = emptyOriginalText ? text : strOriginal + text;

    element.value = strExpected;
    dispatchInputAndChange(element);

    strWrittenText = element.value;
    console.log("element.value", element.value);
  } else if (element.isContentEditable) {
    strOriginal = element.innerText;

    strExpected = emptyOriginalText ? text : strOriginal + text;

    element.innerText = strExpected;
    dispatchInputAndChange(element);

    strWrittenText = element.innerText;
    console.log("element.innerText", element.innerText);
  } else {
    throw new Error("The element's content is not editable.");
  }

  if (
    validateWrittenText &&
    strWrittenText.replace(/\r\n/g, "\n") !== strExpected.replace(/\r\n/g, "\n")
  ) {
    throw new Error(
      `The written text (${JSON.stringify(
        strWrittenText
      )}) is not equal to the expected text(${JSON.stringify(strExpected)}).`
    );
  }
}

const editableInputTypes = new Set([
  "text",
  "search",
  "email",
  "password",
  "tel",
  "url",
  "number",
]);

function isTextInputOrTextarea(
  element: HTMLElement
): element is HTMLInputElement | HTMLTextAreaElement {
  return (
    element instanceof HTMLTextAreaElement ||
    (element instanceof HTMLInputElement && editableInputTypes.has(element.type))
  );
}

function dispatchInputAndChange(element: HTMLElement): void {
  // Notify the page that the element's value has changed.
  // This improves compatibility with Vue, React, Angular, and ordinary event-driven forms.
  // Some heavily controlled React components or custom input components may still require special handling.
  // Call it before assigning strWrittenText because the value might change during the event period.

  element.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
  element.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
}
