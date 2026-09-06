// FileName: store.ts

import { defineStore } from "pinia";

import { loggerRenderer } from "./logger";
import {
  STR_SUFFIX_OMIT,
  STR_SUFFIX_REGEX,
  removeSuffix,
  modifyKeyName,
} from "./attrHandleFunc";
import type {
  UiAnalyzerInitialization,
  SelectorWindow,
  SelectorNonWindow,
  DictForUiAnalyzer,
  DictEleTreeItem,
  ElementTreeResult,
  UiAnalyzerOperationName,
  UiAnalyzerOperationPhase,
} from "../../shared/interface";

export const useSelectorStore = defineStore("selector", {
  state: () => {
    return {
      dictFromPython: {} as DictForUiAnalyzer,
      arrEleHierarchy: [] as Record<string, string>[],
      arrSecondaryAttr: [] as Record<string, string>[],
      arrLayerCheckState: [] as boolean[],
      arrCheckedLayers: [] as Record<string, string>[],
      intClickedLayer: -1 as number,
      strJsonText: "" as string,
      arrEleTree: [] as DictEleTreeItem[],
      arrEleTreeOpened: [] as number[],
      intEleTreeActivated: 0 as number,
      dictEleTreeSelector: {} as Record<number, Record<string, string>[]>,
    };
  },
  getters: {},
  actions: {
    clearElementTree(): void {
      this.arrEleTree = [];
      this.arrEleTreeOpened = [];
      this.intEleTreeActivated = 0;
      this.dictEleTreeSelector = {};
    },

    applyIndicateResult(dictResult: DictForUiAnalyzer): void {
      this.clearElementTree();

      // Update dictFromPython.
      const informationStore = useInformationStore();
      informationStore.resetSelectorValidation();
      this.dictFromPython = structuredClone(dictResult);

      this.updateByDictFromPython();

      informationStore.previewImage = this.dictFromPython.preview ?? "";
    },

    applyElementTreeResult(tupleResult: ElementTreeResult): void {
      this.arrEleTree = structuredClone(tupleResult[0]);
      this.arrEleTreeOpened = [...tupleResult[1]];
      this.intEleTreeActivated = tupleResult[2];
      this.updateEleTreeSelector();
    },

    updateByDictFromPython(): void {
      // Update arrSecondaryAttr.
      this.arrSecondaryAttr = [];

      Object.keys(this.dictFromPython["attributes"]).forEach((keyName) => {
        const strNewKeyName = keyName.replace("secondary-", "");
        this.arrSecondaryAttr.push({
          [strNewKeyName]: this.dictFromPython["attributes"][keyName],
        });
      });

      this.arrEleHierarchy = [];
      const dictSelector = this.dictFromPython["selector"];

      // Keep the editable hierarchy independent from the received selector data.
      this.arrEleHierarchy.push({ ...dictSelector["window"] });

      // Add category and specification parts if it's a SelectorNonWindow object.
      if ("category" in dictSelector) {
        this.arrEleHierarchy.push({
          category: dictSelector["category"],
        });
        dictSelector["specification"].forEach((dictAttributes) => {
          const dictEditableAttributes = { ...dictAttributes };

          if (dictSelector["category"] === "html") {
            // Uncheck HTML attributes that are usually unsuitable for locating elements.
            for (const keyName of Object.keys(dictEditableAttributes)) {
              if (
                [
                  "disabled",
                  "isHidden",
                  "isDisplayedNone",
                  "isLeaf",
                  "innerText",
                  "parentId",
                  "parentClass",
                  "parentName",
                ].includes(keyName)
              ) {
                modifyKeyName(dictEditableAttributes, keyName, keyName + STR_SUFFIX_OMIT);
              }
            }
          }

          this.arrEleHierarchy.push(dictEditableAttributes);
        });
      }

      // console.log("arrEleHierarchy=", this.arrEleHierarchy);
      // console.log("arrSecondaryAttr=", this.arrSecondaryAttr);

      // Initialize checked layer.
      // The situation of SelectorWindow.
      if ("category" in this.dictFromPython["selector"] === false) {
        this.arrLayerCheckState = new Array(this.arrEleHierarchy.length).fill(true);
      } else {
        // The situation of SelectorNonWindow and category === "uia"
        if (this.dictFromPython["selector"]["category"] === "uia") {
          this.arrLayerCheckState = new Array(this.arrEleHierarchy.length).fill(true);
        } else {
          // html and image, only select the layer of window, category and the last layer.
          this.arrLayerCheckState = new Array(this.arrEleHierarchy.length).fill(false);
          this.arrLayerCheckState[0] = true;
          this.arrLayerCheckState[1] = true;
          this.arrLayerCheckState[this.arrLayerCheckState.length - 1] = true;
        }
      }
      // Default select the final layer for Attribute Editor.
      this.intClickedLayer = this.arrLayerCheckState.length - 1;
      this.updateCheckedLayerAndJsonText();
    },

    updateCheckedLayerAndJsonText(): void {
      // Loop all elements in arrEleHierarchy(by index, arrEleHierarchy and arrLayerCheckState should have same length), if it's checked, add it to arrCheckedLayers
      const arrTemp: { [key: string]: string }[] = [];

      /* console.log(
        `this.arrLayerCheckState.length: ${this.arrLayerCheckState.length}`
      );
      console.log(
        `this.arrEleHierarchy.length: ${this.arrEleHierarchy.length}`
      ); */

      for (let index = 0; index < this.arrLayerCheckState.length; index++) {
        // Just need checked key-value pairs of in the Attribute Editor.
        if (this.arrLayerCheckState[index] === true) {
          // if a key contains "-omit", ignore it.
          const dictCheckAttributes: { [key: string]: string } = {};
          Object.keys(this.arrEleHierarchy[index]).forEach((key) => {
            if (!key.endsWith(STR_SUFFIX_OMIT)) {
              dictCheckAttributes[key] = this.arrEleHierarchy[index][key];
            }
          });
          arrTemp.push(dictCheckAttributes);
        }
      }
      this.arrCheckedLayers = arrTemp;

      // Use arrCheckedLayers to generate selector.
      let dictSelector: SelectorWindow | SelectorNonWindow;
      if (this.arrCheckedLayers.length === 1) {
        const dictTemp: SelectorWindow = {
          window: this.arrCheckedLayers[0],
        };
        dictSelector = dictTemp;
      } else {
        const dictTemp: SelectorNonWindow = {
          window: this.arrCheckedLayers[0],
          category: this.arrCheckedLayers[1]["category"] as SelectorNonWindow["category"],
          specification: this.arrCheckedLayers.slice(2),
        };
        dictSelector = dictTemp;
      }

      this.strJsonText = JSON.stringify(dictSelector, null, 2);
      loggerRenderer.debug("Update JSON Selector.");
    },

    updateEleTreeSelector(): void {
      const addSelectorRecursive = (
        id: number,
        attributes: { [key: string]: string },
        parentSelector: { [key: string]: string }[],
        children?: DictEleTreeItem[],
      ): void => {
        const arrSelector = [
          ...parentSelector.map((dictAttributes) => ({ ...dictAttributes })),
          { ...attributes },
        ];
        this.dictEleTreeSelector[id] = arrSelector;

        if (children) {
          children.forEach((child) => {
            addSelectorRecursive(child.id, child.attributes, arrSelector, child.children);
          });
        }
      };

      this.dictEleTreeSelector = {};
      this.arrEleTree.forEach((nodeTop) => {
        addSelectorRecursive(nodeTop.id, nodeTop.attributes, [], nodeTop.children);
      });

      // console.log(JSON.stringify(this.dictEleTreeSelector));
    },

    handleLayerCheck(index: number, event: boolean): void {
      // If check or uncheck a layer, update arrCheckedLayers, and generate Json Selector. But the layer 0 and 1 (window and category) should alway be checked.
      loggerRenderer.debug(`Check or uncheck layer: ${index} ${event}`);
      if (index !== 0 && index !== 1) {
        this.arrLayerCheckState[index] = event;
        this.updateCheckedLayerAndJsonText();
        this.refreshArrtibuteEditor(index);
      } else {
        const informationStore = useInformationStore();
        informationStore.showAlertMessage(
          "The layers of 'window' and 'category' must always be checked.",
        );
      }
    },

    refreshArrtibuteEditor(index: number): void {
      // Update intClickedLayer to make the changement be watched, then refresh automatically.
      loggerRenderer.debug("Click on a selector layer, index: " + index);
      this.intClickedLayer = index;
    },

    updateAttributeValue(keyName: string, strValue: string): void {
      const dictCurrentLayer = this.arrEleHierarchy[this.intClickedLayer];
      if (!dictCurrentLayer || !(keyName in dictCurrentLayer)) return;

      dictCurrentLayer[keyName] = strValue;
      this.updateCheckedLayerAndJsonText();
    },

    omitAttr(event: boolean, keyName: string): void {
      // Add "-omit" for unchecked attributes. Remove "-omit" for checked attributes.
      const arrMustCheckedKey = [
        "category",
        "ControlTypeName",
        "FileName",
        "Grayscale",
        "Confidence",
      ];
      if (arrMustCheckedKey.some((ele) => keyName.startsWith(ele))) {
        const informationStore = useInformationStore();
        informationStore.showAlertMessage(
          "These attributes must be checked: " + JSON.stringify(arrMustCheckedKey),
        );
        return;
      }

      // Name and Name-regex can all be omitted.
      /* if (keyName === "Name" || keyName === "Name-regex") {
        const informationStore = useInformationStore();
        informationStore.information = "Name or Name-regex must be checked.";
        informationStore.showAlert = true;
        this.idle();
        return;
      } */

      if (event === true) {
        modifyKeyName(
          this.arrEleHierarchy[this.intClickedLayer],
          keyName,
          removeSuffix(keyName, STR_SUFFIX_OMIT),
        );
      } else {
        modifyKeyName(
          this.arrEleHierarchy[this.intClickedLayer],
          keyName,
          keyName + STR_SUFFIX_OMIT,
        );
      }

      this.updateCheckedLayerAndJsonText();
    },

    regexAttr(_event: MouseEvent, keyName: string): void {
      // Add or remove"-regex"
      // Not change a omitted attribute. Otherwise the attribute will be lost(disappear).
      if (keyName.endsWith(STR_SUFFIX_OMIT)) {
        const informationStore = useInformationStore();
        informationStore.showAlertMessage(
          "Check the attribute before changing its Regex mode.",
        );
        return;
      }

      // category and some uia attributes not support regex.
      const arrCannotRegex = ["category", "ControlTypeName", "Depth"];
      if (arrCannotRegex.some((ele) => keyName === ele)) {
        const informationStore = useInformationStore();
        informationStore.showAlertMessage(
          "These attributes can't use Regex: " + JSON.stringify(arrCannotRegex),
        );
        return;
      }

      // Image attributes do not support Regex, but the Window layer still can.
      const dictSelector = this.dictFromPython["selector"];
      const strAttributeName = removeSuffix(keyName, STR_SUFFIX_REGEX);
      const boolImageSpecification =
        "category" in dictSelector &&
        dictSelector["category"] === "image" &&
        this.intClickedLayer >= 2;
      if (
        boolImageSpecification &&
        ["FileName", "Grayscale", "Confidence"].includes(strAttributeName)
        // Image's Index will not appear in here.
      ) {
        const informationStore = useInformationStore();
        informationStore.showAlertMessage("Image attributes can't use Regex.");
        return;
      }

      if (keyName.endsWith(STR_SUFFIX_REGEX)) {
        // The regex attribute.
        modifyKeyName(
          this.arrEleHierarchy[this.intClickedLayer],
          keyName,
          removeSuffix(keyName, STR_SUFFIX_REGEX),
        );
      } else {
        // The string attribute.
        modifyKeyName(
          this.arrEleHierarchy[this.intClickedLayer],
          keyName,
          keyName + STR_SUFFIX_REGEX,
        );
      }
      // Delete original keyName.

      this.updateCheckedLayerAndJsonText();
    },
  },
});

export const useSettingStore = defineStore("setting", {
  state: () => {
    return {
      theme: "light" as "light" | "dark",
      minimizeWindow: false as boolean,

      intMatchTimeoutSeconds: 10 as number,
      intIndicateDelaySeconds: 2 as number,
      indexOrPath: "index" as "index" | "path",
      grayscale: true as boolean,
      confidence: 0.9 as number,

      intLocalServerPort: undefined as undefined | number,
      strToken: undefined as undefined | string,
      socketState: false as boolean,
      leftColumnWidth: 250 as number,
      rightColumnWidth: 250 as number,
    };
  },
  getters: {},
  actions: {
    initializeSetting(initialization: UiAnalyzerInitialization): void {
      this.intLocalServerPort = initialization.localServerPort;
      this.strToken = initialization.token;
      this.theme = initialization.theme;
      this.minimizeWindow = initialization.minimizeWindow;
    },
  },
});

const DICT_OPERATION_DESCRIPTION: Record<UiAnalyzerOperationName, string> = {
  indicate_uia: "Indicating UIA element.",
  indicate_chrome: "Indicating Chrome element.",
  indicate_image: "Indicating image element.",
  indicate_window: "Indicating window element.",
  validate: "Validating element.",
};

export const useOperationStore = defineStore("operation", {
  state: () => {
    return {
      intNextOperationId: 1 as number,
      intActiveOperationId: undefined as number | undefined,
      operationName: undefined as UiAnalyzerOperationName | undefined,
      operationPhase: "idle" as UiAnalyzerOperationPhase,
      boolWindowRestoreRequired: false as boolean,
    };
  },
  getters: {
    isBusy(state): boolean {
      return state.intActiveOperationId !== undefined;
    },

    processDescription(state): string {
      if (state.operationPhase === "idle" || state.operationName === undefined) {
        return "Idle";
      }

      if (state.operationPhase === "buildingElementTree") {
        return "Building Element Tree.";
      }

      return DICT_OPERATION_DESCRIPTION[state.operationName];
    },
  },
  actions: {
    beginOperation(operationName: UiAnalyzerOperationName): number {
      if (this.intActiveOperationId !== undefined) {
        throw new Error("Another UI Analyzer operation is already running.");
      }

      const intOperationId = this.intNextOperationId;
      this.intNextOperationId += 1;
      this.intActiveOperationId = intOperationId;
      this.operationName = operationName;
      this.operationPhase = "running";
      this.boolWindowRestoreRequired = false;

      loggerRenderer.debug(
        `Start UI Analyzer operation ${intOperationId}: ${operationName}`,
      );
      return intOperationId;
    },

    isCurrentOperation(intOperationId: number): boolean {
      return this.intActiveOperationId === intOperationId;
    },

    markWindowRestoreRequired(intOperationId: number): void {
      if (!this.isCurrentOperation(intOperationId)) return;
      this.boolWindowRestoreRequired = true;
    },

    markWindowRestored(intOperationId: number): void {
      if (!this.isCurrentOperation(intOperationId)) return;
      this.boolWindowRestoreRequired = false;
    },

    markBuildingElementTree(intOperationId: number): void {
      if (!this.isCurrentOperation(intOperationId)) return;
      this.operationPhase = "buildingElementTree";
    },

    finishOperation(intOperationId: number): void {
      if (!this.isCurrentOperation(intOperationId)) return;

      loggerRenderer.debug(`Finish UI Analyzer operation ${intOperationId}.`);
      this.intActiveOperationId = undefined;
      this.operationName = undefined;
      this.operationPhase = "idle";
      this.boolWindowRestoreRequired = false;
    },
  },
});

export const useInformationStore = defineStore("information", {
  state: () => {
    return {
      information: "..." as string,
      validateState: undefined as undefined | boolean,
      strPendingValidateSelectorText: undefined as string | undefined,
      showAlert: false as boolean,
      strAlertMessage: "" as string,
      intAlertRevision: 0 as number,
      previewImage: "" as string,
    };
  },
  getters: {},
  actions: {
    updateValidateColor(): "success" | "error" | undefined {
      if (this.validateState === undefined) {
        return undefined;
      } else if (this.validateState === true) {
        return "success";
      } else {
        return "error";
      }
    },

    startSelectorValidation(strSelectorText: string): void {
      this.validateState = undefined;
      this.strPendingValidateSelectorText = strSelectorText;
    },

    resetSelectorValidation(): void {
      this.validateState = undefined;
      this.strPendingValidateSelectorText = undefined;
    },

    applySelectorValidationResult(
      boolResult: boolean,
      strCurrentSelectorText: string,
    ): void {
      const strPendingSelectorText = this.strPendingValidateSelectorText;
      this.strPendingValidateSelectorText = undefined;

      if (
        strPendingSelectorText === undefined ||
        strPendingSelectorText !== strCurrentSelectorText
      ) {
        loggerRenderer.debug("Ignore a validation result for an outdated Selector.");
        this.validateState = undefined;
        return;
      }

      this.validateState = boolResult;
    },

    showAlertMessage(message: string): void {
      loggerRenderer.error(message);
      this.strAlertMessage = message;
      this.showAlert = true;
      this.intAlertRevision += 1;
    },

    closeAlert(): void {
      this.showAlert = false;
      this.strAlertMessage = "";
    },
  },
});
