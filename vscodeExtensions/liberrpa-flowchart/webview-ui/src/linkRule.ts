// FileName: linkRule.ts
import type { Model } from "@logicflow/core";
import { useFlowchartStore } from "./store";
import { isObjectRecord } from "./commonFunc";

function getLogicFlowNodeType(node: unknown): string {
  if (!isObjectRecord(node)) {
    return "";
  }

  const nodeType = node.type;

  if (typeof nodeType === "string") {
    return nodeType;
  }

  return "";
}

function getLogicFlowNodeId(node: unknown): string {
  if (!isObjectRecord(node)) {
    return "";
  }

  const nodeId = node.id;

  if (typeof nodeId === "string") {
    return nodeId;
  }

  return "";
}

export const arrRuleBase: Model.ConnectRule[] = [
  {
    message: "Cannot link to Start and SubStart node.",
    validate: (_sourceNode, targetNode, _sourceAnchor, _targetAnchor, _edgeId) => {
      const targetNodeType = getLogicFlowNodeType(targetNode);

      if (targetNodeType !== "Start" && targetNodeType !== "SubStart") {
        return true;
      } else {
        return false;
      }
    },
  },
  {
    message: "Cannot link to itself.",
    validate: (sourceNode, targetNode, _sourceAnchor, _targetAnchor, _edgeId) => {
      if (sourceNode?.id !== targetNode?.id) {
        return true;
      } else {
        return false;
      }
    },
  },
  {
    message: "Cannot create line from same sourceAnchor to same targetAnchor.",
    validate: (sourceNode, _targetNode, sourceAnchor, targetAnchor, _edgeId) => {
      const flowchartStore = useFlowchartStore();

      const lfObj = flowchartStore.lfObj;
      if (!lfObj) {
        return false;
      }

      const sourceNodeId = getLogicFlowNodeId(sourceNode);

      if (!sourceNodeId) {
        return false;
      }

      const arrEdges = lfObj.getNodeOutgoingEdge(sourceNodeId);
      for (let index = 0; index < arrEdges.length; index++) {
        const edge = arrEdges[index];
        if (
          edge.sourceAnchorId === sourceAnchor?.id &&
          edge.targetAnchorId === targetAnchor?.id
        ) {
          return false;
        } else {
          continue;
        }
      }

      return true;
    },
  },
];

export const ruleStart_SubStart_NextNode: Model.ConnectRule = {
  message: "The next node of Start or SubStart node can only be Block or Choose.",
  validate: (_sourceNode, targetNode, _sourceAnchor, _targetAnchor, _edgeID) => {
    const targetNodeType = getLogicFlowNodeType(targetNode);

    return targetNodeType === "Block" || targetNodeType === "Choose";
  },
};

export const ruleStart_SubStart_OneOutgoingEdge: Model.ConnectRule = {
  message: "Start and SubStart node can only have one outgoing line.",
  validate: (sourceNode, _targetNode, _sourceAnchor, _targetAnchor, _edgeID) => {
    const edges = sourceNode?.graphModel.getNodeEdges(sourceNode.id);
    // arrBaseRules has checked the edges' targetNode will not be Start ot SubStart, so just count edges.
    if (edges?.length === 0) {
      return true;
    } else {
      return false;
    }
  },
};

export const ruleEnd_NoOutgoing: Model.ConnectRule = {
  message: "The End node cannot have outgoing lines.",
  validate: (sourceNode, _targetNode, _sourceAnchor, _targetAnchor, _edgeID) => {
    const sourceNodeType = getLogicFlowNodeType(sourceNode);

    return sourceNodeType !== "End";
  },
};

export const ruleBlock_OutgoingCount: Model.ConnectRule = {
  message: "The Block node has up to 2 outgoing lines(common and exception).",
  validate: (sourceNode, _targetNode, _sourceAnchor, _targetAnchor, _edgeID) => {
    const edges = sourceNode?.graphModel.getNodeEdges(sourceNode.id);
    const edgesOutgoing = edges?.filter((edge) => {
      return edge.sourceNode.id === sourceNode?.id;
    });
    if (edgesOutgoing && edgesOutgoing.length < 2) {
      return true;
    } else {
      return false;
    }
  },
};

export const ruleChoose_OutgoingCount: Model.ConnectRule = {
  message: "The Choose node has up to 2 outgoing lines(True and False).",
  validate: (sourceNode, _targetNode, _sourceAnchor, _targetAnchor, _edgeID) => {
    const edges = sourceNode?.graphModel.getNodeEdges(sourceNode.id);
    const edgesOutgoing = edges?.filter((edge) => {
      return edge.sourceNode.id === sourceNode?.id;
    });

    if (edgesOutgoing && edgesOutgoing.length < 2) {
      return true;
    } else {
      return false;
    }
  },
};
