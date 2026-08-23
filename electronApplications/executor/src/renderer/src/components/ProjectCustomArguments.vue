<template>
  <v-container
    v-if="
      projectStore.dictDetail_edit &&
      projectStore.dictDetail_edit.custom_prj_args.length !== 0
    "
    fluid
    class="clean-space flex-column-grow-1 flex-column">
    <v-row
      v-for="(item, index) in projectStore.dictDetail_edit.custom_prj_args"
      :key="index"
      class="clean-space"
      style="width: 100%; max-height: 40px">
      <v-col cols="6" class="pa-0 ma-0">
        <v-text-field
          v-model="item[0]"
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

      <!-- The equal symbol. -->
      <v-col cols="1" class="pa-0 ma-0 pt-4">{{ "=" }}</v-col>

      <!-- The variable's value, it must can be deserialized. -->
      <v-col cols="5" class="pa-0 ma-0">
        <v-text-field
          v-if="arrValueCache"
          v-model="arrValueCache[index]"
          variant="underlined"
          density="comfortable"
          hide-details
          spellcheck="false"
          @blur="
            updateCustomProjectArgumentValue(
              projectStore.dictDetail_edit.custom_prj_args,
              arrValueCache,
              index,
              arrValueCache[index],
            )
          "
          @keyup.enter="
            updateCustomProjectArgumentValue(
              projectStore.dictDetail_edit.custom_prj_args,
              arrValueCache,
              index,
              arrValueCache[index],
            )
          ">
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
import { watch } from "vue";
import { debounce } from "lodash";

import {
  getArgumentValueNote,
  updateCustomProjectArgumentValue,
  createCustomProjectArgumentValueCache,
  getCustomProjectArgumentValueCache,
} from "../RunOptions/runOptions";
import { useProjectStore } from "../Store/projectStore";

const projectStore = useProjectStore();

const arrValueCache = createCustomProjectArgumentValueCache(projectStore.dictDetail_edit);

// Define the debounced update function once
const debouncedUpdateValueCache = debounce(() => {
  if (projectStore.dictDetail_edit) {
    arrValueCache.value = getCustomProjectArgumentValueCache(projectStore.dictDetail_edit);
  }
}, 300);

watch(
  () => projectStore.dictDetail_edit?.custom_prj_args,
  () => {
    debouncedUpdateValueCache();
  },
  { deep: true },
);
</script>

<style scoped>
:deep(input) {
  text-overflow: ellipsis;
}
</style>
