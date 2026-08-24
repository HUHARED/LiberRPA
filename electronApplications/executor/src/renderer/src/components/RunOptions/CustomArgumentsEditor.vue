<template>
  <v-container
    v-if="customArgs.length !== 0"
    fluid
    class="clean-space flex-column-grow-1 flex-column">
    <v-row
      v-for="(item, index) in customArgs"
      :key="index"
      class="clean-space"
      style="width: 100%; max-height: 40px">
      <v-col cols="6" class="pa-0 ma-0">
        <v-text-field
          :model-value="item[0]"
          variant="plain"
          density="comfortable"
          hide-details
          readonly
          spellcheck="false">
          <v-tooltip activator="parent" location="top">
            {{ item[0] }}
          </v-tooltip>
        </v-text-field>
      </v-col>

      <v-col cols="1" class="pa-0 ma-0 pt-4">{{ "=" }}</v-col>

      <v-col cols="5" class="pa-0 ma-0">
        <v-text-field
          v-model="arrValueCache[index]"
          variant="underlined"
          density="comfortable"
          hide-details
          spellcheck="false"
          @blur="updateValue(index)"
          @keyup.enter="updateValue(index)">
          <v-tooltip activator="parent" location="top">
            <span v-html="getArgumentValueNote(item[1])"></span>
          </v-tooltip>
        </v-text-field>
      </v-col>
    </v-row>
  </v-container>

  <v-container v-else fluid class="clean-space"> No custom arguments. </v-container>
</template>

<script setup lang="ts">
import { ref, watch } from "vue";

import {
  getArgumentValueNote,
  updateCustomProjectArgumentValue,
} from "../../RunOptions/runOptions";
import type { TypeCustomProjectArgs } from "../../../../shared/runOptions";

const customArgs = defineModel<TypeCustomProjectArgs>("customArgs", { required: true });

const arrValueCache = ref<string[]>([]);

function refreshValueCache(): void {
  arrValueCache.value = customArgs.value.map((item) => JSON.stringify(item[1], null, 0));
}

function updateValue(index: number): void {
  const value = arrValueCache.value[index];
  if (value === undefined) {
    return;
  }

  const arrCustomArgs = customArgs.value.map(([name, argumentValue]): [string, unknown] => [
    name,
    argumentValue,
  ]);
  updateCustomProjectArgumentValue(arrCustomArgs, arrValueCache.value, index, value);
  customArgs.value = arrCustomArgs;
}

watch(
  customArgs,
  () => {
    refreshValueCache();
  },
  { deep: true, immediate: true },
);
</script>

<style scoped>
:deep(input) {
  text-overflow: ellipsis;
}
</style>
