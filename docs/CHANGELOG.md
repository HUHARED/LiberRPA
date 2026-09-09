# Changelog

All notable changes to LiberRPA will be documented in this file.

This project adheres to [Semantic Versioning](https://semver.org/) (SemVer) and uses version numbers in the format MAJOR.MINOR.PATCH.

## [Unreleased]

> **Component pre-release:** LiberRPA Snippets Tree `0.3.1` was published as an optional VS Code Marketplace pre-release on 2026-09-09. It is compatible with LiberRPA `0.3.0`.

### Added

- **LiberRPA Snippets Tree**
  - Support expression-style snippet insertion. ([723dab5](https://github.com/HUHARED/LiberRPA/commit/723dab50eda0a30c78c04f32d0fe8e0544ffeecf))
  - Add nested CustomArgs key completion. ([7262271](https://github.com/HUHARED/LiberRPA/commit/72622711dc84650d5750c16a57a5b79e2fd2ae63))
  - Add managed import updates for Python paste. ([68d6f2d](https://github.com/HUHARED/LiberRPA/commit/68d6f2d8fa4b47efe5ebfd560d021981b6c6b33a))

### Upgrade Notes

- **LiberRPA Snippets Tree `0.3.1` pre-release**
  - Users upgrading from the LiberRPA `0.3.0` Editor configuration should remove or comment out the following binding in `Editor\data\user-data\User\keybindings.json`:
    ```jsonc
    // Enable Python Paste And Indent for Python (Ctrl+V)
    {
      "key": "ctrl+v",
      "command": "pyPasteIndent.pasteIndent",
      "when": "editorLangId == 'python'"
    },
    ```
  - Restart LiberRPA Editor after changing the keybinding.
  - The old binding intercepts `Ctrl+V` before the Snippets Tree Python paste integration can handle it.

## [0.3.0] - 2026-09-07

### Added

- **Component Management**
  - Introduce reusable Component Projects packaged as Python Wheels.
  - Add a local Component Repository for publishing, importing, and managing Component Wheels.
  - Add PEP 440 direct and transitive dependency resolution.
  - Add exact dependency locking with integrity information in `components.lock.json`.
  - Add project-local Component materialization under `_Components`.
  - Add Project Manager workflows for adding, updating, changing, removing, repairing, and resolving Components.
  - Add Component publishing, Wheel importing, and Repository index rebuilding.
  - Add generated snippets for reusable Component APIs.
- **Python Library**
  - Add choice placeholders for `Literal` and `bool` parameters in generated snippets. ([432434d](https://github.com/HUHARED/LiberRPA/commit/432434d68d8be2574e30772fbbb3b4dc6af6445a))
- **LiberRPA Local Server**
  - Add post-recording video compression. ([a0ba7a5](https://github.com/HUHARED/LiberRPA/commit/a0ba7a50b4867f8cf0575fb15d6e3d3849e6f483))
- **Initialization**
  - Generate portable shortcuts during initialization. ([897a180](https://github.com/HUHARED/LiberRPA/commit/897a180cf9075131b98eef0b891d8961529ab35f))
- **LiberRPA Snippets Tree**
  - Add managed import handling for inserted snippets. ([389b567](https://github.com/HUHARED/LiberRPA/commit/389b5673d68af8510273037eadf6240447135ebb))
- **UI status feedback**
  - Add a distinct Local Server icon while indicating UI elements. ([e60ee66](https://github.com/HUHARED/LiberRPA/commit/e60ee66c96b208e64f02d68c89cec891a38a1eae))
  - Add Chrome Extension icon states for missing Local Server connection and active web-content handling. ([e09fe24](https://github.com/HUHARED/LiberRPA/commit/e09fe24e3d5da9482ba8223d5c45d1cf0e14aacd))
  - Add UI Analyzer title/icon feedback for WebSocket connection state. ([4f02772](https://github.com/HUHARED/LiberRPA/commit/4f027720a56b75f24a6dab99aa7e0c573bde2c53))

### Changed

- **Python Library**
  - Improve logging output, including terminal highlighting, JSONL formatting, hidden stack-level details, and multi-message logging. ([0dbce77](https://github.com/HUHARED/LiberRPA/commit/0dbce77f4e37a0cd553eb2a03607acb132946b62), [2ab6d09](https://github.com/HUHARED/LiberRPA/commit/2ab6d09a6e87f7d0d04f3079416cbc8ae8ce2949))
  - Improve update-check timing. ([f7acb3c](https://github.com/HUHARED/LiberRPA/commit/f7acb3c7ae7737d4f6b08645eebae9aff4cc2031))
  - Replace the Windows product ID with computer information for system identification. ([489b914](https://github.com/HUHARED/LiberRPA/commit/489b91410647dad3db16b507cbea42987b553fc8))
  - Standardize overlay labels on Noto Sans Mono. ([79c4063](https://github.com/HUHARED/LiberRPA/commit/79c4063129b96c29f8620cf869112ddbe1c24b69))
  - Support unnamed UIA elements and restore selector overload narrowing. ([571224a](https://github.com/HUHARED/LiberRPA/commit/571224a2f4242c05b57c2f14c22642a6f1febad1))
- **LiberRPA Local Server**
  - Change the standard startup model from a separate PyInstaller-generated executable to the LiberRPA Python environment, launched through a shortcut. ([bebedce](https://github.com/HUHARED/LiberRPA/commit/bebedce4a96b8900cb95e3c363c4559ac02c7fb4), [fe9e832](https://github.com/HUHARED/LiberRPA/commit/fe9e832b5186c6d6c0d493fe40d76b619d63b001))
  - Improve error text. ([ab4905e](https://github.com/HUHARED/LiberRPA/commit/ab4905e612235d2a4ed1d8d751c0decd016d14a7))
  - Send result to UI Analyzer immediately rather than waiting for the notification to complete while indicating. ([1ff90ca](https://github.com/HUHARED/LiberRPA/commit/1ff90ca492a4cf6369e3b0eeead9cc392fdb37a1))
- **Editor and VS Code extensions**
  - Replace Black with Ruff in the bundled Editor environment. ([354e497](https://github.com/HUHARED/LiberRPA/commit/354e497d92fb1aae1713498f6804b17a987a09f7))
  - Require VS Code 1.121 for snippet choice navigation and refresh related extension dependencies. ([d887263](https://github.com/HUHARED/LiberRPA/commit/d887263e2cb9fb79ecd0cd18155b713d198d79f6))
  - Update Pylance configuration. ([7f62e07](https://github.com/HUHARED/LiberRPA/commit/7f62e07b8e300c719b2c1da8741ed88a3bc28b29))
  - Install missing Editor extensions through the bundled VS Code CLI during initialization. ([65d386a](https://github.com/HUHARED/LiberRPA/commit/65d386aa8eae67890ea1215217e68945a9e538a9))
- **LiberRPA Flowchart**
  - Validate risky Python module names before opening or executing blocks; change built-in folders' names in Enterprise template. ([607cbf5](https://github.com/HUHARED/LiberRPA/commit/607cbf5e37a9f329a611741f1658914b14cfed5c))
- **LiberRPA Project Manager**
  - Rename the Flow Project templates. ([9f7a9af](https://github.com/HUHARED/LiberRPA/commit/9f7a9af7187eb253805f4920492169603a220d14))
- **LiberRPA Snippets Tree**
  - Make snippet insertion and imports atomic. ([39d2448](https://github.com/HUHARED/LiberRPA/commit/39d244807b761e147c3a92ccb0bc0c96191a6eb9))

### Fixed

- **Python Library**
  - Fix mouse and keyboard handling issues, including screen-corner clicks, movement-duration normalization, and modifier-key handling. ([083bb84](https://github.com/HUHARED/LiberRPA/commit/083bb84f68ec808995837625d7cfe4a4fdd69753), [e31d173](https://github.com/HUHARED/LiberRPA/commit/e31d1739ae50bcbb0f704e8f785cc24fd15029a7), [5d00264](https://github.com/HUHARED/LiberRPA/commit/5d00264e5e10dabef11a7647378ccee6d9224791))
  - Serialize public Mouse, Keyboard, UiInterface, and Window operations to avoid conflicting UI operations. ([6138ba8](https://github.com/HUHARED/LiberRPA/commit/6138ba818fe9299a5d21cd6b23959ff949ce87a7))
  - Fix `UiInterface.set_selection` argument validation. ([408a5f9](https://github.com/HUHARED/LiberRPA/commit/408a5f9c58b547c0da0b6040efcf9ba2deb17505))
  - Fix and harden File operations, including directory handling, ZIP creation, and list filtering. ([e4c51d3](https://github.com/HUHARED/LiberRPA/commit/e4c51d3f217fbd24c8df1fadbd67fe37e7d3af8e), [f3313e1](https://github.com/HUHARED/LiberRPA/commit/f3313e1eb1de2adaa658dfb8eb43b5f8f513d701))
  - Improve Excel workbook helpers and correct range-related behavior and documentation. ([037a96f](https://github.com/HUHARED/LiberRPA/commit/037a96f67128959d014f9c216e09fd3cc6986cbe), [874e5c2](https://github.com/HUHARED/LiberRPA/commit/874e5c23a0258de589aae6ed14f40a7e4e921394))
  - Improve Database connection lifecycle and SQLite handling. ([a6ad3b7](https://github.com/HUHARED/LiberRPA/commit/a6ad3b7e9cd054c6e58b0d8b2c830b4feffd6789))
  - Fix Browser launch-parameter handling so quoted parameters are preserved. ([9411e75](https://github.com/HUHARED/LiberRPA/commit/9411e759936457ecbdafcc017624edc93bff2b85))
  - Improve Trigger lifecycle handling so input triggers remain active until a matching event. ([a877c74](https://github.com/HUHARED/LiberRPA/commit/a877c74f56561089c8468688b43c5541e44da3a7))
  - Harden File, Mail, and Outlook operations and correct Outlook importance handling. ([c1af14d](https://github.com/HUHARED/LiberRPA/commit/c1af14d605806311dffc68d3c5bc3d61c2605722))
- **LiberRPA Local Server**
  - Reduce idle-spinning overhead and fix a race risk for very fast command completion. ([0c65bfe](https://github.com/HUHARED/LiberRPA/commit/0c65bfe9315c528aee9cf332cbff963cb8e1b937))
  - Prevent a Chrome indication error from blocking later UI Analyzer commands. ([15b0638](https://github.com/HUHARED/LiberRPA/commit/15b0638501be904c035c42646085ccfc08b603df))
  - Stop the tray icon cleanly during Local Server shutdown. ([b22fb34](https://github.com/HUHARED/LiberRPA/commit/b22fb3477d6f866f58e0ed9b77ddc7818826955e))
  - Reuse the indication overlay to avoid blinking. ([b8acd10](https://github.com/HUHARED/LiberRPA/commit/b8acd1046bd139cc34e2549a50bd11e0efa25bbc))
- **LiberRPA Chrome Extension**
  - Improve the logic of finding the last focused tab. ([a865b51](https://github.com/HUHARED/LiberRPA/commit/a865b5144285a9899af6142fddfbae74ec6a132e))
  - Improve element type checking and written text validation. ([9afe2fc](https://github.com/HUHARED/LiberRPA/commit/9afe2fcf36c60c0b07a0f5fd61a702c6968cafbf))
- **UI Analyzer**
  - Clarify last-focused-tab behavior for HTML indication. ([952e7df](https://github.com/HUHARED/LiberRPA/commit/952e7dff17f5291973a9ef18c423e2d5b6214778))
  - Improve drag/resize interaction, error shutdown, and indication timeout handling. ([afdb24f](https://github.com/HUHARED/LiberRPA/commit/afdb24f0944ec39394c19f06229b2e08b64bb091), [fc27eb3](https://github.com/HUHARED/LiberRPA/commit/fc27eb39a5b05cb8d402f0443af8010adea6d0f6), [56d414c](https://github.com/HUHARED/LiberRPA/commit/56d414c43b9808d420505ca11a4d9db0343a9ecd))
- **Editor**
  - Improve snippet compatibility with TabOut and update formatter settings. ([cff8617](https://github.com/HUHARED/LiberRPA/commit/cff8617b5bd36176e00e90a246b2632b5ca1ef72), [9ae0dd8](https://github.com/HUHARED/LiberRPA/commit/9ae0dd82d82141c5189d1e19a4c05fd940ad74af))
- **LiberRPA Flowchart**
  - Improve drag behavior and shortcut responsiveness by avoiding repeated LogicFlow initialization and duplicated drag listeners. ([284bc68](https://github.com/HUHARED/LiberRPA/commit/284bc685e607956aaa5f3c5d46d572dd04c6da2b), [d9ba560](https://github.com/HUHARED/LiberRPA/commit/d9ba560fd8f41cf7fd730c55e05e1c44dabd7eb2))
  - Fix custom-argument key validation and escaping. ([58a76a5](https://github.com/HUHARED/LiberRPA/commit/58a76a57d3885347948e9171a15bc62480acb1b9))
  - Add Flow Project shortcuts and fix exception debugging behavior. ([78cddcd](https://github.com/HUHARED/LiberRPA/commit/78cddcdbccabd35e96764114f0ac44f31d128c1c))

### Security

- **LiberRPA Local Server**
  - Add WebSocket connection authentication. ([b407533](https://github.com/HUHARED/LiberRPA/commit/b40753368a030c72fc48851e154b0321ba16d11c))
- **LiberRPA Chrome Extension, UI Analyzer, Executor, and Flowchart**
  - Update affected dependencies to address security vulnerabilities. ([6ff7570](https://github.com/HUHARED/LiberRPA/commit/6ff7570dc654c6d321c3fe21a4e9f0732af670dd), [a01b5d3](https://github.com/HUHARED/LiberRPA/commit/a01b5d3cb07d145e01ae1973d46f787e52afc287), [aeb64ab](https://github.com/HUHARED/LiberRPA/commit/aeb64abbf6323a4c70b0e63375a193502b5a3d12), [5c08b83](https://github.com/HUHARED/LiberRPA/commit/5c08b83a61ffbf8d81c57ad2b408617021e1e400), [1656cbf](https://github.com/HUHARED/LiberRPA/commit/1656cbfaff9c236c8b9b5e2031a4ab2c41fb25a9))
- **UI Analyzer and Flowchart**
  - Reduce Electron/Webview attack surface through stricter IPC, CSP, local-resource restrictions, and removal of unsafe tooltip HTML rendering. ([a0fedfe](https://github.com/HUHARED/LiberRPA/commit/a0fedfede0bec41a3dfca88ebeb12998329e9829), [970d4d2](https://github.com/HUHARED/LiberRPA/commit/970d4d2fd41088e10e64708711d33e4421f6e761), [23d9f73](https://github.com/HUHARED/LiberRPA/commit/23d9f730b1a7c7941fba3aa0ff07fda469ccf260))

### Documentation

- Reorganize and expand the main LiberRPA documentation for installation, environment management, architecture, Editor usage, Local Server, Chrome integration, and UI analysis.
- Add the generated LiberRPA Code Reference as the canonical reference for LiberRPA APIs, Project Values, and Snippets Tree entries.
- Expand Component Management, Project Manager, Flowchart, and Snippets Tree documentation.
- Clarify Chrome-related limitations and HTML selector behavior. ([645a4f8](https://github.com/HUHARED/LiberRPA/commit/645a4f880e740d19589d6f113e59d11e0d1c0e71), [1eeb83e](https://github.com/HUHARED/LiberRPA/commit/1eeb83ef216985c162c7c0028b52a102d0e20dd3))
- Improve UI Analyzer documentation. ([b47d08e](https://github.com/HUHARED/LiberRPA/commit/b47d08eb56fdb65bb5f30c527a6a58219c6f6a42))
- Update Flowchart and Snippets Tree guides. ([a028ad4](https://github.com/HUHARED/LiberRPA/commit/a028ad47cf567d43cc96a40ab97f99a487036560))

## [0.2.0] - 2025-07-01

### Added

- Initial release.
