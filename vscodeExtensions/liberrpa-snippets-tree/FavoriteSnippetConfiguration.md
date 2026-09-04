# Favorite Snippet Configuration

This document describes the user-maintained `snippets_favorite.jsonc` file used by LiberRPA Snippets Tree.

For normal insertion workflows, see [LiberRPA Snippets Tree](./README.md).

## File Location

The Favorite file is stored at:

```text
C:/Users/<UserName>/Documents/LiberRPA/snippets_favorite.jsonc
```

If it does not exist, LiberRPA Snippets Tree creates it from the bundled template when the extension loads.

The parent `Documents/LiberRPA` folder must already exist. Run `InitLiberRPA.exe` to initialize or update the required LiberRPA folders.

## Editor Assistance

LiberRPA Snippets Tree automatically associates `snippets_favorite.jsonc` with its bundled JSON Schema. The file does not need a `$schema` field.

VS Code provides field descriptions on hover, field and object-template completion, `insertionMode` value completion, static completion for built-in `liberrpa.Modules` names, and immediate structural validation. The extension's runtime validation remains authoritative when Favorite Snippets are loaded.

## File Structure

```jsonc
{
  "schemaVersion": 1,
  "snippets": {}
}
```

Each property inside `snippets` defines one Favorite Snippet. Its property key is the Favorite title and must be unique within the file:

```jsonc
"Custom Delay": {
  // Snippet fields
}
```

When `label` is omitted, the title is also used as the text displayed in LiberRPA Snippets Tree.

Every Favorite is placed in the `Favorite` Category. If a copied Catalog entry contains `category`, that value is ignored.

## Copy an Existing Snippet

The easiest way to create a Favorite is to copy a complete entry from the `snippets` object in the built-in [Snippet Catalog](https://github.com/HUHARED/LiberRPA/blob/main/vscodeExtensions/liberrpa-snippets-tree/assets/snippets_catalog.json).

Keeping the complete entry preserves its prefix, body, description, label, insertion mode, and imports. You can then edit the fields you need.

A Favorite copied from a Component Catalog can be used only in Projects where the corresponding Component and import source are available.

## Fields

### `prefix`

`prefix` is required. It is the text used to find the Favorite through IntelliSense:

```jsonc
"prefix": "custom_delay"
```

It does not need to match the Favorite title.

### `body`

`body` is required. It can be one string:

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

For Favorite Snippets, `$0` is not added automatically. Include it when a specific final cursor position is required.

### `label`

`label` is optional. It controls the text displayed in LiberRPA Snippets Tree:

```jsonc
"label": "custom delay"
```

When omitted, the Favorite title is used.

### `description`

`description` is optional. It is shown in the Tree and IntelliSense:

```jsonc
"description": "Wait for a specified time, in milliseconds."
```

When omitted, LiberRPA uses a fallback description.

### `insertionMode`

`insertionMode` is optional and defaults to `line`.

`line` inserts the Snippet as one or more statements. LiberRPA creates a new line with the current indentation when needed.

`cursor` inserts directly at the cursor or replaces the current selection. Use it for expressions such as:

```python
PrjArgs.projectPath
```

```jsonc
"insertionMode": "cursor"
```

### `imports`

`imports` is optional. It lists names that should be merged into the LiberRPA Managed Import block:

```jsonc
"imports": {
  "liberrpa.Modules": [
    "delay",
    "PrjArgs"
  ]
}
```

Imports are grouped by Python import source.

Copying `imports` from an existing built-in or Component Snippet is the safest way to preserve the correct source and names.

A Favorite that imports a Component Module requires that Component to be available in the current Project.

List original import names only. Do not include Python alias syntax; Component aliases are derived from the loaded Component Catalog.

## Reload Favorite Snippets

After saving `snippets_favorite.jsonc`, run:

```text
Developer: Reload Window
```

If the file contains invalid JSONC or unsupported fields, Favorite Snippets are skipped for that window while built-in and Component Snippets remain available. Correct the file and reload the window again.

## Complete Example

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
