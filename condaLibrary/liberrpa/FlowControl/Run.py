# FileName: Run.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


import multiprocessing

processName = multiprocessing.current_process().name
# print("Run.py:", processName)
from liberrpa.Logging import Log
from liberrpa.Trigger import register_force_exit
from liberrpa.Basic import start_video_record
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
    CustomArgs,  # The eval() needs it.
)
import liberrpa.FlowControl.End as End

import json

import importlib
from pathlib import Path
import sys


def _get_module_name(pyFile: str) -> str:

    # Try to add "__init__.py" for all middle folders, otherwise importlib.import_module may can't recognize the module.
    strForCheckInitPy = Path(pyFile)
    # print("str:", strForCheckInitPy)
    # print("strForCheckInitPy(Original)", strForCheckInitPy.absolute())
    while True:
        strForCheckInitPy = Path(strForCheckInitPy).parent
        # print("strForCheckInitPy(Parent)", strForCheckInitPy.absolute())
        strInitPyFile = strForCheckInitPy / "__init__.py"
        if str(strForCheckInitPy.absolute()) in sys.path:
            # Not have middle folder, importlib.import_module can recognize it without __init__.py
            # print("Not have middle folder")
            break
        elif strInitPyFile.is_file():
            # Have __init__.py
            # print("Have __init__.py")
            break
        else:
            # Create a __init__.py
            # print(f"Created '{strInitPyFile}' for importlib.import_module can recognize it as a module")
            strInitPyFile.write_text("")

    """ 
    Standardize the module name for importlib.import_module to use:
    Remove "./" in the start if it has.
    Remove the suffix(".py") from the Python file's name.
    Use . to split path.
    """
    return str(Path(pyFile).relative_to(".")).removesuffix((Path(pyFile).suffix)).replace("\\", ".")
    # return re.sub(pattern=R"\.py$", repl="", string=pyFile, count=1, flags=re.IGNORECASE)


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
            if boolConditionCheck and dictChooseNext.get(id) and dictChooseNext[id].get("True"):
                return dictChooseNext[id]["True"]
            elif not boolConditionCheck and dictChooseNext.get(id) and dictChooseNext[id].get("False"):
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
            f"An uncaught error in Node '{dictNodeText[id]}': {json.dumps(get_exception_info(e),ensure_ascii=False,indent=4)}"
        )

        if dictNonChooseNext.get(id) and dictNonChooseNext[id].get("Error"):
            # Save the error in PrjArgs.
            PrjArgs.errorObj = e
            # Log.error(f"Update PrjArgs.errorObj={e}")

            # Return the id to run next node.
            return dictNonChooseNext[id]["Error"]
        else:
            # Assign the value to record exit reason.
            End.exitReason = "error"
            # The node has no "Error" direction. return None to stop the loop.
            return None

    finally:
        Log.info(f"Leave from '{dictNodeText[id]}'")


def _run_substart(id: str) -> None:
    # In Windows, the subprocess will re-import all, not forking anything from MainProcess.
    # Log.set_level(level=dictFlowFile["logLevel"], loggerType="both")
    Log.info(f"Run an SubStart process, '{processName}'")

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
    show_notification(title="LiberRPA", message=f"'{PrjArgs.projectName}' begins.", duration=1)
    Log.info(f"'{PrjArgs.projectName}' begins. Current Working Directory: {PrjArgs.projectPath}")

    # Config running setting.
    # Log.set_level(level=dictFlowFile["logLevel"])
    if dictFlowFile["stopShortcut"]:
        register_force_exit()
    if dictFlowFile["recordVideo"]:
        start_video_record()

    # Print running information.
    Log.debug(f"Custom Project Arguments: {json.dumps(PrjArgs.customArgs,ensure_ascii=False,indent=4)}")
    Log.verbose(f"dictNonChooseNext: {json.dumps(dictNonChooseNext,ensure_ascii=False,indent=4)}")
    Log.verbose(f"dictChooseNext: {json.dumps(dictChooseNext,ensure_ascii=False,indent=4)}")
    Log.verbose(f"dictPyInfo: {json.dumps(dictPyInfo,ensure_ascii=False,indent=4)}")

    # Run "SubStart" in other processes.
    intSubStartIndex: int = 0
    dictSubProcesses: dict[str, multiprocessing.Process] = {}

    # multiprocessing.set_start_method(method="spawn")
    # Loop all keys(NodeId) of dictNonChooseNext, find the SubStart.
    for strNodeId in dictNonChooseNext:
        if dictNodeType[strNodeId] == "SubStart":
            import liberrpa.Common._Initialization as _Initialization

            strProcessName = sanitize_filename(f"SubProcess_{str(intSubStartIndex)}_{dictNodeText[strNodeId]}")

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
