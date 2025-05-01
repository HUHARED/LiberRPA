// FileName: store.ts
import { defineStore } from "pinia";

import { loggerRenderer, invokeMain, connectToServer } from "./ipcOfRenderer";
import {
  strSuffixOmit,
  strSuffixRegex,
  removeSuffix,
  modifyKeyName,
} from "./attrHandleFunc";
import {
  DictBasicConfig,
  SelectorWindow,
  SelectorNonWindow,
  DictForUiAnalyzer,
  DictEleTreeItem,
} from "../../shared/interface";

export const useSelectorStore = defineStore("selector", {
  state: () => {
    return {
      dictFromPython: {} as DictForUiAnalyzer,
      arrEleHierarchy: [] as { [key: string]: string }[],
      arrSecondaryAttr: [] as { [key: string]: string }[],
      arrLayerCheckState: [] as boolean[],
      arrCheckedLayers: [] as { [key: string]: string }[],
      intClickedLayer: -1 as number,
      strJsonText: "" as string,
      processDescription: "Idle" as string,
      arrEleTree: [] as DictEleTreeItem[],
      arrEleTreeOpened: [] as number[],
      intEleTreeActivated: 0 as number,
      dictEleTreeSelector: {} as { [key: number]: { [key: string]: string }[] },
    };
  },
  getters: {},
  actions: {
    setDescription(description: string) {
      loggerRenderer.debug(`-start-${description}-`);
      this.processDescription = description;
    },

    idle() {
      loggerRenderer.debug(`-end-`);
      this.processDescription = "Idle";
    },

    afterIndicate() {
      this.setDescription("afterIndicate");

      // Clean Element Tree
      this.arrEleTree = [];
      this.arrEleTreeOpened = [];
      this.intEleTreeActivated = 0;
      this.dictEleTreeSelector = {};

      // Update dictFromPython.
      const informationStore = useInformationStore();
      this.dictFromPython = JSON.parse(informationStore.information);
      console.log(this.dictFromPython);

      this.updateByDictFromPython();

      // Show preview image.
      if (this.dictFromPython["preview"]) {
        informationStore.previewImage = this.dictFromPython["preview"];
      } else {
        informationStore.previewImage = "";
      }

      this.idle();
    },

    updateByDictFromPython() {
      // Update arrSecondaryAttr.
      this.arrSecondaryAttr = [];

      Object.keys(this.dictFromPython["attributes"]).forEach((keyName) => {
        const strNewKeyName = keyName.replace("secondary-", "");
        this.arrSecondaryAttr.push({
          [strNewKeyName]: this.dictFromPython["attributes"][keyName],
        });
      });

      this.arrEleHierarchy = [];
      // Add window part.
      this.arrEleHierarchy.push(this.dictFromPython["selector"]["window"]);

      // Add category and specification parts if it's a SelectorNonWindow object.
      if ("category" in this.dictFromPython["selector"]) {
        this.arrEleHierarchy.push({
          category: this.dictFromPython["selector"]["category"],
        });
        this.dictFromPython["selector"]["specification"].forEach((dictTemp) => {
          // Uncheck some attributes of HTML element, they are useless in most situations.
          for (const keyName of Object.keys(dictTemp)) {
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
              modifyKeyName(dictTemp, keyName, keyName + strSuffixOmit);
            }
          }

          this.arrEleHierarchy.push(dictTemp);
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
    },

    updateCheckedLayerAndJsonText() {
      // this.setDescription("updateCheckedLayerAndJsonText");

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
            if (!key.endsWith(strSuffixOmit)) {
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
          category: this.arrCheckedLayers[1]["category"] as "uia" | "html",
          specification: this.arrCheckedLayers.slice(2),
        };
        dictSelector = dictTemp;
      }

      this.strJsonText = JSON.stringify(dictSelector, null, 2);
      loggerRenderer.debug("Update Json Selector: " + this.strJsonText);

      // this.idle();
    },

    updateEleTreeSelector() {
      this.setDescription("updateEleTreeSelector");
      const addSelectorRecursive = (
        id: number,
        spec: { [key: string]: string },
        parentSelector: { [key: string]: string }[],
        children?: DictEleTreeItem[]
      ): void => {
        const arrTemp = [...parentSelector, spec];
        this.dictEleTreeSelector[id] = arrTemp;
        if (children) {
          children.forEach((child) => {
            addSelectorRecursive(child.id, child.spec, arrTemp, child.children);
          });
        }
      };

      this.arrEleTree.forEach((nodeTop) => {
        addSelectorRecursive(nodeTop.id, nodeTop.spec, [], nodeTop.children);
      });

      // console.log(JSON.stringify(this.dictEleTreeSelector));

      this.idle();
    },

    handleLayerCheck(index: number, event: boolean) {
      this.setDescription("handleLayerCheck");

      // If check or uncheck a layer, update arrCheckedLayers, and generate Json Selector. But the layer 0 and 1 (window and category) should alway be checked.
      loggerRenderer.debug(`Check or uncheck layer: ${index} ${event}`);
      if (index !== 0 && index !== 1) {
        this.arrLayerCheckState[index] = !this.arrLayerCheckState[index];
        this.updateCheckedLayerAndJsonText();
        this.refreshArrtibuteEditor(index);
      } else {
        const informationStore = useInformationStore();
        informationStore.information =
          "The layer of 'window' and 'category' should alway be checked.";
        informationStore.showAlert = true;
      }

      this.idle();
    },

    refreshArrtibuteEditor(index: number) {
      this.setDescription("refreshArrtibuteEditor");

      // Update intClickedLayer to make the changement be watched, then refresh automatically.
      loggerRenderer.debug("Click on a selector layer, index: " + index);
      this.intClickedLayer = index;

      this.idle();
    },

    omitAttr(event: boolean, keyName: string) {
      // Add "-omit" for unchecked attributes. Remove "-omit" for checked attributes.
      this.setDescription("omitAttr");
      const arrMustCheckedKey = [
        "category",
        "ControlTypeName",
        "FileName",
        "Grayscale",
        "Confidence",
      ];
      if (arrMustCheckedKey.some((ele) => keyName.startsWith(ele))) {
        const informationStore = useInformationStore();
        informationStore.information =
          "These attributes must be checked:" + JSON.stringify(arrMustCheckedKey);
        informationStore.showAlert = true;
        this.idle();
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
          removeSuffix(keyName, strSuffixOmit)
        );
      } else {
        modifyKeyName(
          this.arrEleHierarchy[this.intClickedLayer],
          keyName,
          keyName + strSuffixOmit
        );
      }

      this.idle();
    },

    regexAttr(_: MouseEvent, keyName: string) {
      // Add or remove"-regex"
      this.setDescription("regexAttr");

      // Not change a omitted attribute. Otherwise the attribute will be lost(disappear).
      if (keyName.endsWith(strSuffixOmit)) {
        const informationStore = useInformationStore();
        informationStore.information =
          "Make the attribute checked, then try to modify regex again.";
        informationStore.showAlert = true;
        this.idle();
        return;
      }

      // category and some uia attributes not support regex.
      const arrCannotRegex = ["category", "ControlTypeName", "Depth"];
      if (arrCannotRegex.some((ele) => keyName === ele)) {
        const informationStore = useInformationStore();
        informationStore.information =
          "These attributes can't use regex:" + JSON.stringify(arrCannotRegex);
        informationStore.showAlert = true;
        this.idle();
        return;
      }

      // Image's attributes not supports regex. (But its window could)
      if (
        this.arrEleHierarchy[1]["category"] === "image" &&
        (keyName === "FileName" || keyName === "Grayscale" || keyName === "Confidence")
        // Image's Index will not appear in here.
      ) {
        const informationStore = useInformationStore();
        informationStore.information = "Image attributes can't use regex.";
        informationStore.showAlert = true;
        this.idle();
        return;
      }

      if (keyName.endsWith(strSuffixOmit)) {
        if (keyName.includes(strSuffixRegex)) {
          // The omited regex attribute.
          modifyKeyName(
            this.arrEleHierarchy[this.intClickedLayer],
            keyName,
            removeSuffix(keyName, strSuffixRegex)
          );
        } else {
          // The omited string attribute.
          modifyKeyName(
            this.arrEleHierarchy[this.intClickedLayer],
            keyName,
            keyName.replace(strSuffixOmit, strSuffixRegex + strSuffixOmit)
          );
        }
      } else {
        if (keyName.endsWith(strSuffixRegex)) {
          // The regex attribute.
          modifyKeyName(
            this.arrEleHierarchy[this.intClickedLayer],
            keyName,
            removeSuffix(keyName, strSuffixRegex)
          );
        } else {
          // The string attribute.
          modifyKeyName(
            this.arrEleHierarchy[this.intClickedLayer],
            keyName,
            keyName + strSuffixRegex
          );
        }
      }
      // Delete original keyName.

      this.idle();
    },
  },
});

export const useSettingStore = defineStore("setting", {
  state: () => {
    return {
      theme: "light" as "light" | "dark",
      intMatchTimeoutSeconds: 10 as number,
      intIndicateDelaySeconds: 1 as number,
      indexOrPath: "index" as "index" | "path",
      grayscale: true as boolean,
      confidence: 0.9 as number,
      minimizeWindow: false as boolean,
      strLogPath: "Wait the log path." as string,
      intLocalServerPort: undefined as undefined | number,
      socketState: false as boolean,
      leftColumnWidth: 250 as number,
      rightColumnWidth: 250 as number,
      boolIndicateImage: false as boolean,
    };
  },
  getters: {},
  actions: {
    initializeSetting(dictConfigBasic: DictBasicConfig): void {
      this.strLogPath = dictConfigBasic.outputLogPath;
      this.intLocalServerPort = dictConfigBasic.localServerPort;
      this.theme = dictConfigBasic.uiAnalyzerTheme;
      this.minimizeWindow = dictConfigBasic.uiAnalyzerMinimizeWindow;

      connectToServer(this.intLocalServerPort);
    },

    async toggleWindow() {
      if (this.minimizeWindow) {
        if (this.boolIndicateImage) {
          // Not minimize the UI Analyzer window, because the QT window will also be minimized.
          // Reset the flag value.
          this.boolIndicateImage = false;
          return;
        }
        loggerRenderer.debug("Toggle Ui Analyzer Window.");
        await invokeMain("cmd-toggle-window");
      } else {
        loggerRenderer.debug("Don't need to toggle Ui Analyzer Window.");
      }
    },
  },
});

export const useInformationStore = defineStore("information", {
  state: () => {
    return {
      information: "..." as string,
      validateState: undefined as undefined | boolean,
      showAlert: false as boolean,
      previewImage: "" as string,
    };
  },
  getters: {},
  actions: {
    updateValidateColor() {
      if (this.validateState === undefined) {
        return undefined;
      } else if (this.validateState === true) {
        return "success";
      } else {
        return "error";
      }
    },

    showAlertMessage(message: string): void {
      loggerRenderer.error(message);
      this.information = message;
      this.showAlert = true;
    },
  },
});
