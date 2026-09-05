// FileName: elementFunc.ts
import type {
  DictLayerHtml,
  DictFinalAttr,
  DictElementTreeItem,
  DictFinalSpec,
  ElementTreeResult,
} from "./interface";
import { findElementWithPredelay } from "./timeFunc";
import { getBasicAttr, getFinalAttr, addIndexForTheLayer } from "./elementAttrFunc";

export async function focusElement(
  selector: DictLayerHtml[],
  preDelay: number = 300,
): Promise<void> {
  console.log("--focusElement--");
  const element: HTMLElement = await findElementWithPredelay(selector, preDelay);

  element.focus();
}

export async function getParentElementAttr(
  selector: DictLayerHtml[],
  upwardLevel: number = 1,
  preDelay: number = 300,
): Promise<DictFinalAttr> {
  console.log("--getParentAttr--");
  let element: HTMLElement = await findElementWithPredelay(selector, preDelay);
  for (let index = 0; index < upwardLevel; index++) {
    if (element.parentElement) {
      element = element.parentElement;
    }
  }

  // Only use index on html parment element, due to uia element has no path attributes.
  // Just need its attributes. Not handle upward layer.
  return getFinalAttr(element, false);
}

export async function getChildrenElementAttr(
  selector: DictLayerHtml[],
  preDelay: number = 300,
): Promise<DictFinalAttr[]> {
  console.log("--getChildrenElementAttr--");
  const element: HTMLElement = await findElementWithPredelay(selector, preDelay);
  const arrChildrenElementAttr: DictFinalAttr[] = [];
  const arrChildrenElement = getHtmlElementChildren(element);

  arrChildrenElement.forEach((childElement) => {
    // Only use index on html parment element, due to uia element has no path attributes.
    // Just need its attributes. Not handle upward layer.
    arrChildrenElementAttr.push(
      addIndexForTheLayer(childElement, getBasicAttr(childElement)),
    );
  });

  return arrChildrenElementAttr;
}

export async function setCheckState(
  selector: DictLayerHtml[],
  checkAction: "checked" | "unchecked" | "toggle" = "checked",
  preDelay: number = 300,
): Promise<void> {
  console.log("--setCheckState--");

  const element: HTMLElement = await findElementWithPredelay(selector, preDelay);

  if (
    element instanceof HTMLInputElement &&
    (element.type === "checkbox" || element.type === "radio")
  ) {
    switch (checkAction) {
      case "checked":
        if (!element.checked) {
          // Only set checked if it is not already checked
          element.checked = true;
        }
        break;
      case "unchecked":
        if (element.checked) {
          // Only set unchecked if it is not already unchecked
          element.checked = false;
        }
        break;
      case "toggle":
        element.indeterminate = false;
        element.checked = !element.checked; // Toggle the checked state
        break;
      default:
        return assertNever(checkAction);
    }
  } else {
    throw new Error("The selected element is not a checkbox or radio button.");
  }
}

export async function getSelection(
  selector: DictLayerHtml[],
  selectionType: "text" | "value" | "index",
  preDelay: number = 300,
): Promise<string | number> {
  console.log("--getSelection--");

  const element: HTMLElement = await findElementWithPredelay(selector, preDelay);

  if (!(element instanceof HTMLSelectElement)) {
    throw new Error("The target element is not a <select> element.");
  }

  if (element.selectedIndex === -1) {
    throw new Error("No option is selected.");
  }

  switch (selectionType) {
    case "text":
      return element.options[element.selectedIndex].text;
    case "value":
      return element.value;
    case "index":
      return element.selectedIndex;
    default:
      return assertNever(selectionType);
  }
}

export async function setSelection(
  selector: DictLayerHtml[],
  text: string | null,
  value: string | null,
  index: number | null,
  preDelay: number = 300,
): Promise<void> {
  console.log("--setSelection--");

  // Ensure exactly one parameter is non-null
  const parameters = [text, value, index].filter((param) => param !== null);
  if (parameters.length !== 1) {
    throw new Error(
      "Exactly one of 'text', 'value', or 'index' must be non-null to set the selection.",
    );
  }

  const element: HTMLElement = await findElementWithPredelay(selector, preDelay);

  if (!(element instanceof HTMLSelectElement)) {
    throw new Error("The target element is not a <select> element.");
  }

  const arrOptions = Array.from(element.options);

  if (text !== null) {
    const matchedByText = arrOptions.findIndex((option) => option.text === text);
    if (matchedByText !== -1) {
      element.selectedIndex = matchedByText;
    } else {
      throw new Error(
        `No matching option found for the given text '${text}'. All options' texts are: ${JSON.stringify(
          arrOptions.map((item) => item.text),
        )}`,
      );
    }
  }
  if (value !== null) {
    const matchedByValue = arrOptions.findIndex((option) => option.value === value);
    if (matchedByValue !== -1) {
      element.selectedIndex = matchedByValue;
    } else {
      throw new Error(
        `No matching option found for the given value '${value}'. All options' values are:${JSON.stringify(
          arrOptions.map((item) => item.value),
        )}`,
      );
    }
  }
  if (index !== null) {
    if (index >= 0 && Number.isInteger(index) && index < element.options.length) {
      element.selectedIndex = index;
    } else {
      throw new Error(
        `Index out of range for select options. range is [0, ${arrOptions.length - 1}]`,
      );
    }
  }
}

const HTML_ELEMENT_TREE_TIMEOUT_MS = 10_000;
const HTML_ELEMENT_TREE_MAX_NODE_COUNT = 5_000;
const HTML_ELEMENT_TREE_MAX_DEPTH = 256;
const SET_HTML_ELEMENT_TREE_IGNORED_ATTRIBUTE = new Set<string>([
  "innerText",
  "secondary-x",
  "secondary-y",
  "secondary-width",
  "secondary-height",
]);

export function getElementTree(
  targetElement: HTMLElement,
  usePath: boolean,
): ElementTreeResult {
  console.log("--getElementTree start--");

  const floatStartedAt = performance.now();
  const floatDeadline = floatStartedAt + HTML_ELEMENT_TREE_TIMEOUT_MS;
  const arrExpandedId: number[] = [0]; // The <html> element's ID is 0 and should always be expanded.
  let intActivatedId: number | undefined;
  let intNextElementId = 0;
  let intNodeCount = 0;

  function assertWithinBuildLimits(intDepth: number): void {
    if (intDepth >= HTML_ELEMENT_TREE_MAX_DEPTH) {
      throw new Error(
        `HTML Element Tree depth exceeded ${HTML_ELEMENT_TREE_MAX_DEPTH} levels.`,
      );
    }

    if (performance.now() > floatDeadline) {
      throw new Error(
        `HTML Element Tree generation exceeded ${HTML_ELEMENT_TREE_TIMEOUT_MS} milliseconds.`,
      );
    }

    intNodeCount += 1;
    if (intNodeCount > HTML_ELEMENT_TREE_MAX_NODE_COUNT) {
      throw new Error(
        `HTML Element Tree exceeded ${HTML_ELEMENT_TREE_MAX_NODE_COUNT} elements.`,
      );
    }
  }

  function getNextElementId(): number {
    return intNextElementId++;
  }

  function getSpec(dictFinalAttr: DictFinalAttr): DictFinalSpec {
    const dictFinalSpec: DictFinalSpec = { tagName: dictFinalAttr.tagName };

    for (const key of Object.keys(dictFinalAttr)) {
      // innerText may have too much text, and positions are not part of a specification layer.
      if (SET_HTML_ELEMENT_TREE_IGNORED_ATTRIBUTE.has(key)) {
        continue;
      }

      const value = dictFinalAttr[key];

      if (key === "directText" && value && value.length > 1024) {
        dictFinalSpec.directText =
          "The directText is too long (longer than 1024 characters), so not show it in Element Tree.";
        continue;
      }

      dictFinalSpec[key] = value;
    }

    return dictFinalSpec;
  }

  function createTreeItem(element: HTMLElement, intDepth: number): DictElementTreeItem {
    assertWithinBuildLimits(intDepth);

    const intId = getNextElementId();
    if (element !== targetElement && element.contains(targetElement) && intId !== 0) {
      arrExpandedId.push(intId);
    }
    if (element === targetElement) {
      intActivatedId = intId;
    }

    const dictFinalSpec = getSpec(getFinalAttr(element, usePath));
    if (performance.now() > floatDeadline) {
      throw new Error(
        `HTML Element Tree generation exceeded ${HTML_ELEMENT_TREE_TIMEOUT_MS} milliseconds.`,
      );
    }

    const dictTreeItem: DictElementTreeItem = {
      id: intId,
      title:
        dictFinalSpec.tagName +
        (dictFinalSpec.id ? "-" + dictFinalSpec.id : "") +
        (dictFinalSpec.name ? "-" + dictFinalSpec.name : ""),
      attributes: dictFinalSpec,
    };

    const arrChildItem = getHtmlElementChildren(element).map((elementChild) =>
      createTreeItem(elementChild, intDepth + 1),
    );
    if (arrChildItem.length > 0) {
      dictTreeItem.children = arrChildItem;
    }

    return dictTreeItem;
  }

  const rootElement = document.documentElement;
  const rootItem = createTreeItem(rootElement, 0);

  if (intActivatedId === undefined) {
    throw new Error("The target HTML element was not found in the generated Element Tree.");
  }

  const floatElapsedMs = performance.now() - floatStartedAt;
  console.log(
    `--getElementTree done-- nodes=${intNodeCount}, elapsedMs=${floatElapsedMs.toFixed(1)}`,
  );

  return [[rootItem], arrExpandedId, intActivatedId];
}

function assertNever(value: never): never {
  throw new Error(`Unexpected value: ${JSON.stringify(value)}`);
}

function getHtmlElementChildren(element: Element): HTMLElement[] {
  return Array.from(element.children).filter(
    (child): child is HTMLElement => child instanceof HTMLElement,
  );
}
