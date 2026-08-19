# FileName: Modules.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


"""
Public entry points for LiberRPA snippets and user scripts.

This module intentionally exposes a small set of user-facing objects through
lazy imports. It keeps the old import style compatible:

    from liberrpa.Modules import *

and also supports the future managed import block:

    from liberrpa.Modules import (
        Mouse,
    )

When importing specific names, unrelated LiberRPA modules are not imported until
they are actually requested.
"""

from typing import TYPE_CHECKING, Any
import importlib

# Keep this order aligned with snippets/ApiConfig.py PUBLIC_MODULE_ORDER and import_manifest.json generation.
__all__ = [
    # Basic module
    "Log",
    "delay",
    "get_component_resource_path",
    # UI element manipulation
    "Mouse",
    "Keyboard",
    "Window",
    "UiInterface",
    # Common software manipulation
    "Browser",
    "Excel",
    "Outlook",
    "Application",
    "Database",
    # Data processing
    "Data",
    "Str",
    "List",
    "Dict",
    "Regex",
    "Math",
    "Time",
    "File",
    "OCR",
    # Web protocol
    "Web",
    "Mail",
    "FTP",
    # System information
    "Clipboard",
    "System",
    "Credential",
    # User interaction
    "ScreenPrint",
    "Dialog",
    "Trigger",
    # Special snippet helpers
    "DatabaseConnection",
    "PrjArgs",
    "CustomArgs",
    # Selector types
    "SelectorWindow",
    "SelectorUia",
    "SelectorHtml",
    "SelectorImage",
    "Selector",
]

_LAZY_MODULE_EXPORTS: dict[str, str] = {
    # UI element manipulation
    "Mouse": "liberrpa.Mouse",
    "Keyboard": "liberrpa.Keyboard",
    "Window": "liberrpa.Window",
    "UiInterface": "liberrpa.UiInterface",
    # Common software manipulation
    "Browser": "liberrpa.Browser",
    "Excel": "liberrpa.Excel",
    "Outlook": "liberrpa.Outlook",
    "Application": "liberrpa.Application",
    "Database": "liberrpa.Database",
    # Data processing
    "Data": "liberrpa.Data",
    "Str": "liberrpa.Str",
    "List": "liberrpa.List",
    "Dict": "liberrpa.Dict",
    "Regex": "liberrpa.Regex",
    "Math": "liberrpa.Math",
    "Time": "liberrpa.Time",
    "File": "liberrpa.File",
    "OCR": "liberrpa.OCR",
    # Web protocol
    "Web": "liberrpa.Web",
    "Mail": "liberrpa.Mail",
    "FTP": "liberrpa.FTP",
    # System information
    "Clipboard": "liberrpa.Clipboard",
    "System": "liberrpa.System",
    "Credential": "liberrpa.Credential",
    # User interaction
    "ScreenPrint": "liberrpa.ScreenPrint",
    "Dialog": "liberrpa.Dialog",
    "Trigger": "liberrpa.Trigger",
}

_LAZY_OBJECT_EXPORTS: dict[str, tuple[str, str]] = {
    "Log": ("liberrpa.Logging", "Log"),
    "delay": ("liberrpa.Basic", "delay"),
    "get_component_resource_path": ("liberrpa.Basic", "get_component_resource_path"),
    "DatabaseConnection": ("liberrpa.Database", "DatabaseConnection"),
    "PrjArgs": ("liberrpa.FlowControl.ProjectFlowInit", "PrjArgs"),
    "CustomArgs": ("liberrpa.FlowControl.ProjectFlowInit", "CustomArgs"),
    # Selector types
    "SelectorWindow": ("liberrpa.UI._UiDict", "SelectorWindow"),
    "SelectorUia": ("liberrpa.UI._UiDict", "SelectorUia"),
    "SelectorHtml": ("liberrpa.UI._UiDict", "SelectorHtml"),
    "SelectorImage": ("liberrpa.UI._UiDict", "SelectorImage"),
    "Selector": ("liberrpa.UI._UiDict", "Selector"),
}


def __getattr__(name: str) -> Any:
    """
    Lazily import public LiberRPA entry points.

    This function is called only when a name is not already present in this
    module's global namespace.
    """

    modulePath = _LAZY_MODULE_EXPORTS.get(name)
    if modulePath is not None:
        value = importlib.import_module(modulePath)
        globals()[name] = value
        return value

    objectSpec = _LAZY_OBJECT_EXPORTS.get(name)
    if objectSpec is not None:
        modulePath, attrName = objectSpec
        moduleObj = importlib.import_module(modulePath)
        value = getattr(moduleObj, attrName)
        globals()[name] = value
        return value

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Return public lazy exports in dir(liberrpa.Modules)."""
    return sorted(set(globals()) | set(__all__))


if TYPE_CHECKING:
    # These imports are for static analyzers only.
    # They make tools like Pylance understand the public names exported by this module without importing all modules at runtime.
    from liberrpa.Logging import Log as Log
    from liberrpa.Basic import (
        delay as delay,
        get_component_resource_path as get_component_resource_path,
    )

    from liberrpa import Mouse as Mouse
    from liberrpa import Keyboard as Keyboard
    from liberrpa import Window as Window
    from liberrpa import UiInterface as UiInterface

    from liberrpa import Browser as Browser
    from liberrpa import Excel as Excel
    from liberrpa import Outlook as Outlook
    from liberrpa import Application as Application
    from liberrpa import Database as Database

    from liberrpa import Data as Data
    from liberrpa import Str as Str
    from liberrpa import List as List
    from liberrpa import Dict as Dict
    from liberrpa import Regex as Regex
    from liberrpa import Math as Math
    from liberrpa import Time as Time
    from liberrpa import File as File
    from liberrpa import OCR as OCR

    from liberrpa import Web as Web
    from liberrpa import Mail as Mail
    from liberrpa import FTP as FTP

    from liberrpa import Clipboard as Clipboard
    from liberrpa import System as System
    from liberrpa import Credential as Credential

    from liberrpa import ScreenPrint as ScreenPrint
    from liberrpa import Dialog as Dialog
    from liberrpa import Trigger as Trigger

    from liberrpa.Database import DatabaseConnection as DatabaseConnection
    from liberrpa.FlowControl.ProjectFlowInit import PrjArgs as PrjArgs
    from liberrpa.FlowControl.ProjectFlowInit import CustomArgs as CustomArgs

    from liberrpa.UI._UiDict import (
        SelectorWindow as SelectorWindow,
        SelectorUia as SelectorUia,
        SelectorHtml as SelectorHtml,
        SelectorImage as SelectorImage,
        Selector as Selector,
    )
