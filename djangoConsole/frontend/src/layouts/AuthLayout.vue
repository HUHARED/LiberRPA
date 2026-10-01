<!-- FileName: AuthLayout.vue -->
<template>
  <v-main>
    <v-container fluid class="fill-height">
      <v-row align="center" justify="center">
        <v-col cols="12" sm="9" md="6" lg="4" xl="3">
          <v-card variant="outlined">
            <v-card-text class="pa-6">
              <BrandMark class="mb-6" />
              <slot />
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </v-container>
  </v-main>
</template>

<script setup lang="ts">
import BrandMark from "@/components/common/BrandMark.vue";
</script>

<style scoped></style>
