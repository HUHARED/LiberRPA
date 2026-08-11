// FileName: snippetTreeIcons.ts

export const DICT_CATEGORY_ICON: Readonly<Record<string, string>> = {
  /*
    The identifiers of the VS Code Codicon library are documented at: https://code.visualstudio.com/api/references/icons-in-labels
    Note that using the identifiers in the second table of the chapter "Icon Listing".
  */
  Favorite: "sparkle",
  "Project Values": "symbol-variable",

  Basic: "circle-large-outline",
  LogicControl: "git-compare",
  Log: "pencil",

  Mouse: "inspect",
  Keyboard: "keyboard",
  Window: "multiple-windows",
  UiInterface: "target",

  Browser: "globe",
  Excel: "book",
  Outlook: "mail-read",
  Application: "circuit-board",
  Database: "database",

  Data: "file-binary",
  Str: "symbol-text",
  List: "symbol-array",
  Dict: "json",
  Regex: "regex",
  Math: "symbol-operator",
  Time: "calendar",
  File: "request-changes",
  OCR: "search-fuzzy",

  Web: "cloud",
  Mail: "mail",
  FTP: "references",

  Clipboard: "clippy",
  System: "terminal",
  Credential: "key",

  ScreenPrint: "info",
  Dialog: "bell",
  Trigger: "rocket",
};
