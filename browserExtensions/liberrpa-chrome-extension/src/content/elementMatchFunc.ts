// FileName: elementMatchFunc.ts

import type { DictOriginalAttr, DictLayerHtml, DictAttrForIndex } from "./interface";
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

  const dictAttrForIndex: DictLayerHtml = { ...getBasicAttr(elementCurrent) };

  // Delete attributes that dictSelector does not have, so the index can be calculated under the same attribute constraints as the selector.
  for (const keyName of Object.keys(dictAttrForIndex)) {
    const strKeyWithRegex = `${keyName}-regex`;
    const valueSelector = dictSelector[keyName];
    const valueSelectorRegex = dictSelector[strKeyWithRegex];

    const valueCurrent = dictAttrForIndex[keyName];

    if (valueSelector === undefined && valueSelectorRegex === undefined) {
      // console.log(`Delete '${keyName}' for adding index.`);

      delete dictAttrForIndex[keyName];
      continue;
    }

    if (
      typeof valueSelectorRegex === "string" &&
      typeof valueCurrent === "string" &&
      new RegExp(`^${valueSelectorRegex}$`, "u").test(valueCurrent)
    ) {
      console.log(`Delete '${keyName}' for adding index(It's use regex).`);
      delete dictAttrForIndex[keyName];
      dictAttrForIndex[strKeyWithRegex] = valueSelectorRegex;
    }
  }

  const dictAttrCurrEleWithIndex = addIndexForTheLayer(elementCurrent, dictAttrForIndex);

  console.log("dictAttrCurrEle", JSON.stringify(dictAttrForIndex, null, 2));

  return compareAttrWithSelector(dictSelector, dictAttrCurrEleWithIndex);
}

function compareAttrWithSelector(
  dictSelector: DictLayerHtml,
  dictAttrCurrEle: DictAttrForIndex
): boolean {
  console.log("--compareAttrWithSelector--");

  // If all item in dictSelector matched, return true.
  for (const keyName of Object.keys(dictSelector)) {
    const valueSelector = dictSelector[keyName];

    if (typeof valueSelector !== "string") {
      return false;
    }

    if (keyName.endsWith("-regex")) {
      // The regex string.

      let valueToCheck_Regex = dictAttrCurrEle[keyName];
      if (typeof valueToCheck_Regex === "string") {
        // The key is a regex and dictAttrCurrEle also use the regex to add index.
        // NOTE: 20260507, I have forgotten the logic... Why is it here?
        continue;
      }

      const strBaseKeyName = keyName.replace(/-regex$/u, "");
      valueToCheck_Regex = dictAttrCurrEle[strBaseKeyName];

      if (typeof valueToCheck_Regex !== "string") {
        // The value is not in currentElement's attributes.
        return false;
      }

      // The value must match the whole regex expression.
      const re = new RegExp(`^${valueSelector}$`, "u");
      if (re.test(valueToCheck_Regex) === false) {
        // The attribute doesn't match the selector.
        console.log(
          keyName,
          "in current element is",
          valueToCheck_Regex,
          "it does not match: ",
          valueSelector
        );
        return false;
      }
    } else {
      // The normal string.

      const valueToCheck = dictAttrCurrEle[keyName];

      if (typeof valueToCheck !== "string") {
        // The value is not in currentElement's attributes.
        return false;
      }

      if (valueToCheck !== valueSelector) {
        return false;
      }
    }
  }
  // No attribute returned false in the previous loop.
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
