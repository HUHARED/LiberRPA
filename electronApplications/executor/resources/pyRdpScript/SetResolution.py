# FileName: SetResolution.py

import argparse
import ctypes
from ctypes import wintypes


# Define some needed types and structures.
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


def set_display_resolution(width, height) -> None:
    user32 = ctypes.windll.user32
    ENUM_CURRENT_SETTINGS = -1

    devmode = DEVMODE()
    devmode.dmSize = ctypes.sizeof(DEVMODE)

    # Get the current settings.
    # The first argument is "None" means the main screen.
    if user32.EnumDisplaySettingsW(None, ENUM_CURRENT_SETTINGS, ctypes.byref(devmode)) == 0:
        raise Exception("Failed to get current display settings")

    # Change the resolution values.
    devmode.dmPelsWidth = width
    devmode.dmPelsHeight = height
    # Set dmFields flag to indicate which settings are being changed:
    DM_PELSWIDTH = 0x80000
    DM_PELSHEIGHT = 0x100000
    devmode.dmFields = DM_PELSWIDTH | DM_PELSHEIGHT

    result = user32.ChangeDisplaySettingsW(ctypes.byref(devmode), 0)
    if result != 0:
        raise Exception(f"Failed to change display settings: error code {result}")
    else:
        print(f"Display resolution set to {width} x {height}", flush=True)


try:
    boolIsAdmin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    print(f"Running as Admin: {boolIsAdmin}", flush=True)
    if not boolIsAdmin:
        raise Exception("Executor is not ran as administrator.")

    parser = argparse.ArgumentParser()
    parser.add_argument("--width", required=True, type=int)
    parser.add_argument("--height", required=True, type=int)
    args, unknown = parser.parse_known_args()

    if args.width and args.height:
        set_display_resolution(args.width, args.height)
except Exception as e:
    print(e, flush=True)
