// FileName: commonFunc.ts
import {
  DictFinalAttr,
  DictLayerHtml,
  DictOriginalAttr,
  DictElementTreeItem,
} from "./interface";
import { getBasicAttr, getFinalAttr, getPath } from "./elementAttrFunc";
import {
  findElementByPath,
  compareBasicAttr,
  findElementByQuerySelectorAttr,
  compareBasicAndIndexAttr,
} from "./elementMatchFunc";
import { convertScreenPositionToViewport } from "./positionCalculation";
import { getElementTree } from "./elementFunc";

export function getElementAttrByCoordinates(
  x: number,
  y: number,
  usePath: boolean
): [DictFinalAttr[], [DictElementTreeItem[], number[], number] | null] {
  console.log("--getElementAttrByCoordinates--");

  const tempElement = getElementByCoordinates(x, y);

  if (!tempElement) {
    throw new Error(
      `Didn't found element in the coordinates (${x}, ${y}), maybe the web page scaling is not 100%?`
    );
  }

  return [getElementAttr(tempElement, usePath), getElementTree(tempElement, usePath)];
}

export function getElementAttr(
  targetElement: HTMLElement,
  usePath: boolean
): DictFinalAttr[] {
  console.log("--getElementAttr--");

  const arraySelectorsReturn: DictFinalAttr[] = [];

  // Create the element array, the first element is the target element.
  const arrElementTree: HTMLElement[] = [targetElement];

  // Use the loop to get all parent elements.
  let elementCurrent: HTMLElement | null = targetElement;
  while (elementCurrent && elementCurrent.parentNode instanceof HTMLElement) {
    const elementParent: HTMLElement = elementCurrent.parentNode;
    arrElementTree.unshift(elementParent);
    elementCurrent = elementParent;
  }

  // Each element represents a layer in the whole selector tree. Generate the selector for all.
  arrElementTree.forEach((element) => {
    const dictAttr = getFinalAttr(element, usePath);
    arraySelectorsReturn.push(dictAttr);
  });

  return arraySelectorsReturn;
}

export function getElementAttrBySelector(arrSelector: DictLayerHtml[]): DictOriginalAttr {
  console.log("--getElementAttrBySelector--");
  return getBasicAttr(findElementBySelector(arrSelector));
}

export function findElementBySelector(arrSelector: DictLayerHtml[]): HTMLElement {
  console.log("--findElementBySelector--");
  console.log("arrSelector=", JSON.stringify(arrSelector, null, 2));
  // For each layer, find one target element in its parent element.

  /* The whole logic for each layer's search:
        If selector has "path", use path to find the one element, then compare other attributes.
        Otherwise, get a list of elements by attributes which support querySelectorAll.
                  Then, if selector has "path-regex", compare it first, then compare other attributes.
                        If selector has index, get index and compare index and other attributes.
                        Otherwise (selector has only basic attributes), compare attributes.

    A prerequisite: path and childIndex or documentIndex(and their -regex type) will not appear together normally, unless the user write a wrong selector, should not use too much time to handle it carefully.
  */

  // Starting from the document. Find an element to be a new search start point. After the loop done, return the element.
  let elementFound: HTMLElement | Document = document;

  for (let i = 0; i < arrSelector.length; i++) {
    console.log(`Previous elementFound: `, elementFound);
    console.log(`selector layer ${i}`);

    const selector = arrSelector[i];
    console.log(selector);
    deleteZeroIndex(selector);

    // selector will be modified, so create a backup to for debugging.
    const selectorBackup = structuredClone(selector);

    if (selector.path) {
      // The branch of "path".
      console.log("Find element by path.");

      const elementByPath = findElementByPath(elementFound, selector.path);
      checkWhetherContinue(elementByPath, i, selectorBackup);
      // "path" is useless now.
      delete selector.path;

      const boolSame = compareBasicAttr(elementByPath as HTMLElement, selector);
      checkWhetherContinue(boolSame, i, selectorBackup);

      elementFound = elementByPath as HTMLElement;
      // Use the elementFound to find next layer's target.
      continue;
    }

    // Have no path, it may have path-regex or index.
    console.log("Find element array by basic attributes.");
    // Get the list by attributes which support querySelectorAll.
    const arrElementTemp: NodeListOf<HTMLElement> = findElementByQuerySelectorAttr(
      selector,
      elementFound
    );
    console.log(`arrElementTemp=`, arrElementTemp);

    let boolFoundedInArray = false;
    for (const element of arrElementTemp) {
      if (selector["path-regex"]) {
        // The branch of "path-regex".
        console.log("Check path-regex.");

        if (
          new RegExp(`^${selector["path-regex"]}$`, "u").test(getPath(element)) === true
        ) {
          // "path-regex" is useless now.
          delete selector["path-regex"];

          const boolSame = compareBasicAttr(element, selector);
          if (boolSame) {
            elementFound = element;
            boolFoundedInArray = true;
            // Quit the loop for other elements in the arrya.
            break;
          }
        }
      } else if (
        selector["childIndex"] ||
        selector["childIndex-regex"] ||
        selector["documentIndex"] ||
        selector["documentIndex-regex"]
      ) {
        // The branch of basic and index.
        const boolSame = compareBasicAndIndexAttr(element, selector);

        if (boolSame) {
          elementFound = element;
          boolFoundedInArray = true;
          // Quit the loop for other elements in the arrya.
          break;
        }
      } else {
        // The branch of basic.
        const boolSame = compareBasicAttr(element, selector);

        if (boolSame) {
          elementFound = element;
          boolFoundedInArray = true;
          break;
        }
      }
    }
    checkWhetherContinue(boolFoundedInArray, i, selectorBackup);
  }

  const temp: HTMLElement = elementFound as HTMLElement;
  moveIntoViewIfNeeded(temp);

  // Highlight the element for debugging, delete it later.
  /* const rect = temp.getBoundingClientRect();
  createTestOverlay(rect.left, rect.top, rect.width, rect.height);
  setTimeout(() => {
    removeTestOverlay();
  }, 1000); */

  return elementFound as HTMLElement;
}

function checkWhetherContinue(
  checkValue: boolean | HTMLElement | null,
  layer: number,
  selector: DictLayerHtml
) {
  // If it's falsy, throw an error to stop the process.
  console.log("--checkFindResult--");

  if (!checkValue) {
    throw new Error(
      `Not found the target element by the selector (layer ${layer}) :${JSON.stringify(
        selector,
        null,
        2
      )}`
    );
  }
}

function deleteZeroIndex(selector: DictLayerHtml) {
  // If a index attribute is "0", it is useless, so delete it.
  for (const keyName of [
    "childIndex",
    "childIndex-regex",
    "documentIndex",
    "documentIndex-regex",
  ]) {
    if (selector[keyName] === "0") {
      console.warn(`${keyName} is 0, delete it.`);
      delete selector[keyName];
    }
  }
}

// let overlayForMouseHover: HTMLElement | null;

function getElementByCoordinates(x: number, y: number): HTMLElement | null {
  const { elementX, elementY } = convertScreenPositionToViewport(x, y);

  // console.log(elementX, elementY);

  const elementTemp = document.elementFromPoint(elementX, elementY);
  if (elementTemp instanceof HTMLElement) {
    /* const rect = elementTemp.getBoundingClientRect();
    createTestOverlay(rect.left, rect.top, rect.width, rect.height);
    setTimeout(() => {
      removeTestOverlay();
    }, 1000); */

    return elementTemp;
  }

  return null;
}

/* function createTestOverlay(
  x: number,
  y: number,
  width: number = 100,
  height: number = 100
): void {
  // Create a overlay to check weather the point is I want.
  console.log("--createOverlay--");

  removeTestOverlay();

  overlayForMouseHover = document.createElement("div");
  overlayForMouseHover.style.position = "absolute";
  overlayForMouseHover.style.left = `${x}px`;
  overlayForMouseHover.style.top = `${y}px`;
  overlayForMouseHover.style.width = `${width}px`;
  overlayForMouseHover.style.height = `${height}px`;
  overlayForMouseHover.style.backgroundColor = "rgba(93, 173, 226, 0.42)"; // Semi-transparent blue
  overlayForMouseHover.style.border = "2px solid rgba(255, 0, 0, 0.84)";
  overlayForMouseHover.style.zIndex = "1000";
  overlayForMouseHover.style.pointerEvents = "none"; // Allow clicks to pass through

  document.body.appendChild(overlayForMouseHover);
}

function removeTestOverlay(): void {
  console.log("--removeOverlay--");
  if (overlayForMouseHover) {
    overlayForMouseHover.remove();
    overlayForMouseHover = null;
  }
} */

function moveIntoViewIfNeeded(targetElement: HTMLElement) {
  const rect = targetElement.getBoundingClientRect();

  // 1. Check if it's within the viewport boundaries
  let boolInViewPort =
    rect.top >= 0 &&
    rect.left >= 0 &&
    rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
    rect.right <= (window.innerWidth || document.documentElement.clientWidth);

  // 2. Check if it's covered by another element: test the center of the target.
  const centerX = (rect.left + rect.right) / 2;
  const centerY = (rect.top + rect.bottom) / 2;
  let boolCovered = false;

  // Make sure center is within the window to avoid errors
  if (
    centerX >= 0 &&
    centerX <= window.innerWidth &&
    centerY >= 0 &&
    centerY <= window.innerHeight
  ) {
    const topElement = document.elementFromPoint(centerX, centerY);
    // If the element at the center is not our target or a child of our target, the target is probably covered.
    if (topElement && !targetElement.contains(topElement)) {
      boolCovered = true;
    }
  }

  // If it's not in the viewport or is covered, scroll it into view
  if (!boolInViewPort || boolCovered) {
    targetElement.scrollIntoView({
      behavior: "instant",
      // try "center" so it's less likely to be hidden by headers/footers
      block: "center",
      inline: "nearest",
    });
  }
}
