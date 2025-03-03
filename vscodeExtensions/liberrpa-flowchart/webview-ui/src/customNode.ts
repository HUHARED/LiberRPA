// FileName: customNode.ts
import {
  LogicFlow,
  EllipseNode as EllipseNodeView,
  EllipseNodeModel,
  RectNode as RectNodeView,
  RectNodeModel,
  DiamondNode as DiamondNodeView,
  DiamondNodeModel,
  h,
} from "@logicflow/core";

import {
  arrRuleBase,
  ruleStart_SubStart_NextNode,
  ruleStart_SubStart_OneOutgoingEdge,
  ruleEnd_NoOutgoing,
  ruleBlock_OutgoingCount,
  ruleChoose_OutgoingCount,
} from "./linkRule";

import { clickBlockExecute, clickStartExecute, clickOpen } from "./commonFunc";

import { useSettingStore } from "./store";

class StartModel extends EllipseNodeModel {
  getNodeStyle(): {
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
    const style = super.getNodeStyle();
    style.stroke = "green";
    setFileByTheme(style);

    return style;
  }

  initNodeData(data: LogicFlow.NodeConfig): void {
    super.initNodeData(data);
    this.rx = 55;
    this.ry = 33;
    this.text.editable = false;
    this.sourceRules = this.sourceRules
      .concat(arrRuleBase)
      .concat([ruleStart_SubStart_NextNode, ruleStart_SubStart_OneOutgoingEdge]);
  }

  getTextStyle(): {
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
    overflowMode?: "default" | "autoWrap" | "ellipsis" | undefined;
    textWidth?: number | undefined;
    background?: LogicFlow.CommonTheme | undefined;
    wrapPadding?: string | undefined;
    color?: string | undefined;
    fontSize: number;
    lineHeight?: number | undefined;
    textAnchor?: "middle" | "start" | "end" | undefined;
    dominantBaseline?:
      | "middle"
      | "central"
      | "auto"
      | "text-bottom"
      | "alphabetic"
      | "ideographic"
      | "mathematical"
      | "hanging"
      | "text-top"
      | undefined;
  } {
    const style = super.getTextStyle();
    style.fontSize = 25;
    style.color = "green";

    return style;
  }

  getAnchorStyle(anchorInfo?: LogicFlow.Point): LogicFlow.AnchorTheme {
    const style = super.getAnchorStyle(anchorInfo);
    style.r = 10;
    style.stroke = "green";
    style.strokeDasharray = "2 2";
    setFileByTheme(style);
    return style;
  }
}

class StartView extends EllipseNodeView {
  getShape() {
    const { x, y } = this.props.model;

    // Only Block in flowchart area show the Run symbol.
    return h("g", {}, [
      super.getShape(),
      h(
        "text",
        {
          x: x - 5,
          y: y + 23,
          "font-size": 20,
          fill: "green",
          cursor: "pointer",
          onClick: () => clickStartExecute(),
        },
        "⊳"
      ),
    ]);
  }
}

export const StartNode = {
  type: "Start",
  model: StartModel,
  view: StartView,
};

class SubStartModel extends EllipseNodeModel {
  getNodeStyle(): {
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
    const style = super.getNodeStyle();
    style.stroke = "Teal";
    style.strokeDasharray = "2 2";
    setFileByTheme(style);
    return style;
  }

  initNodeData(data: LogicFlow.NodeConfig): void {
    super.initNodeData(data);
    this.rx = 45;
    this.ry = 27;
    this.text.editable = false;
    this.sourceRules = this.sourceRules
      .concat(arrRuleBase)
      .concat([ruleStart_SubStart_NextNode, ruleStart_SubStart_OneOutgoingEdge]);
  }

  getTextStyle(): {
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
    overflowMode?: "default" | "autoWrap" | "ellipsis" | undefined;
    textWidth?: number | undefined;
    background?: LogicFlow.CommonTheme | undefined;
    wrapPadding?: string | undefined;
    color?: string | undefined;
    fontSize: number;
    lineHeight?: number | undefined;
    textAnchor?: "middle" | "start" | "end" | undefined;
    dominantBaseline?:
      | "middle"
      | "central"
      | "auto"
      | "text-bottom"
      | "alphabetic"
      | "ideographic"
      | "mathematical"
      | "hanging"
      | "text-top"
      | undefined;
  } {
    const style = super.getTextStyle();
    style.fontSize = 13;
    style.color = "Teal";

    return style;
  }

  getAnchorStyle(anchorInfo?: LogicFlow.Point): LogicFlow.AnchorTheme {
    const style = super.getAnchorStyle(anchorInfo);
    style.r = 10;
    style.stroke = "Teal";
    style.strokeDasharray = "2 2";
    setFileByTheme(style);
    return style;
  }
}

class SubStartView extends EllipseNodeView {}

export const SubStartNode = {
  type: "SubStart",
  model: SubStartModel,
  view: SubStartView,
};

class EndModel extends EllipseNodeModel {
  getNodeStyle(): {
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
    const style = super.getNodeStyle();
    style.stroke = "Olive";
    setFileByTheme(style);
    return style;
  }

  initNodeData(data: LogicFlow.NodeConfig): void {
    super.initNodeData(data);
    this.rx = 55;
    this.ry = 33;
    this.text.editable = false;
    this.sourceRules = this.sourceRules.concat(arrRuleBase).concat([ruleEnd_NoOutgoing]);
  }

  getTextStyle(): {
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
    overflowMode?: "default" | "autoWrap" | "ellipsis" | undefined;
    textWidth?: number | undefined;
    background?: LogicFlow.CommonTheme | undefined;
    wrapPadding?: string | undefined;
    color?: string | undefined;
    fontSize: number;
    lineHeight?: number | undefined;
    textAnchor?: "middle" | "start" | "end" | undefined;
    dominantBaseline?:
      | "middle"
      | "central"
      | "auto"
      | "text-bottom"
      | "alphabetic"
      | "ideographic"
      | "mathematical"
      | "hanging"
      | "text-top"
      | undefined;
  } {
    const style = super.getTextStyle();
    style.fontSize = 25;
    style.color = "Olive";

    return style;
  }

  getAnchorStyle(anchorInfo?: LogicFlow.Point): LogicFlow.AnchorTheme {
    const style = super.getAnchorStyle(anchorInfo);
    style.r = 10;
    style.stroke = "Olive";
    style.strokeDasharray = "2 2";
    setFileByTheme(style);
    return style;
  }
}

class EndView extends EllipseNodeView {}

export const EndNode = {
  type: "End",
  model: EndModel,
  view: EndView,
};

class BlockModel extends RectNodeModel {
  getNodeStyle(): {
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
    const style = super.getNodeStyle();
    style.stroke = "gray";
    setFileByTheme(style);
    return style;
  }

  initNodeData(data: LogicFlow.NodeConfig): void {
    super.initNodeData(data);
    this.width = 130;
    this.height = 80;
    this.radius = 10;
    this.text.editable = false;
    this.sourceRules = this.sourceRules
      .concat(arrRuleBase)
      .concat([ruleBlock_OutgoingCount]);
  }

  getTextStyle(): {
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
    overflowMode?: "default" | "autoWrap" | "ellipsis" | undefined;
    textWidth?: number | undefined;
    background?: LogicFlow.CommonTheme | undefined;
    wrapPadding?: string | undefined;
    color?: string | undefined;
    fontSize: number;
    lineHeight?: number | undefined;
    textAnchor?: "middle" | "start" | "end" | undefined;
    dominantBaseline?:
      | "middle"
      | "central"
      | "auto"
      | "text-bottom"
      | "alphabetic"
      | "ideographic"
      | "mathematical"
      | "hanging"
      | "text-top"
      | undefined;
  } {
    const style = super.getTextStyle();
    style.fontSize = 16;
    style.color = "gray";
    const settingStore = useSettingStore();
    if (settingStore.theme === "light") {
      style.stroke = "white";
    } else {
      style.stroke = "black";
    }
    style.strokeWidth = 5;
    // Ensures stroke renders below the text
    style.paintOrder = "stroke fill";

    return { ...style, transform: `matrix(1 0 0 1 0 -10)` };
  }

  getAnchorStyle(anchorInfo?: LogicFlow.Point): LogicFlow.AnchorTheme {
    const style = super.getAnchorStyle(anchorInfo);
    style.r = 10;
    style.stroke = "gray";
    style.strokeDasharray = "2 2";
    setFileByTheme(style);
    return style;
  }
}

class BlockView extends RectNodeView {
  getShape() {
    const { x, y, properties } = this.props.model;
    const additionText = (properties.pyFile as string) || "";
    const settingStore = useSettingStore();

    const arrShape = [
      super.getShape(),
      h(
        "text",
        {
          x,
          y: y + 10,
          "text-anchor": "middle",
          "dominant-baseline": "middle",
          "font-size": 14,
          fill: "gray",
          stroke: settingStore.theme === "light" ? "white" : "black",
          strokeWidth: 5,
          paintOrder: "stroke fill",
        },
        additionText
      ),
    ];

    const arrButton = [
      h(
        "text",
        {
          x: x + 60,
          y: y - 20,
          "font-size": 20,
          fill: "gray",
          cursor: "pointer",
          transform: `rotate(-90, ${x + 60}, ${y - 20})`,
          onClick: () => clickOpen(additionText),
        },
        "⇲"
      ),
      h(
        "text",
        {
          x: x + 45,
          y: y + 35,
          "font-size": 20,
          fill: "gray",
          cursor: "pointer",
          onClick: () => clickBlockExecute(additionText),
        },
        "⊳"
      ),
    ];

    // Only Block in flowchart area show the Run symbol.
    if (additionText.endsWith(".py")) {
      return h("g", {}, arrShape.concat(arrButton));
    } else {
      return h("g", {}, arrShape);
    }
  }
}

export const BlockNode = {
  type: "Block",
  model: BlockModel,
  view: BlockView,
};

class ChooseModel extends DiamondNodeModel {
  getNodeStyle(): {
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
    const style = super.getNodeStyle();
    style.stroke = "orange";
    setFileByTheme(style);
    return style;
  }

  initNodeData(data: LogicFlow.NodeConfig): void {
    super.initNodeData(data);
    this.rx = 50;
    this.ry = 50;
    this.text.editable = false;
    this.sourceRules = this.sourceRules
      .concat(arrRuleBase)
      .concat([ruleChoose_OutgoingCount]);
  }

  getTextStyle(): {
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
    overflowMode?: "default" | "autoWrap" | "ellipsis" | undefined;
    textWidth?: number | undefined;
    background?: LogicFlow.CommonTheme | undefined;
    wrapPadding?: string | undefined;
    color?: string | undefined;
    fontSize: number;
    lineHeight?: number | undefined;
    textAnchor?: "middle" | "start" | "end" | undefined;
    dominantBaseline?:
      | "middle"
      | "central"
      | "auto"
      | "text-bottom"
      | "alphabetic"
      | "ideographic"
      | "mathematical"
      | "hanging"
      | "text-top"
      | undefined;
  } {
    const style = super.getTextStyle();
    style.fontSize = 16;
    style.color = "orange";
    const settingStore = useSettingStore();
    if (settingStore.theme === "light") {
      style.stroke = "white";
    } else {
      style.stroke = "black";
    }
    style.strokeWidth = 5;
    // Ensures stroke renders below the text
    style.paintOrder = "stroke fill";

    return { ...style, transform: `matrix(1 0 0 1 0 -10)` };
  }

  getAnchorStyle(anchorInfo?: LogicFlow.Point): LogicFlow.AnchorTheme {
    const style = super.getAnchorStyle(anchorInfo);
    style.r = 10;
    style.stroke = "orange";
    style.strokeDasharray = "2 2";
    setFileByTheme(style);
    return style;
  }
}

class ChooseView extends DiamondNodeView {
  getShape() {
    const { x, y, properties } = this.props.model;
    const additionText = properties.condition as string;
    const settingStore = useSettingStore();

    return h("g", {}, [
      super.getShape(),
      ,
      h(
        "text",
        {
          x,
          y: y + 10,
          "text-anchor": "middle",
          "dominant-baseline": "middle",
          "font-size": 14,
          fill: "orange",
          stroke: settingStore.theme === "light" ? "white" : "black",
          strokeWidth: 5,
          paintOrder: "stroke fill",
        },
        additionText
      ),
    ]);
  }
}

export const ChooseNode = {
  type: "Choose",
  model: ChooseModel,
  view: ChooseView,
};

function setFileByTheme<T extends { fill?: string }>(style: T): void {
  const settingStore = useSettingStore();
  if (settingStore.theme !== "light" && style.fill) {
    style.fill = "rgb(18, 18, 18)";
  }
  // return style;
}
