# `<Component Name>`

## Overview

Describe what this Component provides, the problem it solves, and the Projects or developers it is intended for.

Replace `<Component Name>` with the actual Component display name.

## Add to a Project

Publish or import the Component Wheel into the configured LiberRPA Component Repository, then use:

```text
LiberRPA: Manage Components
```

to add the Component to a Flow Project or another Component Project.

See the [LiberRPA Project Manager documentation](https://github.com/HUHARED/LiberRPA/blob/main/vscodeExtensions/liberrpa-project-manager/README.md#manage-components-in-a-project) for the dependency-management workflow.

## Usage

Show the shortest useful example first.

```python
from YourPackage import YourModule

YourModule.example_function()
```

Replace this example with real Component code before publishing or distributing the Component.

Add additional examples for common use cases when they make the API easier to understand.

## Public API

Document the public Modules, functions, classes, and other interfaces that callers are expected to use.

Keep this section focused on the supported public API rather than internal implementation details.

### <ModuleName>

Describe the responsibility of this Module and its public interfaces.

Delete unused placeholders and add additional Module sections as required.

## Requirements

Document requirements that are not already provided by the standard LiberRPA environment, such as:

- additional Python dependencies;
- required applications or drivers;
- services or APIs;
- files or other external resources;
- permissions or network access.

Delete this section if no additional requirements exist.

## Configuration

Describe configuration files, environment variables, credentials, or setup steps required by this Component.

Do not store plaintext passwords, tokens, or other sensitive credentials in Component source when a more appropriate credential store is available.

Delete this section if no additional configuration is required.

## Compatibility & Limitations

Document information callers need to know before using the Component, such as:

- supported application or API versions;
- required LiberRPA versions;
- unsupported scenarios;
- platform-specific behavior;
- known limitations.

Delete this section if there are no additional compatibility notes.

## Development

Component source code is stored under:

```text
src/<PackageName>/
```

The package directory directly under `src` must match `packageName` in `component.json`.

A typical Component Project contains:

```text
Project Root
├── .vscode/
├── src/
│   └── <PackageName>/
│       ├── __init__.py
│       ├── py.typed
│       └── <ModuleName>.py
├── .gitignore
├── component.json
├── LICENSE
├── README.md
└── ruff.toml
```

LiberRPA may create additional managed state during dependency management and publication, including `_Components/`, `components.lock.json`, `_Snippets/`, and `.liberrpa-project-manager/`.

This Project uses Ruff for Python linting and formatting.

Public APIs should use clear names, type annotations, and useful docstrings so that developers and generated Snippets can understand their intended use.

Document Component-specific test procedures, internal architecture, and maintenance notes here when needed.

## Snippets

LiberRPA can generate Snippets from supported public functions in public Component Modules.

Publication preparation may create:

```text
_Snippets/
├── ast.snippets.json
└── snippets.jsonc
```

`ast.snippets.json` is generated from source and must not be edited manually.

`snippets.jsonc` is maintained by the Component developer and can customize generated Snippets, add hand-written Snippets, provide category icons, or exclude selected generated entries.

A public API remains usable even when no Snippet is provided for it.

See [Component Snippet Configuration](https://github.com/HUHARED/LiberRPA/blob/main/vscodeExtensions/liberrpa-project-manager/ComponentSnippetConfiguration.md) for the complete configuration format.

## Versioning & Publishing

Component versions and version requirements follow Python PEP 440.

Increase `version` in `component.json` before publishing changed Component content.

Published versions are immutable: do not reuse an existing Component ID and version for different content.

Use:

```text
LiberRPA: Publish Component
```

to prepare Snippets, build and validate the Wheel, and publish the Component to the configured Component Repository.

See the [publishing documentation](https://github.com/HUHARED/LiberRPA/blob/main/vscodeExtensions/liberrpa-project-manager/README.md#publish-a-component) for the complete workflow.

## Version Control

Commit:

- source under `src/`;
- `component.json`;
- `components.lock.json` when present;
- `_Snippets/snippets.jsonc` when present;
- documentation and tests.

Generated state such as `_Components/`, `_Snippets/ast.snippets.json`, `.liberrpa-project-manager/`, `build/`, and `dist/` is excluded by the template `.gitignore` and should not be committed during normal development.

## License

See [LICENSE](./LICENSE).
