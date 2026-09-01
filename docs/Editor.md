# LiberRPA Editor

LiberRPA Editor is a preconfigured portable VS Code environment for LiberRPA development. It uses the official Windows ZIP distribution of Microsoft Visual Studio Code, but the Microsoft VS Code binary is not redistributed in the LiberRPA release archive. On a clean installation, `InitLiberRPA.exe` downloads the tested VS Code version directly from Microsoft and prepares it under `Editor/`.

LiberRPA's portable settings, keybindings, and installed extensions are kept under `Editor/data`. Selected extensions are installed there by `InitLiberRPA.exe` when they are missing.

LiberRPA 0.3.0 uses VS Code 1.121.0 for clean Editor setup. An existing recognized Editor is kept rather than automatically replaced. For download verification, retry instructions, and offline preparation, see [Installation](./Installation.md#editor-setup).

It combines the normal VS Code and Python development experience with:

- LiberRPA-specific extensions;
- the standard LiberRPA Python environment;
- selected third-party development extensions;
- LiberRPA-oriented editor settings;
- custom keybindings.

LiberRPA Editor is the recommended environment for the simplest LiberRPA setup.

For creating and running your first Flow Project, see [Getting Started](./GettingStarted.md).

## Contents

- [Python Environment](#python-environment)
- [LiberRPA Extensions](#liberrpa-extensions)
- [Selected Development Extensions](#selected-development-extensions)
- [Editor Settings](#editor-settings)
- [Python Formatting and Linting](#python-formatting-and-linting)
- [Snippets and Suggestions](#snippets-and-suggestions)
- [Keybindings](#keybindings)
- [Using Your Own VS Code](#using-your-own-vs-code)
- [Further VS Code Documentation](#further-vs-code-documentation)

---

## Python Environment

LiberRPA Editor is configured to use the standard Python environment included with LiberRPA.

The default interpreter is:

```text
<LiberRPA root>\envs\pyenv\default\python.exe
```

The corresponding VS Code setting is:

```json
"python.defaultInterpreterPath": "${env:LiberRPA}\\envs\\pyenv\\default\\python.exe"
```

The `${env:LiberRPA}` value comes from the Windows user environment variable configured by `InitLiberRPA.exe`.

If the Python interpreter cannot be found immediately after initialization or after moving LiberRPA, restart the Editor so that VS Code can read the updated environment variable.

For details about the standard Python environment and dependency management, see [Python Environment](./Environment.md).

---

## LiberRPA Extensions

LiberRPA Editor includes several extensions developed specifically for LiberRPA.

### LiberRPA Flowchart

Provides the visual high-level process editor for Flow Projects.

It supports:

- editing `project.flow`;
- Start, SubStart, Block, Choose, and End nodes;
- Flow-level branches and exception paths;
- running individual Blocks;
- running and debugging complete Flow Projects.

See [LiberRPA Flowchart](../vscodeExtensions/liberrpa-flowchart/README.md).

### LiberRPA Project Manager

Provides Project lifecycle and dependency-management functionality, including:

- creating Flow Projects and Component Projects;
- Project metadata management;
- reusable Component dependencies;
- Component Repository operations;
- dependency resolution and repair;
- Component publishing;
- Flow Project packaging.

See [LiberRPA Project Manager](../vscodeExtensions/liberrpa-project-manager/README.md).

### LiberRPA Snippets Tree

Provides a browsable tree of LiberRPA APIs and code snippets.

Snippets can be:

- inserted by clicking;
- dragged into Python source;
- accessed through normal VS Code suggestions.

See [LiberRPA Snippets Tree](../vscodeExtensions/liberrpa-snippets-tree/README.md).

---

## Selected Development Extensions

LiberRPA selects the following third-party VS Code extensions for general development work. `InitLiberRPA.exe` attempts to install them from the Visual Studio Marketplace when they are missing; supporting extensions required by these extensions are handled automatically by VS Code.

### Python

Provides Python development support, including interpreter selection, debugging, testing integration, IntelliSense, type analysis, inlay hints, source navigation, and related language features.

Supporting extensions required by the Python extension are installed automatically by VS Code.

### Ruff

Provides Python linting and formatting.

LiberRPA uses Ruff instead of maintaining separate Black Formatter and isort integrations.

### Jupyter

Provides Jupyter notebook support for interactive Python development.

Supporting extensions required by the Jupyter extension are installed automatically by VS Code.

### Office Viewer

Provides viewing support for Office documents and additional Markdown editing functionality.

LiberRPA pins Office Viewer to a tested version because newer releases may introduce substantial UI and behavior changes. Automatic updates are therefore disabled.

### Partial Diff

Allows selected text to be compared:

- within a file;
- between files;
- with clipboard content.

### Path Intellisense

Provides filename and path completion.

### Prettier - Code Formatter

Provides formatting for non-Python files such as:

- JSON;
- JSONC;
- TypeScript;
- JavaScript;
- HTML;
- CSS.

### indent-rainbow

Adds visual highlighting to indentation levels.

### Python Indent

Improves automatic Python indentation when pressing Enter.

### Python Paste and Indent

Adjusts indentation when Python code blocks are pasted.

### Select Line Status Bar

Displays the number of currently selected lines in the VS Code status bar.

### TabOut

Allows Tab to move outside quotes, brackets, and similar structures.

---

## Editor Settings

LiberRPA Editor's user settings are stored in:

[Editor/data/user-data/User/settings.json](../Editor/data/user-data/User/settings.json)

Most settings are normal VS Code or extension settings.

You can inspect their built-in descriptions directly through the VS Code Settings interface.

The bundled configuration is intended to provide useful defaults rather than prevent customization.

You may change Editor settings according to your own development preferences.

---

## Python Formatting and Linting

LiberRPA Editor uses Ruff for Python formatting and static diagnostics.

The standard configuration includes settings such as:

```json
"[python]": {
  "editor.defaultFormatter": "charliermarsh.ruff"
},
"ruff.nativeServer": "on",
"ruff.interpreter": [
  "${env:LiberRPA}\\envs\\pyenv\\default\\python.exe"
]
```

Ruff provides functionality including:

- linting;
- formatting;
- import-related checks;
- static diagnostics.

### Manual formatting

LiberRPA does not enable format-on-save by default.

This avoids automatically modifying Python source while the developer is still editing an automation.

To format the current file manually, use:

**Format Document**

Project-specific Ruff rules are controlled by the Project's:

```text
ruff.toml
```

file.

---

## Snippets and Suggestions

LiberRPA APIs and code templates can appear in VS Code's normal suggestion list in addition to being available through LiberRPA Snippets Tree.

VS Code controls where snippets appear relative to other suggestions through:

```json
"editor.snippetSuggestions": "top"
```

Common values are:

| Value      | Behavior                               |
| ---------- | --------------------------------------- |
| `top`    | Show snippets before other suggestions. |
| `bottom` | Show snippets after other suggestions.  |
| `inline` | Mix snippets with other suggestions.    |
| `none`   | Hide snippets from the suggestion list. |

Choose the behavior that best matches your coding workflow.

Changing this setting does not remove snippets from LiberRPA Snippets Tree.

---

## Keybindings

LiberRPA Editor includes several customized keybindings intended to make keyboard-heavy Python and RPA development faster.

The actual configuration is stored in:

[Editor/data/user-data/User/keybindings.json](../Editor/data/user-data/User/keybindings.json)

Important LiberRPA Editor keybindings include:

| Shortcut             | Behavior                                                                          |
| -------------------- | ---------------------------------------------------------------------------------- |
| `Shift+Enter`      | Insert a new line below the current line.                                          |
| `Ctrl+Shift+Enter` | Insert a new line above the current line.                                          |
| `Ctrl+J`           | Select the next item when the suggestion list is visible.                          |
| `Ctrl+K`           | Select the previous item when the suggestion list is visible.                      |
| `Ctrl+Shift+Tab`   | Switch to the previous editor tab.                                                 |
| `Ctrl+Tab`         | Switch to the next editor tab.                                                     |
| `Ctrl+D`           | Delete the current line.                                                           |
| `Ctrl+V` in Python | Paste Python code with indentation adjustment provided by Python Paste and Indent. |

Some standard VS Code shortcuts are disabled or replaced to support these bindings.

For example:

- `Ctrl+Enter` is disabled in favor of the configured line-insertion workflow;
- `Ctrl+PageUp` and `Ctrl+PageDown` are disabled in favor of the configured tab-switching shortcuts.

If you prefer the standard VS Code behavior, edit the keybindings through the normal VS Code Keyboard Shortcuts interface.

---

## Using Your Own VS Code

LiberRPA Editor is provided for convenience and to give users a known development environment.

LiberRPA does not require application logic to be written in a proprietary IDE.

Advanced users may use another VS Code installation if they configure the required environment and extensions themselves.

At minimum, a comparable setup needs to account for:

- the LiberRPA Python environment;
- LiberRPA Flowchart;
- LiberRPA Project Manager;
- LiberRPA Snippets Tree;
- Python development support;
- any settings or keybindings the user wants to reproduce.

LiberRPA Editor remains the recommended configuration when:

- setting up LiberRPA for the first time;
- reproducing a documented workflow;
- troubleshooting Editor-specific behavior;
- verifying whether a problem also occurs with the standard LiberRPA configuration.

Using a custom VS Code configuration may produce behavior different from LiberRPA Editor depending on installed extensions and user settings.

---

## Further VS Code Documentation

LiberRPA Editor remains a VS Code-based development environment, so normal VS Code concepts and workflows continue to apply.

For general topics such as:

- editing;
- source control;
- debugging;
- extension management;
- keyboard shortcuts;
- settings;
- workspace customization;

see the [official VS Code documentation](https://code.visualstudio.com/docs).

For LiberRPA-specific workflows, use the LiberRPA documentation linked throughout this guide.
