<template>
  <el-button-group class="inventory-tabs">
    <el-button :type="isActive('/warehouse/inventory') ? 'primary' : 'default'" @click="go('/warehouse/inventory')">
      货号库存
    </el-button>
    <el-button :type="isActive('/warehouse/inventory-alerts') ? 'primary' : 'default'" @click="go('/warehouse/inventory-alerts')">
      库存预警
    </el-button>
  </el-button-group>
</template>

<script setup>
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const isActive = (path) => route.path === path
const go = (path) => { if (!isActive(path)) router.push(path) }
</script>

<style scoped>
.inventory-tabs :deep(.el-button) { min-width: 104px; }
</style>
