<template>
  <el-button-group class="item-tabs">
    <el-button :type="isActive('/warehouse/inventory') ? 'primary' : 'default'" @click="go('/warehouse/inventory')">
      货号库存
    </el-button>
    <el-button :type="isActive('/warehouse/item-numbers') ? 'primary' : 'default'" @click="go('/warehouse/item-numbers')">
      货号管理
    </el-button>
  </el-button-group>
</template>

<script setup>
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

function isActive(path) {
  return route.path === path
}

function go(path) {
  if (!isActive(path)) router.push(path)
}
</script>

<style scoped>
.item-tabs :deep(.el-button) {
  min-width: 104px;
}
</style>
