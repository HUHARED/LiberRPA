# FileName: ProjectFlowInit.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.FlowControl._ProjectDict import DictProject_Original

import argparse
import os
from pathlib import Path
import json
import time
from typing import Literal, Any

_time_start = time.time()

if not Path("project.flow").is_file():
    raise FileNotFoundError(f"Not found the file '{os.getcwd()+"\\project.flow"}' to initialize the program.")

dictFlowFile: DictProject_Original = json.loads(Path("project.flow").read_text(encoding="utf-8"))

# Update "logLevel", "recordVideo", "stopShortcut", "highlightUi", "customPrjArgs" if argument sent from command line.
parser = argparse.ArgumentParser()
parser.add_argument("--executor_args", required=False)
args = parser.parse_args()

if args.executor_args:
    dictArgs = json.loads(args.executor_args)
    for keyName in dictArgs:
        dictFlowFile[keyName] = dictArgs[keyName]
    Log.info(f"Updated arguments from Executor: {dictArgs}")
else:
    print("No build-in and custom project argument from Executor.")


def _generate_next_dict() -> tuple[
    dict[str, dict[Literal["Normal", "Error"], str]],
    dict[str, dict[Literal["True", "False"], str]],
    dict[str, str],
    dict[str, str],
    dict[str, Literal["Start", "SubStart", "Block", "Choose", "End"]],
    dict[str, str],
]:
    """Generate the direction and other information of all nodes."""

    dictNonChooseNext: dict[str, dict[Literal["Normal", "Error"], str]] = {}
    dictChooseNext: dict[str, dict[Literal["True", "False"], str]] = {}
    dictPyInfo: dict[str, str] = {}
    dictConditionInfo: dict[str, str] = {}

    listNode = dictFlowFile["nodes"]
    listEdge = dictFlowFile["edges"]

    dictNodeType: dict[str, Literal["Start", "SubStart", "Block", "Choose", "End"]] = {}
    dictNodeText: dict[str, str] = {}

    for node in listNode:
        # The Choose node use "condition", the others(Start, Substart, Block, End) use "pyFile".
        if node["type"] == "Choose":
            dictConditionInfo[node["id"]] = node["properties"]["condition"]  # type: ignore - It must have "condition"
        else:
            dictPyInfo[node["id"]] = node["properties"]["pyFile"]  # type: ignore - It must have "pyFile"

        dictNodeType[node["id"]] = node["type"]
        dictNodeText[node["id"]] = node["text"]

    for edge in listEdge:
        strSourceNodeType: Literal["Start", "SubStart", "Block", "Choose"] = dictNodeType[edge["sourceNodeId"]]  # type: ignore - "End" will not be a source.

        match strSourceNodeType:
            case "Start":
                dictNonChooseNext[edge["sourceNodeId"]] = {"Normal": edge["targetNodeId"]}

            case "SubStart":
                dictNonChooseNext[edge["sourceNodeId"]] = {"Normal": edge["targetNodeId"]}

            case "Block":
                if dictNonChooseNext.get(edge["sourceNodeId"]):
                    # Have assign a Normal or Error direction, add a new item.
                    if edge["type"] == "CommonLine":
                        dictNonChooseNext[edge["sourceNodeId"]]["Normal"] = edge["targetNodeId"]
                    else:
                        # ExceptionLine
                        dictNonChooseNext[edge["sourceNodeId"]]["Error"] = edge["targetNodeId"]
                else:
                    # Assign the direction dictionary.
                    if edge["type"] == "CommonLine":
                        dictNonChooseNext[edge["sourceNodeId"]] = {"Normal": edge["targetNodeId"]}
                    else:
                        # ExceptionLine
                        dictNonChooseNext[edge["sourceNodeId"]] = {"Error": edge["targetNodeId"]}

            case "Choose":
                if dictChooseNext.get(edge["sourceNodeId"]):
                    # Have assign a True or False direction, add a new item.
                    if edge["type"] == "TrueLine":
                        dictChooseNext[edge["sourceNodeId"]]["True"] = edge["targetNodeId"]
                    else:
                        # FalseLine
                        dictChooseNext[edge["sourceNodeId"]]["False"] = edge["targetNodeId"]
                else:
                    # Assign the direction dictionary.
                    if edge["type"] == "TrueLine":
                        dictChooseNext[edge["sourceNodeId"]] = {"True": edge["targetNodeId"]}
                    else:
                        # FalseLine
                        dictChooseNext[edge["sourceNodeId"]] = {"False": edge["targetNodeId"]}

            case _:
                # End node doesn't have a next direction.
                raise ValueError(f"(!!!It should not appear.)It is not a known SourceNode type: '{strSourceNodeType}'")

    return dictNonChooseNext, dictChooseNext, dictPyInfo, dictConditionInfo, dictNodeType, dictNodeText


dictNonChooseNext, dictChooseNext, dictPyInfo, dictConditionInfo, dictNodeType, dictNodeText = _generate_next_dict()


class ProjectArguments:
    """
    A class to handle project arguments, initialization from the 'project.flow' file,
    and track elapsed time since object creation.

    Attributes:
        projectPath (str): The path of the current working directory.
        projectName (str): The name of the project (based on the directory name).
        errorObj (Exception | None): An exception object, or None if no errors occurred.
        customArgs (dict[str, Any]): A dictionary to store the custom project arguments.
        elapsedTime (float): The time elapsed since the program started (in seconds).
    """

    def __init__(self):
        # The path of the current working directory.
        self.projectPath: str = os.getcwd()
        self.projectName: str = Log.strProjectName
        self.errorObj: Exception | None = None
        self.customArgs: dict[str, Any] = {}

        for item in dictFlowFile["customPrjArgs"]:
            if item[0] in self.customArgs:
                Log.critical(f"The key '{item[0]}' exists, update.")
            self.customArgs[item[0]] = item[1]

    @property
    def elapsedTime(self) -> float:
        """
        Calculates the program's running time in seconds since the object was created.
        Returns:
            float: The time in seconds since the object was initialized.
        """
        current_time = time.time()
        return current_time - _time_start

    def __str__(self) -> str:
        return f"ProjectArguments(projectPath: {self.projectPath}, projectName: {self.projectName}, errorObj: {self.errorObj}, customArgs: {self.customArgs}, elapsedTime: {self.elapsedTime})"


PrjArgs = ProjectArguments()
CustomArgs: dict[str, Any] = PrjArgs.customArgs

if __name__ == "__main__":
    import time

    time.sleep(1)
    print(PrjArgs)
    print(PrjArgs.elapsedTime)
    print(PrjArgs.customArgs)
    print(PrjArgs.errorObj)
    print(PrjArgs.projectPath)
    print(CustomArgs)
