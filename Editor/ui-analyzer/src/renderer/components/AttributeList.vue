<!-- FileName: AttributeList.vue -->
<template>
  <v-container class="clean-space flex-column" style="height: 350px">
    <v-label class="header-label"> Secondary Attribute List </v-label>

    <!-- Show tip card when have no element. -->
    <v-card
      v-if="selectorStore.arrSecondaryAttr.length === 0"
      class="pa-0 ma-1"
      text="Indicate or validate an element to show its secondary attributes."
    ></v-card>

    <v-container v-else class="clean-space flex-column-grow-1">
      <!-- Display secondary attributes -->
      <v-row
        class="clean-space"
        v-for="(attr, index) in selectorStore.arrSecondaryAttr"
        :key="index"
      >
        <v-col cols="12" class="clean-space">
          <v-label class="clean-space pl-1 pr-1" v-for="(_, key) in attr" :key="key">
            {{ key.toString() }}
          </v-label>
          <v-text-field
            class="clean-space pl-1 pr-1"
            v-for="(value, key) in attr"
            :key="key"
            :value="value"
            variant="underlined"
            density="compact"
            hide-details
            readonly
            spellcheck="false"
          >
          </v-text-field
        ></v-col>
      </v-row>
    </v-container>
  </v-container>
</template>

<script setup lang="ts">
// import { loggerRenderer } from "../ipcOfRenderer";

import { useSelectorStore } from "../store";
const selectorStore = useSelectorStore();
</script>

<style scoped></style>
