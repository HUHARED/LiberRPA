<template>
  <v-container fluid class="pa-2 ma-0">
    <v-tooltip location="bottom">
      <template #activator="{ props }">
        <v-switch
          v-model="settingStore.keepRdpSession"
          label="Keep RDP Session"
          hide-details
          v-bind="props"
          prepend-icon="mdi-account-lock-open-outline"
          true-icon="mdi-lock-open-variant-outline"
          density="compact">
        </v-switch>
      </template>

      <div>
        Keep the GUI session active after an RDP connection is disconnected.<br />
        Executor must run as administrator.<br />
        If the mouse has not moved for 30 seconds, Executor moves it to help prevent the
        screen from locking. This cannot prevent every type of session lock.<br />
        (May not work without a Virtual Display Driver or when multiple users are active.)
      </div>
    </v-tooltip>
  </v-container>

  <v-container fluid class="pa-2 ma-0 flex-row">
    <v-tooltip activator="parent" location="bottom">
      <div>
        Session width after RDP is disconnected.<br />
        Range: 480–7680 px.
      </div>
    </v-tooltip>

    <v-icon class="pa-0 ma-0 mt-2 ml-12 mr-2" color="grey" icon="mdi-arrow-split-vertical">
    </v-icon>

    <v-text-field
      class="clean-space"
      density="compact"
      hide-details
      variant="plain"
      readonly
      spellcheck="false"
      style="max-width: 210px"
      model-value="Session Width">
    </v-text-field>

    <v-number-input
      v-model="intKeepRdpSessionWidth"
      class="pa-0 ma-0 ml-2"
      density="compact"
      hide-details
      control-variant="stacked"
      inset
      :min="480"
      :max="7680"
      :precision="0"
      style="max-width: 100px"
      :disabled="!settingStore.keepRdpSession">
    </v-number-input>

    <span class="pa-0 ma-0 mt-2">px</span>
  </v-container>

  <v-container fluid class="pa-2 ma-0 flex-row">
    <v-tooltip activator="parent" location="bottom">
      <div>
        Session height after RDP is disconnected.<br />
        Range: 480–7680 px.
      </div>
    </v-tooltip>

    <v-icon
      class="pa-0 ma-0 mt-2 ml-12 mr-2"
      color="grey"
      icon="mdi-arrow-split-horizontal">
    </v-icon>

    <v-text-field
      class="clean-space"
      density="compact"
      hide-details
      variant="plain"
      readonly
      spellcheck="false"
      style="max-width: 210px"
      model-value="Session Height">
    </v-text-field>

    <v-number-input
      v-model="intKeepRdpSessionHeight"
      class="pa-0 ma-0 ml-2"
      density="compact"
      hide-details
      control-variant="stacked"
      inset
      :min="480"
      :max="7680"
      :precision="0"
      style="max-width: 100px"
      :disabled="!settingStore.keepRdpSession">
    </v-number-input>

    <span class="pa-0 ma-0 mt-2">px</span>
  </v-container>
</template>

<script setup lang="ts">
import { computed } from "vue";

import { useInformationStore } from "../../Store/informationStore";
import { useSettingStore } from "../../Store/settingStore";

const informationStore = useInformationStore();
const settingStore = useSettingStore();

const intKeepRdpSessionWidth = computed<number>({
  get() {
    return settingStore.keepRdpSessionWidth;
  },
  set(newValue: number | null) {
    if (newValue === null) {
      informationStore.showAlertMessage(
        `It's not an integer between 480 and 7680. (${newValue})`,
      );
      return;
    }

    if (newValue >= 480 && newValue <= 7680) {
      settingStore.keepRdpSessionWidth = newValue;
    }
  },
});

const intKeepRdpSessionHeight = computed<number>({
  get() {
    return settingStore.keepRdpSessionHeight;
  },
  set(newValue: number | null) {
    if (newValue === null) {
      informationStore.showAlertMessage(
        `It's not an integer between 480 and 7680. (${newValue})`,
      );
      return;
    }

    if (newValue >= 480 && newValue <= 7680) {
      settingStore.keepRdpSessionHeight = newValue;
    }
  },
});
</script>

<style scoped></style>
