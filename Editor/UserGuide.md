# LiberRPA Editor User Guide

LiberRPA Editor is essentially a modified version of [the official portable VS Code](https://code.visualstudio.com/docs/editor/portable)—with altered default settings, added plugins, and custom resources. This means you can deploy LiberRPA on your familiar VS Code or modify the LiberRPA Editor according to your own preferences.

# Settings

Review the configurations that LiberRPA has modified by checking the following file:

[LiberRPAEditor/data/user-data/User/settings.json](./data/user-data/User/settings.json)

You can hover over each item to see a description of its functionality.

# Keybindings

To view the keybindings that LiberRPA has modified, refer to:

[LiberRPAEditor/data/user-data/User/keybindings.json](./data/user-data/User/keybindings.json)

If you're not familiar with the default VS Code shortcuts or haven't customized them, here is a summary to streamline your coding workflow:

| Shortcut           | Description                                                                              |
| ------------------ | ---------------------------------------------------------------------------------------- |
| Shift+Enter        | Insert a new line below the current line.                                               |
| Ctrl+Shift+Enter   | Insert a new line above the current line. (Note: Ctrl+Enter is disabled.)               |
| Ctrl+J             | Navigate to the next suggestion in the autocomplete list (when visible).                |
| Ctrl+K             | Navigate to the previous suggestion in the autocomplete list (when visible).            |
| Ctrl+Shift+Tab     | Switch to the previous editor tab.(Note: Ctrl+PageUp is disabled.)                     |
| Ctrl+Tab           | Switch to the next editor tab.(Note: Ctrl+PageDown is disabled.)                        |
| Ctrl+D             | Delete the current line.                                                                 |
| Ctrl+V (in Python) | Paste with auto-indentation in Python files by the extension "Python Paste And Indent". |

# Extensions

LiberRPA comes with several pre-installed VS Code extensions to streamline your coding workflow:

* **ms-python.black-formatter**

  Format Python files using the Black code formatter.
* **indent-rainbow**

  Makes indentation levels easier to read by colorizing them.
* **IntelliCode**

  Provides AI-assisted development suggestions.
* **Jupyter**

  Supports Jupyter notebooks with interactive programming, IntelliSense, debugging, and more.
* **Office Viewer**

  Allows viewing of Word and Excel files, and includes a WYSIWYG editor for Markdown.
* **Partial Diff**

  Compare (diff) text selections within a file, across files, or with the clipboard.
* **Path Intellisense**

  Autocompletes filenames and file paths.
* **Prettier - Code Formatter**

  Formats code using the Prettier code style.
* **Python**

  Adds Python language support including IntelliSense (via Pylance), debugging, linting, formatting, refactoring, unit testing, and more.
* **Python Indent**

  Automatically calculates correct indentation when you press Enter.

  *(Note: Tabs `\t` are not supported because Python indentation uses spaces.)*
* **Python Paste and Indent**

  Automatically indents Python code blocks when pasting.
* **Select Line Status Bar**

  Displays the number of selected lines in the status bar.
* **TabOut**

  Allows you to tab out of quotes, brackets, and similar structures.

# VS Code Docs

For more detailed guidance on customizing LiberRPA Editor to your preferences, feel free to ask AI for assistance and check out the [official VS Code documentation](https://code.visualstudio.com/docs).
