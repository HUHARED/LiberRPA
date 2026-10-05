<!-- FileName: RunDispatchEditor.vue -->
<template>
  <v-row>
    <v-col cols="12" md="6">
      <v-select
        v-model="settings.run_conflict_policy"
        :items="ARR_CONFLICT_POLICY"
        label="Conflict Policy"
        :disabled="disabled" />
    </v-col>
    <v-col cols="12" md="6">
      <v-select
        v-model="settings.priority"
        :items="ARR_PRIORITY"
        label="Priority"
        :disabled="disabled" />
    </v-col>
  </v-row>
  <RunEmailEditor
    v-model="settings.run_email"
    :argument-keys="settings.custom_prj_args.map((argument) => argument[0])"
    :disabled="disabled" />
</template>
<script setup lang="ts">
import RunEmailEditor from "./RunEmailEditor.vue";
import { ARR_CONFLICT_POLICY, ARR_PRIORITY, type RunSettings } from "@/api/runOptions";

defineProps<{ disabled?: boolean }>();
const settings = defineModel<RunSettings>({ required: true });
</script>
<style scoped></style>
