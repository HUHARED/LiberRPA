<!-- FileName: RunLogMessage.vue -->
<template>
  <span :class="{ 'font-italic': boolTrace }">
    <span
      v-for="(part, index) in arrPart"
      :key="index"
      :class="part.className"
      v-text="part.text" />
  </span>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{ message: string }>();

interface LogMessagePart {
  text: string;
  className: string;
}

// NOTE: Match strings, numbers, keywords and trace prefixes from liberrpa.Logging.ColoredConsoleFormatter; JavaScript needs explicit Unicode word boundaries.
const PATTERN_MESSAGE_TOKEN =
  /(?<string>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|(?<keyword>(?<![\p{L}\p{N}_])(?:true|false|null|True|False|None)(?![\p{L}\p{N}_]))|(?<number>(?<![\p{L}\p{N}_.])-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?(?![\p{L}\p{N}_.]))/gu;
const ARR_TRACE_PREFIX = ["CALL  :", "RETURN:", "FLOW  :", "EVAL  :"];

const boolTrace = computed(() =>
  ARR_TRACE_PREFIX.some((prefix) => props.message.startsWith(prefix)),
);

const arrPart = computed<LogMessagePart[]>(() => {
  const arrResult: LogMessagePart[] = [];
  let intPosition = 0;

  for (const match of props.message.matchAll(PATTERN_MESSAGE_TOKEN)) {
    if (match.index > intPosition) {
      arrResult.push({
        text: props.message.slice(intPosition, match.index),
        className: "",
      });
    }

    arrResult.push({
      text: match[0],
      className: match.groups?.string
        ? "text-success"
        : match.groups?.keyword
          ? "text-highlight font-weight-bold"
          : "text-highlight",
    });
    intPosition = match.index + match[0].length;
  }

  if (intPosition < props.message.length) {
    arrResult.push({ text: props.message.slice(intPosition), className: "" });
  }
  return arrResult;
});
</script>

<style scoped></style>
