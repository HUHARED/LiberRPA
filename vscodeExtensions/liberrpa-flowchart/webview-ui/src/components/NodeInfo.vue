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
          <div style="max-width: 560px">
            <div class="font-weight-medium mb-1">Note:</div>

            <div>The path must be a relative path to a .py file.</div>

            <div class="font-weight-medium mt-2">
              The Python file's name can only contain:
            </div>

            <div class="pl-5 mt-1">
              <div v-for="item in arrPyFileNameRules" :key="item" class="d-flex ga-2">
                <span>•</span>
                <span>{{ item }}</span>
              </div>
            </div>

            <div class="mt-2">Use "/" as the folder separator.</div>
            <div>The "./" prefix is optional.</div>

            <div class="font-weight-medium mt-2">
              Avoid using LiberRPA built-in module names:
            </div>

            <div class="pl-5 mt-1">
              {{ arrBuiltinModuleNames.join(", ") }}
            </div>
          </div>
        </v-tooltip>

        <v-tooltip
          v-if="informationStore.nodeType === 'Choose'"
          activator="parent"
          location="top">
          <div>
            <div class="font-weight-medium mb-1">Note:</div>
            <div>The condition will be evaluated by eval().</div>
          </div>
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

const arrPyFileNameRules: string[] = [
  "English letters: a-z, A-Z",
  "Numbers: 0-9, but cannot start with a number",
  "Underscores: _",
];

const arrBuiltinModuleNames: string[] = [
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

function generateBgcolor(): string {
  if (informationStore.nodeType === "Block" && informationStore.nodeProperty) {
    let strNameTemp = informationStore.nodeProperty;
    if (strNameTemp.startsWith("./")) {
      strNameTemp = strNameTemp.slice(2);
    }
    if (strNameTemp.endsWith(".py")) {
      strNameTemp = strNameTemp.slice(0, -3);
    }

    if (arrBuiltinModuleNames.includes(strNameTemp)) {
      return "warning";
    }
  }
  return "";
}
</script>

<style scoped></style>
