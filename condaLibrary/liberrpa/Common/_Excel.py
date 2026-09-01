# FileName: _Excel.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from liberrpa.Logging import Log
from liberrpa.Common._TypedValue import StrPath

import xlwings as xw
import xlwings._xlwindows as _xwWindows

import pandas
from pathlib import Path
import pywintypes
import re
from datetime import datetime
from contextlib import contextmanager
from collections.abc import Generator
import threading
import os
from typing import Literal, cast


if not hasattr(_xwWindows, "N_COM_ATTEMPTS") or not hasattr(_xwWindows, "ExcelBusyError"):
    raise RuntimeError(
        "The installed xlwings version is incompatible with LiberRPA's Excel integration."
    )

# xlwings uses 0 for indefinite retries. Raise after the first failed COM attempt instead.
_xwWindows.N_COM_ATTEMPTS = 1


type ExcelFileType = Literal["xlsx", "xls", "xlsm", "xlsb"]
type ExcelSheet = str | int
type ExcelCell = str | list[int]
type ExcelCellValue = str | int | float | datetime | bool | None

_SET_VALID_EXCEL_FILE_TYPES: set[str] = {"xlsx", "xls", "xlsm", "xlsb"}


# Excel FileFormat values used by Workbook.SaveAs. These mirror the formats selected by xlwings for the four workbook types supported by LiberRPA.
_DICT_EXCEL_FILE_FORMATS: dict[ExcelFileType, int] = {
    "xlsx": 51,  # xlOpenXMLWorkbook
    "xls": -4143,  # xlWorkbookNormal
    "xlsm": 52,  # xlOpenXMLWorkbookMacroEnabled
    "xlsb": 50,  # xlExcel12
}

_INT_EXCEL_MODERN_MAX_COLUMN = 16_384
_INT_EXCEL_MODERN_MAX_ROW = 1_048_576
_INT_EXCEL_LEGACY_MAX_COLUMN = 256
_INT_EXCEL_LEGACY_MAX_ROW = 65_536

# Excel Range.Find constants.
_INT_XL_FORMULAS = -4123
_INT_XL_PART = 2
_INT_XL_BY_ROWS = 1
_INT_XL_BY_COLUMNS = 2
_INT_XL_PREVIOUS = 2
_INT_XL_VALUES = -4163

_PATTERN_EXCEL_COLUMN = re.compile(r"\$?([A-Za-z]{1,3})")
_PATTERN_EXCEL_CELL = re.compile(r"\$?([A-Za-z]{1,3})\$?([1-9]\d*)")


_INT_RPC_E_CALL_REJECTED = -2147418111
_INT_RPC_E_SERVERCALL_RETRYLATER = -2147417846
_INT_VBA_E_IGNORE = -2146777998  # 0x800AC472
_INT_EXCEL_E_APPLICATION_DEFINED = -2146827284  # 0x800A03EC
_STR_EXCEL_BUSY_ERROR_MESSAGE = "Excel rejected the operation. Exit cell edit mode, close modal dialogs, or wait for Excel to finish its current task."


_SET_INVALID_SHEET_NAME_CHARS = frozenset("\\/?*:[]")
_SET_RESERVED_SHEET_NAMES = frozenset({"history"})


_excelOwnerThread: threading.Thread | None = None
_excelOwnerThreadLock = threading.Lock()


class ExcelError(Exception):
    """Custom exception for Excel manipulation"""

    def __init__(self, message: str, *args: object) -> None:
        super().__init__(message, *args)


class ExcelBusyError(ExcelError):
    """Excel currently rejects automation operations."""


def _get_com_error_codes(error: pywintypes.com_error) -> set[int]:
    codes: set[int] = set()

    hresult = getattr(error, "hresult", None)
    if type(hresult) is int:
        codes.add(hresult)

    excepinfo = getattr(error, "excepinfo", None)
    if isinstance(excepinfo, tuple) and len(excepinfo) >= 6:
        scode = excepinfo[5]
        if type(scode) is int:
            codes.add(scode)

    return codes


def _is_excel_busy_error(error: pywintypes.com_error) -> bool:
    return bool(
        _get_com_error_codes(error)
        & {
            _INT_RPC_E_CALL_REJECTED,
            _INT_RPC_E_SERVERCALL_RETRYLATER,
            _INT_VBA_E_IGNORE,
        }
    )


class _ExcelAppState:
    """Shared state for all ExcelObj objects in one Excel application instance."""

    def __init__(
        self,
        app: xw.App,
        *,
        ownsApp: bool,
    ) -> None:
        self.app = app

        try:
            self.api = self.app.api

            # Keep the value selected when this shared state is created. It is a configuration invariant, not a cache that should silently adopt a later change made directly in the Excel UI.
            self.configuredVisible = bool(self.api.Visible)

        except _xwWindows.ExcelBusyError as e:
            raise ExcelBusyError(_STR_EXCEL_BUSY_ERROR_MESSAGE) from e
        except pywintypes.com_error as e:
            if _is_excel_busy_error(e):
                raise ExcelBusyError(_STR_EXCEL_BUSY_ERROR_MESSAGE) from e
            raise

        # Track application ownership, thread affinity, nested operations, and the paths of workbooks that already have a managed ExcelObj.
        self.ownsApp = ownsApp
        self.ownerThread = threading.current_thread()
        self.operationDepth = 0
        self.managedWorkbookKeys: set[str] = set()

    @property
    def excelObjCount(self) -> int:
        """Return the number of distinct workbooks managed in this application."""
        return len(self.managedWorkbookKeys)


_sharedAppState: _ExcelAppState | None = None


def _get_shared_app_state() -> _ExcelAppState | None:
    return _sharedAppState


def _register_shared_app_state(appState: _ExcelAppState) -> None:
    global _sharedAppState

    if _sharedAppState is not None and _sharedAppState is not appState:
        raise ExcelError(
            "A different shared Excel application state is already registered."
        )

    _sharedAppState = appState


def _unregister_shared_app_state(appState: _ExcelAppState) -> None:
    global _sharedAppState

    if _sharedAppState is appState:
        _sharedAppState = None


def _claim_excel_thread() -> None:
    """Restrict every Excel automation call in this Python process to one thread."""

    global _excelOwnerThread

    currentThread = threading.current_thread()

    # Checking threading.active_count() would reject harmless background threads created by logging, networking, or GUI libraries. Instead, only a thread that actually starts an Excel operation claims Excel ownership.
    with _excelOwnerThreadLock:
        if _excelOwnerThread is None:
            _excelOwnerThread = currentThread
        elif _excelOwnerThread is not currentThread:
            raise ExcelError(
                "Excel automation is restricted to one Python thread. "
                f"The owner thread is {_excelOwnerThread.name!r}, "
                f"but the current thread is {currentThread.name!r}."
            )


def _check_shared_app_visibility(appState: _ExcelAppState, visible: bool) -> None:
    if appState.configuredVisible != visible:
        raise ExcelError(
            f"Excel visibility is application-level. The shared Excel instance uses visible={appState.configuredVisible}, but visible={visible} was requested. "
            "All workbooks opened by LiberRPA in the same process must use the "
            "same visible value."
        )


def _get_or_create_shared_app_state(visible: bool) -> tuple[_ExcelAppState, bool]:
    """
    Return the process-wide shared Excel application state.

    The bool return value indicates that a new state was selected, not that LiberRPA necessarily created the underlying Excel process. A new state is registered only after the first workbook has been initialized successfully.
    """

    _claim_excel_thread()

    appState = _get_shared_app_state()
    if appState is not None:
        _check_shared_app_visibility(appState=appState, visible=visible)
        return appState, False

    # xlwings Apps.active returns the first enumerated instance on Windows; it does not reliably identify the foreground Excel window. Reuse an existing instance only when there is exactly one unambiguous choice.
    try:
        listApps = list(xw.apps)
    except _xwWindows.ExcelBusyError as e:
        raise ExcelBusyError(_STR_EXCEL_BUSY_ERROR_MESSAGE) from e
    except pywintypes.com_error as e:
        if _is_excel_busy_error(e):
            raise ExcelBusyError(_STR_EXCEL_BUSY_ERROR_MESSAGE) from e
        raise

    if len(listApps) > 1:
        raise ExcelError(
            "Multiple Excel application instances are running, "
            "so LiberRPA cannot safely choose one for open_excel_file(). "
            "Bind a workbook in the intended instance with bind_excel_file() first."
        )

    boolCreatedApp = not listApps
    if boolCreatedApp:
        xwApp = xw.App(visible=visible, add_book=False)
    else:
        xwApp = listApps[0]

    try:
        appState = _ExcelAppState(app=xwApp, ownsApp=boolCreatedApp)
        _check_shared_app_visibility(appState=appState, visible=visible)
    except Exception:
        if boolCreatedApp:
            # Initialization failed before any ExcelObj was returned. Because this Excel process was just created by LiberRPA, force-terminate it if normal shutdown fails.
            try:
                xwApp.quit()
            except Exception:
                try:
                    xwApp.kill()
                except Exception:
                    pass
        raise

    # Not register here because if opening the first workbook fails, registering at this point would leave a zero-object state that permanently selects this Excel instance despite the documented "first successful open/bind" rule.
    return appState, True


class ExcelObj:
    def __init__(self, appState: _ExcelAppState) -> None:
        self.path: str = ""
        self.readOnly: bool = False
        self.password: str | None = None
        self.writePassword: str | None = None
        self.type: ExcelFileType

        # These properties are managed inside.
        self._book: xw.Book
        self._appState: _ExcelAppState = appState
        self._boolClosed: bool = False
        self._managedWorkbookKey: str | None = None

    def _ensure_open(self) -> None:
        # Intentionally check only LiberRPA's lifecycle flag here. Probing a live COM property on every call would add overhead and could not reliably distinguish an externally closed workbook from a temporarily busy Excel.
        if self._boolClosed:
            raise ExcelError(
                f"The Excel object for {self.path!r} has already been closed."
            )

    def __str__(self) -> str:
        self._ensure_open()

        def _format_password(value: str | None) -> str:
            if value is None:
                return "unknown"

            return "*****" if value else ""

        return (
            f"ExcelObj(path: {self.path}, "
            f"readOnly: {self.readOnly}, "
            f"password: {_format_password(self.password)}, "
            f"writePassword: {_format_password(self.writePassword)}, "
            f"type: {self.type}, "
            f"visible: {self._appState.configuredVisible})"
        )


def _get_workbook_key(path: StrPath) -> str:
    """Return a normalized Windows path used to identify a managed workbook."""

    # resolve(strict=False) also normalizes relative paths and existing symlinks;
    # normcase makes path comparison case-insensitive on Windows.
    return os.path.normcase(str(Path(path).resolve(strict=False)))


def _ensure_workbook_not_open(appState: _ExcelAppState, workbookPath: StrPath) -> None:
    """Reject a workbook that is already open but not managed by LiberRPA."""

    workbookKey = _get_workbook_key(workbookPath)
    strFileName = Path(workbookPath).name.casefold()

    for book in appState.app.books:
        # Comparing the name first avoids an unnecessary FullName COM call for
        # every unrelated workbook in the selected Excel instance.
        if str(book.name).casefold() != strFileName:
            continue

        if _get_workbook_key(book.fullname) == workbookKey:
            raise ExcelError(
                f"The workbook {str(workbookPath)!r} is already open in the selected Excel application instance. "
                "Use bind_excel_file() instead of opening it again."
            )


def _ensure_workbook_key_available(
    appState: _ExcelAppState,
    workbookKey: str,
    *,
    currentKey: str | None = None,
) -> None:
    # Ensure a workbook can only be bound with one ExcelObj.
    if workbookKey in appState.managedWorkbookKeys and workbookKey != currentKey:
        raise ExcelError(
            "This workbook is already managed by another ExcelObj. "
            "Reuse the existing ExcelObj instead of opening or binding it again."
        )


def _update_managed_workbook_key(excelObj: ExcelObj, workbookKey: str) -> None:
    previousKey = excelObj._managedWorkbookKey
    if previousKey is None:
        raise ExcelError("The ExcelObj is not registered as a managed workbook.")

    _ensure_workbook_key_available(
        appState=excelObj._appState,
        workbookKey=workbookKey,
        currentKey=previousKey,
    )

    excelObj._appState.managedWorkbookKeys.remove(previousKey)
    excelObj._appState.managedWorkbookKeys.add(workbookKey)
    excelObj._managedWorkbookKey = workbookKey


def _register_managed_excel_obj(excelObj: ExcelObj, workbookKey: str) -> None:
    _ensure_workbook_key_available(
        appState=excelObj._appState,
        workbookKey=workbookKey,
    )
    excelObj._appState.managedWorkbookKeys.add(workbookKey)
    excelObj._managedWorkbookKey = workbookKey


def _unregister_managed_excel_obj(excelObj: ExcelObj) -> None:
    workbookKey = excelObj._managedWorkbookKey
    if workbookKey is None:
        return

    excelObj._appState.managedWorkbookKeys.discard(workbookKey)
    excelObj._managedWorkbookKey = None


@contextmanager
def _temporary_display_alerts(excelObj: ExcelObj, value: bool) -> Generator[None]:
    """Temporarily set DisplayAlerts without masking the operation result."""

    appState = excelObj._appState
    boolDisplayAlerts = bool(appState.api.DisplayAlerts)
    boolOperationFailed = True

    try:
        appState.api.DisplayAlerts = value
        yield
        boolOperationFailed = False

    finally:
        try:
            appState.api.DisplayAlerts = boolDisplayAlerts
        except Exception as restoreError:
            if boolOperationFailed:
                # Keep propagating the original Excel operation exception.
                Log.error(
                    f"Failed to restore Excel.DisplayAlerts after an operation error: {restoreError}"
                )
            else:
                # The irreversible Excel operation has already completed.
                # A UI-state cleanup error must not encourage the caller to retry a completed save or deletion.
                Log.warning(
                    "The Excel operation completed successfully, "
                    f"but DisplayAlerts could not be restored: {restoreError}"
                )


def _save(excelObj: ExcelObj) -> None:
    # Do not call xlwings Book.save() here. It adds another DisplayAlerts context whose restoration error could make a completed save look failed.
    bookApi = excelObj._book.api

    if excelObj.readOnly:
        if bool(bookApi.Saved):
            return

        raise ExcelError(
            "The workbook is read-only and cannot overwrite its original file. "
            "Use save_as() to save the changes to a new file, or close(save=False) to discard them."
        )

    with _temporary_display_alerts(excelObj=excelObj, value=False):
        bookApi.Save()

        if not bool(bookApi.Saved):
            raise ExcelError(
                "Excel returned from Save(), but the workbook still contains unsaved changes. "
                "A save event may have canceled the save or modified the workbook afterward."
            )


def _save_as(
    excelObj: ExcelObj,
    path: StrPath,
    fileType: ExcelFileType,
    password: str,
) -> None:
    """Save directly through the Excel COM API exposed by xlwings so LiberRPA alone controls DisplayAlerts restoration."""

    strPath = str(Path(path).absolute())
    bookApi = excelObj._book.api

    if excelObj.type == "xlsm" and fileType == "xlsx":
        Log.warning(
            "Saving an .xlsm workbook as .xlsx may remove VBA macros because Excel compatibility prompts are suppressed."
        )
    elif fileType == "xls" and excelObj.type != "xls":
        Log.warning(
            "Saving a modern workbook as .xls may remove unsupported features and is limited to 65,536 rows and 256 columns."
        )
    elif excelObj.type != fileType:
        Log.warning(
            f"Saving the workbook from {excelObj.type!r} to {fileType!r}. "
            "Unsupported content may be removed or changed."
        )

    # Match xlwings behavior for an existing workbook saved with the same extension: preserve its actual format (for example, Strict Open XML).
    # A new unsaved workbook must use the target extension's explicit format.
    if bool(bookApi.Path) and excelObj.type == fileType:
        intFileFormat = int(bookApi.FileFormat)
    else:
        intFileFormat = _DICT_EXCEL_FILE_FORMATS[fileType]

    try:
        strOldRawFullName: str | None = str(bookApi.FullName)
    except Exception as metadataError:
        strOldRawFullName = None
        Log.warning(
            f"The workbook's identity could not be read before SaveAs: {metadataError}"
        )

    with _temporary_display_alerts(excelObj=excelObj, value=False):
        bookApi.SaveAs(
            strPath,
            FileFormat=intFileFormat,
            Password=password or None,
        )

        # The target did not exist before this operation. If it still does not exist, SaveAs was not completed.
        if not Path(strPath).is_file():
            raise ExcelError(
                f"Excel returned from SaveAs, but the requested target file was not created: {strPath!r}."
            )

        try:
            strNewRawFullName: str | None = str(bookApi.FullName)
        except Exception as metadataError:
            strNewRawFullName = None
            Log.warning(
                f"SaveAs created the requested file, but the workbook's COM identity could not be verified: {metadataError}"
            )

        if (
            strOldRawFullName is not None
            and strNewRawFullName is not None
            and strNewRawFullName.casefold() == strOldRawFullName.casefold()
        ):
            raise ExcelError(
                "Excel returned from SaveAs, but the workbook identity did not change. "
                "A BeforeSave event may have canceled the operation."
            )

        # A BeforeSave event can cancel SaveAs without necessarily raising a COM exception.
        # Verify the resulting workbook identity when Excel still allows the property to be read. If this best-effort read alone fails after SaveAs returned, continue so the registry does not remain at the old path solely because of a metadata read failure.
        try:
            # Use xlwings's FullName normalization here: Excel may expose a OneDrive or SharePoint URL even when the caller supplied a local synchronized path.
            strActualPath = str(excelObj._book.fullname)
        except Exception as metadataError:
            Log.warning(
                f"SaveAs returned successfully, but the workbook's actual path could not be verified: {metadataError}"
            )
        else:
            if "://" in strActualPath:
                Log.warning(
                    "SaveAs returned successfully, but Excel reported a URL, "
                    "so the local target path could not be compared directly: "
                    f"{strActualPath!r}"
                )
            elif _get_workbook_key(strActualPath) != _get_workbook_key(strPath):
                raise ExcelError(
                    "Excel did not complete SaveAs to the requested path. "
                    f"Requested: {strPath!r}; actual workbook: {strActualPath!r}."
                )


def _quit_excel_app_best_effort(
    appState: _ExcelAppState,
    *,
    killOnFailure: bool,
    failureContext: str,
) -> None:
    """Quit Excel without leaving DisplayAlerts changed after a failed quit."""

    boolDisplayAlerts: bool | None
    try:
        boolDisplayAlerts = bool(appState.api.DisplayAlerts)
    except Exception as stateError:
        boolDisplayAlerts = None
        Log.warning(f"Could not read Excel.DisplayAlerts before quitting: {stateError}")

    try:
        appState.app.quit()
        return
    except Exception as quitError:
        # xlwings sets DisplayAlerts=False immediately before calling Quit().
        # If Quit fails, restore the previous value so a surviving process does not affect a later LiberRPA run.
        if boolDisplayAlerts is not None:
            try:
                appState.api.DisplayAlerts = boolDisplayAlerts
            except Exception as restoreError:
                Log.error(
                    f"Failed to restore Excel.DisplayAlerts after quit failed: {restoreError}"
                )

        Log.error(f"{failureContext}: {quitError}")

    if killOnFailure:
        try:
            appState.app.kill()
        except Exception as killError:
            Log.error(f"Failed to terminate the Excel process: {killError}")


@contextmanager
def _excel_operation(excelObj: ExcelObj) -> Generator[None]:
    """
    Protect one complete Excel automation operation.

    Nested operations in the same Excel application instance reuse the outer protection.
    Only the outermost operation changes Excel.Interactive.
    """

    _claim_excel_thread()
    excelObj._ensure_open()

    appState = excelObj._appState

    if threading.current_thread() is not appState.ownerThread:
        raise ExcelError(
            "ExcelObj must be used on the same COM thread on which it was opened or bound."
        )

    boolOutermostOperation = appState.operationDepth == 0
    appState.operationDepth += 1

    boolInteractiveChanged = False
    boolOperationFailed = True

    try:
        if boolOutermostOperation:
            # Interactive is not an edit-mode flag. Setting it to False both probes whether Excel accepts automation and prevents manual input from interfering with the operation.
            try:
                if not bool(appState.api.Interactive):
                    raise ExcelBusyError(
                        "Excel is already non-interactive. "
                        "Another automation operation may currently own the Excel instance."
                    )

                # Prevent manual input from interfering with Excel automation.
                appState.api.Interactive = False

            except ExcelBusyError:
                raise
            except _xwWindows.ExcelBusyError as e:
                raise ExcelBusyError(_STR_EXCEL_BUSY_ERROR_MESSAGE) from e
            except pywintypes.com_error as e:
                # Excel commonly returns 0x800A03EC specifically when the Interactive property cannot be changed during cell editing.
                if _is_excel_busy_error(
                    e
                ) or _INT_EXCEL_E_APPLICATION_DEFINED in _get_com_error_codes(e):
                    raise ExcelBusyError(_STR_EXCEL_BUSY_ERROR_MESSAGE) from e
                raise

            boolInteractiveChanged = True

            # Supplemental readiness check only; Ready is not an edit-mode flag.
            if not bool(appState.api.Ready):
                raise ExcelBusyError("Excel is not ready to accept the RPA operation.")

        yield
        boolOperationFailed = False

    except _xwWindows.ExcelBusyError as e:
        # Let the raw exception propagate through nested contexts.
        # The outermost context converts it only once.
        if not boolOutermostOperation:
            raise
        raise ExcelBusyError(_STR_EXCEL_BUSY_ERROR_MESSAGE) from e
    except pywintypes.com_error as e:
        if not boolOutermostOperation:
            raise
        if _is_excel_busy_error(e):
            raise ExcelBusyError(_STR_EXCEL_BUSY_ERROR_MESSAGE) from e
        raise

    finally:
        appState.operationDepth -= 1

        if boolOutermostOperation and boolInteractiveChanged:
            try:
                appState.api.Interactive = True

            except Exception as restoreError:
                if boolOperationFailed:
                    Log.error(
                        f"Failed to restore Excel.Interactive after an operation error: {restoreError}"
                    )
                else:
                    raise ExcelError(
                        "The Excel operation completed, but keyboard and mouse input could not be restored."
                    ) from restoreError


def _check_excel_file_type(path: StrPath) -> ExcelFileType:
    fileType = Path(path).suffix.replace(".", "").lower()

    if fileType not in _SET_VALID_EXCEL_FILE_TYPES:
        raise ExcelError(
            f"Unsupported Excel file type: {fileType!r}. Supported types: {sorted(_SET_VALID_EXCEL_FILE_TYPES)}"
        )

    return cast(ExcelFileType, fileType)


def _check_and_standardize_sheet(excelObj: ExcelObj, sheet: ExcelSheet) -> str:
    if isinstance(sheet, bool) or not isinstance(sheet, int | str):
        raise ExcelError("The argument sheet should be an int or a string.")

    listSheetName: list[str] = [sheet.name for sheet in excelObj._book.sheets]

    if isinstance(sheet, str):
        strSheetCasefold = sheet.casefold()
        for existingName in listSheetName:
            if existingName.casefold() == strSheetCasefold:
                return existingName
        raise ExcelError(
            f"The sheet ({sheet}) does not exist. The current sheets: {listSheetName}"
        )

    if sheet < 0:
        raise ExcelError(f"The sheet index ({sheet}) must be greater than or equal to 0.")

    if sheet >= len(listSheetName):
        raise ExcelError(
            f"The sheet index ({sheet}) is greater than the largest sheet index ({len(listSheetName) - 1})."
        )

    strSheet = excelObj._book.sheets[sheet].name
    Log.verbose("sheet standardized=" + strSheet)
    return strSheet


def _check_sheet_name_compliance(sheetName: str) -> None:
    if not isinstance(sheetName, str):
        raise TypeError("Sheet name must be a string.")

    if not sheetName:
        raise ValueError("Sheet name must not be empty.")

    if len(sheetName) > 31:
        raise ValueError(
            f"Sheet name must not be longer than 31 characters. Current length: {len(sheetName)}."
        )

    setInvalidChars = set(sheetName) & _SET_INVALID_SHEET_NAME_CHARS
    if setInvalidChars:
        raise ValueError(
            "Sheet name contains invalid characters: "
            f"{sorted(setInvalidChars)}. "
            f"Forbidden characters: {sorted(_SET_INVALID_SHEET_NAME_CHARS)}."
        )

    if sheetName.startswith("'") or sheetName.endswith("'"):
        raise ValueError("Sheet name must not begin or end with an apostrophe.")

    if sheetName.casefold() in _SET_RESERVED_SHEET_NAMES:
        raise ValueError(f"The sheet name {sheetName!r} is reserved by Excel.")


def _check_sheet_name_available(
    excelObj: ExcelObj,
    sheetName: str,
    *,
    currentSheetName: str | None = None,
) -> None:
    listCurrentSheetName = [sheet.name for sheet in excelObj._book.sheets]

    for existingName in listCurrentSheetName:
        if currentSheetName is not None and existingName == currentSheetName:
            continue

        if existingName.casefold() == sheetName.casefold():
            raise ValueError(
                f"The sheet name {sheetName!r} is already in use. Current sheets: {listCurrentSheetName}"
            )


def _get_excel_grid_limits(excelObj: ExcelObj | None = None) -> tuple[int, int]:
    """Return maximum column and row counts for the workbook file format."""

    if excelObj is not None and excelObj.type == "xls":
        return _INT_EXCEL_LEGACY_MAX_COLUMN, _INT_EXCEL_LEGACY_MAX_ROW

    return _INT_EXCEL_MODERN_MAX_COLUMN, _INT_EXCEL_MODERN_MAX_ROW


def _validate_excel_column_number(
    column: object,
    *,
    excelObj: ExcelObj | None = None,
) -> int:
    if type(column) is not int:
        raise ValueError("Excel column number must be an integer.")

    intMaxColumn, _ = _get_excel_grid_limits(excelObj=excelObj)
    if not 1 <= column <= intMaxColumn:
        raise ValueError(
            f"Excel column number must be between 1 and {intMaxColumn}. Current value: {column}."
        )

    return column


def _validate_excel_row_number(
    row: object,
    *,
    excelObj: ExcelObj | None = None,
) -> int:
    if type(row) is not int:
        raise ValueError("Excel row number must be an integer.")

    _, intMaxRow = _get_excel_grid_limits(excelObj=excelObj)
    if not 1 <= row <= intMaxRow:
        raise ValueError(
            f"Excel row number must be between 1 and {intMaxRow}. Current value: {row}."
        )

    return row


def _convert_col_num_to_str(
    colNum: int,
    *,
    excelObj: ExcelObj | None = None,
) -> str:
    colNum = _validate_excel_column_number(colNum, excelObj=excelObj)
    strCol: str = xw.utils.col_name(colNum)
    return strCol


def _convert_col_str_to_num(
    colStr: str,
    *,
    excelObj: ExcelObj | None = None,
) -> int:
    if not isinstance(colStr, str) or re.fullmatch(r"[A-Za-z]{1,3}", colStr) is None:
        raise ValueError(f"Invalid Excel column string: {colStr!r}.")

    intCol = 0
    for char in colStr.upper():
        intCol = intCol * 26 + (ord(char) - ord("A")) + 1
    return _validate_excel_column_number(intCol, excelObj=excelObj)


def _check_and_standardize_cell(
    cell: ExcelCell,
    *,
    excelObj: ExcelObj | None = None,
) -> str:
    if isinstance(cell, str):
        match = _PATTERN_EXCEL_CELL.fullmatch(cell)
        if match is None:
            raise ValueError(f"Invalid Excel cell address: {cell!r}.")

        strColumn = match.group(1).upper()
        intColumn = _convert_col_str_to_num(colStr=strColumn, excelObj=excelObj)
        intRow = int(match.group(2))

        _validate_excel_column_number(intColumn, excelObj=excelObj)
        _validate_excel_row_number(intRow, excelObj=excelObj)

        strCell = f"{strColumn}{intRow}"

    elif isinstance(cell, list):
        if len(cell) != 2:
            raise ValueError("A list cell address must contain [column, row].")

        intColumn = _validate_excel_column_number(cell[0], excelObj=excelObj)
        intRow = _validate_excel_row_number(cell[1], excelObj=excelObj)
        strCell = f"{xw.utils.col_name(intColumn)}{intRow}"

    else:
        raise ValueError("The argument 'cell' must be a string or list[int].")

    Log.verbose(f"cell standardized={strCell}")
    return strCell


def _extract_row_column_from_cell(
    cell: str,
    *,
    excelObj: ExcelObj | None = None,
) -> tuple[str, int, int]:
    cell = _check_and_standardize_cell(cell=cell, excelObj=excelObj)

    match = re.fullmatch(r"([A-Z]{1,3})([1-9]\d*)", cell)
    if match is None:
        raise ExcelError(f"Invalid Excel cell address: {cell!r}.")

    strCol = match.group(1)
    intRow = int(match.group(2))
    intCol = _convert_col_str_to_num(colStr=strCol, excelObj=excelObj)

    return (strCol, intCol, intRow)


def _check_and_standardize_column(
    column: str | int,
    *,
    excelObj: ExcelObj | None = None,
) -> str:
    if isinstance(column, bool):
        raise ValueError("The argument 'column' must not be a bool.")

    if type(column) is int:
        intColumn = _validate_excel_column_number(column, excelObj=excelObj)
        strColumn = xw.utils.col_name(intColumn)

    elif isinstance(column, str):
        match = _PATTERN_EXCEL_COLUMN.fullmatch(column)
        if match is None:
            raise ValueError(f"Invalid Excel column: {column!r}.")

        strColumn = match.group(1).upper()
        _convert_col_str_to_num(colStr=strColumn, excelObj=excelObj)

    else:
        raise ValueError("The argument 'column' must be an int or string.")

    Log.verbose(f"column standardized={strColumn}")
    return strColumn


def _find_last_value_or_formula_cell(
    sheetObj: xw.Sheet,
    *,
    searchBy: Literal["rows", "columns"],
) -> tuple[int, int] | None:
    """
    Return the last cell containing a formula or a non-empty displayed value.

    Searches both xlFormulas and xlValues so formula cells and non-empty dynamic-array spill results contribute to the content boundary.
    """

    sheetApi = sheetObj.api
    intSearchOrder = _INT_XL_BY_ROWS if searchBy == "rows" else _INT_XL_BY_COLUMNS

    listFoundCell: list[tuple[int, int]] = []

    for intLookIn in (_INT_XL_FORMULAS, _INT_XL_VALUES):
        foundCellApi = sheetApi.Cells.Find(
            What="*",
            After=sheetApi.Cells(1, 1),
            LookIn=intLookIn,
            LookAt=_INT_XL_PART,
            SearchOrder=intSearchOrder,
            SearchDirection=_INT_XL_PREVIOUS,
            MatchCase=False,
            MatchByte=False,
            SearchFormat=False,
        )

        if foundCellApi is not None:
            listFoundCell.append((
                int(foundCellApi.Row),
                int(foundCellApi.Column),
            ))

    if not listFoundCell:
        return None

    if searchBy == "rows":
        return max(listFoundCell, key=lambda cell: (cell[0], cell[1]))

    return max(listFoundCell, key=lambda cell: (cell[1], cell[0]))


def _get_last_row(
    excelObj: ExcelObj, sheet: ExcelSheet, col: str | int | None = None
) -> int:
    with _excel_operation(excelObj=excelObj):
        sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)

        sheetObj = excelObj._book.sheets[sheet]

        if col is None:
            lastCell = _find_last_value_or_formula_cell(
                sheetObj=sheetObj,
                searchBy="rows",
            )

            # Preserve the existing empty-sheet behavior.
            return lastCell[0] if lastCell is not None else 1
        else:
            col = _check_and_standardize_column(column=col, excelObj=excelObj)
            _, intMaxRow = _get_excel_grid_limits(excelObj=excelObj)
            return sheetObj.range(f"{col}{intMaxRow}").end("up").row


def _get_last_column(
    excelObj: ExcelObj, sheet: ExcelSheet, row: int | None = None
) -> tuple[str, int]:
    if row is not None:
        row = _validate_excel_row_number(row, excelObj=excelObj)

    with _excel_operation(excelObj=excelObj):
        sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)

        sheetObj = excelObj._book.sheets[sheet]

        if row is None:
            lastCell = _find_last_value_or_formula_cell(
                sheetObj=sheetObj,
                searchBy="columns",
            )
            intCol = lastCell[1] if lastCell is not None else 1
        else:
            intMaxColumn, _ = _get_excel_grid_limits(excelObj=excelObj)
            strLastColumn = _convert_col_num_to_str(
                colNum=intMaxColumn, excelObj=excelObj
            )
            intCol = sheetObj.range(f"{strLastColumn}{row}").end("left").column

        strCol = _convert_col_num_to_str(colNum=intCol, excelObj=excelObj)

        return strCol, intCol


def _get_endCell_if_not_provided(
    excelObj: ExcelObj, sheet: ExcelSheet, endCell: ExcelCell | None
) -> str:
    # Determine the end cell if not provided
    if endCell is not None:
        endCell = _check_and_standardize_cell(cell=endCell, excelObj=excelObj)
    else:
        # Default to the last cell containing a value or formula in the sheet if endCell is not specified
        endCell = _get_last_column(excelObj=excelObj, sheet=sheet, row=None)[0] + str(
            _get_last_row(excelObj=excelObj, sheet=sheet, col=None)
        )
        Log.verbose(f"The argument endCell is None, get the last cell({endCell}).")

    return endCell


def _validate_range_order(
    excelObj: ExcelObj,
    startCell: str,
    endCell: str,
) -> None:
    _, startCol, startRow = _extract_row_column_from_cell(
        cell=startCell,
        excelObj=excelObj,
    )
    _, endCol, endRow = _extract_row_column_from_cell(
        cell=endCell,
        excelObj=excelObj,
    )

    if startCol > endCol or startRow > endRow:
        raise ValueError(
            f"startCell {startCell!r} must not be below or to the right of endCell {endCell!r}."
        )


def _read_range(
    excelObj: ExcelObj,
    sheet: ExcelSheet,
    startCell: ExcelCell,
    endCell: ExcelCell | None = None,
    *,
    returnDisplayed: bool = True,
) -> list[list[str]] | list[list[ExcelCellValue]]:
    sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)
    startCell = _check_and_standardize_cell(cell=startCell, excelObj=excelObj)
    endCell = _get_endCell_if_not_provided(
        excelObj=excelObj, sheet=sheet, endCell=endCell
    )

    _validate_range_order(excelObj=excelObj, startCell=startCell, endCell=endCell)

    strRange = f"{startCell}:{endCell}"
    Log.debug(f"Reading range: {strRange}")
    range: xw.Range = excelObj._book.sheets[sheet].range(strRange)

    if returnDisplayed:
        # list[list[str]]
        return [[cell.api.Text for cell in row] for row in range.rows]
    else:
        """If it takes a long time, consider to split the situations of a cell, a row, a column or a range:
        if startCell == endCell:
            # A cell
            return [[range.value]]
        elif intRowStart == intEndRow:
            # A row
            return [range.value]
        elif strColStart == strColEnd:
            # A column
            return [[ele] for ele in range.value]
        else:
            # A 2D range
            return range.value
        """
        # list[list[ExcelCellValue]]
        return [[cell.value for cell in row] for row in range.rows]


@contextmanager
def _preserve_screen_updating(excelObj: ExcelObj) -> Generator[None]:
    """
    Temporarily disable ScreenUpdating without masking an operation error.
    """

    appState = excelObj._appState
    boolScreenUpdating = bool(appState.api.ScreenUpdating)
    boolOperationFailed = True

    try:
        appState.api.ScreenUpdating = False
        yield
        boolOperationFailed = False

    finally:
        try:
            appState.api.ScreenUpdating = boolScreenUpdating

        except Exception as restoreError:
            if boolOperationFailed:
                # Keep propagating the original write exception.
                Log.error(
                    f"Failed to restore Excel.ScreenUpdating after an operation error: {restoreError}"
                )
            else:
                # The write has already succeeded. Do not make the caller
                # retry a completed write because of a UI-state cleanup error.
                Log.warning(
                    "The Excel operation completed successfully, but "
                    f"ScreenUpdating could not be restored: {restoreError}"
                )


def _validate_write_range_data(
    data: pandas.DataFrame | list[list[ExcelCellValue]],
    *,
    writeTitleRow: bool,
) -> None:
    if isinstance(data, pandas.DataFrame):
        if len(data.columns) == 0:
            raise ValueError("The DataFrame must contain at least one column.")

        # An empty DataFrame can still write its column titles.
        if len(data.index) == 0 and not writeTitleRow:
            raise ValueError("The DataFrame contains no data rows to write.")

        return

    if not data:
        raise ValueError("The argument 'data' must not be empty.")

    intColumnCount = len(data[0])
    if intColumnCount == 0:
        raise ValueError("Each row in 'data' must contain at least one value.")

    if any(len(row) != intColumnCount for row in data):
        raise ValueError("All rows in 'data' must contain the same number of values.")

    if not writeTitleRow and len(data) == 1:
        raise ValueError("'data' contains only a title row and no data rows to write.")


def _log_excel_info(excelObj: ExcelObj) -> None:
    # Python evaluates an f-string before Log.verbose decides whether the level is enabled. Keep this message limited to cached values so logging alone never performs extra COM calls or creates another Excel failure point.
    Log.verbose(f"Workbook info: {excelObj}, ownsApp: {excelObj._appState.ownsApp}")
