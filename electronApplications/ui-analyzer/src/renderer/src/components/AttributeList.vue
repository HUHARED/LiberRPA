<!-- FileName: AttributeList.vue -->
<template>
  <v-container class="clean-space flex-column" style="height: 350px">
    <v-label class="area-header"> Secondary Attribute List </v-label>

    <!-- Show tip card when have no element. -->
    <v-card
      v-if="selectorStore.arrSecondaryAttr.length === 0"
      class="pa-0 ma-1"
      text="Indicate or validate an element to show its secondary attributes.">
    </v-card>

    <v-container v-else class="clean-space flex-column-grow-1">
      <!-- Display secondary attributes -->
      <v-row
        v-for="(dictAttr, index) in selectorStore.arrSecondaryAttr"
        :key="index"
        class="clean-space">
        <v-col cols="12" class="clean-space">
          <!-- In fact, all dictionary has only one item. -->

          <v-label class="clean-space pl-1 pr-1">
            {{ Object.keys(dictAttr)[0] }}
          </v-label>

          <v-text-field
            class="clean-space pl-1 pr-1"
            :value="dictAttr[Object.keys(dictAttr)[0]]"
            variant="underlined"
            density="compact"
            hide-details
            readonly
            spellcheck="false">
          </v-text-field>
        </v-col>
      </v-row>
    </v-container>
  </v-container>
</template>

<script setup lang="ts">
import { useSelectorStore } from "../store";

const selectorStore = useSelectorStore();
</script>

<style scoped></style>
