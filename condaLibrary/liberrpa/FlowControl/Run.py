# FileName: Run.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


import multiprocessing


from liberrpa.Logging import Log
from liberrpa.Common._Utils import PATH_PROJECT_ROOT, PROCESS_NAME
from liberrpa.Trigger import _register_force_exit, _register_executor_exit_listener
from liberrpa.Basic import _start_video_record
from liberrpa.Dialog import show_notification
from liberrpa.Data import sanitize_filename
from liberrpa.Common._Exception import get_exception_info
from liberrpa.FlowControl.ProjectFlowInit import (
    dictFlowFile,
    dictNonChooseNext,
    dictChooseNext,
    dictPyInfo,
    dictConditionInfo,
    dictNodeType,
    dictNodeText,
    PrjArgs,
    CustomArgs,  # noqa: F401  # Used by eval().
    boolRunByExecutor,
)
import liberrpa.FlowControl.End as End

import importlib
import json
from pathlib import Path
import sys


def _configure_project_import_paths() -> None:
    listProjectImportPath = [
        str(PATH_PROJECT_ROOT),
        str(PATH_PROJECT_ROOT / "_Components"),
    ]
    listMissingImportPath = [
        strImportPath
        for strImportPath in listProjectImportPath
        if strImportPath not in sys.path
    ]

    for strImportPath in listProjectImportPath:
        while strImportPath in sys.path:
            sys.path.remove(strImportPath)

    sys.path[:0] = listProjectImportPath

    if listMissingImportPath:
        Log.debug(
            "Added missing Project import path(s): " + ", ".join(listMissingImportPath)
        )


_configure_project_import_paths()

if __name__ == "__main__" and PROCESS_NAME == "MainProcess" and boolRunByExecutor:
    _register_executor_exit_listener()


_SET_FLOW_CONTROL_MODULE_FILES = {
    "liberrpa.FlowControl.Start.py",
    "liberrpa.FlowControl.SubStart.py",
    "liberrpa.FlowControl.End.py",
}


def _get_module_name(pyFile: str) -> str:
    """
    Convert a project Python file path or built-in FlowControl file name to an importable module name.
    """

    if pyFile in _SET_FLOW_CONTROL_MODULE_FILES:
        return pyFile.removesuffix(".py")

    pathPyFile = Path(pyFile)

    if pathPyFile.is_absolute() or pathPyFile.anchor:
        raise ValueError(
            f"The Block Python file path must be relative to the project folder: {pyFile}"
        )

    if pathPyFile.suffix.lower() != ".py":
        raise ValueError(f"The Block Python file path must end with '.py': {pyFile}")

    pathResolved = (PATH_PROJECT_ROOT / pathPyFile).resolve()

    try:
        pathRelative = pathResolved.relative_to(PATH_PROJECT_ROOT)
    except ValueError:
        raise ValueError(
            f"The Block Python file path must stay within the project folder: {pyFile}"
        )

    if not pathResolved.is_file():
        raise FileNotFoundError(f"Block Python file does not exist: {pathResolved}")

    moduleParts = pathRelative.with_suffix("").parts

    if not moduleParts or any(not part.isidentifier() for part in moduleParts):
        raise ValueError(
            f"The Block Python file path contains an invalid Python module name: {pyFile}"
        )

    return ".".join(moduleParts)


def _run_by_direction(id: str) -> str | None:
    try:
        Log.info(f"Ready to enter '{dictNodeText[id]}'")

        if dictPyInfo.get(id):
            # It is NonChoose.

            strModuleName: str = _get_module_name(pyFile=dictPyInfo[id])
            # If the module imported, it will not be imported again, just run the its main().
            moduleObj = importlib.import_module(strModuleName)
            moduleObj.main()

            # # Go to "Normal" direction(If it has).
            if dictNonChooseNext.get(id) and dictNonChooseNext[id].get("Normal"):
                return dictNonChooseNext[id]["Normal"]
            else:
                # The node has no "Normal" direction. return None to stop the loop.
                return None

        else:
            # It it a Choose node.
            boolConditionCheck = eval(dictConditionInfo[id], globals())
            Log.info(f"Evaluate {dictConditionInfo[id]} -> {boolConditionCheck}")

            # Go to "True" or "False" direction(If it has).
            if (
                boolConditionCheck
                and dictChooseNext.get(id)
                and dictChooseNext[id].get("True")
            ):
                return dictChooseNext[id]["True"]
            elif (
                not boolConditionCheck
                and dictChooseNext.get(id)
                and dictChooseNext[id].get("False")
            ):
                return dictChooseNext[id]["False"]
            else:
                # The Choose node has no direction. return None to stop the loop.
                return None

    except Exception as e:
        """
        If the node encountered an uncaught error, try to use its "Error" direction's node.
        If it doesn't have, record error then exit.
        The Choose nodes have no "Error" direction.
        """

        Log.error(
            f"An uncaught error in Node '{dictNodeText[id]}': {json.dumps(get_exception_info(e), ensure_ascii=False, indent=4)}"
        )

        if dictNonChooseNext.get(id) and dictNonChooseNext[id].get("Error"):
            # Save the error in PrjArgs.
            PrjArgs.errorObj = e
            # Log.error(f"Update PrjArgs.errorObj={e}")

            # Return the id to run next node.
            return dictNonChooseNext[id]["Error"]
        else:
            # Assign the value to record exit reason.
            End.executionResult = "error"
            # The node has no "Error" direction. return None to stop the loop.
            return None

    finally:
        Log.info(f"Leave from '{dictNodeText[id]}'")


def _run_substart(id: str) -> None:
    # In Windows, the subprocess will re-import all, not forking anything from MainProcess.
    # Log.set_level(level=dictFlowFile["logLevel"], loggerType="both")
    Log.info(f"Run an SubStart process, '{PROCESS_NAME}'")

    while True:
        idTemp = _run_by_direction(id=id)
        if idTemp:
            id = idTemp
        else:
            break

    # If the user didn't link the End node or the subprocess has an uncaught error, run it automatically.
    End.main()


def main() -> None:
    # Print basic information.
    show_notification(
        title="LiberRPA", message=f"'{PrjArgs.projectName}' begins.", duration=1
    )
    Log.info(
        f"'{PrjArgs.projectName}' begins. Current Working Directory: {PrjArgs.projectPath}"
    )

    # Config running setting.
    # Log.set_level(level=dictFlowFile["logLevel"])
    if dictFlowFile["stopShortcut"]:
        _register_force_exit()
    if dictFlowFile["recordVideo"]:
        _start_video_record()

    # Print running information.
    Log.debug(
        f"Custom Project Arguments: {json.dumps(PrjArgs.customArgs, ensure_ascii=False, indent=4)}"
    )
    Log.verbose(
        f"dictNonChooseNext: {json.dumps(dictNonChooseNext, ensure_ascii=False, indent=4)}"
    )
    Log.verbose(
        f"dictChooseNext: {json.dumps(dictChooseNext, ensure_ascii=False, indent=4)}"
    )
    Log.verbose(f"dictPyInfo: {json.dumps(dictPyInfo, ensure_ascii=False, indent=4)}")

    # Run "SubStart" in other processes.
    intSubStartIndex: int = 0
    dictSubProcesses: dict[str, multiprocessing.Process] = {}

    # multiprocessing.set_start_method(method="spawn")
    # Loop all keys(NodeId) of dictNonChooseNext, find the SubStart.
    for strNodeId in dictNonChooseNext:
        if dictNodeType[strNodeId] == "SubStart":
            import liberrpa.Common._Initialization as _Initialization  # noqa: F401  # Import for initialization side effects.

            strProcessName = sanitize_filename(
                f"SubProcess_{str(intSubStartIndex)}_{dictNodeText[strNodeId]}"
            )

            subProcessTemp = multiprocessing.Process(
                target=_run_substart,
                name=strProcessName,
                args=[strNodeId],
                daemon=True,
            )
            dictSubProcesses[strProcessName] = subProcessTemp
            subProcessTemp.start()

            intSubStartIndex += 1

    # Run "Start" in main process.
    id = "LiberRPA_Start"
    while True:
        idTemp = _run_by_direction(id=id)
        if idTemp:
            id = idTemp
        else:
            break

    # If the user didn't link the End node or the subprocess has an uncaught error, stop all subprocesses and run End.
    for strProcessName in dictSubProcesses:
        processObj = dictSubProcesses[strProcessName]
        if processObj.is_alive():
            Log.info(f"The SubStart process '{strProcessName}' is running, terminate it.")
            processObj.terminate()
            processObj.join()
            Log.info(f"Terminated '{strProcessName}'.")

    End.main()


if __name__ == "__main__":
    main()
