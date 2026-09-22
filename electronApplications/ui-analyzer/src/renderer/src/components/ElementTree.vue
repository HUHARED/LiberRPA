<!-- FileName: ElementTree.vue -->
<template>
  <v-container class="clean-space flex-column-grow-1 flex-column element-tree-panel">
    <v-label class="area-header">Element Tree</v-label>

    <v-card v-if="selectorStore.arrEleTree.length === 0" class="ma-1 h-60 pa-3">
      <div>
        Indicate a UIA or HTML element to show its element tree.<br />
        If the Element Tree exceeds its processing limits, LiberRPA will stop building it
        while keeping the selected Selector.
      </div>
    </v-card>

    <div
      v-else
      ref="treeViewport"
      class="element-tree-viewport"
      role="tree"
      aria-label="Element Tree"
      :aria-activedescendant="
        intFocusedNodeId === undefined ? undefined : `element-tree-node-${intFocusedNodeId}`
      "
      tabindex="0"
      @keydown="handleTreeKeydown">
      <v-virtual-scroll
        ref="virtualScroll"
        class="element-tree-scroll"
        :items="arrVisibleTreeRow"
        item-key="node.id"
        :item-height="INT_TREE_ROW_HEIGHT">
        <template #default="{ item }">
          <div
            :id="`element-tree-node-${item.node.id}`"
            :key="item.node.id"
            class="element-tree-row"
            :class="{
              'element-tree-row-active':
                selectorStore.arrEleTreeActivated[0] === item.node.id,
              'element-tree-row-focused': intFocusedNodeId === item.node.id,
            }"
            :style="{
              height: `${INT_TREE_ROW_HEIGHT}px`,
              paddingInlineStart: `${item.intDepth * 18 + 4}px`,
            }"
            role="treeitem"
            :aria-level="item.intDepth + 1"
            :aria-posinset="item.intSiblingPosition"
            :aria-setsize="item.intSiblingCount"
            :aria-selected="selectorStore.arrEleTreeActivated[0] === item.node.id"
            :aria-expanded="item.boolHasChildren ? item.boolExpanded : undefined"
            @click="selectTreeRow(item)">
            <button
              v-if="item.boolHasChildren"
              class="element-tree-toggle"
              type="button"
              tabindex="-1"
              :aria-label="item.boolExpanded ? 'Collapse node' : 'Expand node'"
              @click.stop="toggleTreeRow(item)">
              <v-icon
                :icon="item.boolExpanded ? 'mdi-folder-open-outline' : 'mdi-folder-outline'"
                size="20" />
            </button>
            <span v-else class="element-tree-toggle-spacer" aria-hidden="true"></span>

            <span class="element-tree-title">{{ item.node.title }}</span>
            <v-tooltip activator="parent" location="bottom" :eager="false" max-width="600">
              <div class="element-tree-tooltip">
                {{ item.node.title }}<br />
                {{ JSON.stringify(item.node.attributes, null, 0) }}<br />
                ------------------------<br />
                The layer specification. Click to replace Element Hierarchy.<br />
                For UIA elements, you may need to add "Index" manually if sibling elements
                have the same attributes. You may also need to add "Depth" if the layer is
                too close to its ancestor.<br />
                For HTML elements, you may need to edit or add "childIndex" manually when
                multiple matching descendants exist.
              </div>
            </v-tooltip>
          </div>
        </template>
      </v-virtual-scroll>
    </div>
  </v-container>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import type { VVirtualScroll } from "vuetify/components";

import type { DictEleTreeItem } from "../../../shared/interface";
import { loggerRenderer } from "../logger";
import { useSelectorStore, useInformationStore } from "../store";

interface ElementTreeRow {
  node: DictEleTreeItem;
  intDepth: number;
  intParentId: number | undefined;
  intSiblingPosition: number;
  intSiblingCount: number;
  boolHasChildren: boolean;
  boolExpanded: boolean;
}

const INT_TREE_ROW_HEIGHT = 32;

const selectorStore = useSelectorStore();
const informationStore = useInformationStore();

const virtualScroll = ref<VVirtualScroll | null>(null);
const treeViewport = ref<HTMLElement | null>(null);
const intFocusedNodeId = ref<number | undefined>();

// Keep all source nodes in the store; flatten only expanded branches for display.
// VVirtualScroll mounts only the rows in and near the viewport.
const arrVisibleTreeRow = computed<ElementTreeRow[]>(() => {
  const setOpenedId = new Set(selectorStore.arrEleTreeOpened);
  const arrRow: ElementTreeRow[] = [];

  function appendRows(
    arrNode: DictEleTreeItem[],
    intDepth: number,
    intParentId: number | undefined,
  ): void {
    arrNode.forEach((node, intSiblingIndex) => {
      const boolHasChildren = (node.children?.length ?? 0) > 0;
      const boolExpanded = boolHasChildren && setOpenedId.has(node.id);
      arrRow.push({
        node,
        intDepth,
        intParentId,
        intSiblingPosition: intSiblingIndex + 1,
        intSiblingCount: arrNode.length,
        boolHasChildren,
        boolExpanded,
      });

      if (boolExpanded && node.children !== undefined) {
        appendRows(node.children, intDepth + 1, node.id);
      }
    });
  }

  appendRows(selectorStore.arrEleTree, 0, undefined);
  return arrRow;
});

function scrollToTreeRow(intRowIndex: number): void {
  const row = arrVisibleTreeRow.value[intRowIndex];
  if (row === undefined) {
    return;
  }

  const elementRow = treeViewport.value?.querySelector<HTMLElement>(
    `#element-tree-node-${row.node.id}`,
  );
  if (elementRow !== null && elementRow !== undefined) {
    elementRow.scrollIntoView({ block: "nearest", inline: "nearest" });
  } else {
    virtualScroll.value?.scrollToIndex(intRowIndex);
  }
}

watch(
  () => selectorStore.arrEleTree,
  (_arrTree, _arrPreviousTree, onCleanup) => {
    const intActiveId = selectorStore.arrEleTreeActivated[0];
    const intActiveIndex = arrVisibleTreeRow.value.findIndex(
      (row) => row.node.id === intActiveId,
    );
    const intRowIndex = Math.max(0, intActiveIndex);
    intFocusedNodeId.value = arrVisibleTreeRow.value[intRowIndex]?.node.id;

    // Let the virtual scroller create its spacers before scrolling to a distant target.
    const intFrameId = requestAnimationFrame(() => {
      void nextTick()
        .then(() => scrollToTreeRow(intRowIndex))
        .catch((e: unknown) => loggerRenderer.error(e));
    });
    onCleanup(() => cancelAnimationFrame(intFrameId));
  },
  { flush: "post", immediate: true },
);

function focusTreeRow(row: ElementTreeRow): void {
  intFocusedNodeId.value = row.node.id;
  treeViewport.value?.focus({ preventScroll: true });
}

function toggleTreeRow(row: ElementTreeRow): void {
  if (!row.boolHasChildren) {
    return;
  }

  focusTreeRow(row);
  selectorStore.arrEleTreeOpened = row.boolExpanded
    ? selectorStore.arrEleTreeOpened.filter((intId) => intId !== row.node.id)
    : [...selectorStore.arrEleTreeOpened, row.node.id];
}

function selectTreeRow(row: ElementTreeRow): void {
  focusTreeRow(row);
  handleNodeClick(row.node.id);
}

function handleTreeKeydown(event: KeyboardEvent): void {
  if (event.altKey || event.ctrlKey || event.metaKey) {
    return;
  }

  const arrRow = arrVisibleTreeRow.value;
  let intRowIndex = arrRow.findIndex((row) => row.node.id === intFocusedNodeId.value);
  intRowIndex = Math.max(0, intRowIndex);
  const row = arrRow[intRowIndex];
  if (row === undefined) {
    return;
  }

  switch (event.key) {
    case "ArrowDown":
      intRowIndex = Math.min(arrRow.length - 1, intRowIndex + 1);
      break;
    case "ArrowUp":
      intRowIndex = Math.max(0, intRowIndex - 1);
      break;
    case "Home":
      intRowIndex = 0;
      break;
    case "End":
      intRowIndex = arrRow.length - 1;
      break;
    case "ArrowRight":
      if (row.boolHasChildren && !row.boolExpanded) {
        toggleTreeRow(row);
      } else if (row.boolExpanded) {
        intRowIndex += 1;
      }
      break;
    case "ArrowLeft":
      if (row.boolExpanded) {
        toggleTreeRow(row);
      } else if (row.intParentId !== undefined) {
        intRowIndex = arrRow.findIndex(
          (parentRow) => parentRow.node.id === row.intParentId,
        );
      }
      break;
    case "Enter":
    case " ":
      event.preventDefault();
      selectTreeRow(row);
      return;
    default:
      return;
  }

  event.preventDefault();
  const rowNext = arrVisibleTreeRow.value[intRowIndex];
  if (rowNext !== undefined) {
    intFocusedNodeId.value = rowNext.node.id;
    scrollToTreeRow(intRowIndex);
  }
}

function handleNodeClick(id: number): void {
  loggerRenderer.debug("Click Element Tree node " + id);

  const arrElementTreeSelector = selectorStore.dictEleTreeSelector[id];
  const dictCurrentSelector = selectorStore.dictFromPython["selector"];
  const dictCurrentWindow = selectorStore.arrEleHierarchy[0];
  if (
    !arrElementTreeSelector ||
    !dictCurrentWindow ||
    !("category" in dictCurrentSelector)
  ) {
    informationStore.showAlertMessage(
      "The selected Element Tree node has no valid selector.",
    );
    return;
  }

  selectorStore.arrEleTreeActivated = [id];
  informationStore.$reset();

  selectorStore.dictFromPython = {
    selector: {
      window: { ...dictCurrentWindow },
      category: dictCurrentSelector["category"],
      specification: arrElementTreeSelector.map((dictAttributes) => ({
        ...dictAttributes,
      })),
    },
    attributes: {},
    preview: "",
  };

  selectorStore.updateByDictFromPython();
}
</script>

<style scoped>
.element-tree-panel {
  overflow: hidden;
}

.element-tree-viewport {
  flex: 1 1 0;
  min-height: 0;
  min-width: 0;
  overflow: hidden;
}

.element-tree-scroll {
  height: 100%;
  min-width: 0;
}

.element-tree-scroll :deep(.v-virtual-scroll__container) {
  min-width: 100%;
  width: max-content;
}

.element-tree-row {
  display: flex;
  align-items: center;
  box-sizing: border-box;
  border-radius: 4px;
  padding-inline-end: 8px;
  cursor: pointer;
}

.element-tree-row:hover {
  background: rgba(var(--v-theme-on-surface), 0.06);
}

.element-tree-row-active {
  background: rgba(var(--v-theme-on-surface), 0.12);
}

.element-tree-viewport:focus {
  outline: none;
}

.element-tree-viewport:focus-visible .element-tree-row-focused {
  outline: 2px solid rgb(var(--v-theme-primary));
  outline-offset: -2px;
}

.element-tree-toggle,
.element-tree-toggle-spacer {
  flex: 0 0 28px;
  width: 28px;
  height: 28px;
}

.element-tree-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  color: inherit;
  border: 0;
  background: transparent;
  cursor: pointer;
}

.element-tree-title {
  white-space: nowrap;
}

.element-tree-tooltip {
  overflow-wrap: anywhere;
}
</style>
