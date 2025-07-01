# FileName: Modules.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


# All Block node (custom .py files) should import this file:
# from liberrpa.Modules import *


# LiberRPA module
# Basic module
from liberrpa.Logging import Log
from liberrpa.Basic import *

# UI element manipulation
import liberrpa.Mouse as Mouse
import liberrpa.Keyboard as Keyboard
import liberrpa.Window as Window
import liberrpa.UiInterface as UiInterface

# Common software manipulation
import liberrpa.Browser as Browser
import liberrpa.Excel as Excel
import liberrpa.Outlook as Outlook
import liberrpa.Application as Application
import liberrpa.Database as Database

# Data processing
import liberrpa.Data as Data
import liberrpa.Str as Str
import liberrpa.List as List
import liberrpa.Dict as Dict
import liberrpa.Regex as Regex
import liberrpa.Math as Math
import liberrpa.Time as Time
import liberrpa.File as File
import liberrpa.OCR as OCR

# Web protocal
import liberrpa.Web as Web
import liberrpa.Mail as Mail
import liberrpa.FTP as FTP

# System information.
import liberrpa.Clipboard as Clipboard
import liberrpa.System as System
import liberrpa.Credential as Credential

# User interaction
import liberrpa.ScreenPrint as ScreenPrint
import liberrpa.Dialog as Dialog
import liberrpa.Trigger as Trigger


from liberrpa.FlowControl.ProjectFlowInit import PrjArgs, CustomArgs
from liberrpa.Database import DatabaseConnection

# The selector for users to declare.
from liberrpa.Common._TypedValue import SelectorWindow, SelectorUia, SelectorHtml, SelectorImage

# The LiberRPA errors
from liberrpa.Common._Exception import UiElementNotFoundError, UiTimeoutError, UiOperationError, ChromeError, MailError


# Build-in module that liberrpa-snippets-tree or users may need.
import os
