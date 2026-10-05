<!-- FileName: VerifyRunEmailView.vue -->
<template>
  <v-card max-width="640" class="mx-auto">
    <v-card-title>Run Email Verification</v-card-title>
    <v-card-text>
      <v-alert v-if="strError" type="error" variant="tonal" class="mb-4">
        {{ strError }}
      </v-alert>
      <v-progress-linear v-if="boolLoading" indeterminate />
      <template v-if="info">
        <p class="mb-4">
          {{ info.organization_name }} would like to send automation run notifications to
          {{ info.email }}.
        </p>
        <v-alert v-if="info.verified" type="success" variant="tonal">
          This address is verified.
        </v-alert>
        <v-btn v-else color="primary" :loading="boolBusy" @click="confirm">
          Confirm Email Address
        </v-btn>
      </template>
    </v-card-text>
  </v-card>
</template>
<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { verifyRunEmail } from "@/api/runEmail";
import { getApiError } from "@/api/errors";
const route = useRoute();
const strToken =
  new URLSearchParams(route.hash.slice(1)).get("token") ??
  (typeof route.query.token === "string" ? route.query.token : "");
const info = ref<Awaited<ReturnType<typeof verifyRunEmail>> | null>(null);
const strError = ref("");
const boolLoading = ref(true);
const boolBusy = ref(false);
async function confirm(): Promise<void> {
  boolBusy.value = true;
  strError.value = "";
  try {
    info.value = await verifyRunEmail(strToken, true);
  } catch (e) {
    strError.value = getApiError(e).message;
  } finally {
    boolBusy.value = false;
  }
}
onMounted(async () => {
  try {
    info.value = await verifyRunEmail(strToken);
  } catch (e) {
    strError.value = getApiError(e).message;
  } finally {
    boolLoading.value = false;
  }
});
</script>
<style scoped></style>
