# Changelog

All notable changes to LiberRPA will be documented in this file.

This project adheres to [Semantic Versioning](https://semver.org/) (SemVer) and uses version numbers in the format MAJOR.MINOR.PATCH.

## [Unreleased]

### Added

- Python Library
  - Logging: Highlight terminal log output and refactor the JSONL formatter.([0dbce77](https://github.com/HUHARED/LiberRPA/commit/0dbce77f4e37a0cd553eb2a03607acb132946b62))
  - Logging: Hide stack-level information and support multi-message logging.([2ab6d09](https://github.com/HUHARED/LiberRPA/commit/2ab6d09a6e87f7d0d04f3079416cbc8ae8ce2949))
  - Use choice placeholders for `Literal` and `bool` parameters.([432434d](https://github.com/HUHARED/LiberRPA/commit/432434d68d8be2574e30772fbbb3b4dc6af6445a))
- LiberRPA Local Server
  - Compress video after recording.([a0ba7a5](https://github.com/HUHARED/LiberRPA/commit/a0ba7a50b4867f8cf0575fb15d6e3d3849e6f483))
  - Show a different icon while indicating UI elements.([e60ee66](https://github.com/HUHARED/LiberRPA/commit/e60ee66c96b208e64f02d68c89cec891a38a1eae))
- LiberRPA Chrome Extension
  - Show different icons while no WebSocket connection or handling web content.([e09fe24](https://github.com/HUHARED/LiberRPA/commit/e09fe24e3d5da9482ba8223d5c45d1cf0e14aacd))
- UI Analyzer
  - Change the window title and icon using WebSocket status.([4f02772](https://github.com/HUHARED/LiberRPA/commit/4f027720a56b75f24a6dab99aa7e0c573bde2c53))
  - Add timeout check for UI Analyzer indicating.([56d414c](https://github.com/HUHARED/LiberRPA/commit/56d414c43b9808d420505ca11a4d9db0343a9ecd))
- LiberRPA Snippets Tree
  - Add managed import updater for snippets tree.([389b567](https://github.com/HUHARED/LiberRPA/commit/389b5673d68af8510273037eadf6240447135ebb))
- Documentation
  - Describe limitations about Chrome-related functions.([645a4f8](https://github.com/HUHARED/LiberRPA/commit/645a4f880e740d19589d6f113e59d11e0d1c0e71))
  - Add more detailed usages about HTMLSelector.([1eeb83e](https://github.com/HUHARED/LiberRPA/commit/1eeb83ef216985c162c7c0028b52a102d0e20dd3))
  - Improve UI Analyzer README.([b47d08e](https://github.com/HUHARED/LiberRPA/commit/b47d08eb56fdb65bb5f30c527a6a58219c6f6a42))
  - Update LiberRPA Flowchart and LiberRPA Snippets Tree guides.([a028ad4](https://github.com/HUHARED/LiberRPA/commit/a028ad47cf567d43cc96a40ab97f99a487036560))

### Changed

- Python Library
  - Improve update check delay.([f7acb3c](https://github.com/HUHARED/LiberRPA/commit/f7acb3c7ae7737d4f6b08645eebae9aff4cc2031))
  - System: Replace Windows product ID with computer info.([489b914](https://github.com/HUHARED/LiberRPA/commit/489b91410647dad3db16b507cbea42987b553fc8))
  - Use the "Noto Sans Mono" font for overlay labels.([79c4063](https://github.com/HUHARED/LiberRPA/commit/79c4063129b96c29f8620cf869112ddbe1c24b69))
  - Support unnamed UIA elements and restore selector overload narrowing.([571224a](https://github.com/HUHARED/LiberRPA/commit/571224a2f4242c05b57c2f14c22642a6f1febad1))
- LiberRPA Local Server
  - Use a `.lnk` shortcut to start the Local Server instead of the PyInstaller-generated `.exe`.([bebedce](https://github.com/HUHARED/LiberRPA/commit/bebedce4a96b8900cb95e3c363c4559ac02c7fb4))
  - Improve error text.([ab4905e](https://github.com/HUHARED/LiberRPA/commit/ab4905e612235d2a4ed1d8d751c0decd016d14a7))
  - Send result to UI Analyzer immediately rather than waiting the notification completed while indicating.([1ff90ca](https://github.com/HUHARED/LiberRPA/commit/1ff90ca492a4cf6369e3b0eeead9cc392fdb37a1))
  - Move Local Server files into "liberrpa".([fe9e832](https://github.com/HUHARED/LiberRPA/commit/fe9e832b5186c6d6c0d493fe40d76b619d63b001))
- LiberRPA Chrome Extension
  - Use ESLint and refactor.([de10916](https://github.com/HUHARED/LiberRPA/commit/de10916234bb16a1381f85f1db7cd38a3818d527))
- UI Analyzer
  - Update tooltip text.([7cdc714](https://github.com/HUHARED/LiberRPA/commit/7cdc7145bbcdfddf6cc1b3747a1f0e182e797f90))
- VS Code(Editor)
  - Replace Black with Ruff.([354e497](https://github.com/HUHARED/LiberRPA/commit/354e497d92fb1aae1713498f6804b17a987a09f7))
  - Require VS Code 1.121 for snippet choice navigation; refresh VS Code extension dependencies.([d887263](https://github.com/HUHARED/LiberRPA/commit/d887263e2cb9fb79ecd0cd18155b713d198d79f6))
- LiberRPA Flowchart
  - Validate risky Python module names before opening or executing blocks; change built-in folders' names in Enterprise template.([607cbf5](https://github.com/HUHARED/LiberRPA/commit/607cbf5e37a9f329a611741f1658914b14cfed5c))
  - Require VS Code 1.121 for snippet choice navigation; refresh VS Code extension dependencies.([d887263](https://github.com/HUHARED/LiberRPA/commit/d887263e2cb9fb79ecd0cd18155b713d198d79f6))
- LiberRPA Project Manager
  - Require VS Code 1.121 for snippet choice navigation; refresh VS Code extension dependencies.([d887263](https://github.com/HUHARED/LiberRPA/commit/d887263e2cb9fb79ecd0cd18155b713d198d79f6))
- LiberRPA Snippets Tree
  - Require VS Code 1.121 for snippet choice navigation; refresh VS Code extension dependencies.([d887263](https://github.com/HUHARED/LiberRPA/commit/d887263e2cb9fb79ecd0cd18155b713d198d79f6))
  - Make snippet insertion and imports atomic.([39d2448](https://github.com/HUHARED/LiberRPA/commit/39d244807b761e147c3a92ccb0bc0c96191a6eb9))

### Removed

- LiberRPA Chrome Extension
  - Remove unused Vue dependencies.([ad75692](https://github.com/HUHARED/LiberRPA/commit/ad75692eb96d26bf1f81bedd989f887f8a29d20f))

### Fixed

- Python Library
  - Mouse: Allow clicking screen corners.([083bb84](https://github.com/HUHARED/LiberRPA/commit/083bb84f68ec808995837625d7cfe4a4fdd69753))
  - Standardize "Roboto Mono" font into "Noto Sans Mono".([32d0fcf](https://github.com/HUHARED/LiberRPA/commit/32d0fcfc1c5bf4daf31658f4224bfefd976c34d4))
  - UiInterface: Fix wrong arguments verification in UiInterface.set_selection.([408a5f9](https://github.com/HUHARED/LiberRPA/commit/408a5f9c58b547c0da0b6040efcf9ba2deb17505))
  - File: Remove the logic for creating the folder, as this will cause the subsequent step to fail.([e4c51d3](https://github.com/HUHARED/LiberRPA/commit/e4c51d3f217fbd24c8df1fadbd67fe37e7d3af8e))
  - Excel: Remove the unnecessary Excel range check; fix the order of row and column in the docstrings.([037a96f](https://github.com/HUHARED/LiberRPA/commit/037a96f67128959d014f9c216e09fd3cc6986cbe))
  - Excel: Harden workbook helpers and API docs.([874e5c2](https://github.com/HUHARED/LiberRPA/commit/874e5c23a0258de589aae6ed14f40a7e4e921394))
  - Keyboard: Improve keyboard and mouse modifier key handling.([5d00264](https://github.com/HUHARED/LiberRPA/commit/5d00264e5e10dabef11a7647378ccee6d9224791))
  - Database: Improve connection lifecycle and SQLite handling.([a6ad3b7](https://github.com/HUHARED/LiberRPA/commit/a6ad3b7e9cd054c6e58b0d8b2c830b4feffd6789))
  - Mouse: Normalize mouse movement duration units.([e31d173](https://github.com/HUHARED/LiberRPA/commit/e31d1739ae50bcbb0f704e8f785cc24fd15029a7))
  - File: Improve zip creation and list filtering.([f3313e1](https://github.com/HUHARED/LiberRPA/commit/f3313e1eb1de2adaa658dfb8eb43b5f8f513d701))
  - Outlook: Clarify email text search behavior.([6b43356](https://github.com/HUHARED/LiberRPA/commit/6b43356544591e75d2d67f54643d50c0125bb272))
  - System: Clarify machine identity and WAV sound playback.([98294a3](https://github.com/HUHARED/LiberRPA/commit/98294a3e3ecad412636168596b7e3980900fc0cc))
  - Browser: Preserve quoted browser launch parameters.([9411e75](https://github.com/HUHARED/LiberRPA/commit/9411e759936457ecbdafcc017624edc93bff2b85))
  - Mouse, Keyboard, UiInterface, Window: Serialize public UI operations with reentrant lock.([6138ba8](https://github.com/HUHARED/LiberRPA/commit/6138ba818fe9299a5d21cd6b23959ff949ce87a7))
  - Trigger: Keep input triggers active until a matching event; register executor stdin listener explicitly.([a877c74](https://github.com/HUHARED/LiberRPA/commit/a877c74f56561089c8468688b43c5541e44da3a7))
  - File, Mail, Outlook: Harden file operations and correct Outlook importance.([c1af14d](https://github.com/HUHARED/LiberRPA/commit/c1af14d605806311dffc68d3c5bc3d61c2605722))
- LiberRPA Local Server
  - Reduce performance overhead caused by idle spinning; avoid potential risks when commands complete very quickly.([0c65bfe](https://github.com/HUHARED/LiberRPA/commit/0c65bfe9315c528aee9cf332cbff963cb8e1b937))
  - Resolve the stuck for future UI Analyzer command if an indicating chrome error happens.([15b0638](https://github.com/HUHARED/LiberRPA/commit/15b0638501be904c035c42646085ccfc08b603df))
- LiberRPA Chrome Extension
  - Improve the logic of finding last focused tab.([a865b51](https://github.com/HUHARED/LiberRPA/commit/a865b5144285a9899af6142fddfbae74ec6a132e))
  - Improve element type checking and written text validating.([9afe2fc](https://github.com/HUHARED/LiberRPA/commit/9afe2fcf36c60c0b07a0f5fd61a702c6968cafbf))
- UI Analyzer
  - Emphasize that indicate html can only work on the last focused tab.([952e7df](https://github.com/HUHARED/LiberRPA/commit/952e7dff17f5291973a9ef18c423e2d5b6214778))
  - Avoid text selection and keep resize cursor while dragging.([afdb24f](https://github.com/HUHARED/LiberRPA/commit/afdb24f0944ec39394c19f06229b2e08b64bb091))
  - Ensure app can quit when an error happens.([fc27eb3](https://github.com/HUHARED/LiberRPA/commit/fc27eb39a5b05cb8d402f0443af8010adea6d0f6))
- VS Code(Editor)
  - Make the extension "albert.tabout" compatible with snippets.([cff8617](https://github.com/HUHARED/LiberRPA/commit/cff8617b5bd36176e00e90a246b2632b5ca1ef72))
- LiberRPA Flowchart
  - Avoid text selection and keep resize cursor while dragging.([284bc68](https://github.com/HUHARED/LiberRPA/commit/284bc685e607956aaa5f3c5d46d572dd04c6da2b))
  - Known issues about occasional drag failure and unresponsive shortcuts have been improved by avoiding repeated LogicFlow initialization and duplicated drag event listeners.([d9ba560](https://github.com/HUHARED/LiberRPA/commit/d9ba560fd8f41cf7fd730c55e05e1c44dabd7eb2))
  - Validate and escape custom argument keys.([58a76a5](https://github.com/HUHARED/LiberRPA/commit/58a76a57d3885347948e9171a15bc62480acb1b9))
- LiberRPA Snippets Tree
  - Standardize "Roboto Mono" font into "Noto Sans Mono".([32d0fcf](https://github.com/HUHARED/LiberRPA/commit/32d0fcfc1c5bf4daf31658f4224bfefd976c34d4))

### Security

* LiberRPA Local Server
  * Add WebSocket connection authentication.([b407533](https://github.com/HUHARED/LiberRPA/commit/b40753368a030c72fc48851e154b0321ba16d11c))
* LiberRPA Chrome Extension
  * Update dependencies to address security vulnerabilities.([6ff7570](https://github.com/HUHARED/LiberRPA/commit/6ff7570dc654c6d321c3fe21a4e9f0732af670dd))
* UI Analyzer
  * Update dependencies to address security vulnerabilities.([a01b5d3](https://github.com/HUHARED/LiberRPA/commit/a01b5d3cb07d145e01ae1973d46f787e52afc287))
  * Reduce Electron IPC ability.([a0fedfe](https://github.com/HUHARED/LiberRPA/commit/a0fedfede0bec41a3dfca88ebeb12998329e9829))
* LiberRPA Executor
  * Update dependencies to address security vulnerabilities.([aeb64ab](https://github.com/HUHARED/LiberRPA/commit/aeb64abbf6323a4c70b0e63375a193502b5a3d12))
* LiberRPA Flowchart
  * Update dependencies to address security vulnerabilities.([5c08b83](https://github.com/HUHARED/LiberRPA/commit/5c08b83a61ffbf8d81c57ad2b408617021e1e400))
  * Update LogicFlow dependencies.([1656cbf](https://github.com/HUHARED/LiberRPA/commit/1656cbfaff9c236c8b9b5e2031a4ab2c41fb25a9))
  * Improve Webview CSP and localResourceRoots security.([970d4d2](https://github.com/HUHARED/LiberRPA/commit/970d4d2fd41088e10e64708711d33e4421f6e761))
  * Remove unsafe v-html usage in tooltips.([23d9f73](https://github.com/HUHARED/LiberRPA/commit/23d9f730b1a7c7941fba3aa0ff07fda469ccf260))

## [0.2.0] - 2025-07-01

### Added

- Initial release.
