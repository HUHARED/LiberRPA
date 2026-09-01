# Installation, Portability & Uninstallation

This document explains how to install and initialize LiberRPA, prepare it for offline use, move it between computers, understand the system changes made during initialization, and remove it cleanly.

For creating and running your first automation Project, see [Getting Started](./GettingStarted.md).

## Contents

* [Download and Extract](#download-and-extract)
* [Initialize LiberRPA](#initialize-liberrpa)
* [Install the Chrome Extension](#install-the-chrome-extension)
* [Automatic Startup](#automatic-startup)
* [Portable and Offline Use](#portable-and-offline-use)
* [Moving or Updating LiberRPA](#moving-or-updating-liberrpa)
* [Files and System Changes](#files-and-system-changes)
* [Configuration](#configuration)
* [Uninstallation](#uninstallation)
* [Troubleshooting](#troubleshooting)

---

## Download and Extract

Download the latest LiberRPA release from SourceForge:

**TODO：[Download LiberRPA](TODO_SOURCEFORGE_DOWNLOAD_URL)**

Release archives use the following naming convention:

```text
LiberRPA-<version>-win-x64.7z
```

For example:

```text
LiberRPA-0.3.0-win-x64.7z
```

The release page also publishes the SHA256 hash of the archive. To verify a downloaded file from Command Prompt:

```bat
certutil -hashfile LiberRPA-0.3.0-win-x64.7z SHA256
```

Compare the reported value with the hash published for the same release. SHA256 verifies that the archive matches the published file; it is not a Windows publisher signature, so unsigned executables may still be shown as coming from an unknown publisher.

Extract the archive to a local directory where your Windows account has normal read and write access.

For example:

```text
D:\Tools\LiberRPA-0.3.0\
```

LiberRPA is designed to operate from its extracted directory and does not need to be installed under `Program Files`.

The release archive does not redistribute the Microsoft Visual Studio Code binary. It contains the LiberRPA Editor configuration, while `InitLiberRPA.exe` downloads the tested Windows x64 VS Code ZIP directly from Microsoft when the Editor is first prepared. An internet connection is therefore required for a clean first-time Editor setup.

The extracted directory is referred to in the documentation as the  **LiberRPA root directory** .

---

## Initialize LiberRPA

Run:

```text
InitLiberRPA.exe
```

from the LiberRPA root directory.

`InitLiberRPA.exe` uses its current working directory as the LiberRPA root and configures the current Windows user accordingly.

### What initialization does

Initialization currently performs the following operations:

1. Creates the user data directory:
   ```text
   %USERPROFILE%\Documents\LiberRPA\
   ```
2. Creates or updates the user environment variable:
   ```text
   LiberRPA=<current LiberRPA root directory>
   ```
3. Checks whether the LiberRPA Editor has been prepared. When VS Code is missing, downloads the tested Windows x64 VS Code ZIP directly from Microsoft and prepares it under `Editor/`.
4. Creates the Chrome Native Messaging configuration used by the LiberRPA Chrome Extension.
5. Registers the Native Messaging host for the current Windows user.
6. Creates fresh authentication tokens for local WebSocket communication between LiberRPA components.
7. Installs the bundled Noto Sans Mono font for the current user if the corresponding font file is not already present.
8. Checks the selected VS Code extensions and attempts to install missing ones through the Editor's VS Code CLI and the Visual Studio Marketplace.
9. Creates LiberRPA Local Server and Executor shortcuts in the Windows Startup folder.
10. Creates Editor, Executor, UI Analyzer, and Local Server shortcuts on the desktop.
11. Checks whether an existing Executor configuration is present.
12. Creates the default local Component Repository if it does not already exist.

### Editor setup

LiberRPA Editor uses Microsoft Visual Studio Code in portable mode. The Microsoft VS Code program files are not included in the LiberRPA release archive.

For LiberRPA 0.3.0, a clean Editor setup downloads **VS Code 1.121.0 for Windows x64** directly from Microsoft. Before downloading, the initializer shows the version, download source, Microsoft license, and privacy statement, and asks for confirmation.

The initializer checks the ZIP against the SHA256 returned by Microsoft's download service, verifies the expected version and build, and checks the downloaded `Code.exe` publisher signature through Windows before installing the program files under `Editor/`. It does not continue with an unverified download.

LiberRPA's portable settings, keybindings, and installed extensions remain under `Editor/data`. They are not overwritten by Editor setup. A recognized existing Editor is reused without downloading or automatically upgrading or downgrading it. A different version produces a warning because LiberRPA's tested version remains 1.121.0.

If downloading or verification fails, Editor preparation stops before the later initialization steps. Normal initialization may already have created the user data directory and updated the `LiberRPA` user environment variable at that point. Check the reported error and run `InitLiberRPA.exe` again. Extension installation has a different policy: once the Editor is available, a Marketplace failure does not block the remaining initialization.

If an incomplete Editor installation is found, the initializer does not merge another VS Code copy into it. Close the Editor, keep `Editor/data`, move the other items from `Editor/` into a backup directory, and rerun the initializer.

To prepare only the Editor without changing the Windows user environment variable, local authentication tokens, or shortcuts, run this from the LiberRPA root directory in Command Prompt:

```cmd
InitLiberRPA.exe --editor-only
```

This option prepares the VS Code program files only; run normal initialization afterward to configure LiberRPA and install the selected extensions.

### Editor extension setup

Third-party VS Code extensions are not bundled with the LiberRPA release archive. After VS Code is available, `InitLiberRPA.exe` checks the selected extensions already present in the portable Editor and attempts to install any missing ones from the Visual Studio Marketplace.

The initial download can be relatively large. With the current Windows x64 extension set, a clean setup may download **more than 300 MB** in total after extension dependencies are included. This is an approximate current figure rather than a fixed package size: the actual amount can change as extension versions and dependencies change.

Download time therefore depends strongly on the connection to the Visual Studio Marketplace and its content-delivery infrastructure, as well as local network, proxy, firewall, certificate, and regional conditions. On a slow connection, initial extension setup may take several minutes or longer. `InitLiberRPA.exe` displays the current extension and elapsed installation time while waiting.

Extension installation is best-effort and does not block the remaining LiberRPA initialization. If the Marketplace cannot be reached, initialization reports the unresolved extensions and continues. Restore network access and run `InitLiberRPA.exe` again, or install the missing extensions manually from the Editor Extensions view.

Installed extensions and their dependencies are stored under:

```text
Editor/data/extensions/
```

They therefore move with the portable Editor and can be used offline after installation.

### Reinitializing an existing installation

If a `LiberRPA` user environment variable already exists, initialization asks whether it should be replaced with the current directory.

When installing a new release, moving LiberRPA, or intentionally refreshing the current installation, answer:

```text
y
```

even if the displayed directory is unchanged.

This refreshes machine-specific configuration and generates new local authentication tokens.

After reinitialization:

* restart LiberRPA Editor;
* restart LiberRPA Local Server;
* restart other LiberRPA applications that were already running.

This ensures that all processes use the current environment variable and authentication information.

### Only one active LiberRPA root per Windows user

You may keep multiple LiberRPA release directories on the same computer, but initialization configures several user-level resources to point to one active installation, including:

* the `LiberRPA` environment variable;
* Chrome Native Messaging registration;
* local authentication information;
* startup and desktop integration.

Therefore, only one LiberRPA root should be treated as the currently initialized installation for a Windows user.

Running `InitLiberRPA.exe` from another release directory and confirming the replacement makes that directory the active installation.

### Local authentication file

Initialization creates:

```text
%USERPROFILE%\Documents\LiberRPA\WebSocketAuth.json
```

This file contains authentication tokens used for local communication between LiberRPA components.

**Do not publish, commit, or share this file.**

Running initialization again and confirming the installation refresh generates new tokens.

---

## Install the Chrome Extension

HTML/DOM browser automation requires the LiberRPA Chrome Extension.

**[Install LiberRPA Chrome Extension from the Chrome Web Store](https://chromewebstore.google.com/detail/liberrpa-chrome-extension/cffobgimbemkfgjmcedebofkfcamnajb)**

For permissions, configuration, and browser-specific limitations, see:

[Chrome Extension documentation](../browserExtensions/liberrpa-chrome-extension/README.md)

### Native Messaging

`InitLiberRPA.exe` creates the Native Messaging configuration used by the Chrome Extension at:

```text
%USERPROFILE%\Documents\LiberRPA\NativeMessaging\liberrpachromemessage.json
```

and registers it under:

```text
HKEY_CURRENT_USER\SOFTWARE\Google\Chrome\NativeMessagingHosts\com.liberrpa.chrome.msghost
```

The registration points Chrome to the Native Messaging configuration of the currently initialized LiberRPA installation.

The Chrome Extension itself is installed separately through Chrome and is not installed merely by copying the LiberRPA directory.

---

## Automatic Startup

Initialization places shortcuts for the following applications in the current user's Windows Startup folder:

```text
LocalServer-LiberRPA.lnk
Executor-LiberRPA.lnk
```

The Startup directory is:

```text
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\
```

These applications therefore start when the Windows user signs in.

### Disable automatic startup

If you do not want one of these applications to start automatically, remove its shortcut from the Startup folder.

You can also open the folder by pressing `Win+R` and entering:

```text
shell:startup
```

Deleting the shortcut does not uninstall the corresponding LiberRPA application.

> Running `InitLiberRPA.exe` again and confirming initialization will recreate the standard Startup shortcuts.

---

## Portable and Offline Use

LiberRPA is designed so that a prepared installation can be copied to another compatible Windows computer.

However, some preparation should be completed while internet access is still available.

### Prepare an installation for offline use

On an online Windows computer:

1. Extract the complete LiberRPA release archive.
2. Run `InitLiberRPA.exe` and allow it to prepare VS Code and complete the initial Editor extension setup. Depending on network conditions, downloading VS Code, the selected extensions, and their dependencies may take several minutes or longer.
3. Open LiberRPA Editor once and verify that VS Code starts and the required extensions are available.
4. Install the LiberRPA Chrome Extension if browser automation will be required.
5. Close the Editor and other LiberRPA applications.
6. Copy the complete LiberRPA root directory to the target computer.

On the target computer:

7. Place the copied directory in its final location.
8. Run `InitLiberRPA.exe` from that directory.
9. Start the required LiberRPA applications.

Running initialization on the target computer is important because several paths and integrations are specific to the current user and machine.

### Chrome Extension and offline computers

Copying the LiberRPA root directory does **not** copy an installed Chrome Extension from another computer.

If the target computer will be completely offline and requires browser automation, prepare the browser-extension deployment separately before removing internet access.

### Normal offline operation

After the environment and required integrations have been prepared, normal LiberRPA development and local execution do not require a LiberRPA-hosted cloud service.

Individual automation Projects may still require internet access if they interact with external websites, APIs, email servers, cloud services, or other network resources.

---

## Moving or Updating LiberRPA

### Move an existing installation

The LiberRPA root directory can be moved to another local directory.

After moving it:

1. Close all LiberRPA applications.
2. Run `InitLiberRPA.exe` from the new root directory.
3. If asked to replace the current `LiberRPA` environment variable, answer `y`.
4. Restart LiberRPA applications.

This refreshes environment information, Native Messaging configuration, local authentication, and Windows shortcuts for the new location.

Portable Editor data, including installed VS Code extensions, is stored inside the LiberRPA directory and moves with the directory.

### Copy an installation to another computer

Copy the complete LiberRPA root directory and run `InitLiberRPA.exe` on the destination computer.

Do not rely on Windows shortcuts, environment variables, or Native Messaging configuration copied or recreated manually from the original computer.

Executor stores its operational database, installed Packages, and Project logs outside the LiberRPA root. Copying only the root directory does not transfer that data. See [Move Executor Data to Another Computer](../electronApplications/executor/README.md#move-executor-data-to-another-computer) when installed Projects, Schedules, Run History, logs, or recordings must also be preserved.

### Update to a newer release

Until LiberRPA provides a dedicated updater, the safest approach is to keep releases separate during migration:

1. Back up important Projects and user data.
2. Keep the previous LiberRPA release temporarily as a rollback copy.
3. Extract the new release into a separate directory.
4. Review the release notes for migration requirements.
5. Migrate only settings or data you intentionally want to preserve.
6. Run `InitLiberRPA.exe` from the new release directory.
7. Confirm replacement of the existing `LiberRPA` environment variable.
8. Keep the computer online while initialization prepares the Editor and installs any selected extensions that are missing from the new release's portable Editor data.
9. Verify Executor and Component Repository settings before deleting the previous release.

Avoid blindly copying an old Python environment or application files over a newer release.

---

## Files and System Changes

LiberRPA is primarily portable, but initialization creates several user-level files and integrations outside the root directory.

Understanding them is useful for backup, migration, troubleshooting, and clean removal.

### LiberRPA root directory

Contains the main LiberRPA applications, development environment, configuration files, and portable Editor data. After initialization, it also contains the Microsoft VS Code files downloaded directly from Microsoft and any Editor extensions installed during setup.

Example:

```text
D:\Tools\LiberRPA-0.3.0\
```

Deleting the root directory removes the corresponding release files, but does not remove all user-level LiberRPA integration or data.

### User data directory

Default location:

```text
%USERPROFILE%\Documents\LiberRPA\
```

This directory may contain data such as:

```text
AppData\
ComponentRepository\
ExecutorPackage\
ExecutorRunState\
NativeMessaging\
OutputLog\
WebSocketAuth.json
```

and other data created by LiberRPA tools. Executor's Waiting Queue is held only in memory and is not stored in this directory.

The default Component Repository is:

```text
%USERPROFILE%\Documents\LiberRPA\ComponentRepository\
```

**Treat this directory as user data.**

Do not delete it during an upgrade or uninstall unless you have confirmed that any Components, logs, or other data you want to keep have been backed up.

### User environment variable

Initialization creates:

```text
LiberRPA
```

as a Windows **user** environment variable.

Its value is the active LiberRPA root directory.

### Startup shortcuts

Location:

```text
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\
```

Standard LiberRPA shortcuts:

```text
LocalServer-LiberRPA.lnk
Executor-LiberRPA.lnk
```

### Desktop shortcuts

Initialization creates shortcuts for:

```text
Editor-LiberRPA.lnk
Executor-LiberRPA.lnk
LocalServer-LiberRPA.lnk
UI_Analyzer-LiberRPA.lnk
```

to the current user's Desktop.

### Chrome Native Messaging

Configuration file:

```text
%USERPROFILE%\Documents\LiberRPA\NativeMessaging\liberrpachromemessage.json
```

Registry key:

```text
HKEY_CURRENT_USER\SOFTWARE\Google\Chrome\NativeMessagingHosts\com.liberrpa.chrome.msghost
```

### User font

If the bundled Noto Sans Mono font file is not already present, initialization copies it to:

```text
%LOCALAPPDATA%\Microsoft\Windows\Fonts\
```

The current bundled filename is:

```text
NotoSansMono-VariableFont_wdth,wght.ttf
```

### Files created by dependencies

LiberRPA cannot guarantee that third-party dependencies create no additional cache, configuration, browser, Python, VS Code, or operating-system files outside the locations documented above.

The locations in this document describe LiberRPA's own initialization behavior, not every side effect of every upstream dependency.

---

## Configuration

Common LiberRPA settings are stored in:

```text
<LiberRPA root>\configFiles\basic.jsonc
```

Current settings include:

* output log directory;
* LiberRPA Local Server port;
* UI Analyzer theme;
* UI Analyzer minimize behavior;
* Component Repository path.

The default log root is:

```text
%USERPROFILE%\Documents\LiberRPA\OutputLog\
```

The default Local Server port is:

```text
52000
```

The default Component Repository is:

```text
%USERPROFILE%\Documents\LiberRPA\ComponentRepository\
```

A local directory is recommended for the Component Repository.

A shared network directory should only be used when it provides reliable file locking and atomic file operations. Cloud-synchronised directories such as OneDrive are not recommended as multi-user Component Repositories.

For Python runtime dependencies and environment construction, see:

[Python Environment](./Environment.md)

---

## Uninstallation

LiberRPA 0.3.0 does not currently provide a dedicated uninstaller.

Because the main application is portable, it can be removed manually.

### Before uninstalling

1. Close LiberRPA Editor.
2. Exit LiberRPA Executor.
3. Exit LiberRPA Local Server.
4. Close UI Analyzer and any running LiberRPA Projects.
5. Back up Projects, Components, logs, configuration, or other data that you want to keep.

### 1. Remove automatic-startup shortcuts

Delete, if present:

```text
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\LocalServer-LiberRPA.lnk
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Executor-LiberRPA.lnk
```

### 2. Remove desktop shortcuts

Delete the LiberRPA shortcuts from the current user's Desktop:

```text
Editor-LiberRPA.lnk
Executor-LiberRPA.lnk
LocalServer-LiberRPA.lnk
UI_Analyzer-LiberRPA.lnk
```

### 3. Remove Chrome Native Messaging registration

Delete the registry key:

```text
HKEY_CURRENT_USER\SOFTWARE\Google\Chrome\NativeMessagingHosts\com.liberrpa.chrome.msghost
```

The associated configuration file can then be removed:

```text
%USERPROFILE%\Documents\LiberRPA\NativeMessaging\liberrpachromemessage.json
```

### 4. Remove the `LiberRPA` user environment variable

Open:

```text
Edit environment variables for your account
```

in Windows and delete the user variable:

```text
LiberRPA
```

if it still points to the installation being removed.

If another LiberRPA release should remain active, initialize that release instead of simply deleting the variable.

### 5. Remove the LiberRPA root directory

Delete the release directory, for example:

```text
D:\Tools\LiberRPA-0.3.0\
```

### 6. Decide whether to keep user data

The following directory is **not just application files**:

```text
%USERPROFILE%\Documents\LiberRPA\
```

It may contain:

* Component Repository data;
* logs;
* local authentication information;
* Native Messaging data;
* other LiberRPA-generated user data.

If you intend to reinstall or want to preserve Components and logs, keep or back up this directory.

For a complete removal, delete it only after verifying that nothing inside is needed.

### 7. Remove the Chrome Extension

If LiberRPA browser automation is no longer required, remove the LiberRPA Chrome Extension through Chrome's extension-management interface.

### 8. Optional font cleanup

LiberRPA may have copied:

```text
%LOCALAPPDATA%\Microsoft\Windows\Fonts\NotoSansMono-VariableFont_wdth,wght.ttf
```

during initialization.

Remove it only if you are certain that:

* it was installed by LiberRPA;
* it did not exist before LiberRPA was initialized;
* no other application or user workflow depends on it.

Leaving the font installed is harmless.

---

## Troubleshooting

### LiberRPA still points to an old directory

Run `InitLiberRPA.exe` from the intended LiberRPA root and confirm replacement when prompted.

Then restart LiberRPA applications.

You can also verify the current user environment variable:

```text
LiberRPA
```

### Browser automation stops working after moving LiberRPA

Moving the root directory changes the path used by Chrome Native Messaging.

Run:

```text
InitLiberRPA.exe
```

from the new root directory to recreate the Native Messaging configuration and registration.

Restart Chrome and LiberRPA Local Server afterwards.

### Local communication stops working after reinitialization

Initialization creates new WebSocket authentication tokens.

If Editor, Local Server, UI Analyzer, Chrome, or other related LiberRPA processes were already running, restart them so that they use the current authentication information.

### Startup shortcuts reappear

`InitLiberRPA.exe` creates the standard Local Server and Executor Startup shortcuts.

If you manually removed them and later run initialization again, remove the shortcuts again after initialization if automatic startup is not desired.

### Executor configuration exists after moving or copying LiberRPA

Executor configuration can contain settings from the previous installation or computer.

Review:

```text
<LiberRPA root>\configFiles\Executor.jsonc
```

after moving or copying an existing LiberRPA installation. In particular, verify the Project Log Folder, Time Zone, RDP settings, and retention settings. Executor's database and installed Package migration are documented in [Data and Recovery](../electronApplications/executor/README.md#data-and-recovery).

### Automation cannot interact with an elevated application

Windows privilege boundaries can prevent a normal process from automating an application running with administrator privileges.

If a target application is elevated, the relevant LiberRPA process may also need to run with appropriate privileges.

Only elevate LiberRPA applications when the target automation scenario requires it.

### Offline Editor is missing extensions

An Editor intended for offline use must first be prepared on an online computer. Run `InitLiberRPA.exe` while online so that VS Code and the selected extensions can be downloaded, then open the Editor once and verify that the required extensions are available.

If this preparation was skipped, reconnect the installation to the internet, run `InitLiberRPA.exe` again, verify the Editor, and then copy the prepared LiberRPA root directory to the offline computer again.
