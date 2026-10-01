<!-- FileName: PasswordField.vue -->
<template>
  <v-text-field
    v-model="strPassword"
    :type="boolVisible ? 'text' : 'password'"
    :disabled="disabled"
    variant="outlined">
    <template #append-inner>
      <v-btn
        type="button"
        variant="text"
        size="small"
        :icon="boolVisible ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
        :aria-label="boolVisible ? 'Hide password' : 'Show password'"
        :disabled="disabled"
        @click="boolVisible = !boolVisible" />
    </template>
  </v-text-field>
</template>

<script setup lang="ts">
import { ref, watch } from "vue";

defineProps<{ disabled?: boolean }>();
const strPassword = defineModel<string>({ required: true });
const boolVisible = ref(false);

watch(strPassword, (value) => {
  if (!value) boolVisible.value = false;
});
</script>

<style scoped></style>
