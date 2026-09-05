// FileName: elementAttributeFunc.ts

import type {
  AttrDraftValue,
  BooleanString,
  CheckedString,
  DictLayerIndexAttr,
  DictRawAttr,
  DictOriginalAttr,
  DictHtmlSecondaryAttr,
  DictFinalAttr,
  DictLayerHtml,
  DictAttrForIndex,
} from "./interface";
import { convertViewportPositionToScreen } from "./positionCalculation";

export function getBasicAttr(element: HTMLElement): DictOriginalAttr {
  // console.log("--getBasicAttr--");
  // Get the Chrome tool bar height for calcualting the x, y of elements later.

  const style = window.getComputedStyle(element);

  const { tableRowIndex, tableColumnIndex, tableColumnName } = getTableInfo(element);

  // Get the non-index or non-path attributes.
  const dictRawAttr: DictRawAttr = {
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
    checked: element instanceof HTMLInputElement ? getCheckedState(element) : null,
    disabled:
      element instanceof HTMLInputElement ||
      element instanceof HTMLButtonElement ||
      element instanceof HTMLSelectElement ||
      element instanceof HTMLTextAreaElement ||
      element instanceof HTMLOptGroupElement ||
      element instanceof HTMLOptionElement ||
      element instanceof HTMLFieldSetElement
        ? booleanToString(element.disabled)
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
    tableRowIndex: tableRowIndex !== null ? String(tableRowIndex) : null,
    tableColumnIndex: tableColumnIndex !== null ? String(tableColumnIndex) : null,
    tableColumnName: tableColumnName,

    ...getPosition(element),
  };

  return deleteMeaninglessAttr(dictRawAttr);
}

export function getFinalAttr(element: HTMLElement, usePath: boolean): DictFinalAttr {
  const dictAttr = getBasicAttr(element);

  /* console.log(
      "attributes(remove meaningless keys and convert all to string):",
      JSON.stringify(dictAttr, null, 2)
    ); */

  // Add path or index.
  if (usePath) {
    return {
      ...dictAttr,
      path: getPath(element),
    };
  }
  return addIndexForTheLayer(element, dictAttr);
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
        // eslint-disable-next-line @typescript-eslint/prefer-optional-chain
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

export function getPath(element: HTMLElement): string {
  // console.log("---getPath-");
  const path = [];
  let currentElement = element;
  let tagName = currentElement.tagName.toLowerCase();
  while (currentElement.parentElement && tagName !== "html") {
    const siblingIndex = getSiblingIndex(currentElement);
    // The index is calculated among siblings with the same tag name, so use :nth-of-type().
    // The first matching sibling does not need an explicit pseudo-class because querySelector() returns it first.
    path.unshift(`${tagName}${siblingIndex > 1 ? `:nth-of-type(${siblingIndex})` : ""}`);
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
    const hasSameTagSiblings =
      Array.from(element.parentNode.children).filter(
        (child) => child.tagName === element.tagName,
      ).length > 1;

    if (!hasSameTagSiblings) {
      // It has no, return 0.
      return 0;
    }
  }

  // 2. If it has, calculate the one-based index used by :nth-of-type().
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

function getIndexForTheLayer(
  originalElement: HTMLElement,
  dictAttr: DictAttrForIndex,
): DictLayerIndexAttr {
  const dictIndexAttr: DictLayerIndexAttr = {};

  // IF the current element(layer) doesn't have partent element, didn't need to add index.
  if (!originalElement.parentElement) {
    return dictIndexAttr;
  }

  const documentElementsFinal = getDocumentElements(dictAttr);
  // console.log("documentElementsFinal", documentElementsFinal);
  const childElementsFinal = getChildElements(originalElement.parentElement, dictAttr);
  // console.log("childElementsFinal", childElementsFinal);

  // Check the two arrays' count.
  if (childElementsFinal.length === 0) {
    throw new Error("Didn't find any elements match the attributes in childElementsFinal.");
  }

  if (childElementsFinal.length > 1) {
    for (let index = 0; index < childElementsFinal.length; index++) {
      if (childElementsFinal[index] === originalElement) {
        // The childIndex should also be a string like others.
        dictIndexAttr.childIndex = String(index);
        break;
      }
    }

    if (dictIndexAttr.childIndex === undefined) {
      throw new Error(
        "When childElementsFinal.length > 1, didn't find the original element in childElementsFinal.",
      );
    }
  }

  // Simular with childElementsFinal
  if (documentElementsFinal.length === 0) {
    throw new Error(
      "Didn't find any elements match the attributes in documentElementsFinal",
    );
  }
  if (documentElementsFinal.length > 1) {
    for (let index = 0; index < documentElementsFinal.length; index++) {
      if (documentElementsFinal[index] === originalElement) {
        dictIndexAttr.documentIndex = String(index);
        break;
      }
    }
    if (dictIndexAttr.documentIndex === undefined) {
      throw new Error(
        "documentElementsFinal.length > 1, didn't find the original element in documentElementsFinal.",
      );
    }
  }

  return dictIndexAttr;

  // If childElementsFinal.length === 1 and documentElementsFinal.length === 1, the indexes will not be added.
  // TODO: But will it have the situation that length >1 and index === 0? Test it later.
}

export function addIndexForTheLayer<T extends DictOriginalAttr | DictLayerHtml>(
  originalElement: HTMLElement,
  dictAttr: T,
): T & DictLayerIndexAttr {
  /* Called by each layer, locate elements using the layer's attributes.
  Compare them with the originalElement, if more than one element is found, add the attribute childIndex and documentIndex for the layer. */
  // console.log("--addIndexForTheLayer--");
  // console.log("dictAttr=", dictAttr);

  return { ...dictAttr, ...getIndexForTheLayer(originalElement, dictAttr) };
}

function getDocumentElements(dictAttrOrSlct: DictAttrForIndex): HTMLElement[] {
  // console.log("--getDocumentElements--");
  // Get the CSS Selector, it's same for the search of childIndex and documentIndex.
  const strQuerySelector = createQuerySelectorFromAttrDict(dictAttrOrSlct);

  const documentElementsTemp: NodeListOf<HTMLElement> =
    document.querySelectorAll(strQuerySelector);
  // console.log("documentElementsTemp", documentElementsTemp);

  const documentElementsFinal = Array.from(documentElementsTemp).filter((ele) =>
    filterNonQuerySelectorFromAttrDict(ele, dictAttrOrSlct),
  );

  return documentElementsFinal;
}

function getChildElements(
  parentElement: HTMLElement,
  dictAttrOrSlct: DictAttrForIndex,
): HTMLElement[] {
  // console.log("--getChildElements--");

  // Get the CSS Selector, it's same for the search of childIndex and documentIndex.
  const strQuerySelector = createQuerySelectorFromAttrDict(dictAttrOrSlct);

  const childElementsTemp: NodeListOf<HTMLElement> =
    parentElement.querySelectorAll(strQuerySelector);
  // console.log("childElementsTemp", childElementsTemp);

  const childElementsFinal = Array.from(childElementsTemp).filter((ele) =>
    filterNonQuerySelectorFromAttrDict(ele, dictAttrOrSlct),
  );

  return childElementsFinal;
}

function escapeCssAttrValue(value: string): string {
  return value
    .replace(/\\/g, "\\\\")
    .replace(/"/g, '\\"')
    .replace(/\n/g, "\\A ")
    .replace(/\r/g, "\\D ")
    .replace(/\f/g, "\\C ");
}

export function createQuerySelectorFromAttrDict(dictAttrOrSlct: DictAttrForIndex): string {
  // Join the attributes that supported by querySelectorAll.
  // console.log("--createQuerySelectorFromAttrDict--");
  // console.log("attributes to create Css Selector", dictAttr);

  const arrSelectorParts: string[] = [];

  // Add tagName if available
  if (dictAttrOrSlct.tagName) {
    arrSelectorParts.push(dictAttrOrSlct.tagName.trim());
  }

  // Add id, escaping it if necessary
  if (dictAttrOrSlct.id) {
    arrSelectorParts.push(`#${CSS.escape(dictAttrOrSlct.id.trim())}`);
  }

  // Add className(s), escaping each class
  if (dictAttrOrSlct.className) {
    const classes = dictAttrOrSlct.className.split(/\s+/).filter(Boolean);
    arrSelectorParts.push(classes.map((classTemp) => `.${CSS.escape(classTemp)}`).join(""));
  }

  // Add attributes using a loop for cleaner code
  const arrAttrToInclude = [
    "type",
    /* NOTE: I don't remember why "value" was commented out. It may be because the value attribute is unstable or unreliable for selector matching. */
    // "value",
    "name",
    "aria-label",
    "aria-labelledby",
  ];
  for (const attr of arrAttrToInclude) {
    const strTemp = dictAttrOrSlct[attr];
    if (strTemp) {
      arrSelectorParts.push(`[${attr}="${escapeCssAttrValue(strTemp)}"]`);
    }
  }

  // Handle boolean pseudo-classes like :checked and :disabled
  if (dictAttrOrSlct.checked?.toLowerCase() === "true") {
    arrSelectorParts.push(":checked");
  } else if (dictAttrOrSlct.checked?.toLowerCase() === "indeterminate") {
    arrSelectorParts.push(":indeterminate");
  }
  if (dictAttrOrSlct.disabled?.toLowerCase() === "true") {
    arrSelectorParts.push(":disabled");
  }

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
  dictAttrOrSlct: DictAttrForIndex,
): boolean {
  // console.log("--filterNonQuerySelectorFromAttrDict--");

  /** 20260501, the logic chain created by ChatGPT.
   * Filter elements that were only partially matched by querySelectorAll().
   *
   * createQuerySelectorFromAttrDict() only uses attributes that can be expressed
   * in a CSS selector, such as tagName, id, className, type, name, and some
   * simple attributes.
   *
   * However, some attributes cannot be represented reliably in a CSS selector,
   * for example innerText, directText, parentId, tableRowIndex, or regex-based
   * attributes. querySelectorAll() may therefore return elements that match the
   * CSS selector part but still do not match the full attribute dictionary.
   *
   * This function performs the second-stage filtering:
   *
   * 1. Build the current candidate element's cleaned basic attribute dictionary.
   * 2. Compare every non-querySelector attribute from dictAttr against the
   *    candidate element's attributes.
   * 3. Ignore calculated attributes used only for locating the element among
   *    similar candidates, such as childIndex and documentIndex.
   * 4. Support "-regex" keys by testing the candidate element's base attribute
   *    against the provided regular expression.
   *
   * This function is used only during attribute/selector generation, mainly in:
   *
   * getFinalAttr()
   *   -> addIndexForTheLayer()
   *   -> getIndexForTheLayer()
   *   -> getDocumentElements() / getChildElements()
   *   -> filterNonQuerySelectorFromAttrDict()
   *
   * getChildrenElementAttr()
   *   -> addIndexForTheLayer()
   *   -> getIndexForTheLayer()
   *   -> getDocumentElements() / getChildElements()
   *   -> filterNonQuerySelectorFromAttrDict()
   *
   * compareBasicAndIndexAttr()
   *   -> addIndexForTheLayer()
   *   -> getIndexForTheLayer()
   *   -> getDocumentElements() / getChildElements()
   *   -> filterNonQuerySelectorFromAttrDict()
   *
   * In the first two paths, dictAttr is generated from the current element's
   * cleaned basic attributes.
   *
   * In compareBasicAndIndexAttr(), dictAttr is a selector-like temporary
   * dictionary derived from the current element's basic attributes, then reduced
   * to only the keys that exist in the selector. This makes childIndex and
   * documentIndex calculated under the same attribute constraints as the
   * incoming selector.
   */

  // Check the attributes that don't supported by querySelectorAll.
  // Loop all attributes in the curren layer, check whether the current element has a same attribute.

  // ALthough some attributes have by checked by createQuerySelectorFromAttrDict(), use getBasicAttr() to get all is more concise in logic.
  const dictAttrCurrent = getBasicAttr(element);

  // console.log("dictAttrCurrent", dictAttrCurrent);

  const keysShouldIgnored = new Set<string>([
    "childIndex",
    "documentIndex",
    "childIndex-regex",
    "documentIndex-regex",
    "secondary-x",
    "secondary-y",
    "secondary-width",
    "secondary-height",
  ]);

  // Compare the values. As selector may delete some attributes deliberately, and key in DictOriginalAttributes may not exist in dictAttrCurrent, so should make sure the key is existing then compare.
  for (const [key, valueToCompare] of Object.entries(dictAttrOrSlct)) {
    if (keysShouldIgnored.has(key)) {
      continue;
    }

    if (key.endsWith("-regex")) {
      const strBaseKey = key.slice(0, -"-regex".length);
      const valueCurrent = dictAttrCurrent[strBaseKey];

      if (
        typeof valueCurrent !== "string" ||
        !new RegExp(`^${valueToCompare}$`, "u").test(valueCurrent)
      ) {
        return false;
      }
      // It's a regex attribute in the selector, and it matches with the current attribute, so go to check next attribute.
      console.log(`"${key}" matches: ${dictAttrCurrent[strBaseKey]}`);

      continue;
    }

    // Handle non-regex key.
    const valueCurrent = dictAttrCurrent[key];
    if (typeof valueCurrent !== "string") {
      return false;
    }
    if (valueCurrent !== valueToCompare) {
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

function booleanToString(value: boolean): BooleanString {
  return value ? "true" : "false";
}
function getCheckedState(element: HTMLInputElement): CheckedString {
  if (element.indeterminate) {
    return "indeterminate";
  }

  return booleanToString(element.checked);
}

function isMeaningfulAttrValue(value: AttrDraftValue): value is string {
  return value !== null && value !== undefined && value !== "";
}
export function deleteMeaninglessAttr(dictRawAttr: DictRawAttr): DictOriginalAttr {
  const dictOriginalAttr: DictOriginalAttr = {
    tagName: dictRawAttr.tagName,
    "secondary-x": dictRawAttr["secondary-x"],
    "secondary-y": dictRawAttr["secondary-y"],
    "secondary-width": dictRawAttr["secondary-width"],
    "secondary-height": dictRawAttr["secondary-height"],
  };

  for (const key of Object.keys(dictRawAttr)) {
    const value = dictRawAttr[key];

    if (isMeaningfulAttrValue(value)) {
      dictOriginalAttr[key] = value;
    }
  }

  return dictOriginalAttr;
}
