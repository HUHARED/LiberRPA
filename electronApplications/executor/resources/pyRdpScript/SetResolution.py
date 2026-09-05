# FileName: SetResolution.py

import argparse
import ctypes
from ctypes import wintypes
import sys


# Define the Windows display settings structure used by ChangeDisplaySettingsW.
class DEVMODE(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", wintypes.WCHAR * 32),
        ("dmSpecVersion", wintypes.WORD),
        ("dmDriverVersion", wintypes.WORD),
        ("dmSize", wintypes.WORD),
        ("dmDriverExtra", wintypes.WORD),
        ("dmFields", wintypes.DWORD),
        ("dmOrientation", wintypes.SHORT),
        ("dmPaperSize", wintypes.SHORT),
        ("dmPaperLength", wintypes.SHORT),
        ("dmPaperWidth", wintypes.SHORT),
        ("dmScale", wintypes.SHORT),
        ("dmCopies", wintypes.SHORT),
        ("dmDefaultSource", wintypes.SHORT),
        ("dmPrintQuality", wintypes.SHORT),
        ("dmColor", wintypes.SHORT),
        ("dmDuplex", wintypes.SHORT),
        ("dmYResolution", wintypes.SHORT),
        ("dmTTOption", wintypes.SHORT),
        ("dmCollate", wintypes.SHORT),
        ("dmFormName", wintypes.WCHAR * 32),
        ("dmLogPixels", wintypes.WORD),
        ("dmBitsPerPel", wintypes.DWORD),
        ("dmPelsWidth", wintypes.DWORD),
        ("dmPelsHeight", wintypes.DWORD),
        ("dmDisplayFlags", wintypes.DWORD),
        ("dmDisplayFrequency", wintypes.DWORD),
        ("dmICMMethod", wintypes.DWORD),
        ("dmICMIntent", wintypes.DWORD),
        ("dmMediaType", wintypes.DWORD),
        ("dmDitherType", wintypes.DWORD),
        ("dmReserved1", wintypes.DWORD),
        ("dmReserved2", wintypes.DWORD),
        ("dmPanningWidth", wintypes.DWORD),
        ("dmPanningHeight", wintypes.DWORD),
    ]


def set_display_resolution(width: int, height: int) -> None:
    user32 = ctypes.windll.user32
    ENUM_CURRENT_SETTINGS = -1

    devmode = DEVMODE()
    devmode.dmSize = ctypes.sizeof(DEVMODE)

    # Get the current settings.
    # The first argument is "None" means the main screen.
    if (
        user32.EnumDisplaySettingsW(None, ENUM_CURRENT_SETTINGS, ctypes.byref(devmode))
        == 0
    ):
        raise RuntimeError("Failed to get current display settings.")

    if devmode.dmPelsWidth == width and devmode.dmPelsHeight == height:
        print(f"Display resolution is already {width} x {height}.", flush=True)
        return

    # Change the resolution values.
    devmode.dmPelsWidth = width
    devmode.dmPelsHeight = height
    # Set dmFields flag to indicate which settings are being changed:
    DM_PELSWIDTH = 0x80000
    DM_PELSHEIGHT = 0x100000
    devmode.dmFields = DM_PELSWIDTH | DM_PELSHEIGHT

    result = user32.ChangeDisplaySettingsW(ctypes.byref(devmode), 0)
    if result != 0:
        dictResultDescription = {
            1: (
                "DISP_CHANGE_RESTART",
                "the computer must be restarted for the mode to take effect",
            ),
            -1: (
                "DISP_CHANGE_FAILED",
                "the display driver failed the requested graphics mode",
            ),
            -2: (
                "DISP_CHANGE_BADMODE",
                "the graphics mode is not supported by the current display driver",
            ),
            -3: (
                "DISP_CHANGE_NOTUPDATED",
                "the display settings could not be written",
            ),
            -4: (
                "DISP_CHANGE_BADFLAGS",
                "an invalid set of display flags was supplied",
            ),
            -5: (
                "DISP_CHANGE_BADPARAM",
                "an invalid display parameter was supplied",
            ),
            -6: (
                "DISP_CHANGE_BADDUALVIEW",
                "the requested mode is not supported in the current DualView configuration",
            ),
        }
        strResultName, strResultDescription = dictResultDescription.get(
            result, ("UNKNOWN", "Windows returned an unknown display settings result")
        )
        raise RuntimeError(
            f"Failed to set display resolution to {width}x{height}: "
            f"{strResultName} ({result}), {strResultDescription}."
        )

    print(f"Display resolution set to {width} x {height}", flush=True)


def main() -> None:
    boolIsAdmin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    print(f"Running as Admin: {boolIsAdmin}", flush=True)
    if not boolIsAdmin:
        raise RuntimeError("Executor is not running as administrator.")

    parser = argparse.ArgumentParser()
    parser.add_argument("--width", required=True, type=int)
    parser.add_argument("--height", required=True, type=int)
    args = parser.parse_args()
    if args.width <= 0 or args.height <= 0:
        raise ValueError("Display width and height must be positive integers.")

    set_display_resolution(args.width, args.height)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(e, file=sys.stderr, flush=True)
        sys.exit(1)
