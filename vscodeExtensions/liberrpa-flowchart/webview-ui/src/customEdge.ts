// FileName: customEdge.ts
import type { LogicFlow } from "@logicflow/core";

import { CurvedEdge as CurvedEdgeView, CurvedEdgeModel } from "@logicflow/extension";

import type { DictPosition } from "./interface";
import { optimizeEndpointBendSymmetry } from "./orthogonalEdgeRoute";

const EDGE_CORNER_RADIUS = 10;
const EDGE_TEXT_PATH_DISTANCE = 40;

class FlowchartLineModel extends CurvedEdgeModel {
  initEdgeData(data: LogicFlow.EdgeConfig): void {
    super.initEdgeData(data);
    this.text.editable = false;
    this.radius = EDGE_CORNER_RADIUS;

    // pointsList from a saved Flow is normalized before sourceNodeId and targetNodeId are initialized. Re-run the post-processing once the connected nodes are ready.
    this.pointsList = this.orthogonalizePath(this.pointsList);
    this.points = this.getPath(this.pointsList);
    this.resetTextPosition();
  }

  orthogonalizePath(arrPoints: LogicFlow.Point[]): LogicFlow.Point[] {
    const arrOrthogonalPoints = super.orthogonalizePath(arrPoints);
    const sourceNode = this.sourceNode;
    const targetNode = this.targetNode;
    if (!sourceNode || !targetNode) {
      return arrOrthogonalPoints;
    }

    const arrNodeBounds = this.graphModel.nodes.map((node) => node.getBounds());

    return optimizeEndpointBendSymmetry(
      arrOrthogonalPoints,
      EDGE_CORNER_RADIUS,
      arrNodeBounds,
    );
  }
}

class CommonLineModel extends FlowchartLineModel {
  getEdgeStyle(): LogicFlow.EdgeTheme {
    const style = super.getEdgeStyle();
    style.stroke = "gray";
    return style;
  }
}

class CommonLineView extends CurvedEdgeView {}

export const CommonLineEdge = {
  type: "CommonLine",
  model: CommonLineModel,
  view: CommonLineView,
};

class TrueLineModel extends FlowchartLineModel {
  initEdgeData(data: LogicFlow.EdgeConfig): void {
    super.initEdgeData(data);
    this.text.value = "True";
  }

  getEdgeStyle(): LogicFlow.EdgeTheme {
    const style = super.getEdgeStyle();
    style.stroke = "Gold";
    return style;
  }

  getTextStyle(): LogicFlow.EdgeTextTheme {
    const style = super.getTextStyle();
    style.color = "Gold";
    style.fontSize = 14;
    if (style.background?.fill) {
      style.background.fill = "none";
    }
    return style;
  }

  getTextPosition(): { x: number; y: number } {
    const position = super.getTextPosition();
    const arrCurrentPosition = this.points.split(" ");
    const positionNew = calculateTextPosition(position, arrCurrentPosition);

    return positionNew;
  }
}

class TrueLineView extends CurvedEdgeView {}

export const TrueLineEdge = {
  type: "TrueLine",
  model: TrueLineModel,
  view: TrueLineView,
};

class FalseLineModel extends FlowchartLineModel {
  initEdgeData(data: LogicFlow.EdgeConfig): void {
    super.initEdgeData(data);
    this.text.value = "False";
  }

  getEdgeStyle(): LogicFlow.EdgeTheme {
    const style = super.getEdgeStyle();
    style.stroke = "Chocolate";
    return style;
  }

  getTextStyle(): LogicFlow.EdgeTextTheme {
    const style = super.getTextStyle();
    style.color = "Chocolate";
    style.fontSize = 14;
    if (style.background?.fill) {
      style.background.fill = "none";
    }
    return style;
  }

  getTextPosition(): { x: number; y: number } {
    const position = super.getTextPosition();
    const arrCurrentPosition = this.points.split(" ");
    const positionNew = calculateTextPosition(position, arrCurrentPosition);

    return positionNew;
  }
}

class FalseLineView extends CurvedEdgeView {}

export const FalseLineEdge = {
  type: "FalseLine",
  model: FalseLineModel,
  view: FalseLineView,
};

class ExceptionLineModel extends FlowchartLineModel {
  initEdgeData(data: LogicFlow.EdgeConfig): void {
    super.initEdgeData(data);
    this.text.value = "Exception";
  }

  getEdgeStyle(): LogicFlow.EdgeTheme {
    const style = super.getEdgeStyle();
    style.stroke = "#E57373";
    return style;
  }

  getTextStyle(): LogicFlow.EdgeTextTheme {
    const style = super.getTextStyle();
    style.color = "#E57373";
    style.fontSize = 14;
    if (style.background?.fill) {
      style.background.fill = "none";
    }
    return style;
  }

  getTextPosition(): { x: number; y: number } {
    const position = super.getTextPosition();
    const arrCurrentPosition = this.points.split(" ");
    const positionNew = calculateTextPosition(position, arrCurrentPosition);

    return positionNew;
  }
}

class ExceptionLineView extends CurvedEdgeView {}

export const ExceptionLineEdge = {
  type: "ExceptionLine",
  model: ExceptionLineModel,
  view: ExceptionLineView,
};

function calculateTextPosition(
  position: DictPosition,
  arrCurrentPosition: string[],
): { x: number; y: number } {
  const arrPolylinePoints = parsePolylinePoints(arrCurrentPosition);
  if (arrPolylinePoints.length <= 1) {
    return position;
  }

  let remainingDistance = EDGE_TEXT_PATH_DISTANCE;
  for (let index = 0; index < arrPolylinePoints.length - 1; index += 1) {
    const startPoint = arrPolylinePoints[index];
    const endPoint = arrPolylinePoints[index + 1];
    const segmentLength =
      Math.abs(endPoint.x - startPoint.x) + Math.abs(endPoint.y - startPoint.y);
    if (segmentLength === 0) {
      continue;
    }

    if (remainingDistance <= segmentLength) {
      const positionRatio = remainingDistance / segmentLength;
      return {
        x: startPoint.x + (endPoint.x - startPoint.x) * positionRatio,
        y: startPoint.y + (endPoint.y - startPoint.y) * positionRatio,
      };
    }

    remainingDistance -= segmentLength;
  }

  return position;
}

function parsePolylinePoints(arrCurrentPosition: string[]): DictPosition[] {
  const arrPolylinePoints: DictPosition[] = [];

  for (const strPosition of arrCurrentPosition) {
    const [strX, strY] = strPosition.split(",");
    const x = Number(strX);
    const y = Number(strY);
    if (!Number.isFinite(x) || !Number.isFinite(y)) {
      return [];
    }
    arrPolylinePoints.push({ x, y });
  }

  return arrPolylinePoints;
}
