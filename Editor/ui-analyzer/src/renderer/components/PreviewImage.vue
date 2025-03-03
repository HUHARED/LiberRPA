<!-- FileName: PreviewImage.vue -->
<template>
  <v-container class="clean-space flex-column">
    <v-label class="header-label">Preview Image</v-label>

    <v-container class="clean-space" style="height: 40px">
      <!-- Display the image only if imageTemp is not empty -->
      <v-img v-if="imageTemp" :src="imageTemp" /> </v-container
  ></v-container>
</template>

<script setup lang="ts">
import { watch, ref } from "vue";
import { useInformationStore } from "../store";
const informationStore = useInformationStore();

const imageTemp = ref("");

watch(
  () => informationStore.previewImage,
  (newValue) => {
    console.log("Image updated");

    if (newValue) {
      imageTemp.value = `data:image/png;base64,${newValue}`;
    } else {
      imageTemp.value = "";
    }
  },
  { immediate: true }
);
</script>

<style scoped></style>
