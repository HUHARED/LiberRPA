# LiberRPA Snippets Tree

If the images are not displayed, [view this README on GitHub](https://github.com/HUHARED/LiberRPA/blob/main/vscodeExtensions/liberrpa-snippets-tree/README.md).

**LiberRPA Snippets Tree** displays built-in, Favorite, and Component Snippets and inserts them into Python files together with their required imports.

You do not need to memorize the complete [LiberRPA API](https://github.com/HUHARED/LiberRPA/tree/main/condaLibrary#api).

> **Note:**
>
> Screenshots and animations in this document are provided for reference. As LiberRPA evolves, the current interface may differ slightly in appearance or wording, but these minor differences do not affect the documented workflow or functionality.
> For example:
>
> * The icon has changed from ![old icon](./md_images/README/LiberRPA_icon_v2_line_32px.png) to ![new icon](./md_images/README/LiberRPA_icon_v3_monochrome_plain_32px.png).
> * The current interface and Managed Import Block structure may differ slightly from what is shown.

> **Extension logs:**
>
> This extension writes diagnostic messages to the `liberrpa-snippets-tree` channel in the VS Code Output panel.
>
> Open `View > Output` and select the channel, or run `Output: Show Output Channels` from the Command Palette.
>
> For troubleshooting, run `Developer: Set Log Level...`, select `liberrpa-snippets-tree`, and choose `Debug` or `Trace`. `Info` is normally sufficient for routine use.
>
> This setting does not change the Python runtime log level used by a Flow Project or an individual Block.

## Usage

### Insert Snippets

LiberRPA Snippets can be inserted into Python files by clicking, dragging, or using IntelliSense. All three methods update the Managed Import block when imports are required.

#### Click a Tree Node

Click a Snippet in **LiberRPA Snippets Tree**.

Statement Snippets are inserted on the current empty line or on a new line with matching indentation. Expression Snippets, such as Project Values, are inserted at the cursor or replace the current selection.

![clickToAdd](md_images/README/clickToAdd.gif)

#### Drag and Drop

Drag a Snippet from the Tree to the required editor position.

![dragToAdd](md_images/README/dragToAdd.gif)

#### IntelliSense

Type a Snippet prefix or identifying text in a Python file and select the LiberRPA completion. IntelliSense supports abbreviated matching, so, for example, `deb` can match `Log.debug`, `to_upper` can match `Str.case_to_upper`, and `exop` can match `Excel.open_excel_file`.

The completion details show the Snippet body and description before insertion.

![typeToAdd](md_images/README/typeToAdd.gif)

#### Snippet Placeholders

After insertion, press `Tab` to move through editable Snippet fields.

Some parameters provide a predefined list of valid values. To enter a variable or another expression instead, press `Esc` twice: the first press closes the choice list, and the second exits the active Snippet placeholder mode so normal Python IntelliSense can resume.

After exiting the placeholder mode, `Tab` no longer moves through the remaining Snippet fields.

### Managed Imports

LiberRPA maintains a Managed Import block in Python files:

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

Required imports are merged, deduplicated, and ordered according to the loaded Snippet Catalogs.

Do not manually edit content inside the Managed Import block. Imports outside the block are not modified.

When a file does not yet contain the block, LiberRPA inserts it after the module header, module docstring, and any `__future__` imports.

### Project Values

The **Project Values** Category contains expression Snippets supplied by the current RPA Project, for example:

```python
PrjArgs.elapsedTime
PrjArgs.errorObj
PrjArgs.projectPath
```

Dynamic `CustomArgs` keys are provided through IntelliSense and are read from the current `project.flow`, including unsaved editor changes:

```python
CustomArgs["customerName"]
```

Selecting a Project Value or CustomArgs completion also adds its required import.

### Use the Secondary Sidebar

To keep VS Code Explorer and LiberRPA Snippets Tree visible at the same time, move the Snippets Tree view to the [Secondary Sidebar](https://code.visualstudio.com/api/ux-guidelines/sidebars#secondary-sidebar).

Drag its icon from the Activity Bar into the Secondary Sidebar:

![moveToSecondarySidebar_1](md_images/README/moveToSecondarySidebar_1.gif)

You can also drag it to the right side of the editor:

![moveToSecondarySidebar_2](md_images/README/moveToSecondarySidebar_2.gif)

Move it back to the Activity Bar when needed:

![MoveBack](md_images/README/MoveBack.gif)

### Favorite Snippets

Frequently used Snippets can be added to:

```text
C:/Users/<UserName>/Documents/LiberRPA/snippets_favorite.jsonc
```

If the file does not exist, LiberRPA Snippets Tree creates it from the bundled template when the extension loads. Run `InitLiberRPA.exe` first so that the required LiberRPA folders exist.

Favorite Snippets appear in the `Favorite` Category, are available through IntelliSense, and use the same click, drag-and-drop, and Managed Import workflows as other Snippets.

![1740387312562](md_images/README/1740387312562.png)

The easiest way to create a Favorite is to copy an entry from the built-in [Snippet Catalog](https://github.com/HUHARED/LiberRPA/blob/main/vscodeExtensions/liberrpa-snippets-tree/assets/snippets_catalog.json), then edit its title, prefix, body, label, or description.

After saving the file, run `Developer: Reload Window` to reload Favorite Snippets.

See [Favorite Snippet Configuration](./FavoriteSnippetConfiguration.md) for the complete file structure, field definitions, imports, insertion modes, and examples.

## Known Issues

* The TreeView does not provide a search box. Use IntelliSense to search by prefix or a meaningful part of the API name, or refer to the [LiberRPA API](https://github.com/HUHARED/LiberRPA/tree/main/condaLibrary#api).
* After an invalid extra character closes the IntelliSense list, deleting only that character may not restore the previous suggestions, and `Ctrl+Space` may still return no LiberRPA Snippets. Press `Ctrl+Backspace` to remove the current prefix and type it again, or insert the Snippet through the Tree or drag-and-drop. This affects only IntelliSense suggestions, not Snippet insertion, Managed Imports, or Python execution.
