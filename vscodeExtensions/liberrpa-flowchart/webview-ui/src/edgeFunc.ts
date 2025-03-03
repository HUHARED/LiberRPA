// FileName: edgeFunc.ts

import LogicFlow from "@logicflow/core";

export function getCurrentSourceEdges(node: LogicFlow.NodeData, lfObj: LogicFlow) {
  // console.log("--getCurrentSourceEdges--");
  const arrEdges = lfObj.graphModel.getNodeEdges(node.id).filter((edge) => {
    if (edge.sourceNodeId === node.id) {
      return true;
    } else {
      return false;
    }
  });

  // console.log(`Source edges before the add: `, arrEdges);
  return arrEdges;
}
