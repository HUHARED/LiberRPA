# LiberRPA Snippets Tree

This extension is a part of LiberRPA to displays built-in and user-defined [code snippets](https://code.visualstudio.com/docs/editor/userdefinedsnippets).

With it, you don't need to memorize the entire [LiberRPA API](https://github.com/HUHARED/LiberRPA/tree/main/condaLibrary#api).

# Usage

## Insert Snippets

You can add code snippets to your Python files in the editor using these methods:

1. **Click:**
   Simply click an item in LiberRPA Snippets Tree with your mouse.
   If the current line of cursor is not empty, the snippets will be insert to the next line with the same indent.

<video width="1258" controls>
  <source src="./md_images/clickToAdd.mp4" type="video/mp4">
  Your browser not supports video in Markdown.
</video>

2. **Drag and Drop:**
   Drag an item from LiberRPA Snippets Tree into your editor.

<video width="1258" controls>
  <source src="./md_images/dragToAdd.mp4" type="video/mp4">
  Your browser not supports video in Markdown.
</video>

3. **Type the Prefix:**
   Type the corresponding code snippet prefix in the editor, the snippets will appear in [IntelliSense](https://code.visualstudio.com/docs/editor/intellisense).

<video width="1258" controls>
  <source src="./md_images/typeToAdd.mp4" type="video/mp4">
  Your browser not supports video in Markdown.
</video>

## Use Secondary Side Bar

When developing a new RPA project, you might need to switch between [VS Code Explorer](https://code.visualstudio.com/docs/getstarted/userinterface#_explorer-view) and LiberRPA Snippets Tree. To streamline your workflow, it is recommended to move LiberRPA Snippets Tree into [VS Code Secondary Sidebar](https://code.visualstudio.com/api/ux-guidelines/sidebars#secondary-sidebar).

You can open the Secondary Sidebar, then drag the LiberRPA Snippets Tree icon from [VS Code Activity Bar](https://code.visualstudio.com/api/ux-guidelines/activity-bar) into the Secondary Sidebar.

<video width="1258" controls>
  <source src="./md_images/moveToSecondarySidebar_1.mp4" type="video/mp4">
  Your browser not supports video in Markdown.
</video>

Alternatively, drag the LiberRPA Snippets Tree icon from the Activity Bar and drop it at the right region of [VS Code Editor](https://code.visualstudio.com/api/ux-guidelines/overview#editor).

<video width="1258" controls>
  <source src="./md_images/moveToSecondarySidebar_2.mp4" type="video/mp4">
  Your browser not supports video in Markdown.
</video>

You can also move LiberRPA Snippets Tree back to Activity Bar.

<video width="1258" controls>
  <source src="./md_images/MoveBack.mp4" type="video/mp4">
  Your browser not supports video in Markdown.
</video>

## User-defined Code Snippets

You can define your frequently used snippets by editing the file: `C:/Users/<username>/Documents/LiberRPA/snippets_favorite.jsonc`

Below is an example configuration:

```json
// FineName: snippets_favorite.jsonc
{
  // Copy any snippets from https://github.com/HUHARED/LiberRPA/vscodeExtensions/liberrpa-snippets-tree/assets/snippets_final.snippets and paste them in here, these snippets will be put at the top in LiberRPA Snippets Tree.
  // And you can write your custom snippets in here too.
  // After you modified the file, restart vscode to make the changement works.
  // Example:

  "Test Snippets": {
    "prefix": "test",
    "body": ["delay(${1:1000})", ""],
    "description": "Delay some time, in milliseconds."
  }
}
```

LiberRPA Snippets Tree will display these snippets in a `Favorite` category at the top:

![1740387312562](md_images/README/1740387312562.png)

# Known Issues

* If you drag and drop a LiberRPA snippet and then undo(press `Ctrl+Z`) the editing twice consecutively, you can see a placeholder text:
  `$LIBERRPA_SNIPPET_DROP_PLACEHOLDER(you may see it when you undo(Ctrl+Z), please undo again.) `
  This placeholder is used by LiberRPA to locate the drop position due to a limitation in VS Code.
  Simply press Ctrl+Z once more to remove it.

  ![1740386186601](md_images/README/1740386186601.png)
* LiberRPA Snippets Tree doe not support searching for snippets. To locate snippets, please refer to the [LiberRPA API](https://github.com/HUHARED/LiberRPA/tree/main/condaLibrary#api).
