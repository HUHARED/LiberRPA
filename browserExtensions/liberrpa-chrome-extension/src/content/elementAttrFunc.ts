// FileName: elementAttributeFunc.ts

import {
  DictOriginalAttr,
  DictLayerHtml,
  DictHtmlSecondaryAttr,
  DictFinalAttr,
} from "./interface";
import { convertViewportPositionToScreen } from "./positionCalculation";

export function getBasicAttr(element: HTMLElement): DictOriginalAttr {
  // console.log("--getBasicAttr--");
  // Get the Chrome tool bar height for calcualting the x, y of elements later.

  const style = window.getComputedStyle(element);

  const { tableRowIndex, tableColumnIndex, tableColumnName } = getTableInfo(element);

  // Get the non-index or non-path attributes.
  const dictBasicAttr: DictOriginalAttr = {
    tagName: element.tagName.toLowerCase(),
    id: element.id,
    className: element.className,
    type: element.getAttribute("type"), // For inputbox, etc.
    // For inputbox, etc.
    value:
      element instanceof HTMLInputElement || element instanceof HTMLSelectElement
        ? element.value // The newest value. If the newest value is not same with the initial value, querySelectorAll() will not match it.
        : element.getAttribute("value"), // The initial value.
    name: element.getAttribute("name"),
    "aria-label": element.getAttribute("aria-label"),
    "aria-labelledby": element.getAttribute("aria-labelledby"),
    checked:
      element instanceof HTMLInputElement
        ? element.checked
          ? "true"
          : element.indeterminate
          ? "indeterminate"
          : "false"
        : null,
    disabled:
      element instanceof HTMLInputElement ||
      element instanceof HTMLButtonElement ||
      element instanceof HTMLSelectElement ||
      element instanceof HTMLTextAreaElement ||
      element instanceof HTMLOptGroupElement ||
      element instanceof HTMLOptionElement ||
      element instanceof HTMLFieldSetElement
        ? (String(element.disabled) as "true" | "false")
        : null,

    href: element.getAttribute("href"),
    src: element.getAttribute("src"),
    alt: element.getAttribute("alt"),
    isHidden: style.visibility === "hidden" ? "true" : "false",
    isDisplayedNone: style.display === "none" ? "true" : "false",
    innerText: handleInnerText(element),
    directText: getDirectText(element),
    parentId: element.parentElement ? element.parentElement.id : null,
    parentClass: element.parentElement ? element.parentElement.className : null,
    parentName: element.parentElement ? element.parentElement.getAttribute("name") : null,
    isLeaf: element.children.length === 0 ? "true" : "false",
    tableRowIndex: tableRowIndex ? String(tableRowIndex) : null,
    tableColumnIndex: tableColumnIndex ? String(tableColumnIndex) : null,
    tableColumnName: tableColumnName,

    ...getPosition(element),
  };

  deleteMeaninglessItem(dictBasicAttr);

  return dictBasicAttr;
}

export function getFinalAttr(element: HTMLElement, usePath: boolean): DictFinalAttr {
  const dictAttr = getBasicAttr(element);

  /* console.log(
      "attributes(remove meaningless keys and convert all to string):",
      JSON.stringify(dictAttr, null, 2)
    ); */

  // Add path or index.
  if (usePath) {
    dictAttr.path = getPath(element);
  } else {
    addIndexForTheLayer(element, dictAttr);
  }

  return dictAttr as DictFinalAttr;
}

export function getPosition(element: HTMLElement): DictHtmlSecondaryAttr {
  // console.log("--getPosition--");

  const rect = element.getBoundingClientRect();

  const { screenX, screenY } = convertViewportPositionToScreen(rect.left, rect.top);
  // They may return float, so use Math.trunc.
  // The x and y may be changed if the element be moved into viewport. So may need to update it.

  return {
    "secondary-x": String(Math.trunc(screenX)),
    "secondary-y": String(Math.trunc(screenY)),
    "secondary-width": String(Math.trunc(rect.width)),
    "secondary-height": String(Math.trunc(rect.height)),
  };
}

export function getTableInfo(element: HTMLElement): {
  tableRowIndex: number | null;
  tableColumnIndex: number | null;
  tableColumnName: string | null;
} {
  // console.log("--getTableInfo--");

  let tableRowIndex = null;
  let tableColumnIndex = null;
  let tableColumnName = null;
  try {
    if (
      element instanceof HTMLTableCellElement &&
      (element.tagName.toLowerCase() === "td" || element.tagName.toLowerCase() === "th")
    ) {
      tableColumnIndex = element.cellIndex; // Zero-based index of the cell in its row

      if (element.parentNode && element.parentNode instanceof HTMLTableRowElement) {
        tableRowIndex = element.parentNode.rowIndex; // Zero-based index of the row in the table
      }

      // Attempt to get the column name if the first row contains <th> elements
      const table = element.closest("table");
      // Check if the first row exists and contains <th> elements
      if (
        table &&
        table.rows[0] &&
        Array.from(table.rows[0].cells).every((cell) => cell.tagName.toLowerCase() === "th")
      ) {
        // If there are all <th> elements in the first row, attempt to get the column name based on cellIndex
        const headers = table.rows[0].cells;
        tableColumnName =
          headers.length > element.cellIndex ? headers[element.cellIndex].innerText : null;
      }
    }
  } catch (e) {
    console.error("Error when getting table infomation.", e);
  }

  return { tableRowIndex, tableColumnIndex, tableColumnName };
}

export function getDirectText(element: HTMLElement) {
  // console.log("--getDirectText--");
  let directText = "";
  element.childNodes.forEach((node) => {
    if (node.nodeType === Node.TEXT_NODE && node.nodeValue) {
      directText += node.nodeValue;
    }
  });
  return directText;
}

function deleteMeaninglessItem(dictHandled: { [key: string]: string | null | undefined }) {
  // console.log("--deleteMeaninglessItem--");

  Object.keys(dictHandled).forEach((key) => {
    if (
      dictHandled[key] === null ||
      dictHandled[key] === "" ||
      dictHandled[key] === undefined
    ) {
      delete dictHandled[key];
    }
  });
}

export function getPath(element: HTMLElement): string {
  // console.log("---getPath-");
  let path = [];
  let currentElement = element;
  let tagName = currentElement.tagName.toLowerCase();
  while (currentElement.parentElement && tagName != "html") {
    let siblingIndex = getSiblingIndex(currentElement);
    // If the index is 0 or 1, didn't need ':nth-child'. nth-child starts from 1, so if siblingIndex > 1, declare it, otherwise it's unnecessary. Mean that the current element doesn't have siblings with same tagName, or its siblings is behind it.
    path.unshift(`${tagName}${siblingIndex > 1 ? ":nth-child(" + siblingIndex + ")" : ""}`);
    currentElement = currentElement.parentElement;
    tagName = currentElement.tagName.toLowerCase();
  }
  path.unshift("html");
  return path.join(">");
}

function getSiblingIndex(element: HTMLElement): number {
  // console.log("--getSiblingIndex--");
  if (element.parentNode) {
    // 1, check whether it has same tag siblings.
    let hasSameTagSiblings =
      Array.from(element.parentNode.children).filter(
        (child) => child.tagName === element.tagName
      ).length > 1;

    if (!hasSameTagSiblings) {
      // It has no, return 0.
      return 0;
    }
  }

  // 2, if it has, calculate the index. nth-child starts from 1.
  let index = 1;
  let currentElement = element.previousElementSibling;
  while (currentElement) {
    if (currentElement.tagName === element.tagName) {
      index++;
    }
    currentElement = currentElement.previousElementSibling;
  }

  return index;
}

export function addIndexForTheLayer(
  originalElement: HTMLElement,
  dictAttr: DictOriginalAttr
): void {
  /* Called by each layer, locate elements using the layer's attributes.
  Compare them with the originalElement, if more than one element is found, add the attribute childIndex and documentIndex for the layer. */
  // console.log("--addIndexForTheLayer--");
  // console.log("dictAttr=", dictAttr);

  // IF the current element(layer) doesn't have partent element, didn't need to add index.
  if (!originalElement.parentElement) {
    return;
  }

  const documentElementsFinal = getDocumentElements(dictAttr);
  // console.log("documentElementsFinal", documentElementsFinal);

  const childElementsFinal = getChildElements(originalElement.parentElement, dictAttr);
  // console.log("childElementsFinal", childElementsFinal);

  // Check the 2 arrays' count.
  if (childElementsFinal.length === 0)
    //
    throw new Error("Didn't find any elements match the attributes in childElementsFinal.");
  if (childElementsFinal.length > 1) {
    for (let index = 0; index < childElementsFinal.length; index++) {
      if (childElementsFinal[index] === originalElement) {
        // The childIndex should also be a string like others.
        dictAttr.childIndex = String(index);
        break;
      }
    }
    if (!dictAttr.childIndex)
      throw new Error(
        "When childElementsFinal.length > 1, didn't find the original element in childElementsFinal."
      );
  }

  // Simular with childElementsFinal
  if (documentElementsFinal.length === 0)
    throw new Error(
      "Didn't find any elements match the attributes in documentElementsFinal"
    );
  if (documentElementsFinal.length > 1) {
    for (let index = 0; index < documentElementsFinal.length; index++) {
      if (documentElementsFinal[index] === originalElement) {
        dictAttr.documentIndex = String(index);
        break;
      }
    }
    if (!dictAttr.documentIndex)
      throw new Error(
        "documentElementsFinal.length > 1, didn't find the original element in documentElementsFinal."
      );
  }

  // If childElementsFinal.length === 1 and documentElementsFinal.length === 1, the indexes will not be added.
  // TODO: But will it have the situation that length >1 and index === 0? Test it later.
}

function getDocumentElements(dictAttr: DictOriginalAttr): HTMLElement[] {
  // console.log("--getDocumentElements--");
  // Get the CSS Selector, it's same for the search of childIndex and documentIndex.
  const strQuerySelector = createQuerySelectorFromAttrDict(dictAttr);

  const documentElementsTemp: NodeListOf<HTMLElement> =
    document.querySelectorAll(strQuerySelector);
  // console.log("documentElementsTemp", documentElementsTemp);

  const documentElementsFinal = Array.from(documentElementsTemp).filter((ele) =>
    filterNonQuerySelectorFromAttrDict(ele, dictAttr)
  );

  return documentElementsFinal;
}

function getChildElements(
  parentElement: HTMLElement,
  dictAttr: DictOriginalAttr
): HTMLElement[] {
  // console.log("--getChildElements--");

  // Get the CSS Selector, it's same for the search of childIndex and documentIndex.
  const strQuerySelector = createQuerySelectorFromAttrDict(dictAttr);

  const childElementsTemp: NodeListOf<HTMLElement> =
    parentElement.querySelectorAll(strQuerySelector);
  // console.log("childElementsTemp", childElementsTemp);

  const childElementsFinal = Array.from(childElementsTemp).filter((ele) =>
    filterNonQuerySelectorFromAttrDict(ele, dictAttr)
  );

  return childElementsFinal;
}

export function createQuerySelectorFromAttrDict(
  dictAttr: DictOriginalAttr | DictLayerHtml
): string {
  // Join the attributes that supported by querySelectorAll.
  // console.log("--createQuerySelectorFromAttrDict--");
  // console.log("attributes to create Css Selector", dictAttr);

  const arrSelectorParts: string[] = [];

  // Add tagName if available
  if (dictAttr.tagName) arrSelectorParts.push(dictAttr.tagName.trim());

  // Add id, escaping it if necessary
  if (dictAttr.id) arrSelectorParts.push(`#${CSS.escape(dictAttr.id.trim())}`);

  // Add className(s), escaping each class
  if (dictAttr.className) {
    const classes = dictAttr.className.split(/\s+/).filter(Boolean);
    arrSelectorParts.push(classes.map((classTemp) => `.${CSS.escape(classTemp)}`).join(""));
  }

  /* if (dictAttr.type) arrSelectorParts.push(`[type="${dictAttr.type}"]`);
  if (dictAttr.value) arrSelectorParts.push(`[value="${dictAttr.value}"]`);
  if (dictAttr.name) arrSelectorParts.push(`[name="${dictAttr.name}"]`);
  if (dictAttr["aria-label"])
    arrSelectorParts.push(`[aria-label="${dictAttr["aria-label"]}"]`);
  if (dictAttr["aria-labelledby"])
    arrSelectorParts.push(`[aria-labelledby="${dictAttr["aria-labelledby"]}"]`); */
  // Add attributes using a loop for cleaner code
  const arrAttrToInclude = [
    "type",
    // "value",
    "name",
    "aria-label",
    "aria-labelledby",
  ];
  for (const attr of arrAttrToInclude) {
    const strTemp = dictAttr[attr];
    if (strTemp) {
      arrSelectorParts.push(`[${attr}="${CSS.escape(strTemp)}"]`);
    }
  }

  // Handle boolean pseudo-classes like :checked and :disabled
  if (dictAttr.checked?.toLowerCase() === "true") arrSelectorParts.push(":checked");
  else if (dictAttr.checked?.toLowerCase() === "indeterminate") {
    arrSelectorParts.push(":indeterminate");
  }
  if (dictAttr.disabled?.toLowerCase() === "true") arrSelectorParts.push(":disabled");

  // Join all parts into the final selector
  const strQuerySelector: string = arrSelectorParts.join("");
  // console.log(`strQuerySelector='${strQuerySelector}'`);
  if (strQuerySelector === "") {
    // If the selector have no attributes which supported by querySelectorAll(), return "*" for getting all children elements of it, including its direct children and their descendants.
    return "*";
  } else {
    return strQuerySelector;
  }
}

function filterNonQuerySelectorFromAttrDict(
  element: HTMLElement,
  dictAttr: DictOriginalAttr
): boolean {
  // console.log("--filterNonQuerySelectorFromAttrDict--");
  // Check the attributes that don't supported by querySelectorAll.
  // Loop all attributes in the curren layer, check whether the current element has a same attribute.

  const { tableRowIndex, tableColumnIndex, tableColumnName } = getTableInfo(element);
  const style = window.getComputedStyle(element);

  const dictAttrCurrent: { [key: string]: string | null | undefined } = {
    // Omit tagName, id, etc. due to they are filtered in the querySelectorAll.
    // querySelectorAll() doesn't work with modified "value", so match it in here.
    value:
      element instanceof HTMLInputElement || element instanceof HTMLSelectElement
        ? element.value
        : element.getAttribute("value"),
    href: element.getAttribute("href"),
    src: element.getAttribute("src"),
    alt: element.getAttribute("alt"),
    isHidden: style.visibility === "hidden" ? "true" : "false",
    isDisplayedNone: style.display === "none" ? "true" : "false",
    innerText: handleInnerText(element),
    directText: getDirectText(element),
    parentId: element.parentElement ? element.parentElement.id : null,
    parentClass: element.parentElement ? element.parentElement.className : null,
    parentName: element.parentElement ? element.parentElement.getAttribute("name") : null,
    isLeaf: element.children.length === 0 ? "true" : "false",
    tableRowIndex: tableRowIndex ? String(tableRowIndex) : null,
    tableColumnIndex: tableColumnIndex ? String(tableColumnIndex) : null,
    tableColumnName: tableColumnName,
    // Omit others like url, title, secondary-*, etc due to they are same or unimportant.
  };
  // The attributesOriginal has be processed, so attributesCurrent should be processed before comparing them.

  deleteMeaninglessItem(dictAttrCurrent);

  // console.log("dictAttrCurrent", dictAttrCurrent);

  // Compare the values. Due to selector may delete some attributes deliberately, and key in DictOriginalAttributes may not exist in dictAttrCurrent, so should make sure the key is existing then compare.
  for (const [key, value] of Object.entries(dictAttr)) {
    if (
      key.endsWith("-regex") &&
      dictAttrCurrent[key.slice(0, -"-regex".length)] &&
      new RegExp(`^${dictAttr[key]}$`, "u").test(
        dictAttrCurrent[key.slice(0, -"-regex".length)] as string
      )
    ) {
      // It's a regex attribute in the selector, and it matches with the current attribute, so go to check next attribute.
      console.log(`"${key}" matches: ${dictAttrCurrent[key.slice(0, -"-regex".length)]}`);

      continue;
    }
    if (dictAttrCurrent[key] && dictAttrCurrent[key] !== value) {
      // console.log(`key ${key} does not equal.`);
      return false;
    }
  }
  return true;
}

function handleInnerText(element: HTMLElement): undefined | string {
  if (element.innerText) {
    if (element.innerText.length > 1024) {
      return "The innerText is too long (longer than 1024 characters), so not show it in Element Tree.";
    } else {
      return element.innerText;
    }
  }
  return undefined;
}
