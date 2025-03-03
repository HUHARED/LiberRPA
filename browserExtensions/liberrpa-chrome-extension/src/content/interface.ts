// FileName: interface.ts

export interface DictHtmlSecondaryAttr {
  // These attributes is secondary.
  "secondary-x": string;
  "secondary-y": string;
  "secondary-width": string;
  "secondary-height": string;
}

export interface DictOriginalAttr extends DictHtmlSecondaryAttr {
  [key: string]: string | null | undefined;

  // The attributes that support querySelectorAll;
  tagName: string;
  id: string;
  className: string;
  type?: string | null;
  value?: string | null;
  name?: string | null;
  "aria-label"?: string | null;
  "aria-labelledby"?: string | null;
  checked?: "true" | "false" | "indeterminate" | null;
  disabled?: "true" | "false" | null;

  // The attributes that not support querySelectorAll;
  href?: string | null;
  src?: string | null;
  alt?: string | null;
  isHidden?: "true" | "false" | null;
  isDisplayedNone?: "true" | "false" | null;
  innerText?: string;
  directText?: string;
  parentId?: string | null;
  parentClass?: string | null;
  parentName?: string | null;
  isLeaf?: "true" | "false" | null;
  tableRowIndex?: string | null;
  tableColumnIndex?: string | null;
  tableColumnName?: string | null;

  // The attributes that be calculated.
  childIndex?: string | null; // Indicate the order of the current element among its siblings with the same attribute.
  documentIndex?: string | null; // Indicate the order of the current element among all elements in the document with the same attribute.
  path?: string | null; // nth-child() selector.
}

export interface DictFinalAttr extends DictHtmlSecondaryAttr {
  [key: string]: string | undefined;

  tagName: string;
  id?: string;
  className?: string;
  type?: string;
  value?: string;
  name?: string;
  "aria-label"?: string;
  "aria-labelledby"?: string;
  checked?: string;
  disabled?: string;

  href?: string;
  src?: string;
  alt?: string;
  isHidden?: string;
  isDisplayedNone?: string;
  innerText?: string;
  directText?: string;
  parentId?: string;
  parentClass?: string;
  parentName?: string;
  isLeaf?: string;
  tableRowIndex?: string;
  tableColumnIndex?: string;
  tableColumnName?: string;

  childIndex?: string;
  documentIndex?: string;
  path?: string;
}

export interface DictLayerHtml {
  [key: string]: string | undefined;

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
  checked?: string;
  "checked-regex"?: string;
  disabled?: string;
  "disabled-regex"?: string;

  href?: string;
  "href-regex"?: string;
  src?: string;
  "src-regex"?: string;
  alt?: string;
  "alt-regex"?: string;
  isHidden?: string;
  "isHidden-regex"?: string;
  isDisplayedNone?: string;
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
  isLeaf?: string;
  "isLeaf-regex"?: string;
  tableRowIndex?: string;
  "tableRowIndex-regex"?: string;
  tableColumnIndex?: string;
  "tableColumnIndex-regex"?: string;
  tableColumnName?: string;
  "tableColumnName-regex"?: string;

  // The non-basic attributes. path and index should not appear in a same time.

  childIndex?: string;
  "childIndex-regex"?: string;
  documentIndex?: string;
  "documentIndex-regex"?: string;
  path?: string;
  "path-regex"?: string;
}

export interface DictFinalAttrWithoutPosition {
  [key: string]: string | undefined;

  tagName: string;
  id?: string;
  className?: string;
  type?: string;
  value?: string;
  name?: string;
  "aria-label"?: string;
  "aria-labelledby"?: string;
  checked?: string;
  disabled?: string;

  href?: string;
  src?: string;
  alt?: string;
  isHidden?: string;
  isDisplayedNone?: string;
  innerText?: string;
  directText?: string;
  parentId?: string;
  parentClass?: string;
  parentName?: string;
  isLeaf?: string;
  tableRowIndex?: string;
  tableColumnIndex?: string;
  tableColumnName?: string;

  childIndex?: string;
  documentIndex?: string;
  path?: string;
}

export interface DictElementTreeItem {
  id: number;
  title: string;
  spec: DictFinalAttrWithoutPosition;
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
