# FileName: Excel.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
import pandas
import xlwings as xw
from xlwings import Book, Range
from pathlib import Path
import win32gui
import win32con
import win32com.client
import pythoncom
import re
from datetime import datetime
from typing import Literal, Any

type TypeOfSheet = str | int
type TypeOfCell = str | list[int]
type TypeOfCellData = str | int | float | datetime | bool | None


class ExcelError(Exception):
    """Custom exception for Excel manipulation"""

    def __init__(self, message: str, *args):
        super().__init__(message, *args)


class ExcelObj:
    def __init__(self) -> None:
        self.path: str
        self.visible: bool
        self.readOnly: bool
        self.password: str
        self.writePassword: str
        self.type: Literal["xlsx", "xls", "xlsm"]
        self.book: Book

    def __str__(self) -> str:
        return f"ExcelWorkbook(path: {self.path}, visible: {self.visible}, readOnly: {self.readOnly}, password: {'*****' if self.password else ''}, writePassword: {'*****' if self.writePassword else ''}, type: {self.type})"


def _check_edit_mode():
    try:
        # Ensure Python uses the same COM thread as xlwings
        pythoncom.CoInitialize()

        # Access the Excel COM object
        excelApp = win32com.client.Dispatch("Excel.Application")

        # Check if Excel is in interactive mode
        if not excelApp.Interactive:
            raise ExcelError("Excel is in Edit mode or not responsive.")
    except ExcelError as e:
        raise e
    except Exception as e:
        raise ExcelError(f"{e}, Excel is in Edit mode or not responsive.")
    finally:
        pythoncom.CoUninitialize()


def _check_and_standardize_sheet(excelObj: ExcelObj, sheet: TypeOfSheet) -> str:
    if not (isinstance(sheet, int) or isinstance(sheet, str)):
        raise ExcelError("The argument sheet should be a int or string.")
    listSheetName: list[str] = [sheet.name for sheet in excelObj.book.sheets]

    if isinstance(sheet, str) and (sheet not in listSheetName):
        raise ExcelError(f"The sheet({sheet}) doest not exist. The current sheets: {listSheetName}")
    if isinstance(sheet, int) and sheet >= len(listSheetName):
        raise ExcelError(f"The sheet index ({sheet}) is greater than the largest sheet index({len(listSheetName)-1}).")

    strSheet = excelObj.book.sheets[sheet].name
    if isinstance(sheet, int):
        Log.debug("sheet standardized=" + strSheet)
    return strSheet


def _check_and_standardize_column(column: str | int) -> str:
    if not (isinstance(column, int) or isinstance(column, str)):
        raise ExcelError("The argument column(col) should be a int or string.")
    if isinstance(column, int):
        strCol: str = xw.utils.col_name(column)
        Log.debug("column standardized=" + strCol)
    else:
        # str
        strCol: str = column
    return strCol


def _check_and_standardize_cell(cell: TypeOfCell) -> str:
    if not (isinstance(cell, str) or isinstance(cell, list)):
        raise ExcelError("The argument cell should be a string or list[int].")
    if isinstance(cell, list) and len(cell) == 2 and isinstance(cell[0], int) and isinstance(cell[1], int):
        strCol: str = xw.utils.col_name(cell[0])
        strCell = (strCol + str(cell[1])).upper()
        Log.debug("cell standardized=" + strCell)
        return strCell
    elif isinstance(cell, str):
        strCell = cell.upper()
        if strCell != cell:
            Log.debug("cell standardized=" + strCell)
        return strCell
    else:
        raise ValueError(f"Invalid cell: {repr(cell)}")


def _extract_row_column_from_cell(cell: str) -> tuple[str, int, int]:
    cell = _check_and_standardize_cell(cell=cell)
    match = re.search(pattern="""^[A-Z]*""", string=cell, flags=0)
    if match:
        strCol = match.group()
    else:
        raise ExcelError(f"Failed to extract column string from '{cell}'.")
    intCol = convert_col_str_to_num(colStr=strCol)
    match = re.search(pattern="""\\d*$""", string=cell, flags=0)
    if match:
        row = int(match.group())
    else:
        raise ExcelError(f"Failed to extract row from '{cell}'.")

    return (strCol, intCol, row)


def _print_xw_info(excelObj: ExcelObj) -> None:
    xwApp = excelObj.book.app
    Log.verbose(
        f"Workbook info: books: {xwApp.books}, pid: {xwApp.pid}, version: {xwApp.version}, visible: {xwApp.visible}, screen_updating: {xwApp.screen_updating}, calculation: {xwApp.calculation}, display_alerts: {xwApp.display_alerts}, enable_events: {xwApp.enable_events}, interactive: {xwApp.interactive}, path: {xwApp.path}, startup_path: {xwApp.startup_path}"
    )


@Log.trace()
def open_Excel_file(
    path: str,
    visible: bool = True,
    password: str = "",
    writePassword: str = "",
    createIfNotExist: bool = True,
    readOnly: bool = False,
) -> ExcelObj:
    """
    Opens an Excel file, or creates it if specified.

    If a file have be opened, it will be opened with read-only mode.

    Parameters:
        path: The path to the Excel file.
        visible: If True, opens Excel in visible mode.
        password: The password for opening the workbook, if required.
        writePassword: The password for write access, if required.
        createIfNotExist: If True, creates a new workbook if the file does not exist.
        readOnly: If True, opens the workbook in read-only mode.

    Returns:
        ExcelWorkbook: An object representing the opened workbook.
    """
    _check_edit_mode()
    excelObj = ExcelObj()

    excelObj.path = str(Path(path).absolute())
    excelObj.visible = visible
    excelObj.readOnly = readOnly
    excelObj.password = password
    excelObj.writePassword = writePassword
    excelObj.type = Path(path).suffix.replace(".", "")  # type: ignore

    if Path(excelObj.path).is_file():
        xwApp = xw.App(visible=excelObj.visible, add_book=False)
        excelObj.book = xwApp.books.open(
            fullname=excelObj.path,
            read_only=excelObj.readOnly,
            password=excelObj.password,
            write_res_password=excelObj.writePassword,
            add_to_mru=False,
            local=True,
        )
    else:
        if createIfNotExist:
            # Create a new file
            xwApp = xw.App(visible=excelObj.visible, add_book=False)
            excelObj.book = xwApp.books.add()
            # Save the new book if the path is specified
            excelObj.book.save(path=excelObj.path)
        else:
            raise FileNotFoundError(f"No such file: '{excelObj.path}'")
    _print_xw_info(excelObj=excelObj)
    return excelObj


@Log.trace()
def bind_Excel_file(fileName: str) -> ExcelObj:
    """
    If there are files with same name, it will bind only one of them.

    Parameters:
        fileName: The opening Excel workbook file name.
        visible: If True, opens Excel in visible mode.
        password: The password for opening the workbook, if required.
        writePassword: The password for write access, if required.
        createIfNotExist: If True, creates a new workbook if the file does not exist.
        readOnly: If True, opens the workbook in read-only mode.

    Returns:
        ExcelWorkbook: An object representing the opened workbook.
    """
    _check_edit_mode()
    excelObj = ExcelObj()

    boolFound = False
    xwApp = xw.apps.active
    if xwApp:
        for book in xwApp.books:
            book: Book
            if book.name == fileName:
                boolFound = True
                excelObj.book = book
                excelObj.path = book.fullname
                excelObj.type = Path(book.fullname).suffix.replace(".", "")  # type: ignore
                break
        if not boolFound:
            raise FileNotFoundError(f"No open workbook with name '{fileName}' found")
        _print_xw_info(excelObj=excelObj)
        return excelObj
    else:
        raise ExcelError("No Workbook instance found.")


def _save(excelObj: ExcelObj) -> None:
    _check_edit_mode()
    excelObj.book.save()


@Log.trace()
def save(excelObj: ExcelObj) -> None:
    """
    Save the Excel workbook object.

    Parameters:
        excelObj: The Excel workbook object.
    """
    _save(excelObj=excelObj)


@Log.trace()
def save_as_and_reopen(excelObj: ExcelObj, destinationPath: str, password: str = "") -> str:
    """
    Saves the workbook to a new file and reopens it under the new name.

    Parameters:
        excelObj: The Excel workbook object.
        destinationPath: The path where the workbook will be saved.
        password: An optional password for saving the workbook.
    """
    _check_edit_mode()

    strFilePath = str(Path(destinationPath).absolute())
    if Path(strFilePath).is_file():
        raise ExcelError(f"The file '{strFilePath}' exists.")
    excelObj.book.save(path=strFilePath, password=password)
    return strFilePath


@Log.trace()
def close(excelObj: ExcelObj, save: bool = True) -> None:
    """
    Close the Excel workbook object.

    Parameters:
        excelObj: The Excel workbook object.
        save: If True, saves the workbook before closing.
    """
    _check_edit_mode()

    if save:
        _save(excelObj)
    excelObj.book.close()
    del excelObj


@Log.trace()
def activate_window(excelObj: ExcelObj) -> None:
    """
    Brings the Excel window to the front and restores it if minimized.

    Parameters:
        excelObj: The Excel workbook object.
    """

    def window_enum_handler(hwnd, resultList):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
            resultList.append((hwnd, win32gui.GetWindowText(hwnd)))

    def get_appropriate_window(fileName) -> None:
        listWindow = []
        win32gui.EnumWindows(window_enum_handler, listWindow)
        for hwnd, strWindowText in listWindow:
            if fileName in strWindowText and "Excel" in strWindowText:
                return hwnd

    hwnd = get_appropriate_window(Path(excelObj.path).name)
    if hwnd:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)  # Restore the window if it's minimized
        win32gui.SetForegroundWindow(hwnd)  # Bring the window to the front
    else:
        raise ExcelError(f"No window with title containing '{Path(excelObj.path).name}' found")


@Log.trace()
def get_last_row(excelObj: ExcelObj, sheet: TypeOfSheet, col: str | int | None = None) -> int:
    """
    Get the last row number of a given sheet.

    If a specific column is provided, it returns the last row number of that column.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The name or index(start from 0) of the sheet.
        col: The column (name or number) to check. If None, checks the entire sheet.

    Returns:
        int: The number of the last row with data in the specified sheet/column.
    """
    _check_edit_mode()
    sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)

    if col is None:
        return excelObj.book.sheets[sheet].used_range.last_cell.row
    else:
        col = _check_and_standardize_column(column=col)
        return excelObj.book.sheets[sheet].range(col + "1048576").end("up").row


@Log.trace()
def get_last_column(excelObj: ExcelObj, sheet: TypeOfSheet, row: int | None = None) -> tuple[str, int]:
    """
    Get the last column (number or name) of a given sheet.

    If a specific row is provided, it returns the last column of that row.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The name or index(start from 0) of the sheet.
        row: The row number to check. If None, checks the entire sheet.

    Returns:
        tuple[str,int]: The name and number of the last column with data in the specified sheet/row.
    """
    _check_edit_mode()
    sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)

    if row is None:
        intCol: int = excelObj.book.sheets[sheet].used_range.last_cell.column
        strCol: str = convert_col_num_to_str(colNum=intCol)
    else:
        intCol: int = excelObj.book.sheets[sheet].range("XFD" + str(row)).end("left").column
        strCol: str = convert_col_num_to_str(colNum=intCol)

    return strCol, intCol


@Log.trace()
def convert_col_num_to_str(colNum: int) -> str:
    strCol: str = xw.utils.col_name(colNum)
    return strCol


@Log.trace()
def convert_col_str_to_num(colStr: str) -> int:
    intCol = 0
    for char in colStr.upper():
        if char < "A" or char > "Z":
            raise ValueError(f"Invalid column string '{colStr}'")
        intCol = intCol * 26 + (ord(char) - ord("A")) + 1
    return intCol


@Log.trace()
def read_cell(excelObj: ExcelObj, sheet: TypeOfSheet, cell: TypeOfCell, returnDisplayed: bool = True) -> TypeOfCellData:
    """
    Read the value of a specific cell.

    Can return either the actual value or the displayed value.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The name or index(start from 0) of the sheet.
        cell: The cell to read, either as an address string or a [row, column] list.
        returnDisplayed: If True, returns the displayed value; otherwise, returns the actual value.

    Returns:
        TypeOfCellData: The value of the cell.
    """
    _check_edit_mode()
    sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)
    cell = _check_and_standardize_cell(cell=cell)

    Log.debug("Reading cell=" + cell)
    if returnDisplayed == True:
        return excelObj.book.sheets[sheet].range(cell).api.Text
    else:
        return excelObj.book.sheets[sheet].range(cell).value


@Log.trace()
def read_row(
    excelObj: ExcelObj, sheet: TypeOfSheet, startCell: TypeOfCell, returnDisplayed: bool = True
) -> list[TypeOfCellData]:
    """
    Reads an entire row in an Excel sheet starting from the specified cell.

    Can return either the actual values or the displayed values of the cells in the row.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The name or index(start from 0) of the sheet.
        startCell: The starting cell of the row to be read. Can be specified as a string (e.g., 'A1') or a list indicating the row and column [row, column].
        returnDisplayed: If True, returns the displayed values of the cells. If False, returns their actual values.

    Returns:
        list[TypeOfCellData]|None: A list of values from the specified row. Returns None if the starting cell is beyond the last column with data.
    """
    _check_edit_mode()
    sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)
    startCell = _check_and_standardize_cell(cell=startCell)

    # Extract row and column information from the starting cell
    _, intColStart, intRowStart = _extract_row_column_from_cell(cell=startCell)

    # Get the last column in the specified row
    strColStop, intColStop = get_last_column(excelObj=excelObj, sheet=sheet, row=intRowStart)

    # Check if the starting cell is beyond the last used cell in the row
    if intColStart > intColStop:
        Log.warning(f"The startCell({startCell}) is more right than the last cell in the row. Return empty list.")
        return []

    strRange = f"{startCell}:{strColStop}{intRowStart}"
    Log.debug(f"Reading range: {strRange}")
    range: Range = excelObj.book.sheets[sheet].range(strRange)
    if returnDisplayed == True:
        returnValue = [cell.api.Text for cell in range]
    else:
        returnValue = range.value

    if isinstance(returnValue, list):
        return returnValue
    else:
        # The startCell is the rightmost cell in the row, xlwings won't return a list, so nest it.
        return [returnValue]


@Log.trace()
def read_column(
    excelObj: ExcelObj, sheet: TypeOfSheet, startCell: TypeOfCell, returnDisplayed: bool = True
) -> list[TypeOfCellData] | None:
    """
    Reads an entire column in an Excel sheet starting from the specified cell.

    Can return either the actual values or the displayed values of the cells in the column.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The name or index(start from 0) of the sheet.
        startCell: The starting cell of the column to be read. Can be specified as a string (e.g., 'A1') or a list indicating the row and column [row, column].
        returnDisplayed: If True, returns the displayed values of the cells. If False, returns their actual values.

    Returns:
        list[TypeOfCellData]|None: A list of values from the specified column. Returns None if the starting cell is below the last row with data.
    """
    _check_edit_mode()
    sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)
    startCell = _check_and_standardize_cell(cell=startCell)

    # Extract row and column information from the starting cell
    strColStart, _, intRowStart = _extract_row_column_from_cell(cell=startCell)

    # Get the last row in the specified column
    intRowStop = get_last_row(excelObj=excelObj, sheet=sheet, col=strColStart)

    # Check if the starting cell is below the last used cell in the column
    if intRowStart > intRowStop:
        Log.warning(f"The startCell({startCell}) is more down than the last cell in the column. Return empty list.")
        return []

    strRange = f"{startCell}:{strColStart}{intRowStop}"
    Log.debug(f"Reading range: {strRange}")
    range: Range = excelObj.book.sheets[sheet].range(strRange)
    if returnDisplayed == True:
        returnValue = [cell.api.Text for cell in range]
    else:
        returnValue = range.value

    if isinstance(returnValue, list):
        return returnValue
    else:
        # The startCell is the downmost cell in the column, xlwings won't return a list, so nest it.
        return [returnValue]


def _get_endCell_if_not_provided(excelObj: ExcelObj, sheet: TypeOfSheet, endCell: TypeOfCell | None) -> str:
    # Determine the end cell if not provided
    if endCell is not None:
        endCell = _check_and_standardize_cell(cell=endCell)
    else:
        # Default to the last cell in the sheet if endCell is not specified
        endCell = get_last_column(excelObj=excelObj, sheet=sheet, row=None)[0] + str(
            get_last_row(excelObj=excelObj, sheet=sheet, col=None)
        )
        Log.debug(f"The argument endCell is None, get the last cell({endCell}).")

    return endCell


def _read_range(
    excelObj: ExcelObj,
    sheet: TypeOfSheet,
    startCell: TypeOfCell,
    endCell: TypeOfCell | None = None,
    returnDisplayed: bool = True,
) -> list[list[str]] | list[list[TypeOfCellData]] | None:
    sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)
    startCell = _check_and_standardize_cell(cell=startCell)
    endCell = _get_endCell_if_not_provided(excelObj=excelObj, sheet=sheet, endCell=endCell)

    # Extract row and column information for start and end cells
    _, intColStart, intRowStart = _extract_row_column_from_cell(cell=startCell)
    _, intColEnd, intEndRow = _extract_row_column_from_cell(cell=startCell)

    # Validate the range
    if intColStart > intColEnd and intRowStart > intEndRow:
        Log.debug(f"The startCell({startCell}) is beyond the endCell({endCell}). Return None")
        return None

    strRange = f"{startCell}:{endCell}"
    Log.debug(f"Reading range: {strRange}")
    range: Range = excelObj.book.sheets[sheet].range(strRange)

    if returnDisplayed == True:
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
        # list[list[TypeOfCellData]]
        return [[cell.value for cell in row] for row in range.rows]


@Log.trace()
def read_range_list(
    excelObj: ExcelObj,
    sheet: TypeOfSheet,
    startCell: TypeOfCell,
    endCell: TypeOfCell | None = None,
    returnDisplayed: bool = True,
) -> list[list[str]] | list[list[TypeOfCellData]] | None:
    """
    Reads a specified range from an Excel sheet and returns the data in the desired format.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The name or index(start from 0) of the sheet.
        startCell: The starting cell of the range.
        endCell: The ending cell of the range. If None, reads till the last cell.
        returnDisplayed: If True, returns the displayed values as string; otherwise, returns actual cell values(TypeOfCellData).

    Returns:
        list[list[str]] | list[list[TypeOfCellData]] | None: The data from the specified range in the chosen format. | None
    """
    _check_edit_mode()
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
    sheet: TypeOfSheet,
    startCell: TypeOfCell,
    endCell: TypeOfCell | None = None,
    addTitle: bool = True,
    returnDisplayed: bool = True,
) -> pandas.DataFrame | None:
    """
    Reads a specified range from an Excel sheet and returns the data in the desired format.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The name or index(start from 0) of the sheet.
        startCell: The starting cell of the range.
        endCell: The ending cell of the range. If None, reads till the last cell.
        addTitle: If True, uses the first row as headers.
        returnDisplayed: If True, returns the displayed values as string; otherwise, returns actual cell values(TypeOfCellData).

    Returns:
        pandas.DataFrame | None
    """
    _check_edit_mode()
    listRange = _read_range(
        excelObj=excelObj,
        sheet=sheet,
        startCell=startCell,
        endCell=endCell,
        returnDisplayed=returnDisplayed,
    )
    if listRange is None:
        return None

    if addTitle:
        dfRange = pandas.DataFrame(data=listRange[1:], index=None, columns=listRange[0])
    else:
        dfRange = pandas.DataFrame(data=listRange, index=None, columns=None)

    return dfRange


@Log.trace()
def write_cell(
    excelObj: ExcelObj,
    sheet: TypeOfSheet,
    cell: TypeOfCell,
    data: TypeOfCellData,
    save: bool = False,
) -> None:
    """
    Writes data to a specified cell in an Excel sheet.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The name or index(start from 0) of the sheet.
        cell: The cell to write to, specified as a string (e.g., 'A1') or a list [row, column].
        data: The data to write to the cell.
        save: If True, saves the workbook immediately after writing.
    """
    _check_edit_mode()
    sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)
    cell = _check_and_standardize_cell(cell=cell)

    Log.debug(f"Writing cell: {cell}")
    excelObj.book.sheets[sheet].range(cell).value = data

    if save:
        _save(excelObj=excelObj)


@Log.trace()
def write_row(
    excelObj: ExcelObj,
    sheet: TypeOfSheet,
    startCell: TypeOfCell,
    data: list[TypeOfCellData],
    save: bool = False,
) -> None:
    """
    Writes a list of data to a row in an Excel sheet starting from a specified cell.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The name or index(start from 0) of the sheet.
        startCell: The starting cell of the row.
        data: A list of data to be written to the row.
        save: If True, saves the workbook immediately after writing.
    """
    _check_edit_mode()
    sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)
    startCell = _check_and_standardize_cell(cell=startCell)

    # For debugging purposes, print the range.
    _, intColStart, intRowStart = _extract_row_column_from_cell(cell=startCell)
    strColEnd = convert_col_num_to_str(colNum=(intColStart + len(data) - 1))
    endCell = strColEnd + str(intRowStart)
    strRange = f"{startCell}:{endCell}"
    Log.debug(f"Writing range: {strRange}")

    excelObj.book.app.screen_updating = False

    try:
        excelObj.book.sheets[sheet].range(startCell).value = data
    finally:
        excelObj.book.app.screen_updating = True

    if save:
        _save(excelObj=excelObj)


@Log.trace()
def write_column(
    excelObj: ExcelObj,
    sheet: TypeOfSheet,
    startCell: TypeOfCell,
    data: list[TypeOfCellData],
    save: bool = False,
) -> None:
    """
    Writes a list of data to a column in an Excel sheet starting from a specified cell.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The name or index(start from 0) of the sheet.
        startCell: The starting cell of the column.
        data: A list of data to be written to the column.
        save: If True, saves the workbook immediately after writing.
    """
    _check_edit_mode()
    sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)
    startCell = _check_and_standardize_cell(cell=startCell)

    # For debugging purposes, print the range.
    strColStart, _, intRowStart = _extract_row_column_from_cell(cell=startCell)
    endCell = strColStart + str(intRowStart + len(data) - 1)
    strRange = f"{startCell}:{endCell}"
    Log.debug(f"Writing range: {strRange}")

    excelObj.book.app.screen_updating = False

    try:
        excelObj.book.sheets[sheet].range(startCell).options(transpose=True).value = data
    finally:
        excelObj.book.app.screen_updating = True

    if save:
        _save(excelObj=excelObj)


@Log.trace()
def write_range(
    excelObj: ExcelObj,
    sheet: TypeOfSheet,
    startCell: TypeOfCell,
    data: pandas.DataFrame | list[list[TypeOfCellData]] | None,
    writeTitleRow: bool = True,
    save: bool = False,
) -> None:
    """
    Writes a pandas DataFrame or a 2D list to a specified range in an Excel sheet.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The name or index(start from 0) of the sheet.
        startCell: The starting cell for the data range.
        data: The data to write, either as a DataFrame or a 2D list.
        writeTitleRow: If True, includes the DataFrame's column titles, or the first item of the 2D list.
        save: If True, saves the workbook immediately after writing.
    """

    if data is None:
        Log.warning("The argument data is None.")
        return None

    _check_edit_mode()
    sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)
    startCell = _check_and_standardize_cell(cell=startCell)

    # For debugging purposes, print the range.
    _, intColStart, intRowStart = _extract_row_column_from_cell(cell=startCell)
    if isinstance(data, pandas.DataFrame):
        strColEnd = convert_col_num_to_str(colNum=(intColStart + len(data.columns) - 1))
        if writeTitleRow:
            endCell = strColEnd + str(intRowStart + len(data))
        else:
            endCell = strColEnd + str(intRowStart + len(data) - 1)
    else:
        strColEnd = convert_col_num_to_str(colNum=(intColStart + len(data[0]) - 1))
        if writeTitleRow:
            endCell = strColEnd + str(intRowStart + len(data) - 1)
        else:
            endCell = strColEnd + str(intRowStart + len(data) - 2)
    strRange = f"{startCell}:{endCell}"
    Log.debug(f"Writing range: {strRange}")

    excelObj.book.app.screen_updating = False

    try:
        if isinstance(data, pandas.DataFrame):
            excelObj.book.sheets[sheet].range(startCell).options(index=False, header=writeTitleRow).value = data
        else:
            if writeTitleRow:
                excelObj.book.sheets[sheet].range(startCell).value = data
            else:
                excelObj.book.sheets[sheet].range(startCell).value = data[1:]
    finally:
        excelObj.book.app.screen_updating = True

    if save:
        _save(excelObj=excelObj)


@Log.trace()
def insert_row(
    excelObj: ExcelObj,
    sheet: TypeOfSheet,
    startCell: TypeOfCell,
    data: list[TypeOfCellData],
    save: bool = False,
) -> None:
    """
    Create a new empty row and then write a list of data to a row in an Excel sheet starting from a specified cell.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The name or index(start from 0) of the sheet.
        startCell: The starting cell of the row.
        data: A list of data to be written to the row.
        save: If True, saves the workbook immediately after inserting.
    """
    _check_edit_mode()
    sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)
    startCell = _check_and_standardize_cell(cell=startCell)

    _, _, intRowStart = _extract_row_column_from_cell(cell=startCell)

    excelObj.book.sheets[sheet].range(f"{intRowStart}:{intRowStart}").insert(
        shift="down", copy_origin="format_from_left_or_above"
    )

    write_row(excelObj=excelObj, sheet=sheet, startCell=startCell, data=data, save=save)


@Log.trace()
def insert_column(
    excelObj: ExcelObj,
    sheet: TypeOfSheet,
    startCell: TypeOfCell,
    data: list[TypeOfCellData],
    save: bool = False,
) -> None:
    """
    Create a new empty row and then write a list of data to a column in an Excel sheet starting from a specified cell.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The name or index(start from 0) of the sheet.
        startCell: The starting cell of the column.
        data: A list of data to be written to the column.
        save: If True, saves the workbook immediately after inserting.
    """
    _check_edit_mode()
    sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)
    startCell = _check_and_standardize_cell(cell=startCell)

    strColStart, _, _ = _extract_row_column_from_cell(cell=startCell)

    excelObj.book.sheets[sheet].range(f"{strColStart}:{strColStart}").insert(
        shift="right", copy_origin="format_from_left_or_above"
    )

    write_column(excelObj=excelObj, sheet=sheet, startCell=startCell, data=data, save=save)


@Log.trace()
def delete_row(excelObj: ExcelObj, sheet: TypeOfSheet, cell: TypeOfCell, save: bool = False) -> None:
    """
    Delete the row of the cell and move the next row up.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The name or index(start from 0) of the sheet.
        cell: A cell whthin the row to delete.
        save: If True, saves the workbook immediately after deleting.
    """
    _check_edit_mode()
    sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)
    cell = _check_and_standardize_cell(cell=cell)

    _, _, intRowStart = _extract_row_column_from_cell(cell=cell)

    Log.debug(f"Deleting row: {intRowStart}")

    excelObj.book.sheets[sheet].range(f"{intRowStart}:{intRowStart}").delete(shift="up")

    if save:
        _save(excelObj=excelObj)


@Log.trace()
def delete_column(excelObj: ExcelObj, sheet: TypeOfSheet, cell: TypeOfCell, save: bool = False) -> None:
    """
    Delete the column of the cell and move the next column left.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The name or index(start from 0) of the sheet.
        cell: A cell whthin the column to delete.
        save: If True, saves the workbook immediately after deleting.
    """

    _check_edit_mode()
    sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)
    cell = _check_and_standardize_cell(cell=cell)

    strColStart, _, _ = _extract_row_column_from_cell(cell=cell)

    Log.debug(f"Deleting column: {strColStart}")

    excelObj.book.sheets[sheet].range(f"{strColStart}:{strColStart}").delete(shift="left")

    if save:
        _save(excelObj=excelObj)


@Log.trace()
def select_range(excelObj: ExcelObj, sheet: TypeOfSheet, startCell: TypeOfCell, endCell: TypeOfCell | None) -> None:
    """
    Select the specific range.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The name or index(start from 0) of the sheet.
        startCell: The starting cell of the range.
        endCell: The ending cell of the range.  If None, select till the last cell.
    """
    _check_edit_mode()
    sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)
    startCell = _check_and_standardize_cell(cell=startCell)
    endCell = _get_endCell_if_not_provided(excelObj=excelObj, sheet=sheet, endCell=endCell)

    strRange = f"{startCell}:{endCell}"
    Log.debug(f"Selecting range: {strRange}")

    activate_sheet(excelObj=excelObj, sheet=sheet)
    excelObj.book.sheets[sheet].range(f"{startCell}:{endCell}").select()


@Log.trace()
def get_selected_cells(excelObj: ExcelObj) -> list[str]:
    """
    Get the list of all selected cells of the current activated sheet.

    Parameters:
        excelObj: The Excel workbook object.

    Returns:
        list[str]: A list of selected ranges, with addresses in standard Excel format (e.g., 'A1:B2').
    """
    _check_edit_mode()
    rangeSelected = excelObj.book.selection
    if not rangeSelected:
        raise ExcelError("No range is selected in the active sheet.")
    return [str(cell.address).replace("$", "") for cell in rangeSelected]


@Log.trace()
def get_selected_range(excelObj: ExcelObj) -> list[str]:
    """
    Get the list of all selected ranges of the current activated sheet.

    Parameters:
        excelObj: The Excel workbook object.

    Returns:
        list[str]: A list of selected cells, with addresses in standard Excel format (e.g., 'A1').
    """
    _check_edit_mode()
    rangeSelected = excelObj.book.selection
    if not rangeSelected:
        raise ExcelError("Not select any range.")
    return [range.replace("$", "") for range in str(rangeSelected.address).split(",")]


@Log.trace()
def clear_range(
    excelObj: ExcelObj,
    sheet: TypeOfSheet,
    startCell: TypeOfCell,
    endCell: TypeOfCell | None,
    clearContent: bool = True,
    clearFormat: bool = True,
    save: bool = False,
) -> None:
    """
    Clear the content or format of the range.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The name or index(start from 0) of the sheet.
        startCell: The starting cell of the range.
        endCell: The ending cell of the range.  If None, clear till the last cell.
        clearContent: Whether clear contents of the range.
        clearFormat: Whether clear format of the range.
        save: If True, saves the workbook immediately after clearing.
    """

    if clearContent == False and clearFormat == False:
        raise ValueError("At least oneof the argument clearContents or clearFormats must be True")

    _check_edit_mode()
    sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)
    startCell = _check_and_standardize_cell(cell=startCell)
    endCell = _get_endCell_if_not_provided(excelObj=excelObj, sheet=sheet, endCell=endCell)

    strRange = f"{startCell}:{endCell}"
    Log.debug(f"Clearing range: {strRange}, clearContents: {clearContent}, clearFormats: {clearFormat}")
    range: Range = excelObj.book.sheets[sheet].range(f"{startCell}:{endCell}")
    if clearContent == True and clearFormat == True:
        range.clear()
    elif clearContent == True:
        range.clear_contents()
    else:
        # clearFormats == True
        range.clear_formats()

    if save:
        _save(excelObj=excelObj)


@Log.trace()
def activate_sheet(excelObj: ExcelObj, sheet: TypeOfSheet) -> None:
    """
    Activate sheet by name or index.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The name or index(start from 0) of the sheet.
    """
    _check_edit_mode()
    sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)
    Log.debug(f"Activating sheet: {sheet}")
    excelObj.book.sheets[sheet].activate()


def _check_sheet_name_compliance(sheetName: str) -> None:
    """
    The max. length of a sheet name is 31 characters.
    A sheet name must not contain any of the following characters: \\ / ? * [ ]
    A sheet name can't be empty.
    """
    if sheetName == "":
        raise ValueError(f"Sheet name should not be empty.")
    listErrorChar = ["\\", "/", "?", "*", "[", "]"]
    for item in listErrorChar:
        if sheetName.find(item) != -1:
            raise ValueError(f"Sheet name should not contain any one of {listErrorChar}")
    if len(sheetName) > 31:
        raise ValueError(f"Sheet name should not be longer than 31 characters. Current: {len(sheetName)}")


def _check_sheet_name_exist(excelObj: ExcelObj, sheetName: str) -> None:
    listCurrentSheetName = [sheet.name for sheet in excelObj.book.sheets]
    if sheetName in listCurrentSheetName:
        raise ValueError(
            f"The new sheet name({sheetName}) has been used in target Excel workbook object: {listCurrentSheetName}"
        )


@Log.trace()
def add_sheet(
    excelObj: ExcelObj,
    newSheetName: str,
    anchorSheet: TypeOfSheet = "Sheet1",
    direction: Literal["before", "after"] = "after",
    save: bool = False,
) -> None:
    """
    Add a new sheet in specific position.

    Parameters:
        excelObj: The Excel workbook object.
        newSheetName: The new sheet's name.
        anchorSheet: The new sheet will add before or after the anchor sheet.
        direction: Options are "before" and "after".
        save: If True, saves the workbook immediately after adding.
    """

    _check_edit_mode()
    _check_sheet_name_compliance(sheetName=newSheetName)
    _check_sheet_name_exist(excelObj=excelObj, sheetName=newSheetName)

    anchorSheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=anchorSheet)
    if direction not in ["before", "after"]:
        raise ValueError("The argument direction should be 'before' or 'after'.")
    if direction == "before":
        excelObj.book.sheets.add(name=newSheetName, before=anchorSheet, after=None)
    else:
        # after
        excelObj.book.sheets.add(name=newSheetName, before=None, after=anchorSheet)

    if save:
        _save(excelObj=excelObj)


@Log.trace()
def rename_sheet(excelObj: ExcelObj, sheet: TypeOfSheet, newSheetName: str, save: bool = False) -> None:
    """
    Rename a sheet.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The name or index(start from 0) of the sheet.
        newSheetName: The sheet's new name.
        save: If True, saves the workbook immediately after renaming.
    """
    _check_edit_mode()
    _check_sheet_name_compliance(sheetName=newSheetName)

    sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)
    Log.debug(f"Renaming sheet: {sheet} -> {newSheetName}")
    excelObj.book.sheets[sheet].name = newSheetName

    if save:
        _save(excelObj=excelObj)


@Log.trace()
def copy_sheet(
    srcExcelObj: ExcelObj,
    srcSheet: TypeOfSheet,
    dstExcelObj: ExcelObj,
    dstAnchorSheet: TypeOfSheet,
    newSheetName: str,
    direction: Literal["before", "after"] = "after",
    save: bool = False,
) -> None:
    """
    Copy a sheet.

    Parameters:
        srcExcelObj: The Excel workbook object that copy from.
        srcSheet: The sheet name or index(start from 0) in the source workbook.
        dstExcelObj: The Excel workbook object that copy into.
        dstAnchorSheet: The new sheet will add before or after the anchor sheet in the dstExcelObj.
        newSheetName: The sheet's new name.
        direction: Options are "before" and "after".
        save: If True, saves the workbook immediately after copying.
    """

    _check_edit_mode()
    _check_sheet_name_compliance(sheetName=newSheetName)
    _check_sheet_name_exist(excelObj=dstExcelObj, sheetName=newSheetName)

    srcSheet = _check_and_standardize_sheet(excelObj=srcExcelObj, sheet=srcSheet)
    dstAnchorSheet = _check_and_standardize_sheet(excelObj=dstExcelObj, sheet=dstAnchorSheet)

    Log.debug(
        f"Coping sheet from {srcExcelObj}-{srcSheet} to {dstExcelObj}-{dstAnchorSheet}'s {direction}, new sheet name is {newSheetName}"
    )

    if direction not in ["before", "after"]:
        raise ValueError("The argument direction should be 'before' or 'after'.")
    if direction == "before":
        srcExcelObj.book.sheets[srcSheet].copy(
            name=newSheetName, before=dstExcelObj.book.sheets[dstAnchorSheet], after=None
        )
    else:
        # after
        srcExcelObj.book.sheets[srcSheet].copy(
            name=newSheetName, before=None, after=dstExcelObj.book.sheets[dstAnchorSheet]
        )

    if save:
        _save(excelObj=dstExcelObj)


@Log.trace()
def delete_sheet(excelObj: ExcelObj, sheet: TypeOfSheet, save: bool = False) -> None:
    """
    Delete a sheet.

    Parameters:
        excelObj: The Excel workbook object.
        sheet: The name or index(start from 0) of the sheet.
        save: If True, saves the workbook immediately after writing.
    """
    _check_edit_mode()
    sheet = _check_and_standardize_sheet(excelObj=excelObj, sheet=sheet)
    Log.debug(f"Deleting sheet: {sheet}")
    excelObj.book.sheets[sheet].delete()

    if save:
        _save(excelObj=excelObj)


@Log.trace()
def get_activate_sheet(excelObj: ExcelObj) -> str:
    """
    Get the current activated sheet's name.

    Parameters:
        excelObj: The Excel workbook object.
    """
    _check_edit_mode()
    return excelObj.book.sheets.active.name


@Log.trace()
def get_sheet_list(excelObj: ExcelObj) -> list[str]:
    """
    Get the list of all sheets' names of the Excel workbook object.

    Parameters:
        excelObj: The Excel workbook object.
    """
    _check_edit_mode()
    return [sheet.name for sheet in excelObj.book.sheets]


@Log.trace()
def run_macro(excelObj: ExcelObj, macroName: str, arguments: list[Any] = []) -> Any:
    """
    Run a macro of a xlsm file.

    Parameters:
        excelObj: The Excel workbook object(.xlsm file).
        macroName: Name of Sub or Function with or without module name, e.g., 'Module1.MyMacro' or 'MyMacro'
        arguments: The list of arguments that will send into the macro function.

    Returns:
        The returned value of the marco.
    """
    _check_edit_mode()
    try:
        result = excelObj.book.macro(name=macroName)(*arguments)
    except Exception as e:
        raise ExcelError(f"Failed to run macro '{macroName}': {e} Please check the macroName and Excel config.")
    else:
        return result


if __name__ == "__main__":
    # excelObj = bind_Excel_file(fileName="1.xlsm")

    # temp = get_selected_cells(excelObj=excelObj)
    # print(temp)
    # print(get_selected_range(excelObj=excelObj))
    # run_macro(excelObj=excelObj,macroName="MyMacro")
    # print(run_macro(excelObj=excelObj, macroName="MultiplyByTwo1", arguments=[6]))
    # excelObj.book.macro("宏1")()
    # excelObj.book.macro("MyMacro")()

    excelObj = bind_Excel_file(fileName="1.xls")
    from time import sleep

    # print("Delay.")
    # sleep(3)
    # print(read_cell(excelObj=excelObj, sheet="Sheet3", cell="A1", returnDisplayed=True))
    # activate_window(excelObj=excelObj)
    write_cell(excelObj=excelObj, sheet="Sheet3", cell="C32", data="123")
