# FileName: _Image.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.Common._Exception import UiElementNotFoundError, UiSelectorError, get_exception_info
from liberrpa.UI._UiDict import DictImageAttr
from liberrpa.Common._TypedValue import StrPath
from liberrpa.UI._ScreenshotPath import (
    PATH_SCREENSHOT_DOCUMENTS,
    STR_FULL_SCREENSHOT,
    get_managed_screenshot_file_candidates,
    move_documents_screenshot_to_project,
)
from liberrpa.UI._Screenshot import (
    capture_all_screen,
    create_screenshot_manually,
)

import pyautogui
import os
from typing import cast


def _get_image_path(
    fileNameOrPath: StrPath,
    moveFile: bool = True,
    inScreenshotFolder: bool = True,
) -> str:
    # Built-in SelectorImage calls pass a file name. UiInterface.get_image_position passes an explicit path and inScreenshotFolder is False.
    if not inScreenshotFolder:
        return os.fspath(fileNameOrPath)

    listCandidate = get_managed_screenshot_file_candidates(fileNameOrPath)
    if len(listCandidate) > 1:
        strCandidate = "\n".join(f"- {pathCandidate}" for pathCandidate in listCandidate)
        raise UiSelectorError(
            f"Multiple screenshot files named {os.fspath(fileNameOrPath)!r} were found:\n{strCandidate}"
        )

    if len(listCandidate) == 1:
        Log.verbose(f"SelectorImage screenshot found in Project: {listCandidate[0]}")
        return str(listCandidate[0])

    pathDocuments = PATH_SCREENSHOT_DOCUMENTS / os.fspath(fileNameOrPath)
    if not pathDocuments.is_file():
        raise FileNotFoundError(
            f"SelectorImage screenshot {os.fspath(fileNameOrPath)!r} was not found in the current Project or in {PATH_SCREENSHOT_DOCUMENTS}."
        )

    if not moveFile:
        Log.verbose(f"SelectorImage screenshot found in Documents: {pathDocuments}")
        return str(pathDocuments)

    pathMoved = move_documents_screenshot_to_project(fileNameOrPath)
    Log.info(f"Moved SelectorImage screenshot from {pathDocuments} to {pathMoved}.")
    return str(pathMoved)


def find_image(
    fileNameOrPath: StrPath,
    region: tuple[int, int, int, int] | None,
    confidence: float,
    grayscale: bool = True,
    limit: int = 1,
    moveFile: bool = True,
    inScreenshotFolder: bool = True,
) -> list[DictImageAttr]:

    strFilePath = _get_image_path(
        fileNameOrPath=fileNameOrPath, moveFile=moveFile, inScreenshotFolder=inScreenshotFolder
    )

    try:
        # puautogui can't locate image in non-main screen, so save all screens as an image.
        _, intMinX, intMinY = capture_all_screen()

        # The region's x&y is the window element's real position relative to the (0,0), should modify it relative the the FULL_SCREENSHOT
        if region is not None:
            listRegion = list(region)
            listRegion[0] = listRegion[0] - intMinX
            listRegion[1] = listRegion[1] - intMinY

            boolNegativeCoordinate = False
            if listRegion[0] < 0:
                listRegion[2] = listRegion[2] + listRegion[0]
                listRegion[0] = 0
                boolNegativeCoordinate = True
            if listRegion[1] < 0:
                listRegion[3] = listRegion[3] + listRegion[1]
                listRegion[1] = 0
                boolNegativeCoordinate = True
            if boolNegativeCoordinate:
                Log.verbose(f"The Window's top-left is not in the screen, search region={listRegion}")

            region = cast(tuple[int, int, int, int], tuple(listRegion))

        Log.verbose(f"region={region}")

        generator = pyautogui.locateAll(
            needleImage=strFilePath,
            haystackImage=STR_FULL_SCREENSHOT,
            region=region,
            grayscale=grayscale,
            confidence=confidence,
            limit=limit,
        )
        listMatches: list[DictImageAttr] = [
            {
                "secondary-x": str(box.left + intMinX),
                "secondary-y": str(box.top + intMinY),
                "secondary-width": str(box.width),
                "secondary-height": str(box.height),
            }
            for box in generator
        ]
        Log.debug(f"Found {len(listMatches)} matched images.")
    except Exception as e:
        raise UiElementNotFoundError(str(get_exception_info(e))) from e

    return listMatches


if __name__ == "__main__":
    """from liberrpa.UI._Overlay import create_overlay

    listTemp = list(
        find_image(
            fileName="captured_temp.png", region=None, confidence=0.9, grayscale=True, limit=1000, moveFile=False
        )
    )
    print(listTemp)
    for position in listTemp:
        create_overlay(
            x=int(position["secondary-x"]),
            y=int(position["secondary-y"]),
            width=int(position["secondary-width"]),
            height=int(position["secondary-height"]),
            duration=200,
        )"""
    create_screenshot_manually(timeoutSeconds=10)
