<!-- FileName: ElementTree.vue -->
<template>
  <v-container class="clean-space flex-column-grow-1 flex-column">
    <v-label class="area-header">Element Tree</v-label>
    <v-card v-if="selectorStore.arrEleTree.length === 0" class="ma-1 h-60 pa-3">
      <div>
        Indicate or validate an uia or html element to show its Element Tree.<br />
        If the Element Tree is too big to handle in 10 seconds, LiberRPA will give up.
      </div>
    </v-card>

    <v-container v-else class="clean-space flex-column-grow-1">
      <v-treeview
        :items="selectorStore.arrEleTree"
        class="clean-space"
        style="width: max-content"
        activatable
        rounded
        collapse-icon="mdi-folder-open-outline"
        expand-icon="mdi-folder-outline"
        density="compact"
        :lines="false"
        variant="flat"
        item-value="id"
        :activated="selectorStore.intEleTreeActivated"
        :opened="selectorStore.arrEleTreeOpened">
        <template #title="{ item }">
          <span
            class="clean-space text-no-wrap"
            @click="handleNodeClick($event, item.id)"
            >{{ item.title }}</span
          >
          <v-tooltip activator="parent" location="bottom">
            <div>
              {{ JSON.stringify(item.spec, null, 2) }}
              <br />
              ------------------------
              <br />
              The layer's specification, click to replace the Element Hierarchy.
              <br />
              Note:
              <br />
              For uia element, you maybe need to add "Index" manually if there are other
              elements with same attributes in its parent element, and add "Depth" manually
              if you unchecked some layers;
              <br />
              For html element, you maybe need to edit or add "childIndex" manually.
            </div>
          </v-tooltip>
        </template>
      </v-treeview>
    </v-container>
  </v-container>
</template>

<script setup lang="ts">
import { VTreeview } from "vuetify/labs/VTreeview";

import { loggerRenderer } from "../ipcOfRenderer";
import { SelectorNonWindow } from "../../../shared/interface";
import { useSelectorStore } from "../store";

const selectorStore = useSelectorStore();

function handleNodeClick(_: MouseEvent, id: number): void {
  loggerRenderer.debug("Click Element Tree node " + id);
  console.log(selectorStore.dictEleTreeSelector[id]);

  // Reassign to to clean the highlight. Due to the watcher has 300 ms delay, so add delay before add element into arrEleHierarchy again.
  selectorStore.arrEleHierarchy = [];
  setTimeout(() => {
    const selectorTemp = selectorStore.dictFromPython["selector"] as SelectorNonWindow;

    selectorStore.dictFromPython = {
      selector: {
        window: selectorStore.dictFromPython["selector"]["window"],
        category: selectorTemp["category"],
        specification: selectorStore.dictEleTreeSelector[id],
      },
      attributes: {},
      preview: "",
    };

    selectorStore.updateByDictFromPython();
  }, 300);
}
</script>

<style scoped></style>
