<!-- FileName: NodeInfo.vue -->
<template>
  <v-container class="pa-0 ma-0 border-b-thin">
    <v-card
      v-if="
        informationStore.nodeType !== '' &&
        informationStore.nodeType !== 'Start' &&
        informationStore.nodeType !== 'End'
      "
      variant="outlined"
      class="pa-1 ma-0"
      style="border: none; width: 150px">
      <v-label class="pa-2 ma-0 text-center" style="display: block">Node Info</v-label>
      <v-text-field
        prepend-icon="mdi-card-text-outline"
        variant="underlined"
        hide-details
        spellcheck="false"
        v-model="informationStore.nodeText"></v-text-field>
      <v-text-field
        :prepend-icon="strIcon"
        variant="underlined"
        :bg-color="generateBgcolor()"
        v-if="
          informationStore.nodeType === 'Block' || informationStore.nodeType === 'Choose'
        "
        v-model="informationStore.nodeProperty"
        density="compact"
        hide-details
        spellcheck="false">
        <v-tooltip
          v-if="informationStore.nodeType === 'Block'"
          activator="parent"
          location="top">
          <span v-html="generatePyInfoNote()"></span>
        </v-tooltip>
        <v-tooltip
          v-if="informationStore.nodeType === 'Choose'"
          activator="parent"
          location="top">
          <span v-html="generateConditionNote()"></span>
        </v-tooltip>
      </v-text-field>
    </v-card>
  </v-container>
</template>

<script setup lang="ts">
import { watch, ref } from "vue";
import { useFlowchartStore, useInformationStore } from "../store";
const flowchartStore = useFlowchartStore();
const informationStore = useInformationStore();

const strIcon = ref<string>("");

watch(
  () => informationStore.nodeType,
  (newValue) => {
    switch (newValue) {
      case "Block":
        strIcon.value = "mdi-language-python";
        break;

      case "Choose":
        strIcon.value = "mdi-source-branch";
        break;

      default:
        strIcon.value = "";
        break;
    }
  }
);

watch(
  () => informationStore.nodeText,
  (newValue) => {
    updateText(newValue);
  }
);
function updateText(text: string): void {
  // console.log(flowchartStore.lfObj);
  // console.log(informationStore.nodeId);
  if (flowchartStore.lfObj && informationStore.nodeId) {
    flowchartStore.lfObj.updateText(informationStore.nodeId, text);
  }
}

watch(
  () => informationStore.nodeProperty,
  (newValue) => {
    updateProperty(newValue);
  }
);

function updateProperty(text: string): void {
  // console.log(flowchartStore.lfObj);
  // console.log(informationStore.nodeId);
  if (flowchartStore.lfObj && informationStore.nodeId) {
    const dictProperty: { pyFile?: string; condition?: string } = {};
    if (informationStore.nodeType === "Block") {
      dictProperty["pyFile"] = text;
    } else {
      // informationStore.nodeType === "Choose"
      dictProperty["condition"] = text;
    }
    flowchartStore.lfObj.setProperties(informationStore.nodeId, dictProperty);
  }
}

function generatePyInfoNote(): string {
  return `Note:<br/>
    The path must be a relative path to a .py file.<br/>
    The Python file's name can only contain:<br/>
      - English letters (a-z, A-Z)<br/>
      - Numbers (0-9) (but cannot start with a number)<br/>
      - Underscores(_)<br/>
    Use "/" as the folder separator.<br/>
    The "./" prefix is optional.<br/>
    Avoid using LiberRPA built-in module names: ["Mouse", "Keyboard", "Window", "UiInterface", "Browser", "Excel", "Outlook", "Application", "Database", "Data", "Str", "List", "Dict", "Regex", "Math", "Time", "File", "OCR", "Web", "Mail", "FTP", "Clipboard", "System", "Credential", "ScreenPrint", "Dialog"]
    `;
}
function generateConditionNote(): string {
  return `Note:<br/>
    The condition will be evaluate by eval().`;
}

function generateBgcolor(): string {
  if (informationStore.nodeType === "Block" && informationStore.nodeProperty) {
    const arrBuildinName = [
      "Mouse",
      "Keyboard",
      "Window",
      "UiInterface",
      "Browser",
      "Excel",
      "Outlook",
      "Application",
      "Database",
      "Data",
      "Str",
      "List",
      "Dict",
      "Regex",
      "Math",
      "Time",
      "File",
      "OCR",
      "Web",
      "Mail",
      "FTP",
      "Clipboard",
      "System",
      "Credential",
      "ScreenPrint",
      "Dialog",
    ];
    let strNameTemp = informationStore.nodeProperty;
    if (strNameTemp.startsWith("./")) {
      strNameTemp = strNameTemp.slice(2);
    }
    if (strNameTemp.endsWith(".py")) {
      strNameTemp = strNameTemp.slice(0, -3);
    }

    if (arrBuildinName.includes(strNameTemp)) {
      return "warning";
    }
  }
  return "";
}
</script>

<style scoped></style>
