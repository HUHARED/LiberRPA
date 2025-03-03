# FileName: _Image.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.Common._Exception import UiElementNotFoundError
from liberrpa.Common._TypedValue import DictImageAttr
from liberrpa.UI._Screenshot import (
    SCREENSHOT_DOCUMENTS_PATH,
    FULL_SCREENSHOT_PATH,
    SCREENSHOT_PROJECT_PATH,
    capture_all_screen,
    create_screenshot_manually,
)

import pyautogui
import os
import shutil


def find_image(
    fileName: str,
    region: tuple[int, int, int, int] | None,
    confidence: float,
    grayscale: bool = True,
    limit: int = 1,
    moveFile: bool = True,
    buildinPath: bool = True,
) -> list[DictImageAttr]:

    # When other build-in modules invoke the function, "fileName" should be a fullname, but if UiInterface module invokes it ,"fileName" should be a path.
    if buildinPath:
        # Check whether file exists
        if not os.path.isfile(os.path.join(SCREENSHOT_PROJECT_PATH, fileName)):
            if not os.path.isfile(os.path.join(SCREENSHOT_DOCUMENTS_PATH, fileName)):
                raise FileNotFoundError(
                    f"Not found the image file '{fileName}' in '{SCREENSHOT_PROJECT_PATH}' or '{SCREENSHOT_DOCUMENTS_PATH}'."
                )
            else:
                # If UI Analyzer call it, should not move the file. And a normal RPA project should move the file.
                if moveFile:
                    # Move it to SCREENSHOT_PROJECT_PATH
                    os.makedirs(SCREENSHOT_PROJECT_PATH, exist_ok=True)
                    strFilePath = os.path.abspath(
                        shutil.move(
                            src=os.path.join(SCREENSHOT_DOCUMENTS_PATH, fileName),
                            dst=os.path.join(SCREENSHOT_PROJECT_PATH, fileName),
                        )
                    )
                    Log.info(f"Move '{fileName}' from '{SCREENSHOT_DOCUMENTS_PATH}' to '{SCREENSHOT_PROJECT_PATH}'.")
                else:
                    strFilePath = os.path.join(SCREENSHOT_DOCUMENTS_PATH, fileName)
                    Log.info("File in Documents.")
        else:
            strFilePath = os.path.join(SCREENSHOT_PROJECT_PATH, fileName)
            Log.verbose("File in project.")
    else:
        strFilePath = fileName

    try:
        # puautogui can't locate image in non-main screen, so save all screens as an image.
        _, intMinX, intMinY = capture_all_screen()

        # The region's x&y is the window element's real position relative to the (0,0), should modify it relative the the FULL_SCREENSHOT
        if region is not None:
            listRegion = list(region)
            listRegion[0] = listRegion[0] - intMinX
            listRegion[1] = listRegion[1] - intMinY
            region = tuple(listRegion)  # type: ignore - it's 4 int.

        Log.verbose(f"region={region}")

        generator = pyautogui.locateAll(
            needleImage=strFilePath,
            haystackImage=FULL_SCREENSHOT_PATH,
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
        raise UiElementNotFoundError(str(e))

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
    create_screenshot_manually()
