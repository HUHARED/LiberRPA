<!-- FileName: App.vue -->
<template>
  <v-app class="clean-space fill-height" :theme="settingStore.theme">
    <!-- The Alert area, doesn't join in layout -->
    <Alert />

    <v-main class="clean-space fill-height">
      <v-container class="clean-space fill-height flex-row" fluid>
        <TabBar />
        <component :is="componentCurrent" />
      </v-container>
    </v-main>
  </v-app>
</template>

<script setup lang="ts">
import { computed } from "vue";
import Alert from "./components/Alert.vue";
import TabBar from "./components/TabBar.vue";
import ProjectLocalPackage from "./components/ProjectLocalPackage.vue";
import TaskScheduler from "./components/TaskScheduler.vue";
import TaskQueue from "./components/TaskQueue.vue";
import TaskHistory from "./components/TaskHistory.vue";
import Setting from "./components/Setting.vue";
import { loggerRenderer } from "./ipcOfRenderer";
import {
  useSettingStore,
  useInformationStore,
  useSchedulerStore,
  useQueueStore,
} from "./store";

const settingStore = useSettingStore();
const informationStore = useInformationStore();
const schedulerStore = useSchedulerStore();
const queueStore = useQueueStore();

/*
Run schedulerStore.dbSelectSchedulerList in the root of renderer, to Initialize data for queue. 
So even users didn't opened Task Scheduler or Task Queue, the task can also be ran.
*/
schedulerStore.dbSelectSchedulerList();

/*
Loop to check if there are tasks to run. 
*/
setInterval(async () => {
  if (queueStore.arrListItem.length !== 0) {
    await queueStore.checkWhetherRun_PendingItem();
  }
}, 1000);

const componentCurrent = computed(() => {
  loggerRenderer.info(`Switch to tab: ${informationStore.tab}`);
  switch (informationStore.tab) {
    case "Project Local Package":
      return ProjectLocalPackage;
    case "Task Scheduler":
      // onBeforeMount in TaskScheduler.vue will Initialize data.
      return TaskScheduler;
    case "Task Queue":
      // onBeforeMount in TaskQueue.vue will Initialize data.
      return TaskQueue;
    case "Task History":
      // onBeforeMount in TaskHistory.vue will Initialize data.
      return TaskHistory;
    default:
      return Setting;
  }
});
</script>

<style scoped></style>
