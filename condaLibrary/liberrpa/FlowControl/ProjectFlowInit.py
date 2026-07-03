# FileName: ProjectFlowInit.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.Common._Utils import STR_PROJECT_ROOT, PATH_PROJECT_FLOW
from liberrpa.FlowControl._ProjectDict import DictProject_Original

import argparse
import json
import time
from typing import Literal, Any

_timeStart = time.monotonic()

if not PATH_PROJECT_FLOW.is_file():
    raise FileNotFoundError(f"Not found the file '{PATH_PROJECT_FLOW}' to initialize the program.")

dictFlowFile: DictProject_Original = json.loads(PATH_PROJECT_FLOW.read_text(encoding="utf-8"))

# Update "logLevel", "recordVideo", "stopShortcut", "highlightUi", "customPrjArgs" if argument sent from command line.
_parser = argparse.ArgumentParser()
_parser.add_argument("--executor_args", required=False)
_args, _unknown = _parser.parse_known_args()

if _args.executor_args:
    dictArgs = json.loads(_args.executor_args)
    for keyName in dictArgs:
        dictFlowFile[keyName] = dictArgs[keyName]
    Log.info(f"Updated arguments from Executor: {dictArgs}")
else:
    Log.debug("No built-in and custom project argument from Executor.")


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
        nodeId = node["id"]
        nodeProperties = node["properties"]

        if node["type"] == "Choose":
            condition = nodeProperties.get("condition")
            if not isinstance(condition, str):
                raise ValueError(f"Choose node {nodeId} has no valid condition.")
            dictConditionInfo[nodeId] = condition

        else:
            pyFile = nodeProperties.get("pyFile")
            if not isinstance(pyFile, str):
                raise ValueError(f"Node {nodeId} has no valid pyFile.")
            dictPyInfo[nodeId] = pyFile

        dictNodeType[node["id"]] = node["type"]
        dictNodeText[node["id"]] = node["text"]

    for edge in listEdge:
        strSourceNodeType = dictNodeType[edge["sourceNodeId"]]

        if strSourceNodeType == "End":
            raise ValueError("End node should not be an edge source.")

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
                raise ValueError(f"(!!!It should not appear.) It is not a known SourceNode type: '{strSourceNodeType}'")

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
        self.projectPath: str = STR_PROJECT_ROOT
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
        currentTime = time.monotonic()
        return currentTime - _timeStart

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
