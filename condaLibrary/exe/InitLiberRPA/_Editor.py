# FileName: _Editor.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


"""Prepare the official portable VS Code distribution without replacing user data."""


from dataclasses import dataclass
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zipfile import ZipFile


# Taken from the VS Code product.json supplied with the tested LiberRPA Editor.
_EDITOR_VERSION = "1.121.0"
_EDITOR_COMMIT = "f6cfa2ea2403534de03f069bdf160d06451ed282"
_EDITOR_SHA256 = "519e145e572f8ad7a8146399354e7c57b42ad5d02d67d567092a51aac3fb927b"
_EDITOR_DOWNLOAD_URL = (
    f"https://update.code.visualstudio.com/{_EDITOR_VERSION}/win32-x64-archive/stable"
)
_EDITOR_LICENSE_URL = "https://code.visualstudio.com/license"
_EDITOR_PRIVACY_URL = "https://privacy.microsoft.com/privacystatement"
_DOWNLOAD_TIMEOUT_SECONDS = 60
_DOWNLOAD_ATTEMPTS = 3
_MAX_ARCHIVE_BYTES = 1024**3
_MAX_EXTRACTED_BYTES = 4 * 1024**3


class EditorSetupError(RuntimeError):
    """Editor preparation did not finish; do not continue initialization."""


@dataclass(frozen=True)
class EditorInfo:
    version: str
    commit: str
    appPath: Path


def _inspect_editor(editorPath: Path) -> EditorInfo | None:
    """Inspect files without launching an unverified executable."""
    if not (editorPath / "Code.exe").is_file():
        return None
    if not (editorPath / "bin" / "code.cmd").is_file():
        return None

    # Newer Windows distributions put the application in a commit-named folder.
    listAppPath = [editorPath / "resources" / "app"]
    listAppPath.extend(
        pathChild / "resources" / "app"
        for pathChild in editorPath.iterdir()
        if pathChild.is_dir() and re.fullmatch(r"[0-9a-f]{10}", pathChild.name)
    )
    listInfo: list[EditorInfo] = []
    for pathApp in listAppPath:
        pathProduct = pathApp / "product.json"
        if not pathProduct.is_file():
            continue
        try:
            dictProduct = json.loads(pathProduct.read_text(encoding="utf-8-sig"))
        except (ValueError, OSError):
            continue
        if not isinstance(dictProduct, dict):
            continue
        strVersion = dictProduct.get("version")
        strCommit = dictProduct.get("commit")
        if (
            dictProduct.get("applicationName") != "code"
            or dictProduct.get("quality") != "stable"
            or not isinstance(strVersion, str)
            or not re.fullmatch(r"\d+\.\d+\.\d+", strVersion)
            or not isinstance(strCommit, str)
            or not re.fullmatch(r"[0-9a-f]{40}", strCommit)
        ):
            continue
        if pathApp.parent.parent != editorPath:
            if pathApp.parent.parent.name != strCommit[:10]:
                continue
        if not (pathApp / "out" / "cli.js").is_file():
            continue
        listInfo.append(EditorInfo(strVersion, strCommit, pathApp))

    # Do not guess which of several leftover application folders is active.
    return listInfo[0] if len(listInfo) == 1 else None


class _MicrosoftDownloadRedirectHandler(HTTPRedirectHandler):
    """Read the archive hash from Microsoft's authenticated download redirect."""

    def __init__(self) -> None:
        super().__init__()
        self.expectedSha256: str | None = None

    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: http.client.HTTPMessage,
        newurl: str,
    ) -> Request | None:
        if urlparse(newurl).scheme.lower() != "https":
            raise EditorSetupError(
                "Refusing a VS Code download redirect that does not use HTTPS."
            )
        if req.full_url == _EDITOR_DOWNLOAD_URL:
            strSha256 = headers.get("x-sha256", "").strip().lower()
            if not re.fullmatch(r"[0-9a-f]{64}", strSha256):
                raise EditorSetupError(
                    "Microsoft did not provide a valid SHA256 for the selected VS Code archive. "
                    "The download will not be installed without verification."
                )
            if strSha256 != _EDITOR_SHA256:
                raise EditorSetupError(
                    "Microsoft returned a different SHA256 for the pinned VS Code archive. "
                    "The download will not continue until the LiberRPA Editor definition is reviewed."
                )
            self.expectedSha256 = strSha256
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _download_archive_once(archivePath: Path) -> None:
    redirectHandler = _MicrosoftDownloadRedirectHandler()
    opener = build_opener(redirectHandler)
    request = Request(
        _EDITOR_DOWNLOAD_URL,
        headers={
            "User-Agent": "LiberRPA-Initializer/0.3.0",
            "Accept-Encoding": "identity",
        },
    )
    # The default HTTPS handler validates certificates and honors standard proxy settings.
    with opener.open(request, timeout=_DOWNLOAD_TIMEOUT_SECONDS) as response:
        if redirectHandler.expectedSha256 is None:
            raise EditorSetupError(
                "The VS Code download did not include Microsoft's SHA256 metadata."
            )
        if (
            response.status != 200
            or urlparse(response.geturl()).scheme.lower() != "https"
        ):
            raise EditorSetupError(
                "Microsoft returned an unexpected VS Code download response."
            )
        strLength = response.headers.get("Content-Length", "")
        intExpectedSize = int(strLength) if strLength.isdecimal() else None
        if intExpectedSize is not None and intExpectedSize > _MAX_ARCHIVE_BYTES:
            raise EditorSetupError(
                "The VS Code archive exceeds the allowed download size."
            )

        hashObj = hashlib.sha256()
        intReceived = 0
        floatLastProgress = time.monotonic()
        with archivePath.open("wb") as fileArchive:
            while data := response.read(256 * 1024):
                intReceived += len(data)
                if intReceived > _MAX_ARCHIVE_BYTES:
                    raise EditorSetupError(
                        "The VS Code archive exceeds the allowed download size."
                    )
                fileArchive.write(data)
                hashObj.update(data)
                if time.monotonic() - floatLastProgress >= 2:
                    strTotal = (
                        f" / {intExpectedSize / 1024**2:.1f} MiB"
                        if intExpectedSize
                        else " MiB"
                    )
                    print(
                        f"  Downloaded {intReceived / 1024**2:.1f}{strTotal}", flush=True
                    )
                    floatLastProgress = time.monotonic()
        if intExpectedSize is not None and intReceived != intExpectedSize:
            raise http.client.IncompleteRead(b"", intExpectedSize - intReceived)
        if hashObj.hexdigest() != redirectHandler.expectedSha256:
            raise EditorSetupError(
                "VS Code archive SHA256 verification failed. Nothing has been installed in Editor."
            )
        print(f"VS Code archive SHA256 verified: {hashObj.hexdigest()}")
        return None


def _download_archive(archivePath: Path) -> None:
    for intAttempt in range(1, _DOWNLOAD_ATTEMPTS + 1):
        print(
            f"Downloading VS Code {_EDITOR_VERSION} ({intAttempt}/{_DOWNLOAD_ATTEMPTS})...",
            flush=True,
        )
        try:
            _download_archive_once(archivePath)
            return
        except HTTPError as e:
            if e.code not in (408, 429, 500, 502, 503, 504):
                raise EditorSetupError(
                    f"Microsoft download request failed: HTTP {e.code}."
                ) from e
            strError = str(e)
        except (URLError, http.client.HTTPException, TimeoutError, ConnectionError) as e:
            strError = str(e)
        if intAttempt == _DOWNLOAD_ATTEMPTS:
            raise EditorSetupError(
                f"VS Code download failed: {strError}. Check the network, proxy, and certificates, "
                "then run InitLiberRPA.exe again."
            )
        print(f"[Warning] {strError}. Retrying the download...")
        time.sleep(2)


def _extract_archive(archivePath: Path, extractPath: Path) -> None:
    """Validate every ZIP path before writing anything to the staging directory."""
    with ZipFile(archivePath) as zipObj:
        listMember = zipObj.infolist()
        if sum(member.file_size for member in listMember) > _MAX_EXTRACTED_BYTES:
            raise EditorSetupError(
                "The unpacked VS Code archive exceeds the allowed size."
            )
        setName: set[str] = set()
        for member in listMember:
            strName = member.filename.replace("\\", "/")
            listPart = strName.rstrip("/").split("/")
            if (
                not strName
                or strName.startswith("/")
                or member.orig_filename != member.filename
                or any(part in ("", ".", "..") for part in listPart)
                or any(re.search(r'[\x00-\x1f:<>"|?*]', part) for part in listPart)
                or any(part.endswith((" ", ".")) for part in listPart)
                or any(
                    re.match(
                        r"(?i)^(CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:[ .]|$)", part
                    )
                    for part in listPart
                )
                or stat.S_ISLNK(member.external_attr >> 16)
            ):
                raise EditorSetupError(
                    f"Unsafe path in the VS Code archive: {member.filename!r}"
                )
            if listPart[0].casefold() == "data":
                raise EditorSetupError(
                    "The VS Code archive unexpectedly contains portable user data."
                )
            strKey = "/".join(listPart).casefold()
            if strKey in setName:
                raise EditorSetupError(
                    f"Duplicate path in the VS Code archive: {member.filename!r}"
                )
            setName.add(strKey)
        extractPath.mkdir(parents=True, exist_ok=False)
        for member in listMember:
            pathTarget = extractPath.joinpath(
                *member.filename.replace("\\", "/").rstrip("/").split("/")
            )
            if member.is_dir() or member.filename.endswith("\\"):
                pathTarget.mkdir(parents=True, exist_ok=True)
            else:
                pathTarget.parent.mkdir(parents=True, exist_ok=True)
                with (
                    zipObj.open(member) as fileSource,
                    pathTarget.open("xb") as fileTarget,
                ):
                    shutil.copyfileobj(fileSource, fileTarget)


def _verify_microsoft_signature(executablePath: Path) -> None:
    """Use Windows trust verification, without executing the downloaded program."""
    pathPowerShell = (
        Path(os.environ.get("SystemRoot", r"C:\Windows"))
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )
    strScript = (
        "$ErrorActionPreference = 'Stop'; "
        "$s = Get-AuthenticodeSignature -LiteralPath $env:LIBERRPA_EDITOR_SIGNATURE_PATH; "
        "if ($s.Status -ne 'Valid' -or $null -eq $s.SignerCertificate) { "
        "throw ('Invalid Microsoft signature: ' + $s.Status) }; "
        "if ($s.SignerCertificate.Subject -notmatch '(^|,\\s*)O=Microsoft Corporation(,|$)') { "
        "throw ('Unexpected publisher: ' + $s.SignerCertificate.Subject) }; "
        "Write-Output 'Microsoft signature verified.'"
    )
    dictEnvironment = os.environ.copy()
    dictEnvironment["LIBERRPA_EDITOR_SIGNATURE_PATH"] = str(executablePath)
    try:
        result = subprocess.run(
            [
                str(pathPowerShell),
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                strScript,
            ],
            env=dictEnvironment,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise EditorSetupError(
            f"Could not verify the Microsoft signature of '{executablePath}': {e}"
        ) from e
    if result.returncode != 0:
        raise EditorSetupError(
            f"Microsoft signature verification failed for '{executablePath}'. "
            f"{(result.stderr or result.stdout).strip()}"
        )
    print(f"Microsoft signature verified: {executablePath.name}")


def _check_program_destination(editorPath: Path) -> None:
    if editorPath.is_symlink() or (os.name == "nt" and editorPath.is_junction()):
        raise EditorSetupError(
            "Automatic Editor setup requires a regular Editor directory, not a directory link."
        )
    if editorPath.exists() and not editorPath.is_dir():
        raise EditorSetupError(f"Editor is not a directory: '{editorPath}'.")
    if editorPath.is_dir():
        listExisting = [
            path.name for path in editorPath.iterdir() if path.name.casefold() != "data"
        ]
        if listExisting:
            raise EditorSetupError(
                "Editor contains an incomplete or unrecognized VS Code installation. "
                "Close Editor, keep the 'Editor/data' directory, move the other Editor items "
                "to a backup directory, and run InitLiberRPA.exe again. "
                "Existing program files will not be overwritten automatically."
            )
    pathData = editorPath / "data"
    if pathData.exists() and not pathData.is_dir():
        raise EditorSetupError(f"Portable Editor data is not a directory: '{pathData}'.")


def _install_program_files(extractPath: Path, editorPath: Path) -> None:
    # Recheck after the download, before moving any validated files into place.
    _check_program_destination(editorPath)
    editorPath.mkdir(parents=True, exist_ok=True)
    (editorPath / "data").mkdir(exist_ok=True)
    listMoved: list[Path] = []
    # Publish Code.exe last so an interrupted installation does not look ready.
    listSource = sorted(
        extractPath.iterdir(),
        key=lambda path: (path.name.casefold() == "code.exe", path.name),
    )
    try:
        for pathSource in listSource:
            pathTarget = editorPath / pathSource.name
            pathSource.rename(pathTarget)
            listMoved.append(pathTarget)
    except BaseException:
        # Only move back files placed by this attempt. Never move or delete data.
        for pathTarget in reversed(listMoved):
            try:
                pathTarget.rename(extractPath / pathTarget.name)
            except OSError as e:
                print(f"[Warning] Could not roll back '{pathTarget}': {e}")
        raise


def prepare_editor(rootPath: Path) -> None:
    pathEditor = rootPath / "Editor"
    editorInfo = _inspect_editor(pathEditor)
    if editorInfo is not None:
        (pathEditor / "data").mkdir(exist_ok=True)
        print(
            f"Existing LiberRPA Editor found: VS Code {editorInfo.version}. No download is needed."
        )
        if editorInfo.version != _EDITOR_VERSION:
            print(
                f"[Warning] This LiberRPA release was tested with VS Code {_EDITOR_VERSION}. "
                "The existing Editor will be kept; it will not be upgraded or downgraded automatically."
            )
        return

    _check_program_destination(pathEditor)
    print(
        f"LiberRPA Editor requires Microsoft Visual Studio Code {_EDITOR_VERSION} (Windows x64 ZIP)."
    )
    print(f"Download source: {_EDITOR_DOWNLOAD_URL}")
    print(f"Microsoft license: {_EDITOR_LICENSE_URL}")
    print(f"Microsoft privacy statement: {_EDITOR_PRIVACY_URL}")
    print(
        "The download will be verified before installation. Existing Editor/data will be preserved."
    )
    if (
        input("Download and prepare VS Code under these Microsoft terms? [y/N]: ")
        .strip()
        .lower()
        != "y"
    ):
        raise EditorSetupError("Editor setup was cancelled. Initialization has stopped.")

    # Staging on the same volume makes moving program files fast. User data stays
    # in Editor/data throughout and is never placed inside this temporary folder.
    tempObj = tempfile.TemporaryDirectory(
        prefix=".editor-", dir=rootPath, ignore_cleanup_errors=True
    )
    pathTemp = Path(tempObj.name)
    try:
        with tempObj:
            pathArchive = pathTemp / "vscode.zip"
            pathExtract = pathTemp / "files"
            _download_archive(pathArchive)
            print("Extracting and checking VS Code...", flush=True)
            _extract_archive(pathArchive, pathExtract)
            editorInfo = _inspect_editor(pathExtract)
            if editorInfo is None:
                raise EditorSetupError(
                    "The archive does not contain a complete supported VS Code layout."
                )
            if editorInfo.version != _EDITOR_VERSION:
                raise EditorSetupError(
                    f"The downloaded VS Code version is {editorInfo.version}, expected {_EDITOR_VERSION}."
                )
            if editorInfo.commit != _EDITOR_COMMIT:
                raise EditorSetupError(
                    f"The downloaded VS Code build commit is {editorInfo.commit}, expected {_EDITOR_COMMIT}."
                )
            _verify_microsoft_signature(pathExtract / "Code.exe")
            pathAppExecutable = editorInfo.appPath.parent.parent / "Code.exe"
            if (
                pathAppExecutable != pathExtract / "Code.exe"
                and pathAppExecutable.is_file()
            ):
                _verify_microsoft_signature(pathAppExecutable)
            _install_program_files(pathExtract, pathEditor)
    finally:
        if pathTemp.exists():
            print(
                f"[Warning] Temporary setup files could not be fully removed: '{pathTemp}'."
            )
    print(f"LiberRPA Editor is ready: VS Code {_EDITOR_VERSION}.")
