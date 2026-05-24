# FileName: _ElementTree.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
import liberrpa.UI._UiElement as _UiElement
from liberrpa.Common._TypedValue import DictElementTreeItem
from liberrpa.Common._Exception import UiOperationError


import uiautomation
import time


class IdGenerator:
    """Generator that yields an incrementing integer starting from 0."""

    def __init__(self) -> None:
        # The first one will be 0.
        self.intId: int = -1

    def get_id(self) -> int:
        """Returns the next unique ID and increments the counter."""
        self.intId += 1
        return self.intId

    def reset(self) -> None:
        self.intId = -1


# Generate Element Tree for uia.
idObj = IdGenerator()
listParentChain: list[uiautomation.Control] = []
listExpandedId: list[int] = []
intActivatedId = 0
controlTarget: uiautomation.Control
timeStart = time.time()


def generate_control_tree(elementFinal: uiautomation.Control) -> tuple[list[DictElementTreeItem], list[int], int]:
    """Generates the Element Tree structure, expanded nodes list, and activated element ID."""
    global listParentChain, listExpandedId, intActivatedId, controlTarget, idObj, timeStart

    # Initialize global variables.
    listParentChain = []
    listExpandedId = []
    intActivatedId = 0
    idObj.reset()
    timeStart = time.time()

    listFinalTree: list[DictElementTreeItem] = []

    # Log.debug(f"target info = {elementFinal}")
    controlTop: uiautomation.Control = elementFinal.GetTopLevelControl()  # type: ignore - It should not be None
    # Log.debug(f"Top control: {controlTop}")

    controlTarget = elementFinal

    # Build a list of all parent elements of the target element, excluding the top control.

    eleParent = elementFinal.GetParentControl()
    # Log.debug(f"Parent control: {eleParent}")
    while eleParent and (not uiautomation.ControlsAreSame(controlTop, eleParent)):
        listParentChain.insert(0, eleParent)
        eleParent = eleParent.GetParentControl()
        # Log.debug(f"Parent control to check: {eleParent}")

    # Log.debug("listParentChain" + str([str(ele) for ele in listParentChain]))

    # Begin tree generation
    for idx, ele in enumerate(controlTop.GetChildren(), start=0):
        # Log.debug(f"Handle top child {idx}")
        intId = idObj.get_id()

        for eleParent in listParentChain:
            if uiautomation.ControlsAreSame(eleParent, ele):
                listExpandedId.append(intId)
                break
        if uiautomation.ControlsAreSame(controlTarget, ele):
            intActivatedId = intId

        # Get spec
        dictSpecCurrent = _UiElement.get_control_primary_attr(control=ele)
        if dictSpecCurrent.get("ProcessName"):
            del dictSpecCurrent["ProcessName"]  # type: ignore - it exists
        if dictSpecCurrent.get("FrameworkId"):
            del dictSpecCurrent["FrameworkId"]  # type: ignore - it exists
        dictTemp: DictElementTreeItem = {
            "id": intId,
            "title": dictSpecCurrent["ControlTypeName"].removesuffix("Control") + "-" + dictSpecCurrent.get("Name", ""),
            "spec": dictSpecCurrent,  # type: ignore - it's DictSpecUiaOriginal now. But may not have Name.
        }
        listChildrenTemp = _get_children_spec_recursive(controlAnchor=ele, layerSign=str(idx))
        if len(listChildrenTemp) != 0:
            dictTemp["children"] = listChildrenTemp

        listFinalTree.append(dictTemp)

    return (listFinalTree, listExpandedId, intActivatedId)


def _get_children_spec_recursive(
    controlAnchor: uiautomation.Control,
    layerSign: str,
) -> list[DictElementTreeItem]:
    global listParentChain, listExpandedId, intActivatedId, controlTarget, idObj, timeStart

    if (time.time() - timeStart) >= 10:
        # Some uia window may have too many elements, give up.
        raise UiOperationError("Cannot get all elements in 10 seconds, so give up to generate Element Tree.")

    listFinalRecursive: list[DictElementTreeItem] = []
    for idx, ele in enumerate(controlAnchor.GetChildren(), start=0):
        layerSignNew = f"{layerSign+"-"+str(idx)}"
        # Log.debug(f"Handle layerSign {layerSignNew}")

        intId = idObj.get_id()

        for eleParent in listParentChain:
            if uiautomation.ControlsAreSame(eleParent, ele):
                listExpandedId.append(intId)
                break
        if uiautomation.ControlsAreSame(controlTarget, ele):
            intActivatedId = intId

        # Get spec
        dictSpecCurrent = _UiElement.get_control_primary_attr(control=ele)
        if dictSpecCurrent.get("ProcessName"):
            del dictSpecCurrent["ProcessName"]  # type: ignore - it exists
        if dictSpecCurrent.get("FrameworkId"):
            del dictSpecCurrent["FrameworkId"]  # type: ignore - it exists
        dictTemp: DictElementTreeItem = {
            "id": intId,
            "title": dictSpecCurrent["ControlTypeName"].removesuffix("Control") + "-" + dictSpecCurrent.get("Name", ""),
            "spec": dictSpecCurrent,  # type: ignore - it's DictSpecUiaOriginal now. But may not have Name.
        }
        listChildrenTemp = _get_children_spec_recursive(controlAnchor=ele, layerSign=layerSignNew)
        if len(listChildrenTemp) != 0:
            dictTemp["children"] = listChildrenTemp

        listFinalRecursive.append(dictTemp)

    # Log.debug("Handled done.")
    return listFinalRecursive
