<div style="text-align: center;">
  <img src="./envs/assets/icon/LiberRPA_icon_v1_color.png" alt="LiberRPA icon">
</div>

# LiberRPA

LiberRPA is an RPA toolkit built for hands-on, down-to-earth engineers.

# Features

* **Open Source**

  * LiberRPA is released under the AGPLv3 license—this means that developers are obligated to share the source code of any project built on LiberRPA with its users, even if the service is provided via the web.
* **Free**

  * LiberRPA is completely free for both personal and commercial use.
* **Comprehensive Functionality**

  * Comparable to popular commercial RPA software, LiberRPA will consist of three core components:
    * **Editor** (fully developed and available)

      * A desktop client for writing and running RPA projects.
      * Already includes most local features found in popular commercial RPA software.
    * **Executor** (planned)

      * A desktop client for scheduled execution of RPA projects.
    * **Console** (planned)

      * A web server for managing Executors, data assets, and more.
      * Supports internal network deployment without relying on public internet services.
* **Core Features Built on Python (3.12) and VS Code (1.95+)**

  * Leverage the ecosystems of Python and VS Code to extend functionality beyond LiberRPA's built-in features.
  * With a simple `Ctrl+MouseLeft` click, you can jump directly to the corresponding LiberRPA source code. If you encounter difficulties, besides contacting the developer, you can also send the source code to an AI for help.

  > Note: There are currently no plans to integrate popular AI-assisted programming features into LiberRPA.
  >
* **Code-Driven Approach Over Graphical Interfaces**

  * LiberRPA is not marketed as a low-code or no-code solution—it prioritizes a seamless coding experience for engineers.
  * LiberRPA will not for the sake of the limited convenience that a graphical interface might offer, to accept the consequence below:

    * Waste your time,
    * Reduce program efficiency,
    * Increase maintenance complexity.
  * LiberRPA acknowledges the benefits of graphical interfaces in some scenarios, so it offers features like a snippets tree,  UI analyzer, and flowchart to help engineers develop projects with less effort.
* **Security**

  * LiberRPA can run offline and does not actively collect any of your information.

    * Please note that because LiberRPA uses many open-source projects from conda-forge, PyPI, and npm, it cannot guarantee the security of these dependencies. For more details, please see [Dependencies and Acknowledgments](#dependencies-and-acknowledgments).
    * If, in the future, LiberRPA needs to collect your information (for example, if a free public Console service is launched), a detailed explanation of the scope and purpose will be provided, and your data will be handled with care.
  * In addition to the open-source code on GitHub, browser extensions and VS Code extensions will also be published on the official marketplaces for review.
  * Due to the requirements of the AGPLv3 license, you have the right to request the source code of any project implemented with LiberRPA—even if you access the service via the web.

# Limitations

* Only supports Windows 10+ (Windows Server 2016+) platforms.
* Many mouse and keyboard operations may only work properly if your computer's screen scale is set to 100%.
* Still in development and not yet extensively tested—stability and bugs will be optimized based on user feedback.

# Components

<div style="text-align: center;">
  <img src="./docs/Architecture.svg" alt="LiberRPA architecture">
</div>

## Python Library

A conda library named "liberrpa" with the following purposes:

* Execute [Specific operations](./condaLibrary/liberrpa) for RPA projects.
* [Initialize](./condaLibrary/exe/InitLiberRPA) LiberRPA on computers that do not have it installed.
* Communicate with [the Chrome extension](./condaLibrary/exe/ChromeGetLocalServerPort) to pass WebSocket initialization information.
* Create [a local Flask server](./condaLibrary/exe/LiberRPALocalServer) to accomplish tasks that are difficult to achieve in a standalone Python project.

## LiberRPA Local Server

A Flask-based client that will start automatically on boot.

If you do not want it to start automatically, you can delete the file at this path: `C:/Users/<username>/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup/LiberRPALocalServer.exe - shortcut`

Since LiberRPA is still in development, you might encounter some instability. If that happens, you can locate its icon in the system tray, right-click to exit, and then reopen `LiberRPA/exeFiles/LiberRPALocalServer/LiberRPALocalServer.exe` to restart it.

## LiberRPA Chrome Extension

A [Chrome extension](./browserExtensions/liberrpa-chrome-extension/README.md) that must be installed and enabled to perform operations on browsers and HTML elements.

## [UI Analyzer](./Editor/ui-analyzer/README.md)

An Electron-based client designed to quickly select elements and build the selectors (a specific dictionary format) required for RPA operations.

## VS Code

LiberRPA [Editor](./Editor/vscode) is essentially a modified version of [the official portable VS Code](https://code.visualstudio.com/docs/editor/portable)—with altered default settings, added plugins, and custom resources. This means you can deploy LiberRPA on your familiar VS Code or modify the LiberRPA Editor according to your own preferences.

You can see [VS Code User Guide](https://github.com/HUHARED/LiberRPA/Editor/vscode/UserGuide.md) to learn how to use LiberRPA Editor.

## [LiberRPA Flowchart](./vscodeExtensions/liberrpa-flowchart/README.md)

A VS Code extension used to manage the overall flow of RPA project, including project arguments and settings.

## [LiberRPA Project Manager](./vscodeExtensions/liberrpa-project-manager/README.md)

A VS Code extension for creating new RPA projects.

It offers multiple templates to choose from, and you can customize the templates to suit your needs.

## [LiberRPA Snippets Tree](./vscodeExtensions/liberrpa-snippets-tree/README.md)

A VS Code extension that displays built-in and user-defined code snippets. You can add [code snippets](https://code.visualstudio.com/docs/editor/userdefinedsnippets) to your Python files in the editor using these methods:

* Click on an item in the LiberRPA Snippets Tree with your mouse.
* Drag an item from the LiberRPA Snippets Tree with your mouse.
* Type the corresponding code snippet prefix in the editor.

# Getting Started

## Download Compressed Package

If you're unfamiliar with creating conda environments and setting up VS Code,  it's recommended that download the latest version of the main program's compressed package from [this page](https://1drv.ms/f/s!AjBKSBwsKFwl0ZM5bPY2_oNz1XhPGg?e=JIabBh). After downloading, extract it to your target folder. The final name of the LiberRPA root directory should be "LiberRPA_vX.X.X".

## Initialization

Extract the files to your target folder, then execute the [InitLiberRPA.exe](./InitLiberRPA.exe) in the root directory to complete the initialization setup.

The LiberRPA Editor only creates data in the following locations (the file paths created by dependencies are not guaranteed):

* **LiberRPA root folder**
  * You can move it to different directories or computers as needed. Simply follow the [Initialization](#initialization) steps again, and your current VS Code settings will be preserved.
* **`C:/Users/<username>/Documents/LiberRPA`**
  * Stores logs, screenshots, custom code snippets, and more.
* **`C:/Users/<username>/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup/`**
  * Contains a shortcut for automatically starting LiberRPA Local Server: `LiberRPALocalServer.exe - shortcut`.
* **Regedit** :
  * `HKEY_CURRENT_USER\SOFTWARE\Google\Chrome\NativeMessagingHosts\com.liberrpa.chrome.msghost`
  * Used for Chrome extension initialization.

Currently, there is no uninstaller for LiberRPA. If you wish to uninstall it, you can simply clean the data from the 4 locations mentioned above.

## Install Chrome Extension

The LiberRPA Chrome Extension has uploaded to the Chrome Web Store, and you can install it on your existing Chrome.

TODO: add link

## Create Project

You can open `LiberRPA/Editor/vscode/Code.exe`, press the shortcut `Ctrl+Shift+P` to open the Command Palette, and run `LiberRPA:Create a New Project` to create a new RPA project.

For more details, check [LiberRPA Project Manager](./vscodeExtensions/liberrpa-project-manager/README.md).

## Configuration

You can modify some config of LiberRPA in `LiberRPA/configFiles/basic.jsonc`.

```json
// FineName: basic.jsonc
{
  /* 
  Predefined variables:
        ${LiberRPA}: The value of "LiberRPA" in your computer's User Environment Variables. Since LiberRPA has a portability mechanism, so you should run the "InitLiberRPA.exe" in the LiberRPA root folder. It will add a "LiberRPA" variable in your computer's User Environment Variables.
        ${UserName}: The name of the user currently logged into the system.
        ${HostName}: The computer's hostname.
        ${ToolName}: Don't delete it, it is a flag to control subfolder name in "OutputLog".
  
        */
  "LiberRPAPath": "${LiberRPA}",
  "outputLogPath": "C:\\Users\\${UserName}\\Documents\\LiberRPA\\OutputLog\\${ToolName}\\",
  "localServerPort": "52000",
  "uiAnalyzerTheme": "light", // "light" or "dark"
  "uiAnalyzerMinimizeWindow": "false" // "true" or "false"
}

```

# Dependencies and Acknowledgments

LiberRPA relies on these projects to deliver its functionality. There might be some omissions—please excuse any oversights.

| Name                 | Section                                                  |   Source   | License                                                                                       |
| -------------------- | -------------------------------------------------------- | :---------: | --------------------------------------------------------------------------------------------- |
| bzip2                | Python                                                   | conda-forge | [bzip2-1.0.6](https://anaconda.org/conda-forge/bzip2)                                            |
| ca-certificates      | Python                                                   | conda-forge | [ISC](https://github.com/conda-forge/ca-certificates-feedstock/blob/main/LICENSE.txt)            |
| libexpat             | Python                                                   | conda-forge | [MIT](https://anaconda.org/conda-forge/libexpat)                                                 |
| libffi               | Python                                                   | conda-forge | [MIT](https://github.com/libffi/libffi/blob/master/LICENSE)                                      |
| liblzma              | Python                                                   | conda-forge | [0BSD](https://anaconda.org/conda-forge/liblzma)                                                 |
| libsqlite            | Python                                                   | conda-forge | [Unlicense](https://github.com/mackyle/sqlite/blob/master/LICENSE.md)                            |
| libzlib              | Python                                                   | conda-forge | [Zlib](https://github.com/madler/zlib/blob/develop/LICENSE)                                      |
| openssl              | Python                                                   | conda-forge | [Apache-2.0](https://github.com/openssl/openssl/blob/master/LICENSE.txt)                         |
| pip                  | Python                                                   | conda-forge | [MIT](https://github.com/pypa/pip/blob/main/LICENSE.txt)                                         |
| python               | Python                                                   | conda-forge | [Python-2.0](https://anaconda.org/conda-forge/python)                                            |
| setuptools           | Python                                                   | conda-forge | [MIT](https://github.com/pypa/setuptools/blob/main/LICENSE)                                      |
| tk                   | Python                                                   | conda-forge | [TCL](https://github.com/tcltk/tk?tab)                                                           |
| tzdata               | Python                                                   | conda-forge | [LicenseRef-Public-Domain](https://github.com/eggert/tz/blob/main/LICENSE)                       |
| ucrt                 | Python                                                   | conda-forge | [LicenseRef-MicrosoftWindowsSDK10](https://anaconda.org/conda-forge/ucrt)                        |
| vc                   | Python                                                   | conda-forge | [BSD-3-Clause](https://anaconda.org/conda-forge/vc)                                              |
| vc14_runtime         | Python                                                   | conda-forge | [LicenseRef-MicrosoftVisualCpp2015-2022Runtime](https://anaconda.org/conda-forge/vc14_runtime)   |
| vs2015_runtime       | Python                                                   | conda-forge | [BSD-3-Clause](https://github.com/conda-forge/vc-feedstock/blob/main/LICENSE.txt)                |
| wheel                | Python                                                   | conda-forge | [MIT](https://github.com/pypa/wheel/blob/main/LICENSE.txt)                                       |
| ipykernel            | Python                                                   | conda-forge | [BSD-3-Clause](https://github.com/ipython/ipykernel/blob/main/LICENSE)                           |
| pywin32              | Python                                                   | conda-forge | [PSF-2.0](https://anaconda.org/conda-forge/pywin32)                                              |
| screeninfo           | Python                                                   | conda-forge | [MIT AND BSD-3-Clause](https://github.com/rr-/screeninfo/blob/master/LICENSE.md)                 |
| pywinhook            | Python                                                   | conda-forge | [MIT](https://github.com/Tungsteno74/pyWinhook/blob/master/LICENSE.txt)                          |
| pyautogui            | Python                                                   | conda-forge | [BSD-3-Clause](https://github.com/asweigart/pyautogui/blob/master/LICENSE.txt)                   |
| pyqt                 | Python                                                   | conda-forge | [GPL-3.0-only](https://anaconda.org/conda-forge/pyqt)                                            |
| pyqt-stubs           | Python                                                   | conda-forge | [GPL-3.0-or-later](https://github.com/python-qt-tools/PyQt5-stubs/blob/master/LICENSE)           |
| pynput               | Python                                                   | conda-forge | [LGPL-3.0-only](https://github.com/moses-palmer/pynput/blob/master/COPYING.LGPL)                 |
| keyboard             | Python                                                   | conda-forge | [MIT](https://github.com/boppreh/keyboard/blob/master/LICENSE.txt)                               |
| json5                | Python                                                   | conda-forge | [Apache-2.0](https://github.com/dpranke/pyjson5/blob/main/LICENSE)                               |
| psutil               | Python                                                   | conda-forge | [BSD-3-Clause](https://github.com/giampaolo/psutil/blob/master/LICENSE)                          |
| pypdf                | Python                                                   | conda-forge | [BSD-3-Clause](https://github.com/py-pdf/pypdf/blob/main/LICENSE)                                |
| pathvalidate         | Python                                                   | conda-forge | [MIT](https://github.com/thombashi/pathvalidate/blob/master/LICENSE)                             |
| pillow               | Python                                                   | conda-forge | [HPND](https://github.com/python-pillow/Pillow/blob/main/LICENSE)                                |
| python-mss           | Python                                                   | conda-forge | [MIT](https://github.com/BoboTiG/python-mss/blob/main/LICENSE.txt)                               |
| flask                | Python                                                   | conda-forge | [BSD-3-Clause](https://github.com/pallets/flask/blob/main/LICENSE.txt)                           |
| flask-socketio       | Python                                                   | conda-forge | [MIT](https://github.com/miguelgrinberg/Flask-SocketIO/blob/main/LICENSE)                        |
| requests             | Python                                                   | conda-forge | [Apache-2.0](https://github.com/psf/requests/blob/main/LICENSE)                                  |
| python-socketio      | Python                                                   | conda-forge | [MIT](https://github.com/miguelgrinberg/python-socketio/blob/main/LICENSE)                       |
| websocket-client     | Python                                                   | conda-forge | [Apache-2.0](https://github.com/websocket-client/websocket-client/blob/master/LICENSE)           |
| pyperclip            | Python                                                   | conda-forge | [BSD-3-Clause](https://github.com/asweigart/pyperclip/blob/master/LICENSE.txt)                   |
| sqlalchemy           | Python                                                   | conda-forge | [MIT](https://github.com/sqlalchemy/sqlalchemy/blob/main/LICENSE)                                |
| psycopg2             | Python                                                   | conda-forge | [LGPL-3.0-or-later](https://github.com/psycopg/psycopg2/blob/master/LICENSE)                     |
| pymysql              | Python                                                   | conda-forge | [MIT](https://github.com/PyMySQL/PyMySQL/blob/main/LICENSE)                                      |
| pymssql              | Python                                                   | conda-forge | [LGPL-2.1-only](https://github.com/pymssql/pymssql/blob/master/LICENSE)                          |
| oracledb             | Python                                                   | conda-forge | [Apache-2.0](https://anaconda.org/conda-forge/oracledb)                                          |
| pandas               | Python                                                   | conda-forge | [BSD-3-Clause](https://anaconda.org/conda-forge/pandas)                                          |
| xlwings              | Python                                                   | conda-forge | [BSD-3-Clause](https://anaconda.org/conda-forge/xlwings)                                         |
| ftputil              | Python                                                   | conda-forge | [BSD-3-Clause](https://anaconda.org/conda-forge/ftputil)                                         |
| imapclient           | Python                                                   | conda-forge | [BSD-3-Clause](https://github.com/mjs/imapclient/?tab=License-1-ov-file)                         |
| yagmail              | Python                                                   | conda-forge | [MIT](https://github.com/kootenpv/yagmail/blob/master/LICENSE)                                   |
| ffmpeg               | Python                                                   | conda-forge | [GPL-2.0-or-later](https://anaconda.org/conda-forge/ffmpeg)                                      |
| uiautomation         | Python                                                   |    PyPI    | [Apache-2.0](https://github.com/yinkaisheng/Python-UIAutomation-for-Windows/blob/master/LICENSE) |
| easyocr              | Python                                                   |    PyPI    | [Apache-2.0](https://github.com/JaidedAI/EasyOCR/blob/master/LICENSE)                            |
| pystray              | Python                                                   |    PyPI    | [GPL-3.0, LGPL-3.0 licenses found](https://github.com/moses-palmer/pystray)                      |
| pyzipper             | Python                                                   |    PyPI    | [MIT](https://github.com/danifus/pyzipper/blob/master/LICENSE)                                   |
| PyMuPDF              | Python                                                   |    PyPI    | [AGPL-3.0](https://github.com/pymupdf/pymupdf?tab=AGPL-3.0-1-ov-file#readme)                     |
| mail-parser          | Python                                                   |    PyPI    | [Apache-2.0](https://github.com/SpamScope/mail-parser/blob/develop/LICENSE.txt)                  |
| chrome-inject-eval   | liberrpa-chrome-extension                                |     npm     | [MIT](https://www.npmjs.com/package/chrome-inject-eval)                                          |
| socket.io-client     | liberrpa-chrome-extension ui-analyzer                    |     npm     | [MIT](https://github.com/socketio/socket.io/blob/main/LICENSE)                                   |
| vue                  | liberrpa-chrome-extension liberrpa-flowchart ui-analyzer |     npm     | [MIT](https://github.com/vuejs/core/blob/main/LICENSE)                                           |
| @logicflow/core      | liberrpa-flowchart                                       |     npm     | [Apache-2.0](https://github.com/didi/LogicFlow/blob/master/LICENSE)                              |
| @logicflow/extension | liberrpa-flowchart                                       |     npm     | [Apache-2.0](https://github.com/didi/LogicFlow/blob/master/LICENSE)                              |
| lodash               | liberrpa-flowchart ui-analyzer                           |     npm     | [View license](https://github.com/lodash/lodash/blob/main/LICENSE)                               |
| pinia                | liberrpa-flowchart ui-analyzer                           |     npm     | [MIT](https://github.com/vuejs/pinia/blob/v3/LICENSE)                                            |
| uuid                 | liberrpa-flowchart                                       |     npm     | [MIT](https://github.com/uuidjs/uuid/blob/main/LICENSE.md)                                       |
| vuetify              | liberrpa-flowchart ui-analyzer                           |     npm     | [MIT](https://github.com/vuetifyjs/vuetify/blob/master/LICENSE.md)                               |
| jsonc-parser         | liberrpa-snippets-tree ui-analyzer                       |     npm     | [MIT](https://github.com/microsoft/node-jsonc-parser/blob/main/LICENSE.md)                       |
| @mdi/font            | ui-analyzer                                              |     npm     | [Apache-2.0](https://github.com/Templarian/MaterialDesign-Webfont/blob/master/LICENSE)           |
| moment               | ui-analyzer                                              |     npm     | [MIT](https://github.com/moment/moment/blob/develop/LICENSE)                                     |

# Get in Touch

[Issues](https://github.com/HUHARED/LiberRPA/issues)

[Discussions](https://github.com/HUHARED/LiberRPA/discussions)

[Telegram](https://t.me/+U6oCH5Vs6CcxOTg9)

Email：`mailwork.hu@gmail.com`

# Change Log

Since LiberRPA has components across different platforms, all changes will be recorded in [the unified document](./docs/CHANGELOG.md).

# License

This project is licensed under the GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later).
Copyright (C) 2025 Jiyan Hu.
For more details, see the [LICENSE](./LICENSE) file.
