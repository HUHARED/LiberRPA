<!-- FileName: CustomPrjArgs.vue -->
<template>
  <v-container class="pa-1 ma-0 d-flex flex-column">
    <!-- Label -->
    <v-label class="pa-2 ma-0 text-center" style="display: block"
      >Custom Project Arguments</v-label
    >

    <!-- All argument inputboxes -->
    <v-container class="pa-0 ma-0 flex-grow-1 overflow-y-auto">
      <v-row
        class="pa-0 ma-0"
        v-for="(item, index) in argsStore.customPrjArgs"
        :key="index">
        <!-- The value name inputbox, should not have same name. -->
        <v-col cols="6" class="pa-0 ma-0"
          ><v-text-field
            variant="underlined"
            v-model="item[0]"
            density="comfortable"
            hide-details
            spellcheck="false"
            prepend-inner-icon="mdi-minus"
            prefix='"'
            suffix='"'
            :bg-color="generateBgcolor(item[0])"
            @click:prepend-inner="deleteArgument(index)">
            <v-tooltip
              v-if="generateBgcolor(item[0]) !== ''"
              activator="parent"
              location="top">
              Duplicate names exist.
            </v-tooltip>
          </v-text-field></v-col
        >

        <!-- The equal symbol. -->
        <v-col cols="1" class="pa-0 ma-0 pt-4">{{ "=" }}</v-col>

        <!-- The variable's value, it must can be deserialized. -->
        <v-col cols="5" class="pa-0 ma-0">
          <v-text-field
            variant="underlined"
            density="comfortable"
            hide-details
            spellcheck="false"
            v-model="arrValueCache[index]"
            @blur="updateValue(index, arrValueCache[index])"
            @keyup.enter="updateValue(index, arrValueCache[index])">
            <v-tooltip activator="parent" location="top">
              <span v-html="generateValueNote(item[1])"></span>
            </v-tooltip> </v-text-field
        ></v-col>
      </v-row>
    </v-container>

    <!-- The add button. -->
    <v-btn class="w-100" variant="outlined" @click="addNewArgument">
      <v-tooltip activator="parent" location="top">
        Click to add a new custom argument.
      </v-tooltip>
      <v-icon icon="mdi-playlist-plus"></v-icon>
    </v-btn>
  </v-container>
</template>

<script setup lang="ts">
import { watch, ref } from "vue";
import { debounce } from "lodash";
import { useArgsStore } from "../store";
import { showAlert, updateLocalData } from "../commonFunc";

const argsStore = useArgsStore();

// Initialize localValues as an array of stringified item values
const arrValueCache = ref(
  argsStore.customPrjArgs.map((item) => JSON.stringify(item[1], null, 0))
);

/* console.log("arrValueCache.value", arrValueCache.value);

watch(
  () => arrValueCache.value,
  () => {
    console.log("arrValueCache", JSON.stringify(arrValueCache.value, null, 4));
  },
  { deep: true }
);
 */
watch(
  () => argsStore.customPrjArgs,
  debounce(() => {
    arrValueCache.value = argsStore.customPrjArgs.map((item) =>
      JSON.stringify(item[1], null, 0)
    );

    updateLocalData(null, null, null, null, null, null, argsStore.customPrjArgs);
  }, 300),
  { deep: true }
);

function generateBgcolor(valueName: string): string {
  const arrNames = argsStore.customPrjArgs.filter((arrIn) => {
    if (arrIn[0] === valueName) {
      return true;
    }
  });
  if (arrNames.length >= 2) {
    return "warning";
  }
  return "";
}

function updateValue(index: number, value: string): void {
  try {
    argsStore.customPrjArgs[index][1] = JSON.parse(value);
  } catch (e) {
    showAlert(`It can't be deserialized: ${value}`);
    // Reset inputbox.
    arrValueCache.value = argsStore.customPrjArgs.map((item) =>
      JSON.stringify(item[1], null, 0)
    );
  }
}

function generateValueNote(value: any): string {
  return (
    "Original value:<br/>" +
    JSON.stringify(value, null, 0) +
    "<br/>(The value must can be deserialized.<br/>Press Enter or leave the inputbox to update.)" +
    (typeof value === "object" && value !== null && !Array.isArray(value)
      ? "<br/>(It is a dictionary, the keys may be reordered.)"
      : "")
  );
}
function addNewArgument(): void {
  argsStore.customPrjArgs.push(["", ""]);
}

function deleteArgument(index: number): void {
  argsStore.customPrjArgs.splice(index, 1);
}
</script>

<style scoped></style>
