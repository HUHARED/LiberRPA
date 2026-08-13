// FileName: flowchartTheme.ts

import type { LogicFlow } from "@logicflow/core";
import type { Theme } from "./interface";

const DARK_SURFACE_COLOR = "rgb(18, 18, 18)";
const LIGHT_SURFACE_COLOR = "white";

export function applyLogicFlowTheme(logicFlow: LogicFlow, theme: Theme): void {
  const boolIsDarkTheme = theme === "dark";
  const strSurfaceColor = boolIsDarkTheme ? DARK_SURFACE_COLOR : LIGHT_SURFACE_COLOR;

  logicFlow.setTheme({
    background: {
      backgroundColor: boolIsDarkTheme ? DARK_SURFACE_COLOR : "transparent",
    },
    baseNode: {
      fill: strSurfaceColor,
    },
    anchor: {
      fill: strSurfaceColor,
    },
    arrow: {
      offset: 8,
      verticalLength: 3,
    },
  });
}
