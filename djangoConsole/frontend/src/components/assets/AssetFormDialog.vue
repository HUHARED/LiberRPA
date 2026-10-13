<!-- FileName: AssetFormDialog.vue -->
<template>
  <v-dialog
    :model-value="true"
    persistent
    scrollable
    max-width="760"
    aria-labelledby="asset-form-title">
    <v-card>
      <v-card-title id="asset-form-title">{{ strTitle }}</v-card-title>
      <v-card-text>
        <v-form id="asset-form" validate-on="submit" @submit.prevent="submitAsset">
          <v-alert v-if="saveError" type="error" variant="tonal" class="mb-4" role="alert">
            Save was not confirmed. {{ saveError.message }}
            <p v-for="strMessage in saveError.fields.__all__" :key="strMessage">
              {{ strMessage }}
            </p>
          </v-alert>
          <v-row v-if="mode !== 'value'">
            <v-col cols="12" md="6">
              <v-text-field
                v-model="strName"
                label="Name"
                variant="outlined"
                :rules="[validatePathName]"
                :error-messages="saveError?.fields.name ?? []"
                :disabled="boolSaving" />
            </v-col>
            <v-col cols="12" md="6">
              <v-text-field
                v-if="asset"
                :model-value="asset.department.path"
                label="Department"
                variant="outlined"
                readonly />
              <v-select
                v-else
                v-model="strDepartmentId"
                :items="arrManagedDepartment"
                item-title="path"
                item-value="id"
                label="Department"
                variant="outlined"
                :rules="[(value) => !!value || 'Select a department.']"
                :disabled="boolSaving"
                :error-messages="saveError?.fields.department_id ?? []" />
            </v-col>
          </v-row>
          <v-text-field :model-value="strPath" label="Path" variant="outlined" readonly />
          <v-alert
            v-if="mode === 'details' && asset && strName !== asset.name"
            type="warning"
            variant="tonal"
            class="mb-4">
            Renaming changes the resource path. Update saved paths in your code and
            configuration.
          </v-alert>
          <v-select
            v-if="mode === 'create'"
            v-model="strAssetType"
            :items="ARR_ASSET_TYPE"
            label="Type"
            variant="outlined"
            hint="Department and Type are fixed after creation."
            persistent-hint
            class="mb-4"
            :disabled="boolSaving" />
          <v-text-field
            v-else
            :model-value="getAssetTypeLabel(strAssetType)"
            label="Type"
            variant="outlined"
            readonly />
          <v-textarea
            v-if="mode !== 'value'"
            v-model="strNotes"
            label="Notes"
            variant="outlined"
            rows="3"
            maxlength="2000"
            counter="2000"
            :disabled="boolSaving"
            :error-messages="saveError?.fields.notes ?? []" />
          <template v-if="mode !== 'details'">
            <v-alert v-if="asset && boolSecret" type="info" variant="tonal" class="mb-4">
              Enter the complete replacement value. The stored secret is never displayed.
            </v-alert>
            <v-switch
              v-if="strAssetType === 'boolean'"
              v-model="boolValue"
              :label="`Value: ${boolValue}`"
              color="primary"
              :disabled="boolSaving" />
            <template v-else-if="strAssetType === 'credential'">
              <v-text-field
                v-model="strUsername"
                label="Username"
                variant="outlined"
                autocomplete="off"
                :disabled="boolSaving" />
              <PasswordField
                v-model="strPassword"
                label="Password"
                autocomplete="new-password"
                :disabled="boolSaving" />
            </template>
            <PasswordField
              v-else-if="strAssetType === 'secret_text'"
              v-model="strValue"
              label="Value"
              autocomplete="new-password"
              :disabled="boolSaving" />
            <v-number-input
              v-else-if="strAssetType === 'integer' || strAssetType === 'number'"
              :key="strAssetType"
              v-model="floatValue"
              label="Value"
              variant="outlined"
              control-variant="stacked"
              inset
              :min="Number.MIN_SAFE_INTEGER"
              :max="Number.MAX_SAFE_INTEGER"
              :precision="strAssetType === 'integer' ? 0 : null"
              validate-on="blur"
              :rules="[validateValue]"
              :disabled="boolSaving" />
            <v-textarea
              v-else
              v-model="strValue"
              :label="strAssetType === 'json' ? 'Value (JSON)' : 'Value'"
              variant="outlined"
              rows="6"
              :rules="[validateValue]"
              :disabled="boolSaving" />
            <p
              v-for="strMessage in saveError?.fields.value ?? []"
              :key="strMessage"
              class="text-error mb-2"
              role="alert">
              {{ strMessage }}
            </p>
          </template>
          <v-alert v-if="!boolAllowed" type="info" variant="tonal" class="mt-3">
            No department permission is available for this operation.
          </v-alert>
        </v-form>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="tonal" :disabled="boolSaving" @click="emit('close')">Cancel</v-btn>
        <v-btn
          type="submit"
          form="asset-form"
          color="primary"
          variant="tonal"
          :loading="boolSaving"
          :disabled="boolSaving || !boolAllowed">
          {{ mode === "create" ? "Create" : "Save" }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from "vue";
import type { SubmitEventPromise } from "vuetify";

import PasswordField from "@/components/common/PasswordField.vue";

import { useSessionStore } from "@/stores/sessionStore";

import { validatePathName, validateJsonValue } from "@/app/validators";

import { ApiError, getApiError } from "@/api/errors";
import {
  ARR_ASSET_TYPE,
  isSecretAsset,
  getAssetTypeLabel,
  createAsset,
  updateAssetDetails,
  updateAssetValue,
} from "@/api/assets";
import type {
  AssetType,
  AssetDetailsEntryResponse,
  AssetDetailsResponse,
  AssetValueRequest,
} from "@/api/generated/browserApi";

const props = defineProps<{
  mode: "create" | "details" | "value";
  asset?: AssetDetailsEntryResponse;
}>();
const emit = defineEmits<{ close: []; saved: [response: AssetDetailsResponse] }>();
const sessionStore = useSessionStore();
const arrManagedDepartment = computed(() =>
  (sessionStore.access?.departments ?? []).filter(
    (department) => sessionStore.access?.is_org_admin || department.role === "developer",
  ),
);
const strDepartmentId = ref<string | null>(
  props.asset?.department.id ??
    (arrManagedDepartment.value.length === 1 ? arrManagedDepartment.value[0]!.id : null),
);
const strName = ref(props.asset?.name ?? "");
const strNotes = ref(props.asset?.notes ?? "");
const strAssetType = ref<AssetType>(props.asset?.asset_type ?? "text");
const strValue = ref(
  props.asset?.asset_type === "json"
    ? (JSON.stringify(props.asset.value, null, 2) ?? "")
    : typeof props.asset?.value === "string"
      ? props.asset.value
      : "",
);
const floatValue = ref<number | null>(
  typeof props.asset?.value === "number" ? props.asset.value : null,
);
const boolValue = ref(props.asset?.value === true);
const strUsername = ref("");
const strPassword = ref("");
const boolSaving = ref(false);
const saveError = shallowRef<ApiError | null>(null);
const boolSecret = computed(() => isSecretAsset(strAssetType.value));
const strTitle = computed(() =>
  props.mode === "create"
    ? "New Asset"
    : props.mode === "details"
      ? "Edit Details"
      : boolSecret.value
        ? "Replace Value"
        : "Edit Value",
);
const strPath = computed(() => {
  const strDepartmentPath =
    props.asset?.department.path ??
    arrManagedDepartment.value.find((department) => department.id === strDepartmentId.value)
      ?.path;
  return strDepartmentPath ? `/${strDepartmentPath}/${strName.value}` : "";
});
const boolAllowed = computed(() => {
  if (!sessionStore.access?.business_available) return false;
  if (props.mode === "create")
    return arrManagedDepartment.value.some(
      (department) => department.id === strDepartmentId.value,
    );
  const department = sessionStore.access.departments.find(
    (entry) => entry.id === props.asset?.department.id,
  );
  if (!department) return false;
  return props.mode === "value" && !boolSecret.value
    ? true
    : sessionStore.access.is_org_admin || department.role === "developer";
});
let boolUnmounted = false;

// Reuse the parsed value until one of its inputs changes.
const valueResult = computed(() => {
  try {
    const value = parseValue();
    validateJsonValue(value);
    return { valid: true as const, value };
  } catch (e) {
    return {
      valid: false as const,
      message: e instanceof Error ? e.message : "Enter a valid value.",
    };
  }
});

function parseValue(): AssetValueRequest["value"] {
  if (strAssetType.value === "boolean") return boolValue.value;
  if (strAssetType.value === "credential")
    return { username: strUsername.value, password: strPassword.value };
  if (strAssetType.value === "text" || strAssetType.value === "secret_text")
    return strValue.value;
  if (strAssetType.value === "integer" || strAssetType.value === "number") {
    if (floatValue.value === null) throw new Error("Enter a value.");
    return floatValue.value;
  }
  let value: unknown;
  try {
    value = JSON.parse(strValue.value);
  } catch {
    throw new Error("Enter valid JSON.");
  }
  return value as AssetValueRequest["value"];
}

function validateValue(): true | string {
  return valueResult.value.valid ? true : valueResult.value.message;
}

function getValue(): AssetValueRequest["value"] {
  const result = valueResult.value;
  if (!result.valid) throw new Error(result.message);
  return result.value;
}

async function submitAsset(event: SubmitEventPromise): Promise<void> {
  if (boolSaving.value || !boolAllowed.value || !(await event).valid) return;
  boolSaving.value = true;
  saveError.value = null;
  try {
    const response =
      props.mode === "create"
        ? await createAsset({
            department_id: strDepartmentId.value!,
            name: strName.value,
            notes: strNotes.value,
            asset_type: strAssetType.value,
            value: getValue(),
          })
        : props.mode === "details"
          ? await updateAssetDetails(props.asset!.id, {
              name: strName.value,
              notes: strNotes.value,
            })
          : await updateAssetValue(props.asset!.id, { value: getValue() });
    strValue.value = "";
    strUsername.value = "";
    strPassword.value = "";
    if (!boolUnmounted) emit("saved", response);
  } catch (e) {
    if (boolUnmounted) return;
    saveError.value =
      e instanceof ApiError
        ? e
        : new ApiError(e instanceof Error ? e.message : getApiError(e).message);
    if (saveError.value.statusCode === 403 || saveError.value.statusCode === 404)
      await sessionStore.refreshSession();
  } finally {
    boolSaving.value = false;
  }
}

watch(strAssetType, () => {
  strValue.value = "";
  floatValue.value = null;
  boolValue.value = false;
  strUsername.value = "";
  strPassword.value = "";
  saveError.value = null;
});
onBeforeUnmount(() => {
  boolUnmounted = true;
});
</script>

<style scoped></style>
