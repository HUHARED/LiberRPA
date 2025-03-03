// FileName: elementFunc.ts
import {
  DictLayerHtml,
  DictFinalAttr,
  DictElementTreeItem,
  DictFinalAttrWithoutPosition,
} from "./interface";
import { findElementWithPredelay } from "./timeFunc";
import { getBasicAttr, getFinalAttr, addIndexForTheLayer } from "./elementAttrFunc";

export async function focusElement(
  selector: DictLayerHtml[],
  preExecutionDelay: number = 300
): Promise<void> {
  console.log("--focusElement--");
  const element: HTMLElement = await findElementWithPredelay(selector, preExecutionDelay);

  element.focus();
}

export async function getParentElementAttr(
  selector: DictLayerHtml[],
  upwardLevel: number = 1,
  preExecutionDelay: number = 300
): Promise<DictFinalAttr> {
  console.log("--getParentAttr--");
  let element: HTMLElement = await findElementWithPredelay(selector, preExecutionDelay);
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
  preExecutionDelay: number = 300
): Promise<DictFinalAttr[]> {
  console.log("--getParentAttr--");
  let element: HTMLElement = await findElementWithPredelay(selector, preExecutionDelay);
  const arrChilrenElementAttr: DictFinalAttr[] = [];
  const arrChilrenElement = Array.from(element.children) as HTMLElement[];

  arrChilrenElement.forEach((childElement) => {
    // Only use index on html parment element, due to uia element has no path attributes.
    // Just need its attributes. Not handle upward layer.
    const dictAttr = getBasicAttr(childElement);
    addIndexForTheLayer(childElement, dictAttr);
    arrChilrenElementAttr.push(dictAttr as DictFinalAttr);
  });

  return arrChilrenElementAttr;
}

export async function setCheckState(
  selector: DictLayerHtml[],
  checkAction: "checked" | "unchecked" | "toggle" = "checked",
  preExecutionDelay: number = 300
): Promise<void> {
  console.log("--setCheckState--");

  let element: HTMLElement = await findElementWithPredelay(selector, preExecutionDelay);

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
        throw new Error(`Unsupported check action: ${checkAction}`);
    }
  } else {
    throw new Error("The selected element is not a checkbox or radio button.");
  }
}

export async function getSelection(
  selector: DictLayerHtml[],
  selectionType: "text" | "value" | "index",
  preExecutionDelay: number = 300
): Promise<string | number> {
  console.log("--getSelection--");

  let element: HTMLElement = await findElementWithPredelay(selector, preExecutionDelay);

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
      throw new Error(`Unknown selectionType: '${selectionType}'`);
  }
}

export async function setSelection(
  selector: DictLayerHtml[],
  text: string | null,
  value: string | null,
  index: number | null,
  preExecutionDelay: number = 300
): Promise<void> {
  console.log("--setSelection--");

  // Ensure exactly one parameter is non-null
  const parameters = [text, value, index].filter((param) => param !== null);
  if (parameters.length !== 1) {
    throw new Error(
      "Exactly one of 'text', 'value', or 'index' must be non-null to set the selection."
    );
  }

  let element: HTMLElement = await findElementWithPredelay(selector, preExecutionDelay);

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
          arrOptions.map((item) => item.text)
        )}`
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
          arrOptions.map((item) => item.value)
        )}`
      );
    }
  }
  if (index !== null) {
    if (index >= 0 && Number.isInteger(index) && index < element.options.length) {
      element.selectedIndex = index;
    } else {
      throw new Error(
        `Index out of range for select options. range is [0, ${arrOptions.length - 1}]`
      );
    }
  }
}

export function getElementTree(
  targetElement: HTMLElement,
  usePath: boolean
): [DictElementTreeItem[], number[], number] | null {
  console.log("--getElementTree--");

  try {
    const arrExpanedId: number[] = [0]; // the <html>'s id is 0, it should be opened always.
    let intActivedId: number = 0;

    function* idGenerator(): Generator<number, void, unknown> {
      let i = 0;
      while (true) {
        yield i++;
      }
    }
    const idObj = idGenerator();

    function handleSpec(spec: DictFinalAttrWithoutPosition): void {
      // innerText may have too many text, delete it.
      delete spec.innerText;
      if (spec.directText && spec.directText.length > 1024) {
        spec.directText =
          "The directText is too long (longer than 1024 characters), so not show it in Element Tree.";
      }
      delete spec["secondary-x"];
      delete spec["secondary-y"];
      delete spec["secondary-width"];
      delete spec["secondary-height"];
    }

    function getChildrenSpecRecursive(
      elementParent: HTMLElement,
      usePath: boolean
    ): DictElementTreeItem[] {
      const arrChildren: DictElementTreeItem[] = [];

      const arrChilrenElement = Array.from(elementParent.children) as HTMLElement[];
      for (const element of arrChilrenElement) {
        const intId = idObj.next().value as number;

        if (element.contains(targetElement) && element !== targetElement) {
          arrExpanedId.push(intId);
        }

        if (element === targetElement) {
          intActivedId = intId;
        }

        const specTemp: DictFinalAttrWithoutPosition = getFinalAttr(element, usePath);
        handleSpec(specTemp);

        const dictTemp: DictElementTreeItem = {
          id: intId,
          title:
            specTemp.tagName +
            (specTemp.id ? "-" + specTemp.id : "") +
            (specTemp.name ? "-" + specTemp.name : ""),
          spec: specTemp,
          children: getChildrenSpecRecursive(element, usePath),
        };

        if (dictTemp.children?.length === 0) {
          delete dictTemp.children;
        }

        arrChildren.push(dictTemp);
      }

      return arrChildren;
    }

    let rootElement = document.documentElement;

    const specTemp: DictFinalAttrWithoutPosition = getFinalAttr(rootElement, usePath);
    handleSpec(specTemp);

    const arrFinalTree: DictElementTreeItem[] = [
      {
        id: idObj.next().value as number,
        title: rootElement.tagName.toLowerCase(),
        spec: specTemp,
        children: getChildrenSpecRecursive(rootElement, usePath),
      },
    ];

    console.log("--getElementTree done--");
    return [arrFinalTree, arrExpanedId, intActivedId];
  } catch (e) {
    console.error(e);
    return null;
  }
}
