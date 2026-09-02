# Component Snippet Configuration

This document describes the user-maintained `_Snippets/snippets.jsonc` file used when publishing a LiberRPA Component.

For the publication workflow, see [LiberRPA Project Manager](./README.md#publish-a-component). For a complete working example, see the [Example Delay Component walkthrough](./ExampleDelayComponent.md).

## Snippet Preparation Files

The first `LiberRPA: Publish Component` operation creates:

```text
_Snippets/
├── ast.snippets.json
└── snippets.jsonc
```

`ast.snippets.json` contains the current source scan result, generated Snippets, skipped functions, and warnings. LiberRPA regenerates it during publication. Do not edit it manually.

`snippets.jsonc` contains the Component developer's configuration. It is created only when missing and is preserved during later publications.

Keep all top-level fields, even when their values are empty:

```jsonc
{
  "schemaVersion": 1,
  "categoryIcons": {},
  "excludedAstSnippets": [],
  "astSnippetOverrides": {},
  "snippets": {}
}
```

After editing and saving `snippets.jsonc`, run `LiberRPA: Publish Component` again to validate the configuration and rebuild the final Snippet Catalog.

## Category Icons

Use `categoryIcons` to replace the default `library` icon for selected public Component Module categories:

```jsonc
"categoryIcons": {
  "Delay": "watch",
  "Preset": "list-tree"
}
```

Each key is a public top-level Component Module name. Each value must be a lower-case VS Code Product Icon identifier.

Choose an identifier from the second table under [Icon Listing](https://code.visualstudio.com/api/references/icons-in-labels#icon-listing). The second table contains the general Codicon identifiers intended for extensions.

Examples:

```text
watch
beaker
database
list-tree
symbol-method
```

Modules not listed in `categoryIcons` use the default `library` icon. The object may remain empty.

Custom image paths, SVG files, PNG files, and remote images are not supported.

## Exclude AST-generated Snippets

Use `excludedAstSnippets` when a public function should remain available through the Python API but should not appear in LiberRPA Snippets Tree.

Copy the stable key from `ast.snippets.json`:

```jsonc
"excludedAstSnippets": [
  "ExampleDelay_Delay.sec_20"
]
```

Excluding a Snippet does not remove the function from the Component package.

When a Module or function is intended to be internal, prefer a name that starts with `_`.

A key that no longer exists in the latest AST scan produces a warning. Remove obsolete keys when they are no longer needed.

## Override AST-generated Snippets

Use `astSnippetOverrides` to customize selected fields of an existing AST-generated Snippet:

```jsonc
"astSnippetOverrides": {
  "ExampleDelay_Preset.delay_by_preset": {
    "label": "delay by preset",
    "description": "Delay execution using a named Component preset."
  }
}
```

The key must exist in the latest `ast.snippets.json`.

The following fields can be overridden:

* `label`;
* `body`;
* `description`;
* `insertionMode`;
* `imports`.

Fields not specified continue to use their generated values.

The stable key, `category`, `prefix`, and mandatory import for the owning Component Module cannot be overridden.

An excluded AST Snippet cannot also have an override. To replace the behavior of a generated Snippet, use an override rather than excluding it and creating a hand-written Snippet with the same key.

## Add Hand-written Snippets

Use `snippets` to define Snippets that are not generated directly from a public function. They can represent expressions, reusable code blocks, or common sequences of Component calls.

Each stable key must use:

```text
PackageName_ModuleName.snippet_name
```

For example:

```text
ExampleDelay_Delay.run_quick_demo
```

The package and Module names must belong to the current Component. `ModuleName` must identify an existing public top-level `.py` file under `src/<PackageName>/`. A package-level form such as `PackageName.snippet_name` is not supported.

The owning Module does not need to contain an AST-supported public function when the hand-written Snippet represents a sequence or expression. It still defines the Snippet Category and mandatory Component Module import.

Required fields:

* `body`;
* `description`.

Optional fields:

* `prefix`, which defaults to the stable key;
* `label`, which defaults to `snippet_name`;
* `insertionMode`, which defaults to `line`;
* `imports`, which adds further Managed Imports.

The Category and mandatory Component Module import are derived from the stable key.

A hand-written Snippet cannot use the key of an AST-generated Snippet. Use `astSnippetOverrides` to customize an AST-generated Snippet.

## Insertion Modes and Placeholders

`insertionMode` controls how the Snippet is inserted.

`line` inserts one or more statements. LiberRPA creates a new line with the current indentation when needed. For a Component Snippet using `line`, LiberRPA adds `$0` as the final body line when it is not already present.

`cursor` inserts directly at the current cursor position or replaces the current selection. Its body is kept as written.

Use `cursor` for expressions such as:

```python
ExampleDelay_Preset.get_preset_seconds(presetName="short")
```

VS Code Snippet placeholders are supported:

```text
$1
${1:default value}
${1|first,second,third|}
$0
```

`body` can be either a string or a list of strings.

## Additional Managed Imports

Use `imports` when a Snippet requires objects in addition to its automatically derived Component Module import:

```jsonc
"imports": {
  "liberrpa.Modules": [
    "Log"
  ],
  "ExampleDelay": [
    "Preset"
  ]
}
```

Imports are grouped by Python import source.

Component Snippet configuration can use public names from `liberrpa.Modules` and public Modules from the current Component package.

List the original import names only. LiberRPA generates Component aliases such as `ExampleDelay_Preset` automatically.

When the Snippet is inserted, LiberRPA Snippets Tree merges the declared imports into the Python file's Managed Import block. Do not add alias syntax to `imports` or manually edit the generated block.

## Snippet Order

Within each Component Category:

1. AST-generated Snippets follow the order of their functions in the Python source file.
2. Hand-written Snippets follow the generated Snippets.
3. Hand-written Snippets preserve their declaration order in `snippets.jsonc`.

## Validation

Publication is rejected when `snippets.jsonc` contains invalid configuration, including unsupported fields, invalid stable keys, unknown public Modules, invalid overrides, duplicate prefixes, duplicate labels in one Category, invalid insertion modes, or unavailable import names.

The final Catalog must contain at least one Snippet. A Component may expose additional public APIs without Snippets, but publication is rejected when every AST-generated Snippet is excluded and no hand-written Snippet remains.

Project Manager displays the error and available details. Correct the file, save it, and publish again.

A stale key in `excludedAstSnippets` produces a warning rather than blocking publication.

## Complete Configuration Example

```jsonc
{
  "schemaVersion": 1,

  "categoryIcons": {
    "Delay": "watch",
    "Experimental": "beaker",
    "Preset": "list-tree"
  },

  "excludedAstSnippets": [
    "ExampleDelay_Delay.sec_20"
  ],

  "astSnippetOverrides": {
    "ExampleDelay_Preset.delay_by_preset": {
      "label": "delay by preset",
      "description": "Delay execution using a named Component preset."
    },
    "ExampleDelay_Experimental.delay_for_review": {
      "description": "Delay for a configurable duration."
    }
  },

  "snippets": {
    "ExampleDelay_Delay.run_quick_demo": {
      "prefix": "ExampleDelay.run_quick_demo",
      "label": "run quick demo",
      "body": [
        "Log.info(\"Start ExampleDelay demo.\")",
        "ExampleDelay_Delay.sec_1()",
        "ExampleDelay_Preset.delay_by_preset(presetName=\"short\")",
        "Log.info(\"ExampleDelay demo completed.\")"
      ],
      "description": "Run a short demonstration of the ExampleDelay Component.",
      "insertionMode": "line",
      "imports": {
        "liberrpa.Modules": [
          "Log"
        ],
        "ExampleDelay": [
          "Preset"
        ]
      }
    },

    "ExampleDelay_Preset.short_preset_seconds": {
      "prefix": "ExampleDelay.short_preset_seconds",
      "label": "short preset seconds",
      "body": "ExampleDelay_Preset.get_preset_seconds(presetName=\"short\")",
      "description": "Get the duration of the short ExampleDelay preset.",
      "insertionMode": "cursor"
    }
  }
}
```

Mandatory imports for `ExampleDelay_Delay` and `ExampleDelay_Preset` are derived from their stable keys. Only additional requirements such as `Log` and `Preset` need to be declared explicitly.
