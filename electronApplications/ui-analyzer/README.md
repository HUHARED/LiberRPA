# UI Analyzer

UI Analyzer is the selector-inspection and selector-authoring tool used by LiberRPA.

It is a separate Electron application that works with **LiberRPA Local Server** to indicate, inspect, edit, and validate automation targets.

UI Analyzer supports four selector categories:

| Selector           | Best suited for                                                                 |
| ------------------ | ------------------------------------------------------------------------------- |
| `SelectorUia`    | Windows applications that expose Microsoft UI Automation information            |
| `SelectorHtml`   | Supported elements in normal Chrome web pages                                   |
| `SelectorImage`  | Screen regions where semantic UIA/HTML information is unavailable or unsuitable |
| `SelectorWindow` | Application-window matching without a more specific child element               |

For HTML indication and validation, the **LiberRPA Chrome Extension** must also be installed, connected, and able to access the target page.

For browser runtime behavior and limitations, see the [Chrome Extension documentation](../../browserExtensions/liberrpa-chrome-extension/README.md).

For the local communication layer used by UI Analyzer, see [LiberRPA Local Server](../../docs/LocalServer.md).

> **Note:**
>
> Screenshots and animations in this document are provided for reference. As LiberRPA evolves, the current interface may differ slightly in appearance or wording, but these minor differences do not affect the documented workflow or functionality.

## Contents

- [Connection Status](#connection-status)
- [Choosing a Selector Type](#choosing-a-selector-type)
- [Indicating Elements](#indicating-elements)
- [Editing Selectors](#editing-selectors)
- [Validating Selectors](#validating-selectors)
- [Element Tree](#element-tree)
- [Other Interface Controls](#other-interface-controls)
- [Selector Reference](#selector-reference)
- [Change Log](#change-log)

---

## Connection Status

UI Analyzer requires LiberRPA Local Server.

If the Local Server is not connected, the window title changes to:

```text
UI Analyzer - No Local Server
```

The icon in the top-right corner also shows the current connection state:

<img src="./md_images/README/SocketConnected.svg" width="32" height="32" alt="Connected">

**Connected**

<img src="./md_images/README/SocketDisconnected.svg" width="32" height="32" alt="Not connected">

**Not connected**

If the connection is lost after `InitLiberRPA.exe` has been run again, restart UI Analyzer and LiberRPA Local Server so that both use the current local authentication information.

---

## Choosing a Selector Type

Prefer the most semantic selector that reliably identifies the target.

A practical order is:

1. **HTML** for supported elements in normal Chrome web pages.
2. **UIA** for Windows applications and browser chrome that expose useful UI Automation information.
3. **Image** when semantic selectors are unavailable or unreliable.
4. **Window** when only the application window itself needs to be identified.

This is not a strict hierarchy. The best selector is the one that remains understandable and stable for the target application.

### HTML vs UIA in Chrome

A Chrome page can expose some information through Windows UI Automation, but HTML indication is usually preferable for normal web-page elements because it works with DOM structure and attributes.

Use UIA when the target is part of the browser UI itself or when HTML automation is not appropriate.

---

## Indicating Elements

UI Analyzer creates selectors by indicating a target and then showing the captured hierarchy and attributes for review.

### Indicate delay

**Indicate delay** waits before the indication operation starts.

Use it when you need time to:

- bring the target application into view;
- switch to another window;
- focus the correct Chrome window and tab.

It is particularly useful for HTML indication because the Chrome Extension operates on the active supported tab in the last-focused normal Chrome window.

`Indicate delay` is not the same as **Match timeout**, which controls selector matching during validation.

![1740149355230](md_images/README/1740149355230.png)

### Minimize UI Analyzer during indication

Enable **Minimize** if UI Analyzer would otherwise cover the target.

UI Analyzer restores itself when the indication:

- completes;
- is canceled;
- times out.

![1740149627121](md_images/README/1740149627121.png)

### Indicate UIA Element

Use **UIA** indication for an element that exposes Microsoft UI Automation information.

Single-click the target with the left mouse button.

Press:

```text
Esc
```

to cancel.

After indication starts, UI Analyzer waits for the selection for a limited time. If no target is selected, the operation times out automatically.

![IndicateUIA](md_images/README/IndicateUIA.gif)

The resulting selector is a [`SelectorUia`](#selectoruia).

For each existing UIA hierarchy layer, LiberRPA prepares a concise default attribute recommendation. It always keeps `ControlTypeName` and an existing `Depth`, then considers readable identity attributes in this order: `Name`, `ClassName`, `AriaRole`, `AccessKey`, and `AcceleratorKey`. It starts with one identity attribute and adds at most three when more distinction is needed. If multiple controls still match, it recalculates `Index` from the recommended attributes. `HelpText`, `AriaProperties`, long values, and multiline values are not selected by default.

The existing UIA hierarchy is preserved. All captured attributes remain visible in **Attribute Editor**; attributes outside the recommendation are simply unchecked and can still be restored or edited. `AutomationId` remains a secondary inspection attribute and is not used for generated selectors.

### Indicate HTML Element

Use **HTML** indication for supported elements in a normal Chrome web page.

Requirements:

- LiberRPA Local Server is running;
- Chrome is running;
- LiberRPA Chrome Extension is installed and connected;
- the target page is a supported page that the extension can access.

![IndicateHtml](md_images/README/IndicateHtml.gif)

During indication, LiberRPA works with the active supported tab in the last-focused normal Chrome window.

If the target element is outside the viewport, the browser integration can scroll it into view as part of the element operation.

When normal HTML attributes are not enough to distinguish the target reliably, UI Analyzer can also use index attributes or generated path information.

The two HTML index attributes are:

- **`documentIndex`** — the target element's zero-based position among all elements in the document that match the same selected attributes.
- **`childIndex`** — the target element's zero-based position among matching descendant elements under the parent search area. It is not limited to direct children.

Index values start from `0`. The first match normally does not need an explicit index, so index fields are most useful for the second or later matching element.

![1740147909983](md_images/README/1740147909983.png)

Generated path information uses CSS-selector-style structure with `:nth-of-type()` where needed. It is another fallback when normal attributes are not sufficient.

For the complete matching rules, including regex support, index behavior, and path fields, see [`SelectorHtml`](#selectorhtml).

The resulting selector is a [`SelectorHtml`](#selectorhtml).

For attribute-and-index HTML indication, the Chrome Extension also prepares a concise default recommendation against the live DOM. It keeps `tagName`, may keep `type`, and considers readable identity attributes in this order:

```text
id
name
aria-label
aria-labelledby
alt
directText
tableColumnName
className
```

When the original target does not need an index, the recommendation uses at most three identity attributes and performs at most two uniqueness checks. When the original target already contains an index, it conservatively keeps every suitable identity attribute and recalculates `childIndex` / `documentIndex` from the attributes that remain. Long, multiline, obviously generated, or state-like values are not selected by default. `directText` and `tableColumnName` are considered only when they are single-line values no longer than 80 characters. Path mode defaults to `tagName` plus the generated `path`.

All captured target attributes remain visible in **Attribute Editor**; attributes outside the recommendation are simply unchecked, so the user can restore or edit them.

For iframe, Shadow DOM, restricted-page, `file://`, and other Chrome-specific limitations, see the [Chrome Extension documentation](../../browserExtensions/liberrpa-chrome-extension/README.md#current-limitations).

### Indicate Image Element

Use **Image** indication when UIA and HTML selectors are unavailable or unsuitable.

Once the screen is paused, indicated by a green border around the screen, drag with the left mouse button to select the target region.

![IndicateImage](md_images/README/IndicateImage.gif)

You can configure:

- the default image-matching confidence;
- whether grayscale matching is used.

![1740148367585](md_images/README/1740148367585.png)

![1740148434216](md_images/README/1740148434216.png)

The resulting selector is a [`SelectorImage`](#selectorimage).

Image-based automation is inherently more sensitive than semantic selectors to display scaling, resolution, rendering, and visual changes in the target application.

### Indicate Window Element

Use **Window** indication when the automation needs to identify an application window without selecting a more specific child element.

![IndicateWindow](md_images/README/IndicateWindow.gif)

The resulting selector is a [`SelectorWindow`](#selectorwindow).

For every indicated selector, LiberRPA also prepares a concise default recommendation for the `window` section. It always keeps `ControlTypeName`, normally keeps `ProcessName`, and then considers readable `ClassName` and `Name` values in that order when the simpler combination is not sufficient. If multiple top-level controls still match, it recalculates `Index` from the recommended attributes. Window names or class names that are empty, multiline, or longer than 120 characters are not selected by default.

All captured window attributes remain visible in **Attribute Editor**; attributes outside the recommendation are simply unchecked and can still be restored or edited.

UIA, HTML, and Image selectors also contain a `window` section. UI Analyzer adds this window context automatically before the more specific target information.

---

## Editing Selectors

After indication, use **Element Hierarchy** and **Attribute Editor** to decide which information should remain in the selector.

Select a hierarchy layer, then check or uncheck attributes.

The **JSON Selector** updates automatically.

![-omit-regex](md_images/README/-omit-regex.gif)

### Prefer stable attributes

A selector should normally use the smallest set of attributes that identifies the intended element reliably.

Prefer values that represent stable application semantics.

For values that change predictably, use a `-regex` field where supported rather than hard-coding a volatile value.

### Edit JSON directly

You can also edit **JSON Selector** directly.

![1740148560108](md_images/README/1740148560108.png)

Direct JSON editing accepts:

- standard JSON generated by UI Analyzer;
- JSON-like text with trailing commas, such as selectors copied from Black-formatted Python code.

It does not accept Python syntax such as:

- single-quoted strings;
- `True`, `False`, or `None`;
- `#` comments.

> Direct JSON edits do not update the Attribute Editor representation.

Use **Validate** after manual edits.

---

## Validating Selectors

Use **Validate** to test whether the current JSON Selector can locate the intended target.

![Validate](md_images/README/Validate.gif)

### Match timeout

**Match timeout** controls how long selector validation attempts to find a match.

![1740149519175](md_images/README/1740149519175.png)

It does not change **Indicate delay**.

A red validation result means the Selector is valid, but no matching target was found before the Match timeout. Invalid Selector data, unavailable browser integration, and other operation failures are shown as errors instead of being reported as an ordinary non-match.

When a selector becomes unreliable after an application or page changes, validation is the quickest way to determine whether the problem is:

- the target window;
- a hierarchy layer;
- one selected attribute;
- an index/path fallback;
- the target application/browser state.

---

## Element Tree

The **Element Tree** provides a broader view of elements available under the selected window or target context.

For HTML indication, LiberRPA returns the selected element first and then builds the DOM Element Tree once. It does not rebuild the complete tree while the pointer is moving.

HTML Element Tree generation stops after 10 seconds, 5,000 elements, or 256 hierarchy levels. The selected Selector remains available if tree generation fails.

Use the Element Tree when you need to understand the surrounding UI hierarchy rather than indicating only one element.

![CheckElementTree](md_images/README/CheckElementTree.gif)

---

## Other Interface Controls

### Secondary Attribute List

The **Secondary Attribute List** displays information collected for inspection or debugging that is not currently used as selector matching data.

![1740149234947](md_images/README/1740149234947.png)

For HTML selectors, screen-position/size values such as `secondary-x`, `secondary-y`, `secondary-width`, and `secondary-height` are examples of secondary information.

### Status

The **Status** area reports the current UI Analyzer operation state.

![1740149086118](md_images/README/1740149086118.png)

This area was previously named **Log**.

### Reset

Use **Reset** to clear the current selector data and return the UI to its default selector state.

![Reset](md_images/README/Reset.gif)

### Resize

The left and right panels can be resized by dragging their dividers.

The main UI Analyzer window can also be resized.

![Resize](md_images/README/Resize.gif)

### Theme

Use **Theme** to select the UI Analyzer appearance.

![1740149942519](md_images/README/1740149942519.png)

---

## Selector Reference

The selector definitions below are the canonical selector reference for UI Analyzer.

> **Important:** These definitions are simplified pseudo-schemas intended to explain field meanings and structure.
>
> They are not complete runnable JSON, Python `TypedDict`, or TypeScript declarations.
>
> Notations such as `NotRequired[str]` are descriptive only.
>
> Use UI Analyzer to create, edit, and validate real selectors rather than copying the pseudo-schema as executable code.

### SelectorUia

LiberRPA first locates the target window, then searches each layer in `specification` in order.

**Pseudo-schema:**

```text
{
  "window": {
    "ControlTypeName": str,
    "Name": NotRequired[str],
    "Name-regex": NotRequired[str],
    "AcceleratorKey": NotRequired[str],
    "AcceleratorKey-regex": NotRequired[str],
    "AccessKey": NotRequired[str],
    "AccessKey-regex": NotRequired[str],
    "AriaProperties": NotRequired[str],
    "AriaProperties-regex": NotRequired[str],
    "AriaRole": NotRequired[str],
    "AriaRole-regex": NotRequired[str],
    "ClassName": NotRequired[str],
    "HelpText": NotRequired[str],
    "HelpText-regex": NotRequired[str],
    "Index": NotRequired[str],
    "Index-regex": NotRequired[str],
    "FrameworkId": NotRequired[str],
    "FrameworkId-regex": NotRequired[str],
    "ProcessName": NotRequired[str],
    "ProcessName-regex": NotRequired[str]
  },
  "category": "uia",
  "specification": list[
    {
      "ControlTypeName": str,
      "Name": NotRequired[str],
      "Name-regex": NotRequired[str],
      "AcceleratorKey": NotRequired[str],
      "AcceleratorKey-regex": NotRequired[str],
      "AccessKey": NotRequired[str],
      "AccessKey-regex": NotRequired[str],
      "AriaProperties": NotRequired[str],
      "AriaProperties-regex": NotRequired[str],
      "AriaRole": NotRequired[str],
      "AriaRole-regex": NotRequired[str],
      "ClassName": NotRequired[str],
      "HelpText": NotRequired[str],
      "HelpText-regex": NotRequired[str],
      "Depth": NotRequired[str],
      "Index": NotRequired[str],
      "Index-regex": NotRequired[str]
    }
  ]
}
```

**Example:**

```json
{
  "window": {
    "ProcessName": "chrome.exe",
    "FrameworkId": "Win32",
    "ControlTypeName": "PaneControl",
    "Name": "Material Design Icons - Icon Library - Pictogrammers - Google Chrome",
    "ClassName": "Chrome_WidgetWin_1"
  },
  "category": "uia",
  "specification": [
    {
      "ControlTypeName": "ToolBarControl",
      "Name": "Bookmarks",
      "Depth": "5"
    },
    {
      "ControlTypeName": "ButtonControl",
      "Name": "chat"
    }
  ]
}
```

### SelectorHtml

A `SelectorHtml` contains a `window` section and a `specification` list.

The `window` section is used to locate the browser window first. After that, the Chrome extension searches the active web page using the `specification ` layers one by one.

Each item in `specification` represents one HTML layer. The search starts from `document`, then each matched layer becomes the search root for the next layer.

In simplified form:

```text
document
  -> match specification[0]
    -> match specification[1] under the previous matched element
      -> ...
        -> final target element
```

Each HTML layer can use three kinds of locating information:

* Basic attributes
* Index attributes
* Path attributes

#### Basic attributes

Basic attributes describe the element itself.

Examples:

```json
{
  "tagName": "button",
  "directText": "Submit"
}
```

```json
{
  "tagName": "input",
  "type": "text",
  "aria-label": "Search"
}
```

Some attributes can be used directly in `querySelectorAll()` as a fast pre-filter.

For example:

```text
tagName
id
className
type
name
aria-label
aria-labelledby
checked
disabled
```

Other attributes are checked after the pre-filter step, for example:

```text
value
href
src
alt
isHidden
isDisplayedNone
innerText
directText
parentId
parentClass
parentName
isLeaf
tableRowIndex
tableColumnIndex
tableColumnName
```

#### Regex attributes

Most attributes can also be written as a `-regex` field.

For example:

```json
{
  "tagName": "button",
  "directText-regex": "Submit|Save"
}
```

The regex value is used as a JavaScript regular expression string.

The Chrome extension matches the whole value internally, so this:

```json
{
  "directText-regex": "Submit"
}
```

behaves like:

```text
^Submit$
```

To match partial text, use `.*` explicitly:

```json
{
  "directText-regex": ".*Submit.*"
}
```

Do not write JavaScript regex slashes such as `/Submit/`. Use only the regex

pattern string:

```json
{
  "directText-regex": "Submit"
}
```

#### Index attributes

Index attributes are used when the basic attributes are not enough to uniquely locate an element.

There are two index fields: `childIndex`, `documentIndex`

`documentIndex` is the target element's zero-based position among all elements in the document that match the same selected attributes.

`childIndex` is the target element's zero-based position among matching descendant elements under the target element's parent search area.

> `childIndex` is calculated by searching within the parent element's DOM subtree using `parentElement.querySelectorAll(...)`, then applying additional attribute filtering. Therefore, it is not limited to direct children.

A `childIndex` value of `"0"` is treated as unnecessary and ignored during matching.

> Index values start from `0`. However, `0` is usually omitted because the first matched element is already selected by default. Index fields are most useful when the target is the second, third, or later matching element.

**Example:**

```json
{
  "tagName": "button",
  "directText": "Delete",
  "documentIndex": "2"
}
```

Index fields also support regex:

```
{
  "tagName": "button",
  "directText": "Delete",
  "documentIndex-regex": "[1-3]"
}
```

Index attributes are calculated from the same attributes that remain in the current selector layer. If you remove an attribute from the selector, the index may need to be recalculated using a broader candidate set.

#### Path attributes

When `usePath` is enabled, a `path` field will be generated for each HTML selector layer.

Generated paths are absolute CSS paths that start from `html` and use tag names plus `:nth-of-type()` where needed.

**Example:**

```json
{
  "path": "html>body>div:nth-of-type(2)>button"
}
```

There is also a regex version:

```json
{
  "path-regex": "html>body>.*>button"
}
```

Do not combine `path` / `path-regex` with `childIndex` / `documentIndex` in the same layer. They are different fallback strategies. A layer should normally use either path-based locating or index-based locating, not both.

> A generated path that starts from `html` is resolved from the current document. In a multi-layer Selector, each resolved element must still be a descendant of the element matched by the previous layer. This preserves the normal layer-by-layer hierarchy while allowing every generated layer to keep its absolute path.
>
> A manually written relative path that does not start from `html` is resolved under the previously matched element. Every path must be a valid CSS selector string that can be understood by the browser.
>
> The generated path is an implementation detail of LiberRPA. It is made of tag names joined by `>`. When there are multiple sibling elements with the same tag name, the generator may append `:nth-of-type(...)`, whose position is counted among siblings with that tag name.

In most cases, users should prefer stable attributes such as `id`, `name`, `aria-label`, text attributes, or index-based locating. Path-based locating is mainly a fallback when normal attributes are not reliable enough.

#### Secondary attributes

Some generated attributes are secondary information and are not used as selector fields:

```text
secondary-x
secondary-y
secondary-width
secondary-height
```

These values describe the element's screen position and size. They are useful for display, preview, debugging, or UI Analyzer panels, but they are not part of the HTML selector matching logic.

#### Recommended selector editing workflow

When editing an HTML selector manually:

1. Prefer stable semantic attributes first:
   1. `tagName`
   2. `id`
   3. `name`
   4. `aria-label`
   5. `directText`
   6. `type`
   7. `href`
2. Use `-regex` when the value changes slightly.
3. Use `childIndex` or `documentIndex` only when multiple elements still match.
4. Use `path` only when attributes and indexes are not reliable enough.
5. Avoid using too many text attributes if the page content changes frequently.

---

**Pseudo-schema:**

```text
{
  "window": {
    "ControlTypeName": str,
    "Name": NotRequired[str],
    "Name-regex": NotRequired[str],
    "AcceleratorKey": NotRequired[str],
    "AcceleratorKey-regex": NotRequired[str],
    "AccessKey": NotRequired[str],
    "AccessKey-regex": NotRequired[str],
    "AriaProperties": NotRequired[str],
    "AriaProperties-regex": NotRequired[str],
    "AriaRole": NotRequired[str],
    "AriaRole-regex": NotRequired[str],
    "ClassName": NotRequired[str],
    "HelpText": NotRequired[str],
    "HelpText-regex": NotRequired[str],
    "Index": NotRequired[str],
    "Index-regex": NotRequired[str],
    "FrameworkId": NotRequired[str],
    "FrameworkId-regex": NotRequired[str],
    "ProcessName": NotRequired[str],
    "ProcessName-regex": NotRequired[str]
  },
  "category": "html",
  "specification": list[
    {
      "tagName": NotRequired[str],
      "tagName-regex": NotRequired[str],
      "id": NotRequired[str],
      "id-regex": NotRequired[str],
      "className": NotRequired[str],
      "className-regex": NotRequired[str],
      "type": NotRequired[str],
      "type-regex": NotRequired[str],
      "value": NotRequired[str],
      "value-regex": NotRequired[str],
      "name": NotRequired[str],
      "name-regex": NotRequired[str],
      "aria-label": NotRequired[str],
      "aria-label-regex": NotRequired[str],
      "aria-labelledby": NotRequired[str],
      "aria-labelledby-regex": NotRequired[str],
      "checked": NotRequired[Literal["true", "indeterminate", "false"]],
      "checked-regex": NotRequired[str],
      "disabled": NotRequired[Literal["true", "false"]],
      "disabled-regex": NotRequired[str],
      "href": NotRequired[str],
      "href-regex": NotRequired[str],
      "src": NotRequired[str],
      "src-regex": NotRequired[str],
      "alt": NotRequired[str],
      "alt-regex": NotRequired[str],
      "isHidden": NotRequired[Literal["true", "false"]],
      "isHidden-regex": NotRequired[str],
      "isDisplayedNone": NotRequired[Literal["true", "false"]],
      "isDisplayedNone-regex": NotRequired[str],
      "innerText": NotRequired[str],
      "innerText-regex": NotRequired[str],
      "directText": NotRequired[str],
      "directText-regex": NotRequired[str],
      "parentId": NotRequired[str],
      "parentId-regex": NotRequired[str],
      "parentClass": NotRequired[str],
      "parentClass-regex": NotRequired[str],
      "parentName": NotRequired[str],
      "parentName-regex": NotRequired[str],
      "isLeaf": NotRequired[Literal["true", "false"]],
      "isLeaf-regex": NotRequired[str],
      "tableRowIndex": NotRequired[str],
      "tableRowIndex-regex": NotRequired[str],
      "tableColumnIndex": NotRequired[str],
      "tableColumnIndex-regex": NotRequired[str],
      "tableColumnName": NotRequired[str],
      "tableColumnName-regex": NotRequired[str],
      "childIndex": NotRequired[str],
      "childIndex-regex": NotRequired[str],
      "documentIndex": NotRequired[str],
      "documentIndex-regex": NotRequired[str],
      "path": NotRequired[str],
      "path-regex": NotRequired[str]
    },
  ]
}
```

**Example:**

```json
{
  "window": {
    "ProcessName": "chrome.exe",
    "FrameworkId": "Win32",
    "ControlTypeName": "PaneControl",
    "Name": "Material Design Icons - Icon Library - Pictogrammers - Google Chrome",
    "ClassName": "Chrome_WidgetWin_1"
  },
  "category": "html",
  "specification": [
    {
      "tagName": "p",
      "directText": "dolphin",
      "documentIndex": "0"
    }
  ]
}
```

### SelectorImage

LiberRPA first locates the target window, then searches the single image layer in `specification`.

**Pseudo-schema:**

```text
{
  "window": {
    "ControlTypeName": str,
    "Name": NotRequired[str],
    "Name-regex": NotRequired[str],
    "AcceleratorKey": NotRequired[str],
    "AcceleratorKey-regex": NotRequired[str],
    "AccessKey": NotRequired[str],
    "AccessKey-regex": NotRequired[str],
    "AriaProperties": NotRequired[str],
    "AriaProperties-regex": NotRequired[str],
    "AriaRole": NotRequired[str],
    "AriaRole-regex": NotRequired[str],
    "ClassName": NotRequired[str],
    "HelpText": NotRequired[str],
    "HelpText-regex": NotRequired[str],
    "Index": NotRequired[str],
    "Index-regex": NotRequired[str],
    "FrameworkId": NotRequired[str],
    "FrameworkId-regex": NotRequired[str],
    "ProcessName": NotRequired[str],
    "ProcessName-regex": NotRequired[str]
  },
  "category": "image",
  "specification": list[
    {
      "FileName": str,
      "Grayscale": str,
      "Confidence": str,
      "Index": NotRequired[str]
    }
  ]
}
```

**Example:**

```json
{
  "window": {
    "ProcessName": "chrome.exe",
    "FrameworkId": "Win32",
    "ControlTypeName": "PaneControl",
    "Name": "Material Design Icons - Icon Library - Pictogrammers - Google Chrome",
    "ClassName": "Chrome_WidgetWin_1"
  },
  "category": "image",
  "specification": [
    {
      "FileName": "Material Design Icons - Icon Library - Pictogrammers_20250222_144024.png",
      "Grayscale": "true",
      "Confidence": "0.9"
    }
  ]
}
```

### SelectorWindow

A `SelectorWindow` contains only the `window` section and does not have a `specification` section.

**Pseudo-schema:**

```text
{
  "window": {
    "ControlTypeName": str,
    "Name": NotRequired[str],
    "Name-regex": NotRequired[str],
    "AcceleratorKey": NotRequired[str],
    "AcceleratorKey-regex": NotRequired[str],
    "AccessKey": NotRequired[str],
    "AccessKey-regex": NotRequired[str],
    "AriaProperties": NotRequired[str],
    "AriaProperties-regex": NotRequired[str],
    "AriaRole": NotRequired[str],
    "AriaRole-regex": NotRequired[str],
    "ClassName": NotRequired[str],
    "HelpText": NotRequired[str],
    "HelpText-regex": NotRequired[str],
    "Index": NotRequired[str],
    "Index-regex": NotRequired[str],
    "FrameworkId": NotRequired[str],
    "FrameworkId-regex": NotRequired[str],
    "ProcessName": NotRequired[str],
    "ProcessName-regex": NotRequired[str]
  }
}
```

**Example:**

```json
{
  "window": {
    "ProcessName": "chrome.exe",
    "FrameworkId": "Win32",
    "ControlTypeName": "PaneControl",
    "Name": "Material Design Icons - Icon Library - Pictogrammers - Google Chrome",
    "ClassName": "Chrome_WidgetWin_1"
  }
}
```

---

## Change Log

LiberRPA components are versioned and documented together.

See the unified [Change Log](../../docs/CHANGELOG.md).
