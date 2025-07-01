# FileName: GenerateSnippetsOther.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


import inspect
import json
import importlib
import re
from pathlib import Path


# Modules need to generate snippets
listModule = [
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
    # Web protocal
    "Web",
    "Mail",
    "FTP",
    # System information.
    "Clipboard",
    "System",
    "Credential",
    # User interaction
    "ScreenPrint",
    "Dialog",
    "Trigger",
]

dictSnippets = {}


for strModuleName in listModule:
    print(strModuleName)

    dictSnippets[strModuleName] = {}

    # Database and FTP have "with" statement, add the snippets.
    if strModuleName == "Database":
        strTitleAndPrefix = strModuleName + "." + "build database connection"
        dictSnippets[strModuleName][strTitleAndPrefix] = {
            "prefix": strTitleAndPrefix,
            "body": [
                "with DatabaseConnection(connectString=${1:None}, dbType=${2:None}, username=${3:None}, password=${4:None}, host=${5:None}, port=${6:None}, database=${7:None}, options={$8}) as ${9:connObj}:",
                "\t$10",
            ],
            "description": "You can learn how to use it in liberrpa.Database.DatabaseConnection's Docstring",
        }
    if strModuleName == "FTP":
        strTitleAndPrefix = strModuleName + "." + "build FTP connection"
        dictSnippets[strModuleName][strTitleAndPrefix] = {
            "prefix": strTitleAndPrefix,
            "body": [
                'with FTP.Host(host=$1, user=$2, passwd=$3, encoding=${4:"utf-8"}) as ${5:ftpObj}:',
                "\t$6",
            ],
            "description": "It's an alias of ftputil.FTPHost, so you can search how to use ftputil.FTPHost.",
        }

    moduleObj = importlib.import_module("liberrpa." + strModuleName)

    # Get the "def" functions, to make sure the function belongs to the module, and keep its order.
    strScriptText = Path("./liberrpa/" + strModuleName + ".py").read_text(encoding="utf-8")

    listFuncInOrder: list[str] = re.findall(R"(?<=^def )[^_][a-zA-z0-9_]+(?=\()", strScriptText, re.MULTILINE)

    if strModuleName == "Trigger" and "register_force_exit" in listFuncInOrder:
        listFuncInOrder.remove("register_force_exit")
    print(listFuncInOrder)
    # sys.exit()

    listFuncObj = inspect.getmembers(moduleObj, inspect.isfunction)

    for strFuncName in listFuncInOrder:

        func = getattr(moduleObj, strFuncName, None)

        if not func:
            raise Exception("Error.")

        returnValues = inspect.signature(func).return_annotation
        # print("returnValues", returnValues)
        if returnValues is not None:
            # Some objects, like ExcelObj, BrowserObj, they have only one instance in most situations, so give them a default name.
            strType = str(returnValues)
            match strType:
                case "<class 'liberrpa.Browser.BrowserObj'>":
                    strReturn = "${1:browserObj} = "
                case "<class 'liberrpa.Excel.ExcelObj'>":
                    strReturn = "${1:excelObj} = "
                case "<class 'liberrpa.ScreenPrint.ScreenPrintObj'>":
                    strReturn = "${1:screenPrintObj} = "
                case "<class 'imapclient.imapclient.IMAPClient'>":
                    strReturn = "${1:imapObj} = "
                case _:
                    strReturn = f"${{1:{strType}}} = "

            intIdx = 2
        else:
            strReturn = ""
            intIdx = 1

        params = inspect.signature(func).parameters

        listParam = []

        for strParamName, param in params.items():
            if param.default is inspect.Parameter.empty:

                # Some objects, like ExcelObj, BrowserObj, they have only one instance in most situations, so give them a default name.
                match strParamName:
                    case "browserObj":
                        listParam.append(f"{strParamName}=${{{intIdx}:{strParamName}}}")
                    case "excelObj":
                        listParam.append(f"{strParamName}=${{{intIdx}:{strParamName}}}")
                    case "screenPrintObj":
                        listParam.append(f"{strParamName}=${{{intIdx}:{strParamName}}}")
                    case "connObj":
                        listParam.append(f"{strParamName}=${{{intIdx}:{strParamName}}}")
                    case "imapObj":
                        listParam.append(f"{strParamName}=${{{intIdx}:{strParamName}}}")
                    case "ftpObj":
                        listParam.append(f"{strParamName}=${{{intIdx}:{strParamName}}}")
                    case _:
                        listParam.append(f"{strParamName}=${intIdx}")
            else:
                strDefaultValue = repr(param.default)
                listParam.append(f"{strParamName}=${{{intIdx}:{strDefaultValue}}}")
            intIdx += 1

        strParam = ", ".join(listParam)
        strBody = f"{strReturn}{strModuleName}.{strFuncName}({strParam})"

        strDoc = inspect.getdoc(func) or ""

        strTitleAndPrefix = strModuleName + "." + strFuncName

        # Define the snippet structure
        dictSnippets[strModuleName][strTitleAndPrefix] = {
            "prefix": strTitleAndPrefix,
            "body": strBody,
            "description": strDoc,
        }

strSnippetsDict = json.dumps(dictSnippets, indent=2)
Path("./snippets/snippets_other.snippets").write_text(strSnippetsDict)
