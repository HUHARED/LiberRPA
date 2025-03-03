// FileName: store.ts
import { defineStore } from "pinia";
import { DictFlowchart } from "./interface";
import LogicFlow from "@logicflow/core";

export const useFlowchartStore = defineStore("flowchart", {
  state: () => {
    return {
      data: {} as DictFlowchart,
      nodePanelMounted: false,
      lfObj: null as LogicFlow | null,
    };
  },
  getters: {},
  actions: {},
});

export const useInformationStore = defineStore("information", {
  state: () => {
    return {
      information: "..." as string,
      showAlert: false as boolean,
      nodeId: "" as string,
      nodeType: "" as string,
      nodeText: "" as string,
      nodeProperty: "" as string,
    };
  },
  getters: {},
  actions: {},
});

export const useSettingStore = defineStore("setting", {
  state: () => {
    return {
      executeMode: "Run" as "Run" | "Debug",
      theme: "light" as "light" | "dark",
      // theme: "dark" as "light" | "dark",
    };
  },
  getters: {},
  actions: {},
});

// type CustomArgument = [string, any];

export const useArgsStore = defineStore("args", {
  state: () => {
    return {
      logLevel: "DEBUG" as "VERBOSE" | "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL",
      recordVideo: false as boolean,
      stopShortcut: true as boolean,
      highlightUi: false as boolean,
      customPrjArgs: [] as [string, any][],
    };
  },
  getters: {},
  actions: {},
});
