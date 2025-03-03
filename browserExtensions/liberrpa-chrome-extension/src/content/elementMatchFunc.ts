// FileName: elementMatchFunc.ts

import { DictOriginalAttr, DictLayerHtml } from "./interface";
import {
  getBasicAttr,
  createQuerySelectorFromAttrDict,
  addIndexForTheLayer,
} from "./elementAttrFunc";

export function findElementByPath(
  elementParent: HTMLElement | Document,
  path: string
): HTMLElement | null {
  console.log("--findElementByPath--");

  const element: HTMLElement | null = elementParent.querySelector(path);

  console.log(element);

  return element;
}

export function compareBasicAttr(
  elementCurrent: HTMLElement,
  dictSelector: DictLayerHtml
): boolean {
  console.log("--compareBasicAttr--");
  const dictAttrCurrEle: DictOriginalAttr = getBasicAttr(elementCurrent);

  console.log("dictAttrCurrEle", JSON.stringify(dictAttrCurrEle, null, 2));

  return compareAttrWithSelector(dictSelector, dictAttrCurrEle);
}

export function compareBasicAndIndexAttr(
  elementCurrent: HTMLElement,
  dictSelector: DictLayerHtml
): boolean {
  console.log("--compareBasicAndIndexAttr--");
  const dictAttrCurrEle: DictOriginalAttr = getBasicAttr(elementCurrent);

  // Delete attributes which dictSelector doesn't have, to make the index be calculated in same attributes as possible.
  for (const keyName of Object.keys(dictAttrCurrEle)) {
    if (
      dictSelector[keyName] === undefined &&
      dictSelector[keyName + "-regex"] === undefined
    ) {
      // console.log(`Delete '${keyName}' for adding index.`);

      delete dictAttrCurrEle[keyName];
    } else if (
      dictSelector[keyName + "-regex"] &&
      new RegExp(`^${dictSelector[keyName + "-regex"]}$`, "u").test(
        dictAttrCurrEle[keyName] as string
      )
    ) {
      console.log(`Delete '${keyName}' for adding index(It's use regex).`);
      delete dictAttrCurrEle[keyName];
      dictAttrCurrEle[keyName + "-regex"] = dictSelector[keyName + "-regex"];
    }
  }
  addIndexForTheLayer(elementCurrent, dictAttrCurrEle);

  console.log("dictAttrCurrEle", JSON.stringify(dictAttrCurrEle, null, 2));

  return compareAttrWithSelector(dictSelector, dictAttrCurrEle);
}

function compareAttrWithSelector(
  dictSelector: DictLayerHtml,
  dictAttrCurrEle: DictOriginalAttr
): boolean {
  console.log("--compareAttrWithSelector--");

  // If all item in dictSelector matched, return true.
  for (const keyName of Object.keys(dictSelector)) {
    const valueRight = dictSelector[keyName] as string;

    if (keyName.endsWith("-regex")) {
      // The regex string.

      let valueToCheck = dictAttrCurrEle[keyName];
      if (valueToCheck) {
        // The key is a regex and dictAttrCurrEle also use the regex to add index.
        continue;
      }

      valueToCheck = dictAttrCurrEle[keyName.replace(/-regex$/, "")];
      if (!valueToCheck) {
        // The value is not in currentElement's attributes.
        return false;
      }

      // The value must match the whole regex expression.
      const re = new RegExp(`^${valueRight}$`, "u");
      if (re.test(valueToCheck) === false) {
        // The attribute doesn't match the selector.
        console.log(
          keyName,
          "in current element is",
          valueToCheck,
          "it doesn't match: ",
          valueRight
        );
        return false;
      }
    } else {
      // The normal string.

      const valueToCheck = dictAttrCurrEle[keyName];

      if (!valueToCheck) {
        // The value is not in currentElement's attributes.
        return false;
      }

      if (valueToCheck !== valueRight) {
        return false;
      }
    }
  }
  // Have no attribute return false in the previous loop.
  return true;
}

export function findElementByQuerySelectorAttr(
  dictSelector: DictLayerHtml,
  elementParent: HTMLElement | Document
): NodeListOf<HTMLElement> {
  console.log("--findElementByQuerySelectorAttr--");

  const strQuerySelector = createQuerySelectorFromAttrDict(dictSelector);

  const elementsFound: NodeListOf<HTMLElement> =
    elementParent.querySelectorAll(strQuerySelector);

  return elementsFound;
}
