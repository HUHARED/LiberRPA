# LiberRPA Snippets Tree

(If you can't see the images in the document, have a look on [GitHub](https://github.com/HUHARED/LiberRPA/blob/main/vscodeExtensions/liberrpa-snippets-tree/README.md).)

This extension is a part of LiberRPA to displays built-in and user-defined [code snippets](https://code.visualstudio.com/docs/editor/userdefinedsnippets).

With it, you don't need to memorize the entire [LiberRPA API](https://github.com/HUHARED/LiberRPA/tree/main/condaLibrary#api).

> **Note:**
>
> LiberRPA Snippets Tree has been updated since these animations were recorded.
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
from liberrpa.Modules import (
    Mouse,
    PrjArgs,
)
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

You can define frequently used snippets in:

```text
C:/Users/<username>/Documents/LiberRPA/snippets_favorite.jsonc
```

Favorite snippets use the same snippet-item structure as `assets/snippets_catalog.json`. You can copy a complete entry from the catalog's `snippets` object, or create your own entry. The optional `imports` field lists names that should be added to the LiberRPA managed import block.

The optional `insertionMode` field controls how a TreeView click inserts the snippet:

- `"line"` inserts the snippet as a statement, creating a new line when necessary.
- `"cursor"` inserts it directly at the current cursor position.

    The default value is`"line"`.

The imports field is copied together with the snippet, so renaming a favorite snippet does not remove its import metadata.

After editing the file, run `Developer: Reload Window` in VS Code.

```jsonc
{
  "schemaVersion": 1,
  "snippets": {
    "Custom Delay": {
      "prefix": "custom_delay",
      "body": ["delay(${1:1000})", "$0"],
      "description": "Wait for a specified time, in milliseconds.",
      "insertionMode": "line",
      "imports": {
        "liberrpa.Modules": ["delay"]
      }
    }
  }
}
```

LiberRPA Snippets Tree will display these snippets in a `Favorite` category at the top:

![1740387312562](md_images/README/1740387312562.png)

# Known Issues

* Undoing a drag-and-drop insertion several times may temporarily reveal LiberRPA's internal drop placeholder. Continue undoing once more to remove it.

  ![1740386186601](md_images/README/1740386186601.png)
* The TreeView itself does not currently provide a search box. Use IntelliSense to search snippets by typing their prefix or API name, or refer to the [LiberRPA API](https://github.com/HUHARED/LiberRPA/tree/main/condaLibrary#api).
