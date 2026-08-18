# LiberRPA Snippets Tree

If the images are not displayed, [view this README on GitHub](https://github.com/HUHARED/LiberRPA/blob/main/vscodeExtensions/liberrpa-snippets-tree/README.md).

This extension is a part of LiberRPA to displays built-in and user-defined [code snippets](https://code.visualstudio.com/docs/editor/userdefinedsnippets).

With it, you don't need to memorize the entire [LiberRPA API](https://github.com/HUHARED/LiberRPA/tree/main/condaLibrary#api).

> **Note:**
>
> Screenshots and animations in this README are provided for reference. As LiberRPA evolves, the current interface may differ slightly in appearance or wording, but these minor differences do not affect the documented workflow or functionality.
>
> For example:
>
> * Icon has become ![new icon](./md_images/README/LiberRPA_icon_v3_monochrome_plain_32px.png) from ![old icon](./md_images/README/LiberRPA_icon_v2_line_32px.png) .
> * The current interface and managed import block structure may differ slightly from what is shown.

# Usage

## Insert Snippets

LiberRPA snippets can be inserted into Python files in three ways.

All three methods update the LiberRPA managed import block when the inserted snippet requires imports.

### Click a Tree Node

Click a snippet in  **LiberRPA Snippets Tree** .

For ordinary statement and function snippets:

* If the current line is empty, the snippet is inserted on the current line.
* If the current line is not empty, a new line is created with the same indentation before the snippet is inserted.

Items in the **Project Values** category are expression snippets. They are inserted directly at the current cursor position or replace the current selection.

![clickToAdd](md_images/README/clickToAdd.gif)

### Drag and Drop

Drag a snippet from **LiberRPA Snippets Tree** to the required position in the editor.

The snippet is inserted at the drop position, and its required imports are added automatically.

![dragToAdd](md_images/README/dragToAdd.gif)

### IntelliSense

Type a snippet prefix in a Python file. LiberRPA snippets appear in the [IntelliSense](https://code.visualstudio.com/docs/editor/intellisense) completion list.

Selecting a LiberRPA completion inserts the snippet and updates its required imports.

![typeToAdd](md_images/README/typeToAdd.gif)

## Managed Imports

LiberRPA automatically maintains a managed import block in Python files:

```python
# <LiberRPA imports: managed>
# This block is managed by LiberRPA. Do not edit it manually.
# ruff: isort: off
from liberrpa.Modules import (
    Mouse,
    PrjArgs,
)
# ruff: isort: on
# </LiberRPA imports: managed>
```

When you insert a snippet by clicking, dragging, or using IntelliSense, the required imports are merged into this block.

Imports are deduplicated and ordered according to the snippet catalog.

Do not manually edit content inside the managed block. Imports written outside the block are not modified by LiberRPA.

If a Python file does not yet contain the block, LiberRPA inserts it after the module header, module docstring, and any `__future__` imports.

## Project Values

The **Project Values** category contains expression snippets for values provided by the current RPA project:

```python
PrjArgs.elapsedTime
PrjArgs.errorObj
PrjArgs.projectPath
```

Unlike ordinary statement snippets, these values are inserted directly at the current cursor position.

Dynamic `CustomArgs` keys are provided through IntelliSense rather than TreeView nodes. The available keys are read from the current project's `project.flow`, including unsaved editor changes.

For example:

```python
CustomArgs["customerName"]
```

Selecting a CustomArgs completion automatically adds `CustomArgs` to the managed import block.

## Use Secondary Side Bar

When developing a new RPA project, you might need to switch between [VS Code Explorer](https://code.visualstudio.com/docs/getstarted/userinterface#_explorer-view) and LiberRPA Snippets Tree. To streamline your workflow, it is recommended to move LiberRPA Snippets Tree into [VS Code Secondary Sidebar](https://code.visualstudio.com/api/ux-guidelines/sidebars#secondary-sidebar).

You can open the Secondary Sidebar, then drag the LiberRPA Snippets Tree icon from [VS Code Activity Bar](https://code.visualstudio.com/api/ux-guidelines/activity-bar) into the Secondary Sidebar.

![moveToSecondarySidebar_1](md_images/README/moveToSecondarySidebar_1.gif)

Alternatively, drag the LiberRPA Snippets Tree icon from the Activity Bar and drop it at the right region of [VS Code Editor](https://code.visualstudio.com/api/ux-guidelines/overview#editor).

![moveToSecondarySidebar_2](md_images/README/moveToSecondarySidebar_2.gif)

You can also move LiberRPA Snippets Tree back to Activity Bar.

![MoveBack](md_images/README/MoveBack.gif)

## User-defined Code Snippets

Frequently used Snippets can be added to the Favorite Snippet file:

```text
C:\Users\<username>\Documents\LiberRPA\snippets_favorite.jsonc
```

If the file does not exist, LiberRPA Snippets Tree creates it from the bundled template when the extension loads.

The parent `Documents\LiberRPA` folder must already exist. Run `InitLiberRPA.exe` to initialize or update the required LiberRPA folders and configuration.

Favorite Snippets are:

- displayed in the `Favorite` Category at the top of LiberRPA Snippets Tree;
- available through IntelliSense;
- inserted through the same click, drag-and-drop, and completion workflows as built-in and Component Snippets;
- able to update the LiberRPA Managed Import block.

![1740387312562](md_images/README/1740387312562.png)

### File Structure

The Favorite file uses the following structure:

```jsonc
{
  "schemaVersion": 1,
  "snippets": {}
}
```

Each property inside `snippets` defines one Favorite Snippet.

The property key is the Favorite title and should be unique within the file:

```jsonc
"Custom Delay": {
  // Snippet fields
}
```

When `label` is not provided, the title is also used as the text displayed in LiberRPA Snippets Tree.

Favorite Snippets use the same core Snippet fields as generated Catalog entries, but several fields are optional and every Favorite is always placed in the `Favorite` Category.

If a copied Catalog entry contains `category`, the value is ignored.

### Copy an Existing Snippet

The easiest way to create a Favorite is to copy a complete entry from the `snippets` object in the built-in [Snippet Catalog](https://github.com/HUHARED/LiberRPA/blob/main/vscodeExtensions/liberrpa-snippets-tree/assets/snippets_catalog.json).

Keeping the complete entry preserves important metadata such as:

- `prefix`;
- `body`;
- `description`;
- `label`;
- `insertionMode`;
- `imports`.

You can then change its Favorite title, label, prefix, body, or description as needed.

Changing the Favorite title does not remove its `imports` or insertion metadata because those values are stored inside the Snippet entry.

A Favorite copied from a Component Catalog can be used only in Projects where the corresponding Component and import source are available.

### Snippet Fields

#### `prefix`

`prefix` is required.

It is the text used to find the Favorite through IntelliSense:

```jsonc
"prefix": "custom_delay"
```

The prefix does not need to match the Favorite title.

#### `body`

`body` is required.

It can be one string:

```jsonc
"body": "PrjArgs.projectPath"
```

or a list of lines:

```jsonc
"body": [
  "delay(${1:1000})",
  "$0"
]
```

VS Code Snippet placeholders are supported:

```text
$1
${1:default value}
${1|first,second,third|}
$0
```

For Favorite Snippets, `$0` is not added automatically. Include it in `body` when a specific final cursor position is required.

#### `label`

`label` is optional.

It controls the text displayed for the Snippet in LiberRPA Snippets Tree:

```jsonc
"label": "custom delay"
```

When omitted, the Favorite title is used.

#### `description`

`description` is optional.

It is shown in LiberRPA Snippets Tree and IntelliSense:

```jsonc
"description": "Wait for a specified time, in milliseconds."
```

When omitted, LiberRPA uses a generic fallback description.

#### `insertionMode`

`insertionMode` is optional and defaults to `line`.

```text
line
```

inserts the Snippet as a statement. When necessary, LiberRPA creates a new line with the current indentation.

```text
cursor
```

inserts the Snippet directly at the current cursor position or replaces the current selection.

Use `cursor` for expressions such as:

```python
PrjArgs.projectPath
```

Example:

```jsonc
"insertionMode": "cursor"
```

#### `imports`

`imports` is optional.

It lists names that should be merged into the LiberRPA Managed Import block when the Favorite is inserted:

```jsonc
"imports": {
  "liberrpa.Modules": [
    "delay",
    "PrjArgs"
  ]
}
```

Imports are grouped by Python import source.

Copying the `imports` field from an existing built-in or Component Snippet is the safest way to preserve the correct source and import names.

A Favorite that imports a Component Module requires that Component to be installed in the current Project. Otherwise, the import source is unavailable and the generated Python code cannot run correctly.

Do not include Python alias syntax in the import-name list. Component aliases are derived automatically from the loaded Component Catalog.

### Reload Favorite Snippets

After saving `snippets_favorite.jsonc`, open VS Code Command Palette and run:

```text
Developer: Reload Window
```

LiberRPA Snippets Tree reloads the Favorite file when the VS Code window starts.

If the file contains invalid JSONC or unsupported Snippet fields:

- LiberRPA displays a warning;
- Favorite Snippets are skipped for that window;
- built-in and Component Snippets remain available.

Correct the file and run `Developer: Reload Window` again.

### Complete Example

```jsonc
{
  "schemaVersion": 1,

  "snippets": {
    "Custom Delay": {
      "prefix": "custom_delay",
      "label": "custom delay",
      "body": [
        "delay(${1:1000})",
        "$0"
      ],
      "description": "Wait for a specified time, in milliseconds.",
      "insertionMode": "line",
      "imports": {
        "liberrpa.Modules": [
          "delay"
        ]
      }
    },

    "Current Project Path": {
      "prefix": "favorite.project_path",
      "label": "current project path",
      "body": "PrjArgs.projectPath",
      "description": "Insert the absolute path of the current LiberRPA Project.",
      "insertionMode": "cursor",
      "imports": {
        "liberrpa.Modules": [
          "PrjArgs"
        ]
      }
    }
  }
}
```

# Known Issues

* The TreeView itself does not currently provide a search box. Use IntelliSense to search snippets by typing their prefix or API name, or refer to the [LiberRPA API](https://github.com/HUHARED/LiberRPA/tree/main/condaLibrary#api).
* IntelliSense Suggestions May Not Reopen After an Invalid Prefix
  * When typing a LiberRPA Snippet prefix, the IntelliSense suggestion list may close after the entered text no longer matches any available Snippet.
    For example, a partial prefix may initially match a Snippet, but entering an additional incorrect character can close the suggestion list. Deleting only that incorrect character may not reopen the previous suggestions, and manually running `Trigger Suggest` with `Ctrl+Space` may still return no matching LiberRPA Snippets.
    As a workaround, press `Ctrl+Backspace` to remove the current prefix, then type it again. You can also insert the Snippet through LiberRPA Snippets Tree or drag-and-drop.
    This issue affects only the IntelliSense suggestion interface. Snippet insertion through Tree View or drag-and-drop, Managed Imports, and Python execution are not affected.
