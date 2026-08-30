# liberrpa

`liberrpa` is the core Python library of LiberRPA, an open-source RPA toolchain for Windows.

It provides the public Python APIs used by LiberRPA Projects and also contains internal modules used by LiberRPA tools and runtime services.

For normal use, the recommended approach is to download the complete LiberRPA release rather than installing this package by itself. The complete distribution includes the tested Python environment, Editor, Project templates, UI Analyzer, Local Server integration, Chrome Extension support, Executor, and other required resources.

The `liberrpa` package is also published on PyPI for advanced use cases such as development, debugging, or manually maintaining a compatible Python environment.

## Python Version

LiberRPA 0.3.0 requires:

```text
Python >=3.13,<3.14
```

The standard LiberRPA interpreter is located at:

```text
<LiberRPA root>\envs\pyenv\default\python.exe
```

See [Python Environment](../docs/Environment.md) for the standard environment and dependency-management policy.

## Dependency Management

The complete LiberRPA runtime dependency set is managed by the standard LiberRPA Python environment rather than by `setup.py`.

Installing only:

```text
pip install liberrpa
```

does not reconstruct the complete LiberRPA runtime environment. Users who install the package separately are responsible for providing the dependencies required by the modules they use.

For the Conda-first dependency policy, `environment.yml`, the Windows release snapshot, clean rebuilds, and release verification, see [Python Environment](../docs/Environment.md).

## Development Installation

When developing `liberrpa` from the repository source, the package can be installed into the development environment in editable mode.

From the `condaLibrary` directory:

```bat
python -m pip install -e . --no-deps --config-settings editable_mode=compat
```

`--no-deps` is intentional because the development environment dependencies are managed separately through Conda and the LiberRPA environment definition.

## Project Context

LiberRPA provides two global objects for information associated with the current Flow Project:

```text
PrjArgs
CustomArgs
```

`PrjArgs` contains runtime Project information such as:

- `projectPath` — absolute path of the current Project;
- `projectName` — current Project directory name;
- `errorObj` — current Flow-level exception, or `None` when no Flow error is being handled;
- `elapsedTime` — elapsed seconds since Project runtime initialization;
- `customArgs` — dictionary containing custom Project arguments.

`CustomArgs` is a direct reference to:

```python
PrjArgs.customArgs
```

For example:

```python
print(PrjArgs.projectPath)
print(PrjArgs.projectName)
print(PrjArgs.elapsedTime)
print(PrjArgs.errorObj)
print(CustomArgs)
```

## Code Reference

The generated **LiberRPA Code Reference** documents the categories and entries available through LiberRPA Snippets Tree.

It includes:

- LiberRPA APIs;
- Project values;
- LiberRPA-specific code templates;
- general Python convenience snippets included with LiberRPA Editor.

See:

[**LiberRPA Code Reference**](../docs/Reference.md)

The Reference is generated from the same Snippet catalog used by LiberRPA Snippets Tree, with additional API metadata derived from the corresponding Python objects and docstrings where available.

## Related Documentation

- [Getting Started](../docs/GettingStarted.md)
- [Python Environment](../docs/Environment.md)
- [LiberRPA Editor](../docs/Editor.md)
- [Architecture](../docs/Architecture.md)
- [LiberRPA Snippets Tree](../vscodeExtensions/liberrpa-snippets-tree/README.md)

## License

`liberrpa` is part of LiberRPA and is licensed under the **GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later)**.

See [LICENSE](../LICENSE) for the complete license terms.
