# `<Project Name>`

## Overview

Describe the business purpose of this automation and the process it is responsible for.

Include enough context that a developer who did not build the Project can understand why it exists.

Suggested information:

- business process and scope;
- intended users or business team;
- technical owner or support team;
- systems involved;
- important assumptions or exclusions.

Replace `<Project Name>` with the actual Project name.

## Process

Describe the production workflow at a business level.

Focus on the major stages, decisions, and external systems rather than duplicating Python implementation details already visible in the source code.

If useful, include a short process diagram or numbered workflow.

## Operation

Document how this Project is operated in production.

Include information such as:

- how execution is started or scheduled;
- required Project arguments;
- input files, folders, queues, or records;
- expected outputs;
- normal completion conditions;
- operator actions before or after execution.

If an Executor schedule is part of the production design, document the expected schedule here rather than relying only on the current machine configuration.

## Requirements

Document external requirements that must be available for the Project to work, such as:

- target applications and supported versions;
- browsers or drivers;
- accounts, roles, and permissions;
- network access and service endpoints;
- shared folders and file locations;
- databases, email systems, or APIs;
- other environment prerequisites.

Do not include passwords, tokens, or other secret values.

## Configuration

Document Project-specific configuration and explain which values may differ between environments.

This may include:

- configuration files;
- business rules and mapping tables;
- local or shared paths;
- service addresses;
- non-secret environment-specific values;
- where required credentials are expected to be stored.

Avoid storing plaintext credentials in the Project source when a more appropriate credential store is available.

## Failure & Recovery

Document how production failures should be handled.

Include the information a maintainer or operator needs to answer questions such as:

- Is it safe to rerun the entire Project after a failure?
- Can a partially completed transaction be repeated?
- Which outputs or external records must be checked before retrying?
- Which failures require manual intervention?
- How should an interrupted process be resumed or recovered?
- When should the issue be escalated instead of retried?

Document business-state recovery, not only technical exception handling.

## Deployment

Document how this Project is delivered to its runtime environment.

Record information such as:

- target Executor or machine requirements;
- Component dependencies that must be resolved before packaging;
- environment-specific configuration that must be applied after deployment;
- any external files or resources that must accompany the Project.

Use:

```text
LiberRPA: Package Project
```

to create the distributable `.rpa.zip` Package for LiberRPA Executor.

See the [LiberRPA Project Manager documentation](https://github.com/HUHARED/LiberRPA/blob/main/vscodeExtensions/liberrpa-project-manager/README.md#package-a-flow-project) for the current packaging workflow.

## Testing & Verification

Describe how changes to the Project should be verified before production deployment.

Include relevant items such as:

- representative test cases;
- test data or test accounts;
- expected outputs;
- regression checks;
- external systems that must be verified;
- manual checks required after deployment.

Keep test-only scripts, sample data, and diagnostic code under `_Test/` where practical.

## Maintenance

Record information that future maintainers are likely to need, including:

- known limitations;
- selectors or applications that change frequently;
- external dependencies that have caused previous incidents;
- important implementation decisions;
- upgrade considerations;
- operational workarounds that are still required.

Update this section when production experience reveals information that would help the next maintainer.

## Project Structure

This template provides the following structure:

```text
Project Root
├── .vscode/
├── _Config/
├── _Screenshots/
├── _Selectors/
│   └── default.py
├── _Test/
├── _Utils/
│   └── default.py
├── .gitignore
├── flow.json
├── LICENSE
├── project.flow
├── README.md
└── ruff.toml
```

LiberRPA may create additional managed state when Component dependencies are used, including `_Components/`, `components.lock.json`, and `.liberrpa-project-manager/`.

### `_Config/`

Stores Project-owned configuration such as mapping tables, business settings, and environment options.

### `_Selectors/`

Stores reusable selectors belonging to this Project.

Small Projects can keep selectors in `default.py`. Larger Projects should split them into focused Modules according to the target application, system, or business area.

### `_Screenshots/`

Stores Project-owned images used by image-based automation and related Project resources.

### `_Test/`

Stores Project-specific tests, sample data, diagnostic scripts, and manual verification code.

### `_Utils/`

Stores reusable helper functions that are specific to this Project.

Use a reusable Component instead when logic should be versioned and shared across multiple LiberRPA Projects.

### `flow.json`

Stores Flow Project metadata and direct Component dependency requirements.

Use LiberRPA Project Manager for normal Project and dependency-management operations.

### `project.flow`

Stores the high-level Flowchart structure and Flow execution settings.

Use LiberRPA Flowchart to edit it.

### `components.lock.json`

Created when Component dependencies are resolved.

Commit this file when present so that the exact resolved Component versions and integrity information are preserved. Do not edit it manually.

### `_Components/`

Generated from resolved Component dependencies.

Do not edit or commit this directory during normal development.

## Version Control

Commit the Project source together with `project.flow`, `flow.json`, and `components.lock.json` when present.

The template `.gitignore` excludes generated or local state such as `_Components/`, `.liberrpa-project-manager/`, Python caches, and Ruff cache.

Keep implementation changes reviewable as ordinary Python source wherever practical.

## License

See [LICENSE](./LICENSE).
