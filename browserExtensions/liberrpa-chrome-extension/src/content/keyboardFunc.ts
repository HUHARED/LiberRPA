// FileName: keyboardFunc.ts

import { DictLayerHtml } from "./interface";
import { findElementWithPredelay } from "./timeFunc";

export async function setElementText(
  selector: DictLayerHtml[],
  text: string,
  emptyOriginalText: boolean = false,
  validateWrittenText: boolean = false,
  preExecutionDelay: number = 300
): Promise<void> {
  console.log("--setElementText--");
  const element: HTMLElement = await findElementWithPredelay(
    selector,
    preExecutionDelay
  );

  if (
    !(
      element.isContentEditable ||
      element.tagName === "TEXTAREA" ||
      (element.tagName === "INPUT" && element.getAttribute("type") === "text")
    )
  ) {
    throw new Error("The element's content is not editable.");
  }

  const boolUseValue =
    element.tagName === "INPUT" || element.tagName === "TEXTAREA";

  if (emptyOriginalText) {
    if (boolUseValue) {
      (element as HTMLInputElement).value = text;
    } else {
      element.innerText = text;
    }
  } else {
    if (boolUseValue) {
      (element as HTMLInputElement).value += text;
    } else {
      element.innerText += text;
    }
  }

  console.log(
    "(element as HTMLInputElement).value",
    (element as HTMLInputElement).value
  );
  console.log("element.innerText", element.innerText);

  if (
    validateWrittenText &&
    (boolUseValue
      ? (element as HTMLInputElement).value
      : element.innerText
    ).replace("\r\n", "\n") !== text.replace("\r\n", "\n")
  ) {
    throw new Error(
      `The written text (${JSON.stringify(
        boolUseValue ? (element as HTMLInputElement).value : element.innerText
      )}) is not equals with the argument text(${JSON.stringify(text)}).`
    );
  }
}
