# LiberRPA Editor User Guide

LiberRPA [Editor](./Editor/vscode) is essentially a modified version of [the official portable VS Code](https://code.visualstudio.com/docs/editor/portable)—with altered default settings, added plugins, and custom resources. This means you can deploy LiberRPA on your familiar VS Code or modify the LiberRPA Editor according to your own preferences.

# Settings

Review the configurations that LiberRPA has modified by checking the following file:

[LiberRPAEditor/vscode/data/user-data/User/settings.json](./data/user-data/User/settings.json)

You can hover over each item to see a description of its functionality.

# Keybindings

To view the keybindings that LiberRPA has modified, refer to:

[LiberRPAEditor/vscode/data/user-data/User/keybindings.json](./data/user-data/User/keybindings.json)

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

# VS Code Docs

For more detailed guidance on customizing LiberRPA Editor to your preferences, feel free to ask AI for assistance and check out the [official VS Code documentation](https://code.visualstudio.com/docs).
