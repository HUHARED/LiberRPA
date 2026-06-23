// FileName: store.ts
import { defineStore } from "pinia";
import type { Flowchart, ExecuteMode, LogLevel, Theme } from "./interface";
import type LogicFlow from "@logicflow/core";

export const useFlowchartStore = defineStore("flowchart", {
  state: () => {
    return {
      data: {} as Flowchart,
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
      executeMode: "Run" as ExecuteMode,
      theme: "light" as Theme,
      // theme: "dark" as Theme,
    };
  },
  getters: {},
  actions: {},
});

// JsonValue cannot be calculated correctly in Pinia store state.
export type StoreCustomPrjArg = [name: string, value: unknown];

export const useArgsStore = defineStore("args", {
  state: () => {
    return {
      logLevel: "DEBUG" as LogLevel,
      recordVideo: false as boolean,
      stopShortcut: true as boolean,
      highlightUi: false as boolean,
      customPrjArgs: [] as StoreCustomPrjArg[],
    };
  },
  getters: {},
  actions: {},
});
