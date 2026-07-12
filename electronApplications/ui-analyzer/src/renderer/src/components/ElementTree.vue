<!-- FileName: ElementTree.vue -->
<template>
  <v-container class="clean-space flex-column-grow-1 flex-column">
    <v-label class="area-header">Element Tree</v-label>

    <v-card v-if="selectorStore.arrEleTree.length === 0" class="ma-1 h-60 pa-3">
      <div>
        Indicate or validate a UIA or HTML element to show its element tree.<br />
        If the element tree is too large to process within 10 seconds, LiberRPA will stop
        building it.
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
              {{ JSON.stringify(item.attributes, null, 0) }}<br />
              ------------------------<br />
              The layer specification. Click to replace Element Hierarchy.<br />
              For UIA elements, you may need to add "Index" manually if sibling elements
              have the same attributes. You may also need to add "Depth" if the layer is too
              close to its ancestor.<br />
              For HTML elements, you may need to edit or add "childIndex" manually when multiple matching descendants exist.
            </div>
          </v-tooltip>
        </template>
      </v-treeview>
    </v-container>
  </v-container>
</template>

<script setup lang="ts">
import { loggerRenderer } from "../ipcOfRenderer";
import type { SelectorNonWindow } from "../../../shared/interface";
import { useSelectorStore, useInformationStore } from "../store";

const selectorStore = useSelectorStore();
const informationStore = useInformationStore();

function handleNodeClick(_: MouseEvent, id: number): void {
  loggerRenderer.debug("Click Element Tree node " + id);
  // console.log(selectorStore.dictEleTreeSelector[id]);

  selectorStore.arrEleHierarchy = [];
  informationStore.$reset();

  /* // Reassign to clean the highlight. Due to the watcher has 300 ms delay, so add delay before add element into arrEleHierarchy again.
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
  }, 300); */

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
}
</script>

<style scoped></style>
