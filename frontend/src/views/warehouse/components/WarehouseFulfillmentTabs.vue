<template>
  <el-button-group class="fulfillment-tabs">
    <el-button :type="isActive('/warehouse/preparing') ? 'primary' : 'default'" @click="go('/warehouse/preparing')">
      备货订单
    </el-button>
    <el-button :type="isActive('/warehouse/outs') ? 'primary' : 'default'" @click="go('/warehouse/outs')">
      出库记录
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
.fulfillment-tabs :deep(.el-button) {
  min-width: 104px;
}
</style>
