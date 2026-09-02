<!-- FileName: PublishComponentView.vue -->
<template>
  <v-card class="mx-auto" max-width="1050">
    <v-card-title class="d-flex align-center pa-5 pb-2">
      <span class="text-h5">Publish Component</span>
      <v-spacer></v-spacer>
      <v-btn
        icon="mdi-refresh"
        variant="text"
        :disabled="projectManagerStore.busy"
        @click="refresh">
      </v-btn>
    </v-card-title>

    <v-card-subtitle class="px-5 pb-4">
      {{ manifest.displayName }} · {{ publishComponentStore.projectPath }}
    </v-card-subtitle>

    <v-divider></v-divider>

    <v-card-text class="pa-5">
      <v-row class="mb-2">
        <v-col cols="12" sm="6" lg="3">
          <v-card variant="tonal" class="pa-3 h-100">
            <div class="text-caption mb-1">Package</div>
            <div class="font-weight-medium">{{ manifest.packageName }}</div>
          </v-card>
        </v-col>
        <v-col cols="12" sm="6" lg="3">
          <v-card variant="tonal" class="pa-3 h-100">
            <div class="text-caption mb-1">Version</div>
            <div class="font-weight-medium">{{ manifest.version }}</div>
          </v-card>
        </v-col>
        <v-col cols="12" sm="6" lg="3">
          <v-card variant="tonal" class="pa-3 h-100">
            <div class="text-caption mb-1">requiresLiberrpa</div>
            <div class="font-weight-medium">{{ manifest.requiresLiberrpa }}</div>
          </v-card>
        </v-col>
        <v-col cols="12" sm="6" lg="3">
          <v-card variant="tonal" class="pa-3 h-100">
            <div class="text-caption mb-1">Direct dependencies</div>
            <div class="font-weight-medium">{{ directDependencyCount }}</div>
          </v-card>
        </v-col>
      </v-row>

      <v-card variant="outlined" class="mb-5">
        <v-card-title class="text-subtitle-1">Component identity</v-card-title>
        <v-card-text>
          <div class="text-caption text-medium-emphasis">Component ID</div>
          <div class="text-body-2 text-break">{{ manifest.id }}</div>
          <div v-if="manifest.description" class="mt-3">
            <div class="text-caption text-medium-emphasis">Description</div>
            <div class="text-body-2">{{ manifest.description }}</div>
          </div>
        </v-card-text>
      </v-card>

      <v-card variant="outlined" class="mb-5">
        <v-card-title class="text-subtitle-1">Snippet files</v-card-title>
        <v-card-text>
          <v-row align="center" class="mb-2">
            <v-col cols="12" md="7">
              <div class="font-weight-medium">AST Snippet scan result</div>
              <div class="text-caption text-medium-emphasis text-break">
                {{ publishComponentStore.astSnippetsFile }}
              </div>
            </v-col>
            <v-col cols="12" md="5" class="d-flex align-center justify-end ga-2">
              <v-chip
                size="small"
                :color="
                  publishComponentStore.astSnippetsFileExists ? 'success' : 'warning'
                ">
                {{ publishComponentStore.astSnippetsFileExists ? "Available" : "Missing" }}
              </v-chip>
              <v-btn
                size="small"
                variant="tonal"
                prepend-icon="mdi-file-code-outline"
                :disabled="
                  projectManagerStore.busy || !publishComponentStore.astSnippetsFileExists
                "
                @click="openFile('astSnippets')">
                Open
              </v-btn>
            </v-col>
          </v-row>

          <v-divider class="my-3"></v-divider>

          <v-row align="center">
            <v-col cols="12" md="7">
              <div class="font-weight-medium">Snippet configuration</div>
              <div class="text-caption text-medium-emphasis text-break">
                {{ publishComponentStore.snippetsJsoncFile }}
              </div>
            </v-col>
            <v-col cols="12" md="5" class="d-flex align-center justify-end ga-2">
              <v-chip
                size="small"
                :color="
                  publishComponentStore.snippetsJsoncFileExists ? 'success' : 'warning'
                ">
                {{
                  publishComponentStore.snippetsJsoncFileExists ? "Available" : "Missing"
                }}
              </v-chip>
              <v-btn
                size="small"
                variant="tonal"
                prepend-icon="mdi-file-edit-outline"
                :disabled="
                  projectManagerStore.busy || !publishComponentStore.snippetsJsoncFileExists
                "
                @click="openFile('snippetsConfig')">
                Open
              </v-btn>
            </v-col>
          </v-row>
        </v-card-text>
      </v-card>

      <v-alert v-if="publishResult === null" type="info" variant="tonal" class="mb-4">
        <template v-if="publishComponentStore.snippetsJsoncFileExists">
          The Snippet configuration exists. Running Publish Component will scan the current
          source, rebuild the Snippet Catalog and publish the Wheel.
        </template>
        <template v-else>
          Running Publish Component will first create the AST scan result and Snippet
          configuration template.<br />
          Review the files in the VS Code editor, then run Publish Component again.
        </template>
      </v-alert>

      <template v-else-if="publishResult.status === 'preparationCreated'">
        <v-alert type="info" variant="tonal" class="mb-4">
          Publish preparation was created. Review the generated AST result and edit
          snippets.jsonc in the VS Code editor before publishing.
        </v-alert>
        <v-row class="mb-2">
          <v-col cols="12" sm="4">
            <v-card variant="tonal" class="pa-3 h-100">
              <div class="text-caption mb-1">Generated</div>
              <div class="text-h6">{{ publishResult.generatedCount }}</div>
            </v-card>
          </v-col>
          <v-col cols="12" sm="4">
            <v-card variant="tonal" class="pa-3 h-100">
              <div class="text-caption mb-1">Skipped</div>
              <div class="text-h6">{{ publishResult.skippedCount }}</div>
            </v-card>
          </v-col>
          <v-col cols="12" sm="4">
            <v-card variant="tonal" class="pa-3 h-100">
              <div class="text-caption mb-1">Warnings</div>
              <div class="text-h6">{{ publishResult.warningCount }}</div>
            </v-card>
          </v-col>
        </v-row>
      </template>

      <template v-else>
        <v-alert
          :type="publishResult.status === 'published' ? 'success' : 'warning'"
          variant="tonal"
          class="mb-4">
          <template v-if="publishResult.status === 'published'">
            The Component Wheel was published successfully.
          </template>
          <template v-else>
            An identical Component version is already present in the ComponentRepository.
          </template>
        </v-alert>

        <v-card variant="outlined" class="mb-5">
          <v-card-title class="text-subtitle-1">Publish result</v-card-title>
          <v-card-text>
            <v-row>
              <v-col cols="12" md="6">
                <div class="text-caption text-medium-emphasis">Wheel file</div>
                <div class="text-body-2 text-break">
                  {{ publishResult.wheelFileName }}
                </div>
              </v-col>
              <v-col cols="12" md="6">
                <div class="text-caption text-medium-emphasis">SHA-256</div>
                <div class="text-body-2 text-break">{{ publishResult.sha256 }}</div>
              </v-col>
            </v-row>
            <v-row class="mt-1">
              <v-col cols="6" sm="4" lg="2">
                <div class="text-caption">Generated</div>
                <div class="font-weight-medium">{{ publishResult.generatedCount }}</div>
              </v-col>
              <v-col cols="6" sm="4" lg="2">
                <div class="text-caption">Excluded</div>
                <div class="font-weight-medium">{{ publishResult.excludedCount }}</div>
              </v-col>
              <v-col cols="6" sm="4" lg="2">
                <div class="text-caption">Hand-written</div>
                <div class="font-weight-medium">{{ publishResult.handWrittenCount }}</div>
              </v-col>
              <v-col cols="6" sm="4" lg="2">
                <div class="text-caption">Final</div>
                <div class="font-weight-medium">{{ publishResult.finalCount }}</div>
              </v-col>
              <v-col cols="6" sm="4" lg="2">
                <div class="text-caption">Skipped</div>
                <div class="font-weight-medium">{{ publishResult.skippedCount }}</div>
              </v-col>
              <v-col cols="6" sm="4" lg="2">
                <div class="text-caption">Warnings</div>
                <div class="font-weight-medium">{{ publishResult.warningCount }}</div>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>
      </template>

      <v-alert
        v-for="(warningMessage, intIndex) in publishComponentStore.warningMessages"
        :key="`publish-warning-${String(intIndex)}`"
        type="warning"
        variant="tonal"
        class="mb-3">
        {{ warningMessage }}
      </v-alert>
    </v-card-text>

    <v-divider></v-divider>

    <v-card-actions class="pa-5 justify-end">
      <v-btn variant="text" :disabled="projectManagerStore.busy" @click="close">
        Close
      </v-btn>
      <v-btn
        color="primary"
        prepend-icon="mdi-package-up"
        :loading="projectManagerStore.busy"
        :disabled="projectManagerStore.busy"
        @click="runPublish">
        {{ publishButtonLabel }}
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup lang="ts">
import { computed } from "vue";

import { postMessage } from "../Adapter/Extension/vscodeApi";
import { usePublishComponentStore } from "../Application/Publish/publishComponentStore";
import { useProjectManagerStore } from "../Application/projectManagerStore";
import type { Str_PublishComponentFile } from "../Adapter/Extension/projectManagerMessages";

const projectManagerStore = useProjectManagerStore();
const publishComponentStore = usePublishComponentStore();

const manifest = computed(() => {
  if (publishComponentStore.manifest === null) {
    throw new Error("Publish Component Manifest is unavailable.");
  }
  return publishComponentStore.manifest;
});

const publishResult = computed(() => publishComponentStore.publishResult);
const directDependencyCount = computed(
  () => Object.keys(manifest.value.componentDependencies).length,
);
const publishButtonLabel = computed(() =>
  publishComponentStore.snippetsJsoncFileExists ? "Publish Component" : "Prepare Publish",
);

function runPublish(): void {
  if (!projectManagerStore.busy) {
    postMessage({ command: "runPublishComponent" });
  }
}

function refresh(): void {
  if (!projectManagerStore.busy) {
    postMessage({ command: "refreshPublishComponent" });
  }
}

function openFile(file: Str_PublishComponentFile): void {
  if (!projectManagerStore.busy) {
    postMessage({ command: "openPublishComponentFile", file });
  }
}

function close(): void {
  if (!projectManagerStore.busy) {
    postMessage({ command: "cancel" });
  }
}
</script>
