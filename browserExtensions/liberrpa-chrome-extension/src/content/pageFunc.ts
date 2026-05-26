// FileName: pageFunc.ts

import { getEvalInstance, transformCode } from "chrome-inject-eval";

type EvalFunction = (code: string) => unknown;

export function getSourceCode(): string {
  console.log("--getSourceCode--");

  return document.documentElement.outerHTML;
}

export function getAllText(): string {
  console.log("--getAllText--");

  return document.body.innerText;
}

export function getScrollPosition(): number[] {
  console.log("--getScrollPosition--");

  return [window.scrollX, window.scrollY];
}

export function setScrollPosition(x: number, y: number): void {
  console.log("--setScrollPosition--");

  window.scrollTo(x, y);
}

export function executeJsCode(jsCode: string, returnImmediately: boolean): unknown {
  console.log("--executeJsCode--");

  try {
    const evil = getEvalInstance(window) as EvalFunction;
    const result = evil(transformCode(jsCode));

    if (!returnImmediately) {
      return result;
    } else {
      return null;
    }
  } catch (e) {
    console.error("Error executing JS code:", e);
    return null;
  }
}
