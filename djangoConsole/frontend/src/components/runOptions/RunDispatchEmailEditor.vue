<!-- FileName: RunDispatchEmailEditor.vue -->
<template>
  <v-row>
    <v-col cols="12" md="6">
      <v-select
        v-model="settings.run_conflict_policy"
        :error-messages="getFieldErrors(fieldErrors, 'settings.run_conflict_policy')"
        :items="ARR_CONFLICT_POLICY_OPTION"
        label="Conflict Policy"
        :disabled="disabled" />
    </v-col>
    <v-col cols="12" md="6">
      <v-select
        v-model="settings.priority"
        :error-messages="getFieldErrors(fieldErrors, 'settings.priority')"
        :items="ARR_PRIORITY_OPTION"
        label="Priority"
        :disabled="disabled" />
    </v-col>
  </v-row>
  <RunEmailEditor
    v-model="settings.run_email"
    :field-errors="fieldErrors"
    :argument-keys="settings.custom_prj_args.map((argument) => argument[0])"
    :disabled="disabled" />
</template>
<script setup lang="ts">
import { getFieldErrors } from "@/api/errors";
import RunEmailEditor from "./RunEmailEditor.vue";
import type { RunSettings } from "@/api/runOptions";
import { ARR_CONFLICT_POLICY_OPTION, ARR_PRIORITY_OPTION } from "@/app/runLabels";

defineProps<{
  disabled?: boolean;
  fieldErrors?: Record<string, string[]>;
}>();
const settings = defineModel<RunSettings>({ required: true });
</script>
<style scoped></style>
