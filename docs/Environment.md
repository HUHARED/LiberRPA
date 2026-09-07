# Python Environment

LiberRPA 0.3.0 uses a standard **Python 3.13** environment for Project development and execution.

Normal users do not need to build this environment manually. The official LiberRPA release package includes a prepared environment, and LiberRPA Editor is configured to use it automatically.

This document is mainly intended for:

* LiberRPA contributors;
* release maintainers;
* advanced users who want to understand or rebuild the runtime environment;
* users who install the `liberrpa` Python package separately.

## Contents

* [Standard Environment](#standard-environment)
* [Why LiberRPA Provides a Standard Environment](#why-liberrpa-provides-a-standard-environment)
* [Environment Files](#environment-files)
* [Rebuild the Environment](#rebuild-the-environment)
* [Dependency Management Policy](#dependency-management-policy)
* [Install liberrpa](#install-liberrpa)
* [Adding or Updating Dependencies](#adding-or-updating-dependencies)
* [Release Environment Snapshot](#release-environment-snapshot)
* [Verification](#verification)

---

## Standard Environment

The standard LiberRPA Python interpreter is located at:

```text
<LiberRPA root>\envs\pyenv\default\python.exe
```

LiberRPA Editor is configured to use:

```text
${env:LiberRPA}\envs\pyenv\default\python.exe
```

as its default Python interpreter.

LiberRPA 0.3.0 requires:

```text
Python >=3.13,<3.14
```

The standard environment contains dependencies used by the complete LiberRPA automation API, including desktop automation, browser integration, Office automation, databases, networking, document processing, OCR, image processing, and supporting runtime services.

---

## Why LiberRPA Provides a Standard Environment

A typical automation Project may need only a small subset of LiberRPA's capabilities.

For example, one Project might use only browser and Excel automation while another also requires OCR, databases, email, image processing, or Windows UI Automation.

LiberRPA nevertheless provides a broad standard environment for three reasons.

### Consistent development environment

LiberRPA integrates many automation technologies behind one Python-oriented API.

Using a standard environment ensures that the Editor, Executor, built-in modules, and supporting tools operate against a known dependency set.

### Less environment assembly per Project

Without a standard environment, users would repeatedly need to determine which independent packages, versions, native dependencies, and supporting tools are required for each automation scenario.

The standard environment trades a larger installation footprint for a more complete and predictable development environment.

### Easier Project transfer

Projects developed against the standard environment can be moved between compatible LiberRPA installations without requiring every user to independently reconstruct the basic runtime stack.

Project-specific external requirements may still need additional handling when a Project intentionally uses libraries outside the standard LiberRPA environment.

---

## Environment Files

LiberRPA maintains two different environment specifications because they serve different purposes.

### `envs/environment.yml`

This is the  **human-maintained environment specification** .

It lists the direct third-party packages that LiberRPA intentionally requires.

It should remain readable and should not contain every transitive dependency selected by Conda or pip.

This is the primary file to update when LiberRPA intentionally adds or removes a runtime dependency.

### `envs/environment-win-64.yml`

This is the **release snapshot** of the tested Windows x64 environment.

It is generated from the final environment used to build and validate a release.

Unlike `environment.yml`, it may contain:

* exact package versions;
* Conda build identifiers;
* transitive dependencies;
* pip-installed packages.

Its purpose is traceability and reproduction of a particular LiberRPA release environment.

Do not use it as the primary manually maintained dependency list.

### Runtime directory

The actual environment distributed with LiberRPA is:

```text
envs\pyenv\default\
```

This directory contains installed runtime files and is not a substitute for the environment specifications above.

---

## Rebuild the Environment

> Normal LiberRPA users should use the environment included with the official release package instead of rebuilding it manually.

To rebuild the standard environment, a compatible Conda distribution is required.

From the LiberRPA repository root, create the environment at the path expected by LiberRPA Editor:

```bat
conda env create ^
  --prefix "%CD%\envs\pyenv\default" ^
  --file "envs\environment.yml"
```

If an existing environment is being rebuilt, remove or rename the old environment first instead of copying new packages over an unknown previous state.

After creation, verify the Python version:

```bat
envs\pyenv\default\python.exe --version
```

The result for LiberRPA 0.3.0 should be Python 3.13.x.

### Why use a prefix instead of only the YAML environment name?

The official LiberRPA layout expects the interpreter at:

```text
envs\pyenv\default\python.exe
```

The `name` stored in `environment.yml` is primarily descriptive. The runtime path is what the bundled LiberRPA configuration relies on.

---

## Dependency Management Policy

LiberRPA uses a **Conda-first** dependency strategy for its standard Python environment.

When a suitable package is available from `conda-forge`, the standard LiberRPA environment normally installs it through Conda. Pip is used for packages that are unavailable from the selected Conda channels or for which the required version cannot be supplied appropriately through Conda.

The `liberrpa` package itself is distributed through PyPI and can also be installed from a local source tree or Wheel.

This separation is intentional.

`liberrpa` does not declare the complete LiberRPA runtime environment through `install_requires`, because doing so would cause pip to independently resolve dependencies that are normally managed by Conda in the official LiberRPA environment.

The standard distribution therefore follows this model:

```text
Conda / conda-forge
    ↓
Most runtime dependencies

pip / PyPI
    ↓
Dependencies not supplied appropriately through Conda
    +
liberrpa

LiberRPA release
    ↓
Prepared and tested Python environment
```

As a result, installing only:

```bash
pip install liberrpa
```

does not reconstruct the complete standard LiberRPA environment.

This is intentional. Users who install `liberrpa` separately are responsible for providing the dependencies required by the modules they use.

For normal LiberRPA development and execution, the complete official LiberRPA distribution is recommended.

### BLAS implementation

The standard Windows environment explicitly selects the OpenBLAS implementation through the conda-forge `libblas` variant:

```text
libblas[build=*_openblas]
```

BLAS provides the optimized linear-algebra backend used by numerical packages such as NumPy and SciPy. Selecting the implementation explicitly keeps the LiberRPA environment independent of the platform-default BLAS choice while allowing Conda to resolve the matching `libcblas`, `liblapack`, and OpenBLAS packages.

LiberRPA code does not call OpenBLAS directly; numerical packages continue to use the normal BLAS/LAPACK interfaces.

---

## Install liberrpa

The environment specification defines third-party dependencies.

The `liberrpa` package itself is developed in:

```text
condaLibrary\
```

and should match the LiberRPA release being built.

### Development installation

For repository development, install the local source in editable mode:

```bat
envs\pyenv\default\python.exe -m pip install -e condaLibrary --no-deps --config-settings editable_mode=compat
```

This allows changes under `condaLibrary/liberrpa/` to be used without rebuilding the package after every edit.

### Release installation

For an official release, build the corresponding `liberrpa` package and install the resulting Wheel into the prepared standard environment.

For example:

```bat
envs\pyenv\default\python.exe -m pip install --no-deps condaLibrary\dist\liberrpa-0.3.0-py3-none-any.whl
```

The installed `liberrpa` version should match the LiberRPA release.

Verify it with:

```bat
envs\pyenv\default\python.exe -c "import importlib.metadata; print(importlib.metadata.version('liberrpa'))"
```

---

## Adding or Updating Dependencies

The standard environment should not grow merely because a package might be useful.

A new dependency should normally be added only when it is required by:

* an official `liberrpa` module;
* a LiberRPA runtime service;
* an officially supported automation capability;
* a development/runtime feature included in the standard distribution.

### Add a Conda dependency

Prefer `conda-forge` when a suitable package is available and works correctly with LiberRPA.

Add the direct requirement to:

```text
envs/environment.yml
```

and rebuild a clean environment to verify it.

### Add a pip dependency

Use the `pip:` section of:

```text
envs/environment.yml
```

when a required package cannot reasonably be supplied through the standard Conda source used by LiberRPA.

For 0.3.0, this currently includes packages such as:

```text
easyocr
pyzipper
```

### Do not manually add transitive dependencies

If package A requires package B internally, list package A as the direct LiberRPA requirement and normally allow the package manager to resolve B.

Only list B directly when LiberRPA itself intentionally depends on B.

This keeps `environment.yml` focused on the dependencies LiberRPA actually chose.

### Test from a clean environment

After changing dependencies, do not rely only on an already modified development environment.

Create a clean environment from `environment.yml` and verify that:

* `liberrpa` imports correctly;
* LiberRPA Editor can use the interpreter;
* LiberRPA Local Server starts;
* UI Analyzer integration works;
* browser integration works where applicable;
* representative automation modules import and execute;
* Executor can run a packaged Project.

This catches undeclared dependencies that may have been present accidentally in the developer's existing environment.

---

## Release Environment Snapshot

Before publishing a LiberRPA release, generate a snapshot from the  **final tested standard environment** , not from an arbitrary development environment.

From a Conda shell:

```bat
conda env export ^
  --prefix "<LiberRPA root>\envs\pyenv\default" ^
  > "<LiberRPA root>\envs\environment-win-64.yml"
```

Open the generated file and remove the machine-specific final line if it contains:

```yaml
prefix: ...
```

Do not otherwise simplify the generated snapshot merely to make it shorter.

The snapshot is intended to record what was actually tested.

Before committing it, confirm that the export also contains the expected pip-installed packages.

For 0.3.0 this should include, among others:

```text
easyocr
pyzipper
```

The release snapshot should be regenerated whenever the tested release environment changes.

---

## Verification

After building or modifying the standard environment, perform at least the following checks.

### Python

```bat
envs\pyenv\default\python.exe --version
```

Expected for 0.3.0:

```text
Python 3.13.x
```

### liberrpa version

```bat
envs\pyenv\default\python.exe -c "import importlib.metadata; print(importlib.metadata.version('liberrpa'))"
```

Expected:

```text
0.3.0
```

### Basic import

```bat
envs\pyenv\default\python.exe -c "import liberrpa; print('liberrpa import OK')"
```

### Editor interpreter

Open LiberRPA Editor and verify that the selected interpreter resolves to:

```text
<LiberRPA root>\envs\pyenv\default\python.exe
```

### Runtime verification

Environment validation should not stop at successful package installation.

Before a release, run representative tests covering the main dependency groups used by LiberRPA, especially:

* Windows UI Automation;
* browser communication;
* Excel/Office integration;
* image and OCR functionality;
* HTTP/network operations;
* databases;
* email;
* logging;
* Project execution;
* Component management;
* Executor execution.

The environment is considered release-ready only after the actual LiberRPA runtime has been tested against it.
