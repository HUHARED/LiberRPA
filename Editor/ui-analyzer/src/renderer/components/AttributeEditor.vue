<!-- FileName: AttributeEditor.vue -->
<template>
  <v-container class="clean-space flex-column-grow-1 flex-column">
    <v-label class="header-label"> Attribute Editor </v-label>
    <v-container class="clean-space flex-column-grow-1">
      <v-card
        v-if="selectorStore.intClickedLayer < 0"
        class="ma-1"
        text="Click a layer of Element Hierarchy to edit its attributes."
      >
      </v-card>

      <v-row
        v-else
        class="clean-space"
        v-for="key in Object.keys(
          selectorStore.arrEleHierarchy[selectorStore.intClickedLayer]
        )"
      >
        <v-col cols="12" class="pa-1 ma-0">
          <!-- Remove "-omit" and "-regex" in the key's name. -->
          <v-label>{{
            removeSuffix(removeSuffix(key, strSuffixOmit), strSuffixRegex)
          }}</v-label>

          <!-- // Remove [" or " at the start and " or "] at the end, them will be showed in prefix and suffix. -->
          <!-- Click prepend inner icon to swtich the mode between string and regex. -->
          <v-text-field
            :model-value="
              cutQuotesForTextfield(
                selectorStore.arrEleHierarchy[selectorStore.intClickedLayer][key]
              )
            "
            @update:model-value="
              selectorStore.arrEleHierarchy[selectorStore.intClickedLayer][key] =
                generateEleForArr($event)
            "
            color="secondary"
            :prepend-inner-icon="
              key.includes(strSuffixRegex) ? 'mdi-regex' : 'mdi-code-string'
            "
            @click:prependInner="
              console.log($event, key);
              selectorStore.regexAttr($event, key);
            "
            :prefix="'&quot;'"
            :suffix="'&quot;'"
            variant="filled"
            density="compact"
            hide-details
            spellcheck="false"
          >
            <template #prepend>
              <v-list-item-action end>
                <v-checkbox-btn
                  :model-value="!key.includes('-omit')"
                  @update:model-value="
                    // console.log($event, key);
                    selectorStore.omitAttr($event, key)
                  "
                  density="compact"
                ></v-checkbox-btn>
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
import { strSuffixOmit, strSuffixRegex, removeSuffix } from "../commonFunc";
import { useSelectorStore } from "../store";
const selectorStore = useSelectorStore();

watch(
  () => selectorStore.intClickedLayer,
  () => {
    console.log(
      `Click layer: ${selectorStore.intClickedLayer}`,
      selectorStore.arrEleHierarchy[selectorStore.intClickedLayer]
    );
  }
);

function cutQuotesForTextfield(strText: string): string {
  // console.log("cutQuotesForTextfield", strText);

  strText = JSON.stringify(strText).replace(/^"(.*)"$/, "$1");
  // console.log("cutQuotesForTextfield(stringify and replace)", strText);

  return strText;
}

function generateEleForArr(strText: string): string {
  console.log("generateEleForArr", strText);
  if (strText.endsWith("\\") && !strText.endsWith("\\\\")) {
    // The escape character backslash(\) should always lead a character. So if there is a single \ at the end, didn't need to update, return undefined and Vue will not update component, just wait the next character be typed, and Vue will update normally.
    console.error("End with backslash, wait the next character");
    // @ts-ignore
    return undefined;
  }
  // Add the original quotes to the text.
  strText = '"' + strText + '"';

  console.log(
    "generateEleForArr(add quotes)",
    strText,
    "\ngenerateEleForArr(deserialized)",
    JSON.parse(strText)
  );
  return JSON.parse(strText);
}
</script>

<style scoped></style>
