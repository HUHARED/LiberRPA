<!-- FileName: ScheduleDetailsView.vue -->
<template>
  <div class="d-flex align-center ga-2 mb-4">
    <v-btn to="/schedules" variant="tonal" prepend-icon="mdi-arrow-left">
      Back to Schedules
    </v-btn>
    <v-spacer />
    <v-btn :loading="boolLoading" variant="tonal" @click="load">Refresh</v-btn>
  </div>

  <v-alert v-if="strError" type="error" variant="tonal" class="mb-4">
    {{ strError }}
  </v-alert>

  <template v-if="schedule">
    <div class="d-flex align-center flex-wrap ga-3 mb-4">
      <h1 class="text-h5">{{ schedule.name }}</h1>
      <v-chip>{{ schedule.enabled ? "Enabled" : "Disabled" }}</v-chip>
      <v-spacer />
      <v-btn v-if="schedule.can_manage" variant="tonal" @click="boolEdit = true">
        Edit
      </v-btn>

      <v-btn
        v-if="schedule.can_manage"
        color="error"
        variant="tonal"
        @click="boolDelete = true">
        Delete
      </v-btn>
    </div>

    <v-card variant="outlined" class="mb-4">
      <v-card-text>
        <v-table>
          <tbody>
            <tr>
              <th scope="row" class="text-caption text-medium-emphasis">Department</th>
              <td>{{ schedule.department.path }}</td>
            </tr>

            <tr>
              <th scope="row" class="text-caption text-medium-emphasis">Package</th>
              <td>
                <RouterLink
                  class="text-primary text-decoration-none"
                  :to="{
                    name: 'package-details',
                    params: { packageId: schedule.package_id },
                  }">
                  {{ schedule.project_name }} · {{ schedule.project_version }}
                </RouterLink>
              </td>
            </tr>

            <tr>
              <th scope="row" class="text-caption text-medium-emphasis">Target</th>
              <td>
                <RouterLink
                  v-if="schedule.group_id"
                  class="text-primary text-decoration-none"
                  :to="{
                    name: 'executor-group-details',
                    params: { groupId: schedule.group_id },
                  }">
                  {{ schedule.executor_group?.name || "Executor Group" }}
                </RouterLink>
                <template v-else>
                  <p v-for="executor in schedule.executors ?? []" :key="executor.id">
                    <RouterLink
                      class="text-primary text-decoration-none"
                      :to="{
                        name: 'executor-details',
                        params: { executorId: executor.id },
                      }">
                      {{ executor.name }}
                    </RouterLink>
                  </p>
                </template>
              </td>
            </tr>

            <tr>
              <th scope="row" class="text-caption text-medium-emphasis">Notes</th>
              <td class="text-pre-wrap">{{ schedule.notes || "—" }}</td>
            </tr>

            <tr>
              <th scope="row" class="text-caption text-medium-emphasis">Conflict Policy</th>
              <td>{{ CONFLICT_POLICY_LABELS[schedule.settings.run_conflict_policy] }}</td>
            </tr>

            <tr>
              <th scope="row" class="text-caption text-medium-emphasis">Priority</th>
              <td>{{ PRIORITY_LABELS[schedule.settings.priority] }}</td>
            </tr>
          </tbody>
        </v-table>
      </v-card-text>
    </v-card>

    <v-card variant="outlined" class="mb-4">
      <v-card-title>Time</v-card-title>

      <v-card-text>
        <p>{{ strDescription }}</p>

        <p>
          <span class="text-caption text-medium-emphasis">Cron:</span>
          {{ schedule.cron }}
        </p>

        <p>
          <span class="text-caption text-medium-emphasis">Time Zone:</span>
          {{ schedule.time_zone }}
        </p>

        <p>
          <span class="text-caption text-medium-emphasis">Active From:</span>
          {{ formatDateTime(schedule.active_from, schedule.time_zone) }}
        </p>

        <p>
          <span class="text-caption text-medium-emphasis">Active Until:</span>
          {{ formatDateTime(schedule.active_until, schedule.time_zone) }}
        </p>

        <h3 class="text-subtitle-1 mt-4">Upcoming Triggers</h3>

        <p v-for="time in schedule.upcoming_triggers" :key="time">
          {{ formatDateTime(time, schedule.time_zone) }}
        </p>

        <p v-if="!schedule.upcoming_triggers.length">
          No upcoming trigger within the active period.
        </p>
      </v-card-text>
    </v-card>

    <v-card variant="outlined" class="mb-4">
      <v-card-title>Run Settings</v-card-title>

      <v-card-text>
        <RunArgumentsDetails
          :settings="schedule.settings"
          :python-environment-name="schedule.python_environment_name" />

        <h3 class="text-subtitle-1 mt-4">Asset Bindings</h3>

        <p
          v-for="(binding, index) in schedule.settings.custom_arg_assets"
          v-show="binding"
          :key="index">
          {{ schedule.settings.custom_prj_args[index]?.[0] }} → {{ binding?.name }} ({{
            binding?.asset_type
          }})
        </p>
      </v-card-text>
    </v-card>

    <v-card variant="outlined">
      <v-card-title>Run Email</v-card-title>

      <v-card-text>
        <RunEmailEditor
          :model-value="schedule.settings.run_email"
          :argument-keys="
            schedule.settings.custom_prj_args.map(
              (argument: [string, unknown]) => argument[0],
            )
          "
          disabled />
      </v-card-text>
    </v-card>
  </template>

  <ScheduleFormDialog
    v-if="boolEdit"
    :schedule-id="scheduleId"
    @close="boolEdit = false"
    @saved="saved" />

  <v-dialog v-model="boolDelete" persistent max-width="560">
    <v-card>
      <v-card-title>Delete Schedule</v-card-title>

      <v-card-text>
        Future triggers will stop. Already accepted Jobs continue independently, including
        waiting and retries.
        <v-alert v-if="strDeleteError" type="error" variant="tonal" class="mt-4">
          {{ strDeleteError }}
        </v-alert>
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn variant="tonal" :disabled="boolBusy" @click="boolDelete = false">
          Cancel
        </v-btn>

        <v-btn variant="tonal" color="error" :loading="boolBusy" @click="remove">
          Delete
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { shallowRef, computed, ref, watch } from "vue";
import { RouterLink, useRouter } from "vue-router";
import cronstrue from "cronstrue";

import ScheduleFormDialog from "@/components/schedules/ScheduleFormDialog.vue";
import RunArgumentsDetails from "@/components/runSettings/RunArgumentsDetails.vue";
import RunEmailEditor from "@/components/runSettings/RunEmailEditor.vue";

import { getSchedule, deleteSchedule, type ScheduleInfo } from "@/api/schedules";
import { getApiError } from "@/api/errors";

import { CONFLICT_POLICY_LABELS, PRIORITY_LABELS } from "@/app/runLabels";
import { formatDateTime } from "@/app/formatters";

const props = defineProps<{ scheduleId: string }>();
const router = useRouter();
const schedule = shallowRef<ScheduleInfo | null>(null);
const boolLoading = ref(false);
const boolBusy = ref(false);
const boolEdit = ref(false);
const boolDelete = ref(false);
const strError = ref("");
const strDeleteError = ref("");

const strDescription = computed(() => {
  try {
    return cronstrue.toString(schedule.value?.cron ?? "", { use24HourTimeFormat: true });
  } catch {
    return "";
  }
});

let intLoadRevision = 0;

async function load(): Promise<void> {
  const intRevision = ++intLoadRevision;
  boolLoading.value = true;
  strError.value = "";
  try {
    const response = await getSchedule(props.scheduleId);
    if (intRevision === intLoadRevision) schedule.value = response;
  } catch (e) {
    if (intRevision === intLoadRevision) strError.value = getApiError(e).message;
  } finally {
    if (intRevision === intLoadRevision) boolLoading.value = false;
  }
}

function saved(): void {
  boolEdit.value = false;
  void load();
}

async function remove(): Promise<void> {
  boolBusy.value = true;
  strDeleteError.value = "";
  try {
    await deleteSchedule(props.scheduleId);
    await router.push({ name: "schedules" });
  } catch (e) {
    strDeleteError.value = getApiError(e).message;
  } finally {
    boolBusy.value = false;
  }
}

watch(
  () => props.scheduleId,
  () => {
    schedule.value = null;
    void load();
  },
  { immediate: true },
);
</script>

<style scoped></style>
