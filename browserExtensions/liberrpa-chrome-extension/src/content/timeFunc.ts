// FileName: timeFunc.ts

import { findElementBySelector } from "./commonFunc";
import { DictLayerHtml } from "./interface";

export async function delay(ms: number): Promise<void> {
  console.log(`Dealy ${ms} ms.`);

  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

export async function withTimeout<T>(
  func: () => Promise<T>,
  timeout: number
): Promise<T> {
  let timeoutHandle: number;
  const timeoutPromise = new Promise<never>((_, reject) => {
    timeoutHandle = setTimeout(() => {
      reject(new Error(`Function timed out after ${timeout} milliseconds`));
    }, timeout);
  });

  return Promise.race([
    func().then((result) => {
      clearTimeout(timeoutHandle);
      return result;
    }),
    timeoutPromise,
  ]);
}

export async function findElementWithPredelay(
  selector: DictLayerHtml[],
  preExecutionDelay: number = 300
): Promise<HTMLElement> {
  console.log("--findElementWithPredelay--");
  const timeStart = Date.now();
  const element: HTMLElement = findElementBySelector(selector);
  const timeUsed = Date.now() - timeStart;

  if (timeUsed < preExecutionDelay) {
    await delay(preExecutionDelay - timeUsed);
  }
  return element;
}
