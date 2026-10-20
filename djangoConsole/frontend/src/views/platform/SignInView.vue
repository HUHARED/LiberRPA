<!-- FileName: SignInView.vue -->
<template>
  <AuthLayout>
    <h1 class="text-h5 mb-6">Platform Sign In</h1>

    <SignInForm platform />
  </AuthLayout>
</template>

<script setup lang="ts">
import AuthLayout from "@/layouts/AuthLayout.vue";
import SignInForm from "@/components/accounts/SignInForm.vue";
</script>

<style scoped></style>
