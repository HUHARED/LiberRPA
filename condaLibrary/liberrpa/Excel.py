# FileName: Excel.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.Common._TypedValue import StrPath
from liberrpa.Common._Excel import (
    _ExcelAppState,
    ExcelObj,
    #
    ExcelSheet,
    ExcelCell,
    ExcelCellValue,
    #
    ExcelError,
    ExcelBusyError,
    _STR_EXCEL_BUSY_ERROR_MESSAGE,
    _is_excel_busy_error,
    #
    _claim_excel_thread,
    _get_or_create_shared_app_state,
    #
    _excel_operation,
    #
    _get_shared_app_state,
    _register_shared_app_state,
    _unregister_shared_app_state,
    #
    _get_workbook_key,
    _ensure_workbook_not_open,
    _ensure_workbook_key_available,
    _update_managed_workbook_key,
    #
    _register_managed_excel_obj,
    _unregister_managed_excel_obj,
    #
    _temporary_display_alerts,
    _save,
    _save_as,
    #
    _quit_excel_app_best_effort,
    #
    _check_excel_file_type,
    _check_and_standardize_sheet,
    _check_sheet_name_compliance,
    _check_sheet_name_available,
    #
    _validate_excel_column_number,
    _validate_excel_row_number,
    #
    _convert_col_num_to_str,
    _convert_col_str_to_num,
    #
    _check_and_standardize_cell,
    _extract_row_column_from_cell,
    #
    _get_last_row,
    _get_last_column,
    _get_endCell_if_not_provided,
    #
    _validate_range_order,
    _read_range,
    #
    _preserve_screen_updating,
    _validate_write_range_data,
    #
    _log_excel_info,
)

import xlwings as xw
import xlwings._xlwindows as _xwWindows

import pandas
from pathlib import Path
import win32gui
import win32con
import pywintypes
from typing import Literal, Any, overload


@Log.trace()
def open_excel_file(
    path: StrPath,
    visible: bool = True,
    password: str = "",
    writePassword: str = "",
    createIfMissing: bool = True,
    readOnly: bool = False,
    updateLinks: bool = False,
) -> ExcelObj:
    """
    Open an Excel workbook, or create it if it does not exist.

    If the workbook is already open in the selected Excel instance, use bind_excel_file() instead.

    Supported workbook file types are .xlsx, .xls, .xlsm, and .xlsb.
    CSV files should be handled by CSV-specific functions instead of Excel workbook functions.

    LiberRPA restricts Excel automation to one Python thread and reuses one shared Excel application instance for all managed workbooks. If exactly one Excel instance is running, it is reused. If multiple instances are running and no shared instance has been selected yet, call bind_excel_file() first to select the intended instance. Because visible is an application-level setting, every workbook opened through this module must use the same visible value.

    Do not manually close the workbook or save it under another path while its ExcelObj is managed by LiberRPA. Use close() and save_as() so the shared application state and managed workbook registry remain synchronized.

    Parameters:
        path: The path to the Excel workbook. Accepts str or PathLike[str].
        visible: The visibility of the shared Excel application instance. It must match the value used by earlier workbook objects.
        password: The password for opening the workbook, if required. password is also used as a new workbook's opening password.
        writePassword: The password for write access, if required. writePassword applies only when opening an existing write-reserved workbook.
        createIfMissing: If True, creates a new workbook if the file does not exist.
        readOnly: If True, opens the workbook in read-only mode. For a newly created workbook, readOnly must be False.
        updateLinks: If True, updates links to external workbooks while opening the file. If False, keeps the workbook's cached link values and avoids Excel's update-links prompt.

    Returns:
        ExcelObj: An object representing the opened workbook.
    """

    strPath = str(Path(path).absolute())
    pathExcel = Path(strPath)
    boolFileExists = pathExcel.is_file()

    # Validate everything that does not require Excel/COM before selecting or creating an Excel application. Invalid arguments must not start Excel, select a user instance, or claim the process-wide Excel thread.
    excelFileType = _check_excel_file_type(strPath)

    if not boolFileExists and not createIfMissing:
        raise FileNotFoundError(f"No such file: {strPath!r}")

    if not boolFileExists and readOnly:
        raise ExcelError("readOnly=True cannot be used when creating a new workbook.")

    if not boolFileExists and writePassword:
        raise ExcelError(
            "writePassword is only used when opening an existing write-reserved workbook."
        )

    workbookKey = _get_workbook_key(strPath)
    appState, boolNewState = _get_or_create_shared_app_state(visible=visible)
    _ensure_workbook_key_available(appState=appState, workbookKey=workbookKey)

    excelObj = ExcelObj(appState=appState)
    excelObj.path = strPath
    excelObj.readOnly = readOnly
    excelObj.password = password
    excelObj.writePassword = writePassword
    excelObj.type = excelFileType

    boolBookOpened = False
    boolWorkbookRegistered = False

    try:
        with _excel_operation(excelObj=excelObj):
            # configuredVisible is the value selected when the shared state was created. Do not overwrite it with a live value: doing so would silently turn an external UI change into LiberRPA's new contract.
            boolActualVisible = bool(appState.api.Visible)
            if boolActualVisible != appState.configuredVisible:
                raise ExcelError(
                    "Excel.Visible was changed outside LiberRPA. "
                    f"Expected {appState.configuredVisible}, but found {boolActualVisible}."
                )

            if boolFileExists:
                # Workbooks.Open may prompt, return an existing workbook, or open a read-only connection when the same file is already open.
                # Require an explicit bind instead, so cleanup can never close a workbook that the user opened manually.
                _ensure_workbook_not_open(
                    appState=appState,
                    workbookPath=excelObj.path,
                )

                excelObj._book = appState.app.books.open(
                    fullname=excelObj.path,
                    # None can display an update-links prompt. An explicit bool keeps unattended RPA deterministic; False retains cached values.
                    update_links=updateLinks,
                    read_only=excelObj.readOnly,
                    password=excelObj.password,
                    write_res_password=excelObj.writePassword,
                    # This only suppresses Excel's "read-only recommended" prompt; read_only above still determines the requested open mode.
                    ignore_read_only_recommended=True,
                    add_to_mru=False,
                    local=True,
                )
                # Mark the workbook immediately after open succeeds. ReadOnly or any later COM property can still fail and must trigger cleanup.
                boolBookOpened = True

                # Store the actual state, which may differ from the requested value.
                excelObj.readOnly = bool(excelObj._book.api.ReadOnly)

            else:
                excelObj._book = appState.app.books.add()
                # books.add() has already created a live workbook. If its first save fails, the exception path must still close that workbook.
                boolBookOpened = True

                _save_as(
                    excelObj=excelObj,
                    path=excelObj.path,
                    fileType=excelObj.type,
                    password=excelObj.password or "",
                )

                excelObj.readOnly = False

            _log_excel_info(excelObj=excelObj)

        _register_managed_excel_obj(excelObj=excelObj, workbookKey=workbookKey)
        boolWorkbookRegistered = True

        # Only a successful first open commits the selected application as the shared state. ownsApp separately records who created the Excel process.
        if boolNewState:
            _register_shared_app_state(appState)
        return excelObj

    except Exception:
        if boolWorkbookRegistered:
            _unregister_managed_excel_obj(excelObj)

        if boolBookOpened:
            try:
                excelObj._book.close()
            except Exception as cleanupError:
                Log.error(
                    f"Failed to close the workbook after opening it failed: {cleanupError}"
                )

        if boolNewState:
            _unregister_shared_app_state(appState)

            # Never quit an Excel instance that belonged to the user. If LiberRPA created the Excel process and initialization failed before any ExcelObj was returned, force-terminate it only when normal shutdown also fails.
            if appState.ownsApp:
                _quit_excel_app_best_effort(
                    appState=appState,
                    killOnFailure=True,
                    failureContext="Failed to quit Excel after opening the workbook failed",
                )

        raise


@Log.trace()
def bind_excel_file(fileName: str) -> ExcelObj:
    """
    Bind to an already open Excel workbook by file name.

    Supported workbook file types are .xlsx, .xls, .xlsm, and .xlsb.
    CSV files should be handled by CSV-specific functions instead of Excel workbook functions.

    The first successful open or bind operation determines the shared Excel application instance. Later bind operations search only that same instance, so all ExcelObj objects remain compatible with each other. If no shared instance has been selected yet, all running Excel instances are searched. If the same file name exists in multiple instances, binding is
    rejected as ambiguous.

    Do not manually close the workbook or save it under another path while its ExcelObj is managed by LiberRPA. Use close() and save_as() so the shared application state and managed workbook registry remain synchronized.

    Parameters:
        fileName: The file name of an already open Excel workbook, such as "Report.xlsx".

    Returns:
        ExcelObj: An object representing the bound workbook.
    """

    # Reject unsupported names before this call claims the process-wide Excel thread.
    _check_excel_file_type(fileName)
    _claim_excel_thread()

    appState = _get_shared_app_state()

    if appState is not None:
        excelObj = ExcelObj(appState=appState)
        workbookKey: str | None = None

        with _excel_operation(excelObj=excelObj):
            for book in appState.app.books:
                if str(book.name).casefold() != fileName.casefold():
                    continue

                excelObj._book = book
                excelObj.path = book.fullname
                workbookKey = _get_workbook_key(excelObj.path)
                _ensure_workbook_key_available(appState=appState, workbookKey=workbookKey)
                excelObj.readOnly = bool(excelObj._book.api.ReadOnly)
                excelObj.type = _check_excel_file_type(excelObj.path)
                _log_excel_info(excelObj=excelObj)
                break

        if workbookKey is None:
            raise FileNotFoundError(
                f"No open workbook with name {fileName!r} was found in the shared Excel application instance."
            )

        _register_managed_excel_obj(excelObj=excelObj, workbookKey=workbookKey)
        return excelObj

    try:
        listApps = list(xw.apps)
    except _xwWindows.ExcelBusyError as e:
        raise ExcelBusyError(_STR_EXCEL_BUSY_ERROR_MESSAGE) from e
    except pywintypes.com_error as e:
        if _is_excel_busy_error(e):
            raise ExcelBusyError(_STR_EXCEL_BUSY_ERROR_MESSAGE) from e
        raise

    if not listApps:
        raise ExcelError("No running Excel instance was found.")

    listMatches: list[tuple[_ExcelAppState, xw.Book, str]] = []

    for xwApp in listApps:
        candidateState = _ExcelAppState(app=xwApp, ownsApp=False)
        candidateObj = ExcelObj(appState=candidateState)

        # Do not skip a busy instance. It could contain another workbook with the same name, so binding from an incomplete search would be ambiguous. ExcelBusyError intentionally propagates immediately from this context.
        with _excel_operation(excelObj=candidateObj):
            for book in xwApp.books:
                if str(book.name).casefold() == fileName.casefold():
                    listMatches.append((candidateState, book, book.fullname))

    if len(listMatches) > 1:
        raise ExcelError(
            f"Multiple open workbooks with name {fileName!r} were found in different Excel application instances."
        )

    if not listMatches:
        raise FileNotFoundError(f"No open workbook with name {fileName!r} was found.")

    appState, book, strPath = listMatches[0]

    excelObj = ExcelObj(appState=appState)
    excelObj._book = book
    excelObj.path = strPath
    excelObj.type = _check_excel_file_type(strPath)
    workbookKey = _get_workbook_key(strPath)
    _ensure_workbook_key_available(appState=appState, workbookKey=workbookKey)

    with _excel_operation(excelObj=excelObj):
        excelObj.readOnly = bool(excelObj._book.api.ReadOnly)
        _log_excel_info(excelObj=excelObj)

    _register_managed_excel_obj(excelObj=excelObj, workbookKey=workbookKey)

    try:
        # Registration happens only after every COM property needed to initialize the first bound ExcelObj has been read successfully.
        _register_shared_app_state(appState)
    except Exception:
        _unregister_managed_excel_obj(excelObj)
        raise

    return excelObj


@Log.trace()
def save(excelObj: ExcelObj) -> None:
    """
    Save the Excel workbook object.

    Parameters:
        excelObj: The Excel workbook object.
    """
    with _excel_operation(excelObj=excelObj):
        _save(excelObj=excelObj)


@Log.trace()
def save_as(excelObj: ExcelObj, dstPath: StrPath, password: str = "") -> str:
    """
    Save the current workbook as a new file.

    This behaves like Excel's "Save As" operation. The current workbook remains open as the workbook at the new path after saving.

    Do not manually close or save the workbook under another path while its ExcelObj is managed by LiberRPA.

    Parameters:
        excelObj: The Excel workbook object.
        dstPath: The path where the workbook will be saved. Accepts str or PathLike[str].
        password: An optional password for saving the workbook.

    Returns:
        str: The absolute path of the saved workbook.
    """
    with _excel_operation(excelObj=excelObj):
        strFilePath = str(Path(dstPath).absolute())
        newFileType = _check_excel_file_type(strFilePath)
        newWorkbookKey = _get_workbook_key(strFilePath)

        if Path(strFilePath).is_file():
            raise ExcelError(f"The file '{strFilePath}' exists.")

        _ensure_workbook_key_available(
            appState=excelObj._appState,
            workbookKey=newWorkbookKey,
            currentKey=excelObj._managedWorkbookKey,
        )

        # Create the folder if it doesn't exist.
        Path(strFilePath).parent.mkdir(parents=True, exist_ok=True)

        _save_as(
            excelObj=excelObj,
            path=strFilePath,
            fileType=newFileType,
            password=password,
        )

        # SaveAs has already changed the identity of the open workbook.
        # Update the registry and identity immediately.
        _update_managed_workbook_key(excelObj=excelObj, workbookKey=newWorkbookKey)
        excelObj.path = strFilePath
        excelObj.password = password
        excelObj.type = newFileType

        # SaveAs does not preserve a recoverable write-reservation password, so do not keep reporting the old password as current metadata.
        excelObj.writePassword = None

        try:
            bookApi = excelObj._book.api
            excelObj.readOnly = bool(bookApi.ReadOnly)

            # Whether write reservation exists can be determined, but it cannot reliably recover the actual password.
            if not bool(bookApi.WriteReserved):
                excelObj.writePassword = ""

        except Exception as metadataError:
            Log.warning(
                "The workbook was saved successfully, but its post-SaveAs "
                f"metadata could not be refreshed: {metadataError}"
            )

        return strFilePath


@Log.trace()
def close(excelObj: ExcelObj, save: bool = True) -> None:
    """
    Close the Excel workbook.

    Workbooks share one Excel application instance. LiberRPA quits that instance only when it created the instance, no managed ExcelObj remains, and the instance contains no other workbooks.

    Do not close the workbook or save it under another path directly in the Excel UI while it is managed. LiberRPA intentionally avoids a COM liveness probe before every operation because a closed workbook cannot be reliably distinguished from a temporarily busy Excel without extra failure-prone calls.

    Parameters:
        excelObj: The Excel workbook object.
        save: If True, saves the workbook before closing.
    """

    appState = excelObj._appState
    boolBookClosed = False

    try:
        with _excel_operation(excelObj=excelObj):
            if save:
                _save(excelObj=excelObj)

            workbookKey = _get_workbook_key(excelObj.path)
            strWorkbookName = Path(excelObj.path).name.casefold()

            excelObj._book.close()

            # Workbook.Close() can return normally even when a BeforeClose event cancels the close operation. Confirm that the workbook is no longer present before changing LiberRPA's managed state.
            for book in appState.app.books:
                if str(book.name).casefold() != strWorkbookName:
                    continue

                if _get_workbook_key(book.fullname) == workbookKey:
                    raise ExcelError(
                        "Excel returned from Close(), but the workbook is still open. "
                        "A Workbook.BeforeClose event may have canceled the close."
                    )

            boolBookClosed = True

    finally:
        if boolBookClosed:
            excelObj._boolClosed = True
            _unregister_managed_excel_obj(excelObj)

            if appState.excelObjCount == 0:
                # Quit the Excel instance only if LiberRPA created it and no workbook remains open.
                try:
                    boolShouldQuit = (
                        appState.ownsApp and int(appState.api.Workbooks.Count) == 0
                    )

                except Exception as cleanupError:
                    Log.error(
                        "Failed to inspect the shared Excel application after "
                        f"closing its last managed workbook: {cleanupError}"
                    )

                else:
                    if boolShouldQuit:
                        # Normal close is best-effort. Do not force-terminate an Excel process after ExcelObj objects have been returned, because it might now contain workbooks that the user opened manually.
                        _quit_excel_app_best_effort(
                            appState=appState,
                            killOnFailure=False,
                            failureContext=(
                                "Failed to quit the shared Excel application; the Excel process may require manual cleanup"
                            ),
                        )

                finally:
                    _unregister_shared_app_state(appState)


@Log.trace()
def activate_window(excelObj: ExcelObj) -> None:
    """
    Brings the Excel window to the front and restores it if minimized.

    Parameters:
        excelObj: The Excel workbook object.
    """

    with _excel_operation(excelObj=excelObj):
        # Use the exact COM Window that belongs to this workbook. Matching a desktop title by substring could confuse e.g. 1.xlsx with 11.xlsx.
        bookApi = excelObj._book.api
        windowApi = bookApi.Windows(1)
        hwnd = int(windowApi.Hwnd)

        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        windowApi.Activate()
        win32gui.SetForegroundWindow(hwnd)


@Log.trace()
def get_last_row(
    excelObj: ExcelObj, sheet: ExcelSheet, col: str | int | None = None
) -> int:
    """
    Get the last row number of a given sheet.

    If a specific column is provided, it returns the last row number of that column.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The sheet name as str, or zero-based sheet index as int.
        col: The column (name or number) to check. If None, checks the entire sheet.

    Returns:
        int: The number of the last row with data in the specified sheet/column.
    """
    return _get_last_row(excelObj=excelObj, sheet=sheet, col=col)


@Log.trace()
def get_last_column(
    excelObj: ExcelObj, sheet: ExcelSheet, row: int | None = None
) -> tuple[str, int]:
    """
    Get the last column (number or name) of a given sheet.

    If a specific row is provided, it returns the last column of that row.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The sheet name as str, or zero-based sheet index as int.
        row: The row number to check. If None, checks the entire sheet.

    Returns:
        tuple[str,int]: The name and number of the last column with data in the specified sheet/row.
    """
    return _get_last_column(excelObj=excelObj, sheet=sheet, row=row)


@Log.trace()
def convert_col_num_to_str(colNum: int) -> str:
    """
    Convert an Excel column number to a column letter.

    Parameters:
        colNum: The Excel column number, starting from 1.

    Returns:
        str: The Excel column letter, such as "A", "D", or "AA".
    """
    return _convert_col_num_to_str(colNum=colNum)


@Log.trace()
def convert_col_str_to_num(colStr: str) -> int:
    """
    Convert an Excel column letter to a column number.

    Parameters:
        colStr: The Excel column letter, such as "A", "D", or "AA".

    Returns:
        int: The Excel column number, starting from 1.
    """
    return _convert_col_str_to_num(colStr=colStr)


@overload
def read_cell(
    excelObj: ExcelObj,
    sheet: ExcelSheet,
    cell: ExcelCell,
    returnDisplayed: Literal[True] = True,
) -> str: ...


@overload
def read_cell(
    excelObj: ExcelObj,
    sheet: ExcelSheet,
    cell: ExcelCell,
    returnDisplayed: Literal[False],
) -> ExcelCellValue: ...


@Log.trace()
def read_cell(
    excelObj: ExcelObj,
    sheet: ExcelSheet,
    cell: ExcelCell,
    returnDisplayed: bool = True,
) -> ExcelCellValue:
    """
    Read the value of a specific cell.

    Can return either the actual value or the displayed value.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The sheet name as str, or zero-based sheet index as int.
        cell: The cell address, such as "A1", or [column, row], such as [1, 1] for A1.
        returnDisplayed: If True, returns displayed values as strings; otherwise, returns the actual value.

    Returns:
        str | ExcelCellValue: The displayed value as str if returnDisplayed=True; otherwise the actual cell value as str, int, float, datetime, bool, or None.
    """
    with _excel_operation(excelObj=excelObj):
        sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)
        cell = _check_and_standardize_cell(cell=cell, excelObj=excelObj)

        Log.verbose("Reading cell=" + cell)
        if returnDisplayed:
            return excelObj._book.sheets[sheet].range(cell).api.Text
        else:
            return excelObj._book.sheets[sheet].range(cell).value


@overload
def read_row(
    excelObj: ExcelObj,
    sheet: ExcelSheet,
    startCell: ExcelCell,
    returnDisplayed: Literal[True] = True,
) -> list[str]: ...


@overload
def read_row(
    excelObj: ExcelObj,
    sheet: ExcelSheet,
    startCell: ExcelCell,
    returnDisplayed: Literal[False],
) -> list[ExcelCellValue]: ...


@Log.trace()
def read_row(
    excelObj: ExcelObj,
    sheet: ExcelSheet,
    startCell: ExcelCell,
    returnDisplayed: bool = True,
) -> list[str] | list[ExcelCellValue]:
    """
    Read an entire row starting from a cell.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The sheet name as str, or zero-based sheet index as int.
        startCell: The starting cell address, such as "A1", or [column, row], such as [1, 1] for A1.
        returnDisplayed: If True, returns displayed values as strings. If False, returns actual cell values.

    Returns:
        list[str] | list[ExcelCellValue]: Displayed values as strings if returnDisplayed=True; otherwise actual values as str, int, float, datetime, bool, or None. Returns an empty list if startCell is to the right of the last cell containing a value or formula in the row.
    """
    with _excel_operation(excelObj=excelObj):
        sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)
        startCell = _check_and_standardize_cell(cell=startCell, excelObj=excelObj)

        # Extract row and column information from the starting cell
        _, intColStart, intRowStart = _extract_row_column_from_cell(
            cell=startCell, excelObj=excelObj
        )

        # Get the last column in the specified row
        strColStop, intColStop = get_last_column(
            excelObj=excelObj, sheet=sheet, row=intRowStart
        )

        # Check if the starting cell is beyond the last cell containing a value or formula in the row
        if intColStart > intColStop:
            Log.warning(
                f"The startCell({startCell}) is more right than the last cell in the row. Return empty list."
            )
            return []

        strRange = f"{startCell}:{strColStop}{intRowStart}"
        Log.debug(f"Reading range: {strRange}")
        range: xw.Range = excelObj._book.sheets[sheet].range(strRange)
        if returnDisplayed:
            returnValue = [cell.api.Text for cell in range]
        else:
            returnValue = range.value

        if isinstance(returnValue, list):
            return returnValue
        else:
            # The startCell is the rightmost cell in the row, xlwings won't return a list, so nest it.
            return [returnValue]


@overload
def read_column(
    excelObj: ExcelObj,
    sheet: ExcelSheet,
    startCell: ExcelCell,
    returnDisplayed: Literal[True] = True,
) -> list[str]: ...


@overload
def read_column(
    excelObj: ExcelObj,
    sheet: ExcelSheet,
    startCell: ExcelCell,
    returnDisplayed: Literal[False],
) -> list[ExcelCellValue]: ...


@Log.trace()
def read_column(
    excelObj: ExcelObj,
    sheet: ExcelSheet,
    startCell: ExcelCell,
    returnDisplayed: bool = True,
) -> list[str] | list[ExcelCellValue]:
    """
    Read an entire column starting from a cell.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The sheet name as str, or zero-based sheet index as int.
        startCell: The starting cell address, such as "A1", or [column, row], such as [1, 1] for A1.
        returnDisplayed: If True, returns displayed values as strings. If False, returns actual cell values.

    Returns:
        list[str] | list[ExcelCellValue]: Displayed values as strings if returnDisplayed=True; otherwise actual values as str, int, float, datetime, bool, or None. Returns an empty list if startCell is below the last cell containing a value or formula in the column.
    """
    with _excel_operation(excelObj=excelObj):
        sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)
        startCell = _check_and_standardize_cell(cell=startCell, excelObj=excelObj)

        # Extract row and column information from the starting cell
        strColStart, _, intRowStart = _extract_row_column_from_cell(
            cell=startCell, excelObj=excelObj
        )

        # Get the last row in the specified column
        intRowStop = get_last_row(excelObj=excelObj, sheet=sheet, col=strColStart)

        # Check if the starting cell is below the last cell containing a value or formula in the column
        if intRowStart > intRowStop:
            Log.warning(
                f"The startCell({startCell}) is more down than the last cell in the column. Return empty list."
            )
            return []

        strRange = f"{startCell}:{strColStart}{intRowStop}"
        Log.debug(f"Reading range: {strRange}")
        range: xw.Range = excelObj._book.sheets[sheet].range(strRange)
        if returnDisplayed:
            returnValue = [cell.api.Text for cell in range]
        else:
            returnValue = range.value

        if isinstance(returnValue, list):
            return returnValue
        else:
            # The startCell is the downmost cell in the column, xlwings won't return a list, so nest it.
            return [returnValue]


@overload
def read_range_list(
    excelObj: ExcelObj,
    sheet: ExcelSheet,
    startCell: ExcelCell,
    endCell: ExcelCell | None = None,
    *,
    returnDisplayed: Literal[True] = True,
) -> list[list[str]]: ...


@overload
def read_range_list(
    excelObj: ExcelObj,
    sheet: ExcelSheet,
    startCell: ExcelCell,
    endCell: ExcelCell | None = None,
    *,
    returnDisplayed: Literal[False],
) -> list[list[ExcelCellValue]]: ...


@Log.trace()
def read_range_list(
    excelObj: ExcelObj,
    sheet: ExcelSheet,
    startCell: ExcelCell,
    endCell: ExcelCell | None = None,
    *,
    returnDisplayed: bool = True,
) -> list[list[str]] | list[list[ExcelCellValue]]:
    """
    Read a range and return it as a 2D list.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The sheet name as str, or zero-based sheet index as int.
        startCell: The starting cell address, such as "A1", or [column, row], such as [1, 1] for A1.
        endCell: The ending cell address. If None, reads to the last cell containing a value or formula.
        returnDisplayed: If True, returns displayed values as strings. If False, returns actual cell values.

    Returns:
        list[list[str]] | list[list[ExcelCellValue]]: Displayed values as strings if returnDisplayed=True; otherwise actual values as str, int, float, datetime, bool, or None.
    """
    with _excel_operation(excelObj=excelObj):
        listRange = _read_range(
            excelObj=excelObj,
            sheet=sheet,
            startCell=startCell,
            endCell=endCell,
            returnDisplayed=returnDisplayed,
        )
        return listRange


@Log.trace()
def read_range_df(
    excelObj: ExcelObj,
    sheet: ExcelSheet,
    startCell: ExcelCell,
    endCell: ExcelCell | None = None,
    addTitle: bool = True,
    returnDisplayed: bool = True,
) -> pandas.DataFrame:
    """
    Read a range and return it as a pandas DataFrame.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The sheet name as str, or zero-based sheet index as int.
        startCell: The starting cell address, such as "A1", or [column, row], such as [1, 1] for A1.
        endCell: The ending cell address. If None, reads to the last cell containing a value or formula.
        addTitle: If True, uses the first row as DataFrame column names.
        returnDisplayed: If True, reads displayed values as strings. If False, reads actual cell values.

    Returns:
        pandas.DataFrame: The range data as a DataFrame.
    """
    with _excel_operation(excelObj=excelObj):
        listRange = _read_range(
            excelObj=excelObj,
            sheet=sheet,
            startCell=startCell,
            endCell=endCell,
            returnDisplayed=returnDisplayed,
        )

        if addTitle:
            # Constructing an Index makes the supported pandas columns type explicit and avoids an invariant list union in Pylance.
            columnIndex = pandas.Index(listRange[0])
            dfRange = pandas.DataFrame(
                data=listRange[1:], index=None, columns=columnIndex
            )
        else:
            dfRange = pandas.DataFrame(data=listRange, index=None, columns=None)

        return dfRange


@Log.trace()
def write_cell(
    excelObj: ExcelObj,
    sheet: ExcelSheet,
    cell: ExcelCell,
    data: ExcelCellValue,
    save: bool = False,
) -> None:
    """
    Writes data to a specified cell in an Excel sheet.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The sheet name as str, or zero-based sheet index as int.
        cell: The cell to write to, such as "A1", or [column, row], such as [1, 1] for A1.
        data: The value to write. Can be str, int, float, datetime, bool, or None.
        save: If True, saves the workbook immediately after writing. This is not transactional: if saving fails, the operation may already have been applied to the open workbook.
    """
    with _excel_operation(excelObj=excelObj):
        sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)
        cell = _check_and_standardize_cell(cell=cell, excelObj=excelObj)

        Log.verbose(f"Writing cell: {cell}")
        excelObj._book.sheets[sheet].range(cell).value = data

        if save:
            _save(excelObj=excelObj)


@Log.trace()
def write_row(
    excelObj: ExcelObj,
    sheet: ExcelSheet,
    startCell: ExcelCell,
    data: list[ExcelCellValue],
    save: bool = False,
) -> None:
    """
    Writes a list of data to a row in an Excel sheet starting from a specified cell.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The sheet name as str, or zero-based sheet index as int.
        startCell: The starting cell of the row, such as "A1", or [column, row], such as [1, 1] for A1.
        data: The value to write. Can be str, int, float, datetime, bool, or None.
        save: If True, saves the workbook immediately after writing. This is not transactional: if saving fails, the operation may already have been applied to the open workbook.
    """
    if not data:
        raise ValueError("The argument 'data' must not be empty.")

    with _excel_operation(excelObj=excelObj):
        sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)
        startCell = _check_and_standardize_cell(cell=startCell, excelObj=excelObj)

        # For debugging purposes, print the range.
        _, intColStart, intRowStart = _extract_row_column_from_cell(
            cell=startCell, excelObj=excelObj
        )
        intColEnd = _validate_excel_column_number(
            intColStart + len(data) - 1, excelObj=excelObj
        )
        strColEnd = convert_col_num_to_str(colNum=intColEnd)
        endCell = strColEnd + str(intRowStart)
        strRange = f"{startCell}:{endCell}"
        Log.debug(f"Writing range: {strRange}")

        with _preserve_screen_updating(excelObj=excelObj):
            excelObj._book.sheets[sheet].range(startCell).value = data

        if save:
            _save(excelObj=excelObj)


@Log.trace()
def write_column(
    excelObj: ExcelObj,
    sheet: ExcelSheet,
    startCell: ExcelCell,
    data: list[ExcelCellValue],
    save: bool = False,
) -> None:
    """
    Writes a list of data to a column in an Excel sheet starting from a specified cell.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The sheet name as str, or zero-based sheet index as int.
        startCell: The starting cell of the column, such as "A1", or [column, row], such as [1, 1] for A1.
        data: The value to write. Can be str, int, float, datetime, bool, or None.
        save: If True, saves the workbook immediately after writing. This is not transactional: if saving fails, the operation may already have been applied to the open workbook.
    """
    if not data:
        raise ValueError("The argument 'data' must not be empty.")

    with _excel_operation(excelObj=excelObj):
        sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)
        startCell = _check_and_standardize_cell(cell=startCell, excelObj=excelObj)

        # For debugging purposes, print the range.
        strColStart, _, intRowStart = _extract_row_column_from_cell(
            cell=startCell, excelObj=excelObj
        )
        intRowEnd = _validate_excel_row_number(
            intRowStart + len(data) - 1, excelObj=excelObj
        )
        endCell = strColStart + str(intRowEnd)
        strRange = f"{startCell}:{endCell}"
        Log.debug(f"Writing range: {strRange}")

        with _preserve_screen_updating(excelObj=excelObj):
            excelObj._book.sheets[sheet].range(startCell).options(
                transpose=True
            ).value = data

        if save:
            _save(excelObj=excelObj)


@Log.trace()
def write_range(
    excelObj: ExcelObj,
    sheet: ExcelSheet,
    startCell: ExcelCell,
    data: pandas.DataFrame | list[list[ExcelCellValue]] | None,
    writeTitleRow: bool = True,
    save: bool = False,
) -> None:
    """
    Write a pandas DataFrame or a 2D list to a range.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The sheet name as str, or zero-based sheet index as int.
        startCell: The starting cell address, such as "A1", or [column, row], such as [1, 1] for A1.
        data: The data to write. Pass a pandas DataFrame or a 2D list. For a 2D list, each cell value can be str, int, float, datetime, bool, or None.
        writeTitleRow: If data is a DataFrame, writes its column names when True. If data is a 2D list, treats the first row as a title row and writes it only when True.
        save: If True, saves the workbook after writing. This is not transactional: if saving fails, the operation may already have been applied to the open workbook.
    """

    if data is None:
        Log.warning("The argument data is None.")
        return None

    _validate_write_range_data(
        data=data,
        writeTitleRow=writeTitleRow,
    )

    with _excel_operation(excelObj=excelObj):
        sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)
        startCell = _check_and_standardize_cell(cell=startCell, excelObj=excelObj)

        # For debugging purposes, print the range.
        _, intColStart, intRowStart = _extract_row_column_from_cell(
            cell=startCell, excelObj=excelObj
        )
        if isinstance(data, pandas.DataFrame):
            intColEnd = intColStart + len(data.columns) - 1
            intRowEnd = (
                intRowStart + len(data) if writeTitleRow else intRowStart + len(data) - 1
            )

        else:
            intColEnd = intColStart + len(data[0]) - 1
            intRowEnd = (
                intRowStart + len(data) - 1
                if writeTitleRow
                else intRowStart + len(data) - 2
            )

        intColEnd = _validate_excel_column_number(intColEnd, excelObj=excelObj)
        intRowEnd = _validate_excel_row_number(intRowEnd, excelObj=excelObj)
        strColEnd = convert_col_num_to_str(colNum=intColEnd)
        endCell = f"{strColEnd}{intRowEnd}"

        strRange = f"{startCell}:{endCell}"
        Log.debug(f"Writing range: {strRange}")

        with _preserve_screen_updating(excelObj=excelObj):
            if isinstance(data, pandas.DataFrame):
                excelObj._book.sheets[sheet].range(startCell).options(
                    index=False, header=writeTitleRow
                ).value = data
            else:
                if writeTitleRow:
                    excelObj._book.sheets[sheet].range(startCell).value = data
                else:
                    excelObj._book.sheets[sheet].range(startCell).value = data[1:]

        if save:
            _save(excelObj=excelObj)


@Log.trace()
def insert_row(
    excelObj: ExcelObj,
    sheet: ExcelSheet,
    startCell: ExcelCell,
    data: list[ExcelCellValue],
    save: bool = False,
) -> None:
    """
    Insert a new row at startCell's row, then write data from startCell.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The sheet name as str, or zero-based sheet index as int.
        startCell: The first cell to write after inserting the row, such as "A1", or [column, row], such as [1, 1] for A1.
        data: A list of values to write. Each value can be str, int, float, datetime, bool, or None.
        save: If True, saves the workbook after inserting. This is not transactional: if saving fails, the operation may already have been applied to the open workbook.
    """
    if not data:
        raise ValueError("The argument 'data' must not be empty.")

    with _excel_operation(excelObj=excelObj):
        sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)
        startCell = _check_and_standardize_cell(cell=startCell, excelObj=excelObj)

        # Validate the complete write range before inserting anything.
        _, intColStart, intRowStart = _extract_row_column_from_cell(
            cell=startCell, excelObj=excelObj
        )
        _validate_excel_column_number(intColStart + len(data) - 1, excelObj=excelObj)

        excelObj._book.sheets[sheet].range(f"{intRowStart}:{intRowStart}").insert(
            shift="down", copy_origin="format_from_left_or_above"
        )

        write_row(
            excelObj=excelObj, sheet=sheet, startCell=startCell, data=data, save=save
        )


@Log.trace()
def insert_column(
    excelObj: ExcelObj,
    sheet: ExcelSheet,
    startCell: ExcelCell,
    data: list[ExcelCellValue],
    save: bool = False,
) -> None:
    """
    Insert a new column at startCell's column, then write data from startCell.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The sheet name as str, or zero-based sheet index as int.
        startCell: The first cell to write after inserting the column, such as "A1", or [column, row], such as [1, 1] for A1.
        data: A list of values to write. Each value can be str, int, float, datetime, bool, or None.
        save: If True, saves the workbook after inserting. This is not transactional: if saving fails, the operation may already have been applied to the open workbook.
    """
    if not data:
        raise ValueError("The argument 'data' must not be empty.")

    with _excel_operation(excelObj=excelObj):
        sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)
        startCell = _check_and_standardize_cell(cell=startCell, excelObj=excelObj)

        strColStart, _, intRowStart = _extract_row_column_from_cell(
            cell=startCell, excelObj=excelObj
        )

        # Validate the complete write range before inserting anything.
        _validate_excel_row_number(intRowStart + len(data) - 1, excelObj=excelObj)

        excelObj._book.sheets[sheet].range(f"{strColStart}:{strColStart}").insert(
            shift="right", copy_origin="format_from_left_or_above"
        )

        write_column(
            excelObj=excelObj, sheet=sheet, startCell=startCell, data=data, save=save
        )


@Log.trace()
def delete_row(
    excelObj: ExcelObj, sheet: ExcelSheet, cell: ExcelCell, save: bool = False
) -> None:
    """
    Delete the entire row that contains the specified cell.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The sheet name as str, or zero-based sheet index as int.
        cell: A cell within the row to delete, such as "A1", or [column, row], such as [1, 1] for A1.
        save: If True, saves the workbook after deleting. This is not transactional: if saving fails, the operation may already have been applied to the open workbook.
    """
    with _excel_operation(excelObj=excelObj):
        sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)
        cell = _check_and_standardize_cell(cell=cell, excelObj=excelObj)

        _, _, intRowStart = _extract_row_column_from_cell(cell=cell, excelObj=excelObj)

        Log.verbose(f"Deleting row: {intRowStart}")

        excelObj._book.sheets[sheet].range(f"{intRowStart}:{intRowStart}").delete(
            shift="up"
        )

        if save:
            _save(excelObj=excelObj)


@Log.trace()
def delete_column(
    excelObj: ExcelObj, sheet: ExcelSheet, cell: ExcelCell, save: bool = False
) -> None:
    """
    Delete the entire column that contains the specified cell.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The sheet name as str, or zero-based sheet index as int.
        cell: A cell within the column to delete, such as "A1", or [column, row], such as [1, 1] for A1.
        save: If True, saves the workbook after deleting. This is not transactional: if saving fails, the operation may already have been applied to the open workbook.
    """
    with _excel_operation(excelObj=excelObj):
        sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)
        cell = _check_and_standardize_cell(cell=cell, excelObj=excelObj)

        strColStart, _, _ = _extract_row_column_from_cell(cell=cell, excelObj=excelObj)

        Log.verbose(f"Deleting column: {strColStart}")

        excelObj._book.sheets[sheet].range(f"{strColStart}:{strColStart}").delete(
            shift="left"
        )

        if save:
            _save(excelObj=excelObj)


@Log.trace()
def select_range(
    excelObj: ExcelObj, sheet: ExcelSheet, startCell: ExcelCell, endCell: ExcelCell | None
) -> None:
    """
    Select the specific range.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The sheet name as str, or zero-based sheet index as int.
        startCell: The starting cell of the range, such as "A1", or [column, row], such as [1, 1] for A1.
        endCell: The ending cell of the range. If None, select till the last cell containing a value or formula.
    """
    with _excel_operation(excelObj=excelObj):
        sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)
        startCell = _check_and_standardize_cell(cell=startCell, excelObj=excelObj)
        endCell = _get_endCell_if_not_provided(
            excelObj=excelObj, sheet=sheet, endCell=endCell
        )

        _validate_range_order(excelObj=excelObj, startCell=startCell, endCell=endCell)

        strRange = f"{startCell}:{endCell}"
        Log.debug(f"Selecting range: {strRange}")

        activate_sheet(excelObj=excelObj, sheet=sheet)
        excelObj._book.sheets[sheet].range(f"{startCell}:{endCell}").select()


@Log.trace()
def get_selected_cells(excelObj: ExcelObj) -> list[str]:
    """
    Get the list of all selected cells of the current activated sheet.

    Parameters:
        excelObj: The Excel workbook object.

    Returns:
        list[str]: A list of selected cell addresses, such as ["B3", "C3", "B4"].
    """
    with _excel_operation(excelObj=excelObj):
        rangeSelected = excelObj._book.selection
        if not rangeSelected:
            raise ExcelError("No range is selected in the active sheet.")
        return [str(cell.address).replace("$", "") for cell in rangeSelected]


@Log.trace()
def get_selected_range(excelObj: ExcelObj) -> list[str]:
    """
    Get the selected range addresses from the active sheet.

    Parameters:
        excelObj: The Excel workbook object.

    Returns:
        list[str]: Selected range addresses, such as ["B3"], ["B3:C6"], or ["A1:B2", "D1:E2"].
    """
    with _excel_operation(excelObj=excelObj):
        rangeSelected = excelObj._book.selection
        if not rangeSelected:
            raise ExcelError("Not select any range.")
        return [range.replace("$", "") for range in str(rangeSelected.address).split(",")]


@Log.trace()
def clear_range(
    excelObj: ExcelObj,
    sheet: ExcelSheet,
    startCell: ExcelCell,
    endCell: ExcelCell | None,
    clearContent: bool = True,
    clearFormat: bool = True,
    save: bool = False,
) -> None:
    """
    Clear values, formatting, or both from a range.

    When endCell is None, Excel's UsedRange is used. It may include cells that were formatted or used previously and can therefore be larger than the current visible data area.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The sheet name as str, or zero-based sheet index as int.
        startCell: The starting cell address, such as "A1", or [column, row], such as [1, 1] for A1.
        endCell: The ending cell address. If None, clears to the last used cell.
        clearContent: If True, clears cell values.
        clearFormat: If True, clears cell formatting.
        save: If True, saves the workbook after clearing. This is not transactional: if saving fails, the operation may already have been applied to the open workbook.
    """

    if not clearContent and not clearFormat:
        raise ValueError("At least one of 'clearContent' or 'clearFormat' must be True.")

    with _excel_operation(excelObj=excelObj):
        sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)
        startCell = _check_and_standardize_cell(cell=startCell, excelObj=excelObj)

        sheetObj = excelObj._book.sheets[sheet]

        if endCell is None:
            lastUsedCell = sheetObj.used_range.last_cell
            strLastColumn = _convert_col_num_to_str(
                colNum=int(lastUsedCell.column),
                excelObj=excelObj,
            )
            endCell = f"{strLastColumn}{int(lastUsedCell.row)}"
        else:
            endCell = _check_and_standardize_cell(
                cell=endCell,
                excelObj=excelObj,
            )

        _validate_range_order(excelObj=excelObj, startCell=startCell, endCell=endCell)

        strRange = f"{startCell}:{endCell}"
        Log.debug(
            f"Clearing range: {strRange}, clearContents: {clearContent}, clearFormats: {clearFormat}"
        )
        range: xw.Range = sheetObj.range(strRange)

        if clearContent and clearFormat:
            range.clear()
        elif clearContent:
            range.clear_contents()
        else:
            # clearFormats == True
            range.clear_formats()

        if save:
            _save(excelObj=excelObj)


@Log.trace()
def activate_sheet(excelObj: ExcelObj, sheet: ExcelSheet) -> None:
    """
    Activate sheet by name or index.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The sheet name as str, or zero-based sheet index as int.
    """
    with _excel_operation(excelObj=excelObj):
        sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)
        # Log.verbose(f"Activating sheet: {sheet}")
        excelObj._book.sheets[sheet].activate()


@Log.trace()
def add_sheet(
    excelObj: ExcelObj,
    newSheetName: str,
    anchorSheet: ExcelSheet = "Sheet1",
    direction: Literal["before", "after"] = "after",
    save: bool = False,
) -> None:
    """
    Add a new sheet before or after an existing sheet.

    Parameters:
        excelObj: The Excel workbook object.
        newSheetName: The name of the new sheet.
        anchorSheet: The existing sheet used as the insert position. Accepts sheet name as str or zero-based sheet index as int.
        direction: Where to insert the new sheet relative to anchorSheet, either "before" or "after".
        save: If True, saves the workbook after adding the sheet. This is not transactional: if saving fails, the operation may already have been applied to the open workbook.
    """
    # This validation is pure Python. Reject invalid input before touching the shared Excel application or changing its Interactive state.
    _check_sheet_name_compliance(sheetName=newSheetName)

    if direction not in ["before", "after"]:
        raise ValueError("The argument direction should be 'before' or 'after'.")

    with _excel_operation(excelObj=excelObj):
        _check_sheet_name_available(excelObj=excelObj, sheetName=newSheetName)

        anchorSheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=anchorSheet)
        anchorSheetObj = excelObj._book.sheets[anchorSheet]

        if direction == "before":
            excelObj._book.sheets.add(
                name=newSheetName, before=anchorSheetObj, after=None
            )
        else:
            # after
            excelObj._book.sheets.add(
                name=newSheetName, before=None, after=anchorSheetObj
            )

        if save:
            _save(excelObj=excelObj)


@Log.trace()
def rename_sheet(
    excelObj: ExcelObj, sheet: ExcelSheet, newSheetName: str, save: bool = False
) -> None:
    """
    Rename a sheet.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The sheet name as str, or zero-based sheet index as int.
        newSheetName: The sheet's new name.
        save: If True, saves the workbook immediately after renaming. This is not transactional: if saving fails, the operation may already have been applied to the open workbook.
    """
    _check_sheet_name_compliance(sheetName=newSheetName)

    with _excel_operation(excelObj=excelObj):
        sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)
        _check_sheet_name_available(
            excelObj=excelObj, sheetName=newSheetName, currentSheetName=sheet
        )
        Log.verbose(f"Renaming sheet: {sheet} -> {newSheetName}")
        excelObj._book.sheets[sheet].name = newSheetName

        if save:
            _save(excelObj=excelObj)


@Log.trace()
def copy_sheet(
    srcExcelObj: ExcelObj,
    srcSheet: ExcelSheet,
    dstExcelObj: ExcelObj,
    dstAnchorSheet: ExcelSheet,
    newSheetName: str,
    direction: Literal["before", "after"] = "after",
    save: bool = False,
) -> None:
    """
    Copy a sheet to another workbook, before or after an existing destination sheet.

    Excel can directly copy a worksheet only when both workbooks belong to the same Excel application instance. LiberRPA normally guarantees this by using one shared application state for all opened and bound workbooks.

    Parameters:
        srcExcelObj: The source Excel workbook object.
        srcSheet: The sheet to copy. Accepts sheet name as str or zero-based sheet index as int.
        dstExcelObj: The destination Excel workbook object.
        dstAnchorSheet: The destination sheet used as the insert position. Accepts sheet name as str or zero-based sheet index as int.
        newSheetName: The name of the copied sheet in the destination workbook.
        direction: Where to insert the copied sheet relative to dstAnchorSheet, either "before" or "after".
        save: If True, saves the destination workbook after copying. This is not transactional: if saving fails, the operation may already have been applied to the open workbook.
    """

    _check_sheet_name_compliance(sheetName=newSheetName)
    if direction not in ["before", "after"]:
        raise ValueError("The argument direction should be 'before' or 'after'.")

    srcExcelObj._ensure_open()
    dstExcelObj._ensure_open()

    if srcExcelObj._appState is not dstExcelObj._appState:
        raise ExcelError(
            "The source and destination workbooks do not share the same Excel application instance."
        )

    with _excel_operation(excelObj=srcExcelObj):
        _check_sheet_name_available(excelObj=dstExcelObj, sheetName=newSheetName)

        srcSheet = _check_and_standardize_sheet(excelObj=srcExcelObj, sheet=srcSheet)
        dstAnchorSheet = _check_and_standardize_sheet(
            excelObj=dstExcelObj, sheet=dstAnchorSheet
        )

        Log.debug(
            f"Copying sheet from {srcExcelObj}-{srcSheet} to {dstExcelObj}-{dstAnchorSheet}'s {direction}, new sheet name is {newSheetName}"
        )

        if direction == "before":
            srcExcelObj._book.sheets[srcSheet].copy(
                name=newSheetName,
                before=dstExcelObj._book.sheets[dstAnchorSheet],
                after=None,
            )
        else:
            # after
            srcExcelObj._book.sheets[srcSheet].copy(
                name=newSheetName,
                before=None,
                after=dstExcelObj._book.sheets[dstAnchorSheet],
            )

        if save:
            _save(excelObj=dstExcelObj)


@Log.trace()
def delete_sheet(excelObj: ExcelObj, sheet: ExcelSheet, save: bool = False) -> None:
    """
    Delete a sheet.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The sheet name as str, or zero-based sheet index as int.
        save: If True, saves the workbook after deleting the sheet. This is not transactional: if saving fails, the operation may already have been applied to the open workbook.
    """
    with _excel_operation(excelObj=excelObj):
        sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)
        if len(excelObj._book.sheets) <= 1:
            raise ExcelError("Excel requires at least one worksheet in a workbook.")

        Log.verbose(f"Deleting sheet: {sheet}")

        # Call Excel's COM Delete() through the xlwings API wrapper so LiberRPA alone controls DisplayAlerts restoration.
        sheetApi = excelObj._book.sheets[sheet].api
        with _temporary_display_alerts(excelObj=excelObj, value=False):
            sheetApi.Delete()

        if save:
            _save(excelObj=excelObj)


@Log.trace()
def get_active_sheet(excelObj: ExcelObj) -> str:
    """
    Get the current activated sheet's name.

    Parameters:
        excelObj: The Excel workbook object.

    Returns:
        str: The name of the current active sheet.
    """
    with _excel_operation(excelObj=excelObj):
        return excelObj._book.sheets.active.name


@Log.trace()
def get_sheet_list(excelObj: ExcelObj) -> list[str]:
    """
    Get the list of all sheets' names of the Excel workbook object.

    Parameters:
        excelObj: The Excel workbook object.

    Returns:
        list[str]: A list of all sheet names in the workbook.
    """
    with _excel_operation(excelObj=excelObj):
        return [sheet.name for sheet in excelObj._book.sheets]


@Log.trace()
def run_macro(
    excelObj: ExcelObj, macroName: str, arguments: list[Any] | None = None
) -> Any:
    """
    Run an Excel macro.

    Parameters:
        excelObj: The Excel workbook object that contains the macro.
        macroName: Name of a Sub or Function, with or without module name, such as "Module1.MyMacro" or "MyMacro".
        arguments: Arguments passed to the macro. If None, no arguments are passed.

    Returns:
        Any: The value returned by the macro.
    """
    arguments = [] if arguments is None else arguments

    try:
        with _excel_operation(excelObj=excelObj):
            return excelObj._book.macro(name=macroName)(*arguments)

    except ExcelError:
        raise

    except Exception as e:
        raise ExcelError(
            f"Failed to run macro '{macroName}': {e} Please check the macroName and Excel config."
        ) from e


if __name__ == "__main__":
    Log.set_level("VERBOSE")
    excelObj1 = bind_excel_file(fileName="1.xlsx")
    # excelObj2 = bind_excel_file(fileName="2.xlsx")
    # excelObj3 = bind_excel_file(fileName="3.xlsx")

    print(excelObj1)
    # print(excelObj2)

    from time import sleep

    print("sleep start")
    sleep(3)
    print("sleep done")

    """ flag: bool = False
    temp = read_row(
        excelObj=excelObj1,
        sheet="Sheet3",
        startCell="A2",
        # returnDisplayed=flag,
    )
    print(temp) """
    """ copy_sheet(
        srcExcelObj=excelObj1,
        srcSheet="Sheet3",
        dstExcelObj=excelObj2,
        dstAnchorSheet="Sheet1",
        newSheetName="test copy",
        direction="before",
        save=False,
    ) """
    # close(excelObj=excelObj)

    # write_cell(excelObj=excelObj1, sheet="Sheet3", cell="A36", data=None, save=False)
    print(get_last_row(excelObj=excelObj1, sheet="Sheet1", col=None))
    print(get_last_column(excelObj=excelObj1, sheet="Sheet1", row=None))
