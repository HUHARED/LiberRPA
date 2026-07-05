# LiberRPA Chrome Extension

The **LiberRPA Chrome Extension** works alongside **LiberRPA Local Server** to enable seamless browser automation.

## Notes and Limitations

- The extension works with LiberRPA Local Server and the registered Native Messaging host `com.liberrpa.chrome.msghost`.
- HTML automation currently targets the top-level document. iframe and shadow DOM support may be limited.

> HTML selectors are currently resolved in the DOM context where the LiberRPA Chrome content script is running.
>
> By default, the current extension mainly targets the top-level document of the active tab. Elements inside iframes may not be available.
>
> Shadow DOM support is also limited. The current selector logic uses normal DOM APIs such as `querySelector()` and `querySelectorAll()` on the current document or parent element. It does not recursively traverse shadow roots. Elements inside closed shadow roots are not accessible through normal page scripts.
>
> In practice, HTML selectors work best for standard HTML elements in the main document. For iframe-heavy pages, web components, closed shadow DOM, canvas-based UI, or browser-controlled pages, users may need other automation methods such as UI automation, image recognition, or future dedicated frame/shadow-DOM support.

- `clickMouseEvent` dispatches DOM mouse events; it is not the same as a real OS-level mouse click.
- `executeJsCode` runs in the extension/content-script environment and is not exactly the same as DevTools console execution.
- Commands are applied to the active normal Chrome tab.
- Chrome internal pages such as `chrome://...`, Chrome Web Store pages, extension pages, and some browser-controlled pages cannot be automated by the extension.
- To automate `file://` pages, the user must enable file URL access for the extension in Chrome extension settings.

> LiberRPA uses LiberRPA Chrome Extension to inspect and automate the DOM of the active web page. To do this, the extension needs host permissions for the pages that may be automated.
>
> LiberRPA Chrome Extension is designed for general-purpose browser automation, so it uses broad host permissions for normal HTTP and HTTPS pages. This allows LiberRPA to read page information, locate HTML elements, and perform DOM-based actions on the user's active browser tab.
>
> Chrome may show permission warnings for broad host permissions. This is expected for an RPA tool because the extension must be able to interact with user-selected web pages.
>
> For local `file://` pages, Chrome requires separate user approval. The user must enable file URL access for the extension in Chrome's extension details page before LiberRPA Chrome Extension can automate local HTML files.

## Icon Status

The extension toolbar icon changes according to its current state:

> If the extension fails to set up the socket connection with the Local Server, it shows the disconnected icon:
> ![NoLink icon](./assets/NoLink_32px.png)

> If the extension is executing a command in the content layer, it shows the finding icon:
> ![Finding icon](./assets/Finding_32px.png)

> In the normal connected state, it shows the default LiberRPA icon:
> ![LiberRPA icon](./assets/LiberRPA_icon_v3_color_32px.png)

## Functionality

The extension receives commands from the LiberRPA Local Server and returns results accordingly.

Supported commands include:

* **Background**
  * getState
  * goBackward
  * goForward
  * refresh
  * waitForLoad
  * navigate
  * openNewTab
  * openNewWindow
  * switchTab
  * closeCurrentTab
  * getDownloadList
  * getUrl
  * getTitle
  * getCookies
  * setCookies
* **Content**
  * getElementAttrByCoordinates
  * getElementAttrBySelector
  * clickMouseEvent
  * setElementText
  * focusElement
  * getParentElementAttr
  * getChildrenElementAttr
  * setCheckState
  * getSelection
  * setSelection
  * getSourceCode
  * getAllText
  * getScrollPosition
  * setScrollPosition
  * executeJsCode

## Permissions

The extension requires the following permissions:

* tabs
* activeTab
* scripting
* cookies
* downloads
* nativeMessaging

# Change Log

Since LiberRPA has components across different platforms, all changes will be recorded in [the unified document](https://github.com/HUHARED/LiberRPA/blob/main/docs/CHANGELOG.md).
