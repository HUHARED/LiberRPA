// FileName: pageFunc.ts
// import injectEval from "chrome-inject-eval";
import { getEvalInstance, transformCode } from "chrome-inject-eval";

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

export function executeJsCode(jsCode: string, returnImmediately: boolean): any {
  console.log("--executeJsCode--");

  try {
    const evil = getEvalInstance(window);
    const resutl = evil(transformCode(jsCode));

    if (!returnImmediately) {
      return resutl;
    } else {
      return null;
    }
  } catch (e) {
    console.error("Error executing JS code:", e);
    return null;
  }
}
