// FileName: mouseFunc.ts

import { DictLayerHtml } from "./interface";
import { MouseButton, ClickMode } from "./interface";
import { findElementWithPredelay } from "./timeFunc";

export async function clickMouseEvent(
  selector: DictLayerHtml[],
  button: MouseButton = "left",
  clickMode: ClickMode = "single_click",
  pressCtrl: boolean = false,
  pressShift: boolean = false,
  pressAlt: boolean = false,
  pressWin: boolean = false,
  preExecutionDelay: number = 300
): Promise<void> {
  console.log("--clickMouseEvent--");
  const element: HTMLElement = await findElementWithPredelay(
    selector,
    preExecutionDelay
  );

  let clickModeForEvent: string;
  switch (clickMode) {
    case "single_click":
      clickModeForEvent = "click";
      break;
    case "double_click":
      clickModeForEvent = "dblclick";
      break;
    case "up":
      clickModeForEvent = "mouseup";
      break;
    case "down":
      clickModeForEvent = "mousedown";
      break;
    default:
      // It will not happen, Python will check it.
      throw new Error("Unknown clickMode" + clickMode);
  }
  let buttonForEvent: number;
  switch (button) {
    case "left":
      buttonForEvent = 0;
      break;
    case "right":
      buttonForEvent = 2;
      break;
    case "middle":
      buttonForEvent = 1;
      break;
    default:
      throw new Error("Unknown button" + button);
  }
  const event: MouseEvent = new MouseEvent(clickModeForEvent, {
    button: buttonForEvent,
    ctrlKey: pressCtrl,
    shiftKey: pressShift,
    altKey: pressAlt,
    metaKey: pressWin,

    bubbles: true,
    cancelable: true,
    view: window,
  });
  element.dispatchEvent(event);
}
