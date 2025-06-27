<!-- FileName: AttributeEditor.vue -->
<template>
  <v-container class="clean-space flex-column-grow-1 flex-column">
    <v-label class="area-header"> Attribute Editor </v-label>

    <v-container class="clean-space flex-column-grow-1">
      <v-card
        v-if="
          selectorStore.intClickedLayer < 0 ||
          !selectorStore.arrEleHierarchy[selectorStore.intClickedLayer]
        "
        class="ma-1"
        text="Click a layer of Element Hierarchy to edit its attributes.">
      </v-card>

      <v-row
        v-for="(strAttrName, index) in Object.keys(
          selectorStore.arrEleHierarchy[selectorStore.intClickedLayer]
        )"
        v-else
        :key="index"
        class="clean-space">
        <v-col cols="12" class="pa-1 ma-0">
          <!-- Remove "-omit" and "-regex" in the key's name. -->
          <v-label>
            {{ removeSuffix(removeSuffix(strAttrName, strSuffixOmit), strSuffixRegex) }}
          </v-label>

          <!--
          Remove " at the start and " at the end, them will be showed in prefix and suffix.
          Click prepend inner icon to swtich the mode between string and regex.
          -->
          <v-text-field
            :model-value="
              cutQuotesForTextfield(
                selectorStore.arrEleHierarchy[selectorStore.intClickedLayer][strAttrName]
              )
            "
            color="secondary"
            :prepend-inner-icon="
              strAttrName.includes(strSuffixRegex) ? 'mdi-regex' : 'mdi-code-string'
            "
            :prefix="'&quot;'"
            :suffix="'&quot;'"
            variant="filled"
            density="compact"
            hide-details
            spellcheck="false"
            @click:prepend-inner="selectorStore.regexAttr($event, strAttrName)"
            @update:model-value="
              selectorStore.arrEleHierarchy[selectorStore.intClickedLayer][strAttrName] =
                generateEleForArr($event) ??
                selectorStore.arrEleHierarchy[selectorStore.intClickedLayer][strAttrName]
            ">
            <template #prepend>
              <v-list-item-action end>
                <v-checkbox-btn
                  :model-value="!strAttrName.includes('-omit')"
                  density="compact"
                  @update:model-value="selectorStore.omitAttr($event, strAttrName)">
                </v-checkbox-btn>
              </v-list-item-action>
            </template>
          </v-text-field>
        </v-col>
      </v-row>
    </v-container>
  </v-container>
</template>
<script setup lang="ts">
import { watch } from "vue";

import { strSuffixOmit, strSuffixRegex, removeSuffix } from "../attrHandleFunc";
import { useSelectorStore, useInformationStore } from "../store";
import { loggerRenderer } from "@renderer/ipcOfRenderer";

const selectorStore = useSelectorStore();
const informationStore = useInformationStore();

watch(
  () => selectorStore.intClickedLayer,
  () => {
    console.log(
      `Click layer: ${selectorStore.intClickedLayer}`,
      selectorStore.arrEleHierarchy[selectorStore.intClickedLayer]
    );
  }
);

function cutQuotesForTextfield(text: string): string {
  // console.log("cutQuotesForTextfield", strText);

  text = JSON.stringify(text).replace(/^"(.*)"$/, "$1");
  // console.log("cutQuotesForTextfield(stringify and replace)", strText);

  return text;
}

function generateEleForArr(text: string): string | undefined {
  // console.log("generateEleForArr", text);
  if (text.trimEnd().endsWith("\\") && !text.trimEnd().endsWith("\\\\")) {
    // The escape character backslash(\) should always lead a character. So if there is a single \ at the end, didn't need to update, return undefined and Vue will not update component, just wait the next character be typed, and Vue will update normally.
    loggerRenderer.debug("End with backslash, wait the next character");
    return undefined;
  }

  // Add the original quotes to the text.
  text = '"' + text + '"';

  /* console.log(
    "generateEleForArr(add quotes)",
    text,
    "\ngenerateEleForArr(deserialized)",
    JSON.parse(text)
  ); */

  try {
    const strJson = JSON.parse(text);
    return strJson;
  } catch (e) {
    const message = e instanceof Error ? e.message : "Unknown error";
    informationStore.showAlertMessage(`Syntax error: ${message}`);
    return undefined;
  }
}
</script>

<style scoped></style>
