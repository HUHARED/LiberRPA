# FileName: _EditorExtensions.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


@dataclass(frozen=True)
class EditorExtensionSpec:
    extensionId: str
    version: str | None = None

    @property
    def installTarget(self) -> str:
        if self.version is None:
            return self.extensionId
        return f"{self.extensionId}@{self.version}"


@dataclass(frozen=True)
class EditorExtensionInstallResult:
    success: bool
    networkFailure: bool
    elapsedSeconds: float


# Keep this list limited to extensions that LiberRPA intentionally selects.
# Dependencies such as Pylance, Debugpy, Python Environments, and the Jupyter companion
# extensions are installed automatically by the Marketplace.
_EDITOR_EXTENSION_SPECS = (
    EditorExtensionSpec(extensionId="ms-python.python"),
    EditorExtensionSpec(extensionId="charliermarsh.ruff"),
    EditorExtensionSpec(extensionId="ms-toolsai.jupyter"),
    EditorExtensionSpec(extensionId="esbenp.prettier-vscode"),
    EditorExtensionSpec(extensionId="oderwat.indent-rainbow"),
    EditorExtensionSpec(extensionId="christian-kohler.path-intellisense"),
    EditorExtensionSpec(extensionId="tomoki1207.selectline-statusbar"),
    EditorExtensionSpec(extensionId="kevinrose.vsc-python-indent"),
    EditorExtensionSpec(extensionId="albert.tabout"),
    EditorExtensionSpec(extensionId="hyesun.py-paste-indent"),
    EditorExtensionSpec(extensionId="ryu1kn.partial-diff"),
    # Office Viewer 3.5.4 is intentionally fixed because later releases may introduce
    # substantial UI and behavior changes.
    EditorExtensionSpec(extensionId="cweijan.vscode-office", version="3.5.4"),
    EditorExtensionSpec(extensionId="liberrpa.liberrpa-flowchart"),
    EditorExtensionSpec(extensionId="liberrpa.liberrpa-project-manager"),
    EditorExtensionSpec(extensionId="liberrpa.liberrpa-snippets-tree"),
)

_MARKETPLACE_NETWORK_ERROR_MARKERS = (
    "getaddrinfo enotfound",
    "getaddrinfo eai_again",
    "enotfound marketplace.visualstudio.com",
    "etimedout",
    "econnrefused",
    "econnreset",
    "enetunreach",
    "ehostunreach",
    "network is unreachable",
    "tunneling socket could not be established",
    "407 proxy authentication required",
    "self signed certificate in certificate chain",
    "unable to get local issuer certificate",
    "unable to verify the first certificate",
    "502 bad gateway",
    "503 service unavailable",
    "504 gateway timeout",
    "429 too many requests",
)


def _get_editor_code_command_path(rootPath: Path) -> Path:
    return rootPath / "Editor" / "bin" / "code.cmd"


def _build_editor_code_command(rootPath: Path, arguments: list[str]) -> list[str]:
    pathCodeCommand = _get_editor_code_command_path(rootPath=rootPath)

    # code.cmd is a batch file. Run it through COMSPEC with CALL so this process blocks until the VS Code CLI operation has completed.
    strCommand = subprocess.list2cmdline(["call", str(pathCodeCommand), *arguments])
    return [
        os.environ.get("COMSPEC", "cmd.exe"),
        "/d",
        "/s",
        "/c",
        strCommand,
    ]


def _run_editor_code_command(
    rootPath: Path,
    arguments: list[str],
    captureOutput: bool = False,
) -> subprocess.CompletedProcess[str]:
    pathEditor = rootPath / "Editor"

    return subprocess.run(
        _build_editor_code_command(rootPath=rootPath, arguments=arguments),
        cwd=pathEditor,
        check=False,
        capture_output=captureOutput,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _get_installed_editor_extensions(rootPath: Path) -> dict[str, str] | None:
    pathCodeCommand = _get_editor_code_command_path(rootPath=rootPath)
    if not pathCodeCommand.is_file():
        print(
            f"[Warning] VS Code CLI was not found: '{pathCodeCommand}'. "
            "Skip Editor extension setup."
        )
        return None

    result = _run_editor_code_command(
        rootPath=rootPath,
        arguments=["--list-extensions", "--show-versions"],
        captureOutput=True,
    )
    if result.returncode != 0:
        print(
            "[Warning] Could not query the extensions installed in LiberRPA Editor. "
            "Skip Editor extension setup."
        )
        if result.stdout:
            print(result.stdout.rstrip())
        if result.stderr:
            print(result.stderr.rstrip(), file=sys.stderr)
        return None

    dictInstalled: dict[str, str] = {}
    for strLine in result.stdout.splitlines():
        strItem = strLine.strip()
        if not strItem or "@" not in strItem:
            continue

        strExtensionId, strVersion = strItem.rsplit("@", maxsplit=1)
        if strExtensionId and strVersion:
            dictInstalled[strExtensionId.lower()] = strVersion

    return dictInstalled


def _format_elapsed(seconds: float) -> str:
    intSeconds = max(0, int(seconds))
    intMinutes, intSeconds = divmod(intSeconds, 60)
    if intMinutes < 100:
        return f"{intMinutes:02d}:{intSeconds:02d}"

    intHours, intMinutes = divmod(intMinutes, 60)
    return f"{intHours:02d}:{intMinutes:02d}:{intSeconds:02d}"


def _is_marketplace_network_error(output: str) -> bool:
    strOutputLower = output.lower()
    return any(marker in strOutputLower for marker in _MARKETPLACE_NETWORK_ERROR_MARKERS)


def _run_editor_extension_install_with_progress(
    rootPath: Path,
    extensionSpec: EditorExtensionSpec,
    index: int,
    total: int,
    targetWidth: int,
) -> EditorExtensionInstallResult:
    listArguments = [
        "--install-extension",
        extensionSpec.installTarget,
    ]
    if extensionSpec.version is not None:
        listArguments.append("--force")

    pathEditor = rootPath / "Editor"
    listCommand = _build_editor_code_command(rootPath=rootPath, arguments=listArguments)
    floatStartedAt = time.monotonic()
    listSpinner = ["|", "/", "-", "\\"]
    intSpinnerIndex = 0
    intLastProgressLength = 0

    # Write VS Code CLI output to a temporary file while the parent process renders a lightweight spinner.
    # This avoids pipe-buffer deadlocks while still letting us show activity during large Marketplace downloads.
    with tempfile.TemporaryFile(mode="w+b") as fileOutput:
        processObj = subprocess.Popen(
            listCommand,
            cwd=pathEditor,
            stdout=fileOutput,
            stderr=subprocess.STDOUT,
        )

        if sys.stdout.isatty():
            while processObj.poll() is None:
                strProgress = (
                    f"[{index:02d}/{total:02d}] "
                    f"{extensionSpec.installTarget:<{targetWidth}}  "
                    f"Installing... {_format_elapsed(time.monotonic() - floatStartedAt)} "
                    f"{listSpinner[intSpinnerIndex % len(listSpinner)]}"
                )
                sys.stdout.write("\r" + strProgress)
                sys.stdout.flush()
                intLastProgressLength = max(intLastProgressLength, len(strProgress))
                intSpinnerIndex += 1
                time.sleep(0.15)
        else:
            print(
                f"[{index:02d}/{total:02d}] {extensionSpec.installTarget}  Installing..."
            )
            processObj.wait()

        intReturnCode = processObj.wait()
        floatElapsedSeconds = time.monotonic() - floatStartedAt

        if sys.stdout.isatty() and intLastProgressLength:
            sys.stdout.write("\r" + (" " * intLastProgressLength) + "\r")
            sys.stdout.flush()

        fileOutput.seek(0)
        strOutput = fileOutput.read().decode("utf-8", errors="replace").strip()

    boolSuccess = intReturnCode == 0
    strStatus = "Installed" if boolSuccess else "Failed"
    print(
        f"[{index:02d}/{total:02d}] "
        f"{extensionSpec.installTarget:<{targetWidth}}  "
        f"{strStatus} ({floatElapsedSeconds:.1f}s)"
    )

    if not boolSuccess and strOutput:
        print(strOutput)

    return EditorExtensionInstallResult(
        success=boolSuccess,
        networkFailure=(not boolSuccess and _is_marketplace_network_error(strOutput)),
        elapsedSeconds=floatElapsedSeconds,
    )


def install_editor_extensions(rootPath: Path) -> None:
    # Extension setup is intentionally best-effort.
    # LiberRPA initialization should not fail only because the external VS Code Marketplace is unavailable or blocked by the current network environment.
    dictInstalled = _get_installed_editor_extensions(rootPath=rootPath)
    if dictInstalled is None:
        return

    listToInstall: list[EditorExtensionSpec] = []
    for extensionSpec in _EDITOR_EXTENSION_SPECS:
        strInstalledVersion = dictInstalled.get(extensionSpec.extensionId.lower())

        if extensionSpec.version is None:
            if strInstalledVersion is None:
                listToInstall.append(extensionSpec)
        elif strInstalledVersion != extensionSpec.version:
            listToInstall.append(extensionSpec)

    intSelectedCount = len(_EDITOR_EXTENSION_SPECS)
    intAvailableCount = intSelectedCount - len(listToInstall)
    print(
        f"Selected VS Code extensions already available: "
        f"{intAvailableCount}/{intSelectedCount}."
    )

    if not listToInstall:
        print("LiberRPA Editor extension setup is already complete.")
        return

    print(f"VS Code extensions to install: {len(listToInstall)}")
    print()

    intTargetWidth = max(len(item.installTarget) for item in listToInstall)
    listUnresolved: list[str] = []
    boolStoppedForNetwork = False

    for intIndex, extensionSpec in enumerate(listToInstall, start=1):
        result = _run_editor_extension_install_with_progress(
            rootPath=rootPath,
            extensionSpec=extensionSpec,
            index=intIndex,
            total=len(listToInstall),
            targetWidth=intTargetWidth,
        )

        if result.success:
            continue

        listUnresolved.append(extensionSpec.installTarget)

        if result.networkFailure:
            listRemaining = listToInstall[intIndex:]
            listUnresolved.extend(item.installTarget for item in listRemaining)
            boolStoppedForNetwork = True

            print()
            if listRemaining:
                print(
                    "[Warning] Visual Studio Marketplace appears unavailable. "
                    f"Skip the remaining {len(listRemaining)} extension download attempt(s) in this initialization."
                )
            else:
                print("[Warning] Visual Studio Marketplace appears unavailable.")
            break

        print(
            f"[Warning] Failed to install VS Code extension '{extensionSpec.installTarget}'. "
            "Continue with the remaining extensions."
        )

    if listUnresolved:
        print()
        print("[Warning] Editor extension setup is incomplete.")
        print("Unresolved VS Code extensions:")
        for strExtension in listUnresolved:
            print(f"  - {strExtension}")

        if boolStoppedForNetwork:
            print(
                "Connect to the Internet and run InitLiberRPA.exe again after checking "
                "the network, proxy, firewall, or certificate environment."
            )
        else:
            print(
                "You can retry InitLiberRPA.exe or install the unresolved extension(s) "
                "manually from the Editor Extensions view."
            )

        print("LiberRPA initialization will continue.")
    else:
        print()
        print("LiberRPA Editor extension setup completed.")
