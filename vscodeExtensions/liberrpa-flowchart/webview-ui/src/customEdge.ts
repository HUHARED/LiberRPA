// FileName: customEdge.ts
import { LogicFlow } from "@logicflow/core";

import { CurvedEdge as CurvedEdgeView, CurvedEdgeModel } from "@logicflow/extension";

import { DictPosition } from "./interface";

class CommonLineModel extends CurvedEdgeModel {
  initEdgeData(data: LogicFlow.EdgeConfig): void {
    super.initEdgeData(data);
    this.text.editable = false;
    this.radius = 10;
  }

  getEdgeStyle(): {
    [x: string]: unknown;
    fill?: string | undefined;
    stroke?: string | undefined;
    strokeWidth?: number | undefined;
    radius?: number | undefined;
    rx?: number | undefined;
    ry?: number | undefined;
    width?: number | undefined;
    height?: number | undefined;
    path?: string | undefined;
  } {
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

class TrueLineModel extends CurvedEdgeModel {
  initEdgeData(data: LogicFlow.EdgeConfig): void {
    super.initEdgeData(data);
    this.text.editable = false;
    this.radius = 10;
    this.text.value = "True";
  }

  getEdgeStyle(): {
    [x: string]: unknown;
    fill?: string | undefined;
    stroke?: string | undefined;
    strokeWidth?: number | undefined;
    radius?: number | undefined;
    rx?: number | undefined;
    ry?: number | undefined;
    width?: number | undefined;
    height?: number | undefined;
    path?: string | undefined;
  } {
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

class FalseLineModel extends CurvedEdgeModel {
  initEdgeData(data: LogicFlow.EdgeConfig): void {
    super.initEdgeData(data);
    this.text.editable = false;
    this.radius = 10;
    this.text.value = "False";
  }

  getEdgeStyle(): {
    [x: string]: unknown;
    fill?: string | undefined;
    stroke?: string | undefined;
    strokeWidth?: number | undefined;
    radius?: number | undefined;
    rx?: number | undefined;
    ry?: number | undefined;
    width?: number | undefined;
    height?: number | undefined;
    path?: string | undefined;
  } {
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

class ExceptionLineModel extends CurvedEdgeModel {
  initEdgeData(data: LogicFlow.EdgeConfig): void {
    super.initEdgeData(data);
    this.text.editable = false;
    this.radius = 10;
    this.text.value = "Exception";
  }

  getEdgeStyle(): {
    [x: string]: unknown;
    fill?: string | undefined;
    stroke?: string | undefined;
    strokeWidth?: number | undefined;
    radius?: number | undefined;
    rx?: number | undefined;
    ry?: number | undefined;
    width?: number | undefined;
    height?: number | undefined;
    path?: string | undefined;
  } {
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
  arrCurrentPosition: string[]
): { x: number; y: number } {
  const arrPoints: DictPosition[] = [];
  arrCurrentPosition &&
    arrCurrentPosition.forEach((item) => {
      const [x, y] = item.split(",");
      arrPoints.push({ x: Number(x), y: Number(y) });
    });
  if (arrCurrentPosition.length > 1) {
    let [strX1, strY1] = arrCurrentPosition[0].split(",");
    let [strX2, strY2] = arrCurrentPosition[1].split(",");
    const intX1 = Number(strX1);
    const intY1 = Number(strY1);
    const intX2 = Number(strX2);
    const intY2 = Number(strY2);
    if (intX1 === intX2) {
      // Vertical direction
      if (intY2 < intY1) {
        //
        position.y = intY1 - 40;
      } else {
        //
        position.y = intY1 + 40;
      }
      position.x = intX1;
    } else {
      // y1 === y2，Horizontal direction
      if (intX2 < intX1) {
        //
        position.x = intX1 - 40;
      } else {
        //
        position.x = intX1 + 40;
      }
      position.y = intY1;
    }
  }
  return position;
}
