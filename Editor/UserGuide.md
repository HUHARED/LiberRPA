# LiberRPA Editor User Guide

LiberRPA Editor is essentially a modified version of [the official portable VS Code](https://code.visualstudio.com/docs/editor/portable), with adjusted default settings, pre-installed extensions, and custom LiberRPA resources.

You can use LiberRPA Editor directly, or apply similar settings and extensions to your own VS Code installation.

# Settings

LiberRPA Editor's user settings are stored here:

[Editor/data/user-data/User/settings.json](./data/user-data/User/settings.json)

You can hover over each setting item in VS Code to see its built-in explanation.

## Python interpreter

LiberRPA uses the `LiberRPA` environment variable to locate the bundled Python environment. The Python interpreter setting is expected to use this form:

```json
"python.defaultInterpreterPath": "${env:LiberRPA}\\envs\\pyenv\\python.exe"
```

After running `InitLiberRPA.exe`, restart LiberRPA Editor if the interpreter cannot be found immediately. Windows and VS Code may not see newly updated environment variables until the process is restarted.

## Ruff

LiberRPA Editor uses Ruff for Python linting and formatting.

It provides fast Python checking and formatting, and can also detect common mistakes such as unused variables, invalid syntax, unsafe patterns, and strings that look like missing f-strings.

Recommended settings include:

```json
"[python]": {
  "editor.defaultFormatter": "charliermarsh.ruff"
},
"ruff.nativeServer": "on",
"ruff.interpreter": [
  "${env:LiberRPA}\\envs\\pyenv\\python.exe"
]
```

LiberRPA does not enable format-on-save by default. This avoids unexpected code changes while users are still editing RPA scripts. You can format the current Python file manually with **Format Document**.

Project-level Ruff rules are controlled by the project's `ruff.toml` file.

## Snippets and suggestions

LiberRPA provides snippets through the `liberrpa-snippets-tree` extension and VS Code's normal suggestion list.

If LiberRPA snippets appear before or after symbols in the current file in a way that does not match your preference, you can adjust VS Code's snippet sorting behavior with:

```json
"editor.snippetSuggestions": "top"
```

Common values include:

| Value      | Meaning                                 |
| ---------- | --------------------------------------- |
| `top`    | Show snippets before other suggestions. |
| `bottom` | Show snippets after other suggestions.  |
| `inline` | Mix snippets with other suggestions.    |
| `none`   | Hide snippets from the suggestion list. |

You can choose the value that best fits your coding workflow.

# Keybindings

To view the keybindings that LiberRPA has modified, refer to:

[Editor/data/user-data/User/keybindings.json](./data/user-data/User/keybindings.json)

If you're not familiar with the default VS Code shortcuts or haven't customized them, here is a summary to streamline your coding workflow:

| Shortcut         | Description                                                                             |
| ---------------- | --------------------------------------------------------------------------------------- |
| Shift+Enter      | Insert a new line below the current line.                                               |
| Ctrl+Shift+Enter | Insert a new line above the current line. Ctrl+Enter is disabled.                       |
| Ctrl+J           | Navigate to the next suggestion in the autocomplete list when visible.                  |
| Ctrl+K           | Navigate to the previous suggestion in the autocomplete list when visible.              |
| Ctrl+Shift+Tab   | Switch to the previous editor tab. Ctrl+PageUp is disabled.                             |
| Ctrl+Tab         | Switch to the next editor tab. Ctrl+PageDown is disabled.                               |
| Ctrl+D           | Delete the current line.                                                                |
| Ctrl+V in Python | Paste with auto-indentation in Python files by the extension "Python Paste And Indent". |

# Extensions

LiberRPA Editor comes with several pre-installed VS Code extensions to streamline RPA script development.

* **Python**

  Adds Python language support, including interpreter selection, debugging, testing integration, and other Python workflow features.
* **Pylance**

  Provides Python IntelliSense, type checking, inlay hints, and code navigation.
* **Ruff**

  Provides Python linting and formatting. LiberRPA Editor uses Ruff instead of Black Formatter and isort.
* **liberrpa-snippets-tree**

  Provides LiberRPA snippets and drag-and-drop script generation.
* **liberrpa-flowchart**

  Provides LiberRPA flowchart editing and project-level visual workflow support.
* **liberrpa-project-manager**

  Provides LiberRPA project creation, project packaging, and related project-management features.
* **Jupyter**

  Supports Jupyter notebooks with interactive programming, IntelliSense, debugging, and more.
* **Office Viewer**

  Allows viewing Word and Excel files, and includes a WYSIWYG editor for Markdown.
* **Partial Diff**

  Compares selected text within a file, across files, or with the clipboard.
* **Path Intellisense**

  Autocompletes filenames and file paths.
* **Prettier - Code Formatter**

  Formats JSON, JSONC, Vue, TypeScript, JavaScript, HTML, CSS, and other non-Python files.
* **indent-rainbow**

  Makes indentation levels easier to read by colorizing them.
* **Python Indent**

  Automatically calculates correct indentation when you press Enter.

  Note: tabs (`\t`) are not supported because Python indentation uses spaces.
* **Python Paste and Indent**

  Automatically indents Python code blocks when pasting.
* **Select Line Status Bar**

  Displays the number of selected lines in the status bar.
* **TabOut**

  Allows you to tab out of quotes, brackets, and similar structures.

# VS Code Docs

For more detailed guidance on customizing LiberRPA Editor to your preferences, see the [official VS Code documentation](https://code.visualstudio.com/docs).
