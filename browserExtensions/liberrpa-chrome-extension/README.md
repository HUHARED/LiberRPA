# LiberRPA Chrome Extension

The **LiberRPA Chrome Extension** provides the browser-side integration used by LiberRPA for Chrome automation and HTML/DOM element operations.

It works together with:

- LiberRPA Local Server;
- the registered Native Messaging host `com.liberrpa.chrome.msghost`;
- LiberRPA Python browser/UI APIs;
- UI Analyzer for HTML element indication and selector validation.

**[Install LiberRPA Chrome Extension from the Chrome Web Store](https://chromewebstore.google.com/detail/liberrpa-chrome-extension/cffobgimbemkfgjmcedebofkfcamnajb)**

## Contents

- [How It Works](#how-it-works)
- [Target Browser Context](#target-browser-context)
- [HTML Selectors](#html-selectors)
- [Supported Functionality](#supported-functionality)
- [DOM Operation Semantics](#dom-operation-semantics)
- [Permissions](#permissions)
- [Icon Status](#icon-status)
- [Current Limitations](#current-limitations)
- [Troubleshooting](#troubleshooting)
- [Change Log](#change-log)

---

## How It Works

The extension uses Native Messaging only to discover the connection information of the currently initialized LiberRPA installation.

The bootstrap flow is:

```text
Chrome Extension
      │
      │ Native Messaging: get_port
      ▼
ChromeGetLocalServerPort
      │
      ├── Local Server port
      └── chrome authentication token
      │
      ▼
Chrome Extension
      │
      │ Socket.IO / WebSocket
      ▼
http://127.0.0.1:<port>
      │
      ▼
LiberRPA Local Server
```

After the port and token have been obtained, normal browser automation does **not** use Native Messaging.

The extension connects directly to LiberRPA Local Server with:

```text
clientType = chrome
```

and the current Chrome authentication token.

After the Socket.IO connection is established, the extension registers itself with Local Server for browser-command routing.

Normal command flow is:

```text
LiberRPA Python API
        │
        ▼
LiberRPA Local Server
        │
        ▼
Chrome Extension background
        │
        ├── Chrome browser APIs
        │
        └── content script
              │
              ▼
           Page DOM
        │
        ▼
LiberRPA Local Server
        │
        ▼
Python caller
```

Browser-level operations such as tabs, windows, cookies, downloads, navigation, URL, and title are handled by the extension background/service worker.

DOM-level operations are forwarded to the content script running in the active supported web page.

Each relayed command carries an internal request ID so that asynchronous results can be returned to the correct waiting Python request.

For the Local Server side of this architecture, see [LiberRPA Local Server](../../docs/LocalServer.md).

---

## Target Browser Context

LiberRPA browser commands operate on the active supported tab of the **last focused normal Chrome window**.

For content-level automation, the current active tab must be a page whose URL uses one of these protocols:

```text
http://
https://
file://
```

`file://` automation additionally requires the user to enable file URL access for the extension in Chrome's extension settings.

Chrome-controlled pages and other restricted browser contexts are not normal automation targets for the extension.

---

## HTML Selectors

The Chrome Extension resolves LiberRPA `SelectorHtml` values against the active supported web page.

HTML selectors can combine:

- DOM hierarchy layers;
- stable element attributes;
- parent context;
- regular-expression matching;
- `childIndex` and `documentIndex`;
- generated DOM path information.

At runtime, the extension can use CSS/query-selector-compatible attributes as an initial candidate search and then apply additional attribute, regex, hierarchy, index, or path checks.

When a matched element is outside the current viewport, LiberRPA can scroll it into view before continuing with the requested operation.

The canonical documentation for:

- selector structure;
- supported selector fields;
- regex behavior;
- index semantics;
- path semantics;
- selector editing;
- selector validation;

is maintained in the [UI Analyzer documentation](../../electronApplications/ui-analyzer/README.md#selector-reference).

This Chrome Extension document focuses on browser connection, browser/DOM operations, permissions, and browser-specific limitations.

---

## Supported Functionality

The extension receives commands through LiberRPA Local Server and returns their results to the requesting Python process.

### Browser/background operations

| Command             | Purpose                                                               |
| ------------------- | --------------------------------------------------------------------- |
| `getState`        | Read the current active tab loading state.                            |
| `goBackward`      | Navigate backward in tab history.                                     |
| `goForward`       | Navigate forward in tab history.                                      |
| `refresh`         | Reload the active tab.                                                |
| `waitForLoad`     | Wait for the active tab to reach Chrome's `complete` loading state. |
| `navigate`        | Navigate the active tab to a URL.                                     |
| `openNewTab`      | Open a new tab.                                                       |
| `openNewWindow`   | Open a new normal Chrome window.                                      |
| `switchTab`       | Activate a tab by index or exact title.                               |
| `closeCurrentTab` | Close the active supported tab.                                       |
| `getDownloadList` | Read recent Chrome download information.                              |
| `getUrl`          | Read the active tab URL.                                              |
| `getTitle`        | Read the active tab title.                                            |
| `getCookies`      | Read cookies for the active page domain.                              |
| `setCookies`      | Modify an existing matching cookie.                                   |

### Content/DOM operations

| Command                         | Purpose                                                                           |
| ------------------------------- | --------------------------------------------------------------------------------- |
| `getElementAttrByCoordinates` | Identify an element from screen coordinates and return selector/tree information. |
| `getElementAttrBySelector`    | Resolve a selector and return the target's current attributes.                    |
| `clickMouseEvent`             | Dispatch a DOM mouse event to a selected element.                                 |
| `setElementText`              | Set or append text in supported editable elements.                                |
| `focusElement`                | Call `focus()` on a selected element.                                           |
| `getParentElementAttr`        | Return attributes of an ancestor element.                                         |
| `getChildrenElementAttr`      | Return attributes of child elements.                                              |
| `setCheckState`               | Change the checked state of a checkbox or radio input.                            |
| `getSelection`                | Read a native `<select>` selection by text, value, or index.                    |
| `setSelection`                | Change a native `<select>` selection by text, value, or index.                  |
| `getSourceCode`               | Return `document.documentElement.outerHTML`.                                    |
| `getAllText`                  | Return `document.body.innerText`.                                               |
| `getScrollPosition`           | Read the current page scroll position.                                            |
| `setScrollPosition`           | Scroll the current page to the requested coordinates.                             |
| `executeJsCode`               | Execute JavaScript through the extension's page-code execution mechanism.         |

Users normally call the corresponding public LiberRPA Python APIs rather than these internal command names directly.

---

## DOM Operation Semantics

Several operations intentionally work at the DOM level rather than simulating physical keyboard or mouse input.

Understanding this distinction is useful when automating complex web applications.

### Element lookup and scrolling

After a selector resolves an element, the content layer checks whether the target is outside the current viewport or appears to be covered at its center point.

When necessary, the element is automatically scrolled into view before the requested operation continues.

### `clickMouseEvent`

`clickMouseEvent` creates and dispatches a DOM `MouseEvent`.

It supports:

- left, middle, and right button values;
- single click;
- double click;
- mouse down;
- mouse up;
- Ctrl, Shift, Alt, and Windows/meta modifier flags.

This is **not** the same as a physical OS-level mouse action.

Pages that explicitly require trusted physical input may behave differently. When real mouse input is required, use the appropriate Windows/mouse automation method instead.

### `setElementText`

`setElementText` supports:

- `<textarea>`;
- editable `<input>` types such as text, search, email, password, telephone, URL, and number;
- `contenteditable` elements.

The operation can append to existing content or replace it.

After modifying the element, the extension dispatches bubbling/composed:

```text
input
change
```

events to improve compatibility with event-driven applications and frameworks.

Some heavily controlled framework components or custom input implementations may still require a different interaction method.

When text validation is enabled, the extension compares the resulting content with the expected content after the operation.

### Checkboxes, radio buttons, and `<select>`

`setCheckState` currently changes the DOM `checked` state of native checkbox/radio inputs directly.

`setSelection` currently changes the `selectedIndex` of a native `<select>` directly.

These operations do not currently dispatch additional `input`, `change`, or click events after modifying the state.

Pages that depend on those events may therefore require another interaction method or explicit page-side handling.

### `executeJsCode`

`executeJsCode` uses the extension's JavaScript execution mechanism and should not be assumed to behave identically to manually entering code in Chrome DevTools.

Use it only with code and pages you trust.

---

## Permissions

The extension requires browser permissions used for RPA functionality, including:

- `tabs`;
- `scripting`;
- `cookies`;
- `downloads`;
- `nativeMessaging`.

LiberRPA is intended for general-purpose browser automation and therefore also needs host access to the normal HTTP/HTTPS pages selected by the user for automation.

This allows LiberRPA to:

- inspect page information;
- inject its content layer where Chrome permits it;
- locate HTML elements;
- perform DOM-based actions.

Chrome may display permission warnings for broad page access. This is expected for a general-purpose browser automation extension.

### Local `file://` pages

Chrome requires separate user approval before an extension may access local `file://` pages.

To automate a local HTML file, enable **Allow access to file URLs** for LiberRPA Chrome Extension in Chrome's extension details page.

---

## Icon Status

The toolbar icon shows the current connection/execution state.

### Connected

The normal LiberRPA icon means that the extension is connected to LiberRPA Local Server.

![LiberRPA icon](./assets/LiberRPA_icon_v3_color_32px.png)

### Local Server not connected

The `NoLink` icon means that the extension does not currently have a working Socket.IO connection to LiberRPA Local Server.

![NoLink icon](./assets/NoLink_32px.png)

The tooltip is:

```text
LiberRPA Local Server is not connected.
```

### Content command running

The `Finding` icon is shown temporarily while a page/content command is being executed.

![Finding icon](./assets/Finding_32px.png)

The tooltip is:

```text
LiberRPA is executing a content command.
```

---

## Current Limitations

### Top-level document

HTML automation currently primarily targets the top-level document in which the LiberRPA content script is running.

#### iframes

Elements inside iframes may not be available to the current selector logic.

Dedicated frame traversal is not currently implemented as part of the normal selector model.

#### Shadow DOM

The current selector implementation uses ordinary DOM APIs such as:

```text
querySelector()
querySelectorAll()
```

on the current document or selected parent element.

It does not recursively traverse shadow roots.

Elements inside closed shadow roots are not accessible through normal page scripts.

For iframe-heavy pages, web components, closed Shadow DOM, canvas-based UI, or other unsupported structures, use another appropriate automation method such as Windows UI Automation or image-based automation when possible.

### Restricted Chrome pages

Chrome does not allow ordinary extension content scripts to automate every browser-controlled page.

Examples include:

- `chrome://...` pages;
- Chrome Web Store pages;
- extension pages;
- other Chrome-controlled or permission-restricted contexts.

### Active-tab model

Commands target the active supported tab of the last focused normal Chrome window.

LiberRPA does not currently expose an independent long-lived automation session for every open tab simultaneously.

Use tab-switching operations when another tab needs to become the active target.

### Coordinate-based indication

Converting screen coordinates to page viewport coordinates depends on browser-window geometry.

Coordinate-based HTML indication can therefore be more sensitive to Windows display scaling and Chrome window state than selector-based operations.

A 100% Windows display scale is recommended when maximum consistency is required for coordinate-dependent automation.

### Synthetic DOM interaction

DOM-generated mouse events and direct DOM state changes are not identical to trusted physical user input.

Some applications may intentionally react only to particular browser/framework events or trusted input. Use the interaction method appropriate to the target application.

---

## Troubleshooting

### The extension shows the `NoLink` icon

Check that:

- LiberRPA Local Server is running;
- the current LiberRPA installation has been initialized with `InitLiberRPA.exe`;
- the Native Messaging registration points to the current installation;
- Chrome has been restarted or the extension reloaded after relevant installation/token changes.

`InitLiberRPA.exe` regenerates local authentication tokens. A Chrome Extension service worker that still holds an older token may need to be restarted/reloaded so that it obtains the current port and token again through Native Messaging.

### Browser APIs work but a page element command fails

The extension background can perform some browser-level operations without a working content script in the current page.

For DOM operations, confirm that the active tab is a supported `http://`, `https://`, or permitted `file://` page and that Chrome permits content-script access to it.

### A selector no longer finds an element

Inspect the element again with UI Analyzer and check whether the page changed attributes or hierarchy used by the selector.

Consider using:

- more stable semantic attributes;
- parent context;
- regular-expression matching for changing attribute values;
- child/document indexes only when needed;
- path matching only when it is appropriate for the page structure.

Avoid depending on volatile values when a more stable selector can be constructed.

### Text changes but the page does not react

`setElementText` dispatches `input` and `change`, but some heavily controlled custom components may still reject or overwrite direct DOM changes.

Use another browser/UI interaction strategy if the target application's component model requires it.

### Checkbox or selection changes visually but application logic does not react

The current `setCheckState` and `setSelection` implementations directly update DOM state and do not dispatch additional change/input/click events.

Use an interaction method that triggers the events required by that page.

### Local HTML files cannot be automated

Enable **Allow access to file URLs** in the Chrome extension details page.

---

## Change Log

LiberRPA components share a unified change log:

[View the LiberRPA Change Log](https://github.com/HUHARED/LiberRPA/blob/main/docs/CHANGELOG.md)
