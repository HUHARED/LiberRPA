# LiberRPA Chrome Extension

The **LiberRPA Chrome Extension** works alongside **LiberRPA Local Server** to enable seamless browser automation.

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
  * waitLoadCompleted
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
* **Centent**

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
