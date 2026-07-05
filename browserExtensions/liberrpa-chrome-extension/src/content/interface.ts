// FileName: interface.ts

export interface DictHtmlSecondaryAttr {
  // These attributes is secondary.
  "secondary-x": string;
  "secondary-y": string;
  "secondary-width": string;
  "secondary-height": string;
}

export type AttrDraftValue = string | null | undefined;
type AttrFinalValue = string | undefined;
export type BooleanString = "true" | "false";
export type CheckedString = BooleanString | "indeterminate";

export interface DictRawAttr extends DictHtmlSecondaryAttr {
  [key: string]: AttrDraftValue;

  // The attributes that support querySelectorAll; - Basic attributes.
  tagName: string;
  id: string;
  className: string;
  type?: string | null;
  value?: string | null;
  name?: string | null;
  "aria-label"?: string | null;
  "aria-labelledby"?: string | null;
  checked?: CheckedString | null;
  disabled?: BooleanString | null;

  // Non-querySelector attributes.
  href?: string | null;
  src?: string | null;
  alt?: string | null;
  isHidden?: BooleanString | null;
  isDisplayedNone?: BooleanString | null;
  innerText?: string;
  directText?: string;
  parentId?: string | null;
  parentClass?: string | null;
  parentName?: string | null;
  isLeaf?: BooleanString | null;
  tableRowIndex?: string | null;
  tableColumnIndex?: string | null;
  tableColumnName?: string | null;
}

export interface DictOriginalAttr extends DictHtmlSecondaryAttr {
  [key: string]: AttrFinalValue;

  tagName: string;
  id?: string;
  className?: string;
  type?: string;
  value?: string;
  name?: string;
  "aria-label"?: string;
  "aria-labelledby"?: string;
  checked?: CheckedString;
  disabled?: BooleanString;

  href?: string;
  src?: string;
  alt?: string;
  isHidden?: BooleanString;
  isDisplayedNone?: BooleanString;
  innerText?: string;
  directText?: string;
  parentId?: string;
  parentClass?: string;
  parentName?: string;
  isLeaf?: BooleanString;
  tableRowIndex?: string;
  tableColumnIndex?: string;
  tableColumnName?: string;
}

export interface DictLayerIndexAttr {
  // Calculated attributes.
  childIndex?: string; // Indicate the order of the current element among its siblings with the same attribute.
  documentIndex?: string; // Indicate the order of the current element among all elements in the document with the same attribute.
}
interface DictLayerPathAttr {
  path?: string; // nth-child() selector.
}

export interface DictFinalAttr
  extends DictOriginalAttr,
    DictLayerIndexAttr,
    DictLayerPathAttr {}

// export type DictLayerIndexAttr = Pick<DictFinalAttr, "childIndex" | "documentIndex">;

export interface DictLayerHtml extends DictLayerIndexAttr, DictLayerPathAttr {
  [key: string]: AttrFinalValue;

  // The basic attributes.

  tagName?: string;
  "tagName-regex"?: string;
  id?: string;
  "id-regex"?: string;
  className?: string;
  "className-regex"?: string;
  type?: string;
  "type-regex"?: string;
  value?: string;
  "value-regex"?: string;
  name?: string;
  "name-regex"?: string;
  "aria-label"?: string;
  "aria-label-regex"?: string;
  "aria-labelledby"?: string;
  "aria-labelledby-regex"?: string;
  checked?: CheckedString;
  "checked-regex"?: string;
  disabled?: BooleanString;
  "disabled-regex"?: string;

  href?: string;
  "href-regex"?: string;
  src?: string;
  "src-regex"?: string;
  alt?: string;
  "alt-regex"?: string;
  isHidden?: BooleanString;
  "isHidden-regex"?: string;
  isDisplayedNone?: BooleanString;
  "isDisplayedNone-regex"?: string;
  innerText?: string;
  "innerText-regex"?: string;
  directText?: string;
  "directText-regex"?: string;
  parentId?: string;
  "parentId-regex"?: string;
  parentClass?: string;
  "parentClass-regex"?: string;
  parentName?: string;
  "parentName-regex"?: string;
  isLeaf?: BooleanString;
  "isLeaf-regex"?: string;
  tableRowIndex?: string;
  "tableRowIndex-regex"?: string;
  tableColumnIndex?: string;
  "tableColumnIndex-regex"?: string;
  tableColumnName?: string;
  "tableColumnName-regex"?: string;

  // The non-basic attributes. path and index should not appear in a same time.
  "childIndex-regex"?: string;
  "documentIndex-regex"?: string;
  "path-regex"?: string;
}

export type DictAttrForIndex = DictOriginalAttr | DictLayerHtml;

export interface DictFinalSpec extends DictLayerIndexAttr, DictLayerPathAttr {
  /* Compared with DictFinalAttr, it has no innerText, position. */
  [key: string]: AttrFinalValue;

  tagName: string;
  id?: string;
  className?: string;
  type?: string;
  value?: string;
  name?: string;
  "aria-label"?: string;
  "aria-labelledby"?: string;
  checked?: CheckedString;
  disabled?: BooleanString;

  href?: string;
  src?: string;
  alt?: string;
  isHidden?: BooleanString;
  isDisplayedNone?: BooleanString;
  directText?: string;
  parentId?: string;
  parentClass?: string;
  parentName?: string;
  isLeaf?: BooleanString;
  tableRowIndex?: string;
  tableColumnIndex?: string;
  tableColumnName?: string;
}

export interface DictElementTreeItem {
  id: number;
  title: string;
  spec: DictFinalSpec;
  children?: DictElementTreeItem[];
}

/* export interface Position {
  x: number;
  y: number;
  width: number;
  height: number;
} */

export type MouseButton = "left" | "right" | "middle";
export type ClickMode = "single_click" | "double_click" | "down" | "up";
// export type ExecutionMode = "simulate" | "api";

/* Dict Type for content.ts */

interface DictCommonAttribute {
  htmlSelector: DictLayerHtml[];
  preDelay: number;
  timeout: number;
}

type DictCommandClickMouseEvent = DictCommonAttribute & {
  commandName: "clickMouseEvent";
  button: MouseButton;
  clickMode: ClickMode;
  pressCtrl: boolean;
  pressShift: boolean;
  pressAlt: boolean;
  pressWin: boolean;
};

type DictCommandSetElementText = DictCommonAttribute & {
  commandName: "setElementText";
  text: string;
  clearBeforeWrite: boolean;
  validateText: boolean;
};

type DictCommandFocusElement = DictCommonAttribute & {
  commandName: "focusElement";
};

type DictCommandGetParentElementAttr = DictCommonAttribute & {
  commandName: "getParentElementAttr";
  upwardLevel: number;
};

type DictCommandGetChildrenElementAttr = DictCommonAttribute & {
  commandName: "getChildrenElementAttr";
};

type DictCommandSetCheckState = DictCommonAttribute & {
  commandName: "setCheckState";
  checkAction: "checked" | "unchecked" | "toggle";
};

type DictCommandGetSelection = DictCommonAttribute & {
  commandName: "getSelection";
  selectionType: "text" | "value" | "index";
};

type DictCommandSetSelection = DictCommonAttribute & {
  commandName: "setSelection";
  text: string | null;
  value: string | null;
  index: number | null;
};

interface DictCommandGetElementAttrByCoordinates {
  commandName: "getElementAttrByCoordinates";
  x: number;
  y: number;
  usePath: boolean;
}

interface DictCommandGetElementAttrBySelector {
  commandName: "getElementAttrBySelector";
  htmlSelector: DictLayerHtml[];
}

interface DictCommandGetSourceCode {
  commandName: "getSourceCode";
}

interface DictCommandGetAllText {
  commandName: "getAllText";
}

interface DictCommandGetScrollPosition {
  commandName: "getScrollPosition";
}

interface DictCommandSetScrollPosition {
  commandName: "setScrollPosition";
  x: number;
  y: number;
}

interface DictCommandExecuteJsCode {
  commandName: "executeJsCode";
  jsCode: string;
  returnImmediately: boolean;
}

export type DictCommandContent =
  | DictCommandClickMouseEvent
  | DictCommandSetElementText
  | DictCommandFocusElement
  | DictCommandGetParentElementAttr
  | DictCommandGetChildrenElementAttr
  | DictCommandSetCheckState
  | DictCommandGetSelection
  | DictCommandSetSelection
  | DictCommandGetElementAttrByCoordinates
  | DictCommandGetElementAttrBySelector
  | DictCommandGetSourceCode
  | DictCommandGetAllText
  | DictCommandGetScrollPosition
  | DictCommandSetScrollPosition
  | DictCommandExecuteJsCode;
