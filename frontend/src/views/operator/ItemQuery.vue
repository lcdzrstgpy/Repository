<template>
  <div class="page-container">
    <el-card shadow="never" class="search-card">
      <el-form inline>
        <el-form-item label="货号 / 商品">
          <el-input
            v-model="keyword"
            placeholder="请输入货号、商品名称或规格"
            clearable
            style="width: 260px"
            @keyup.enter="load"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="load">
            <el-icon><Search /></el-icon>
            <span style="margin-left: 4px">查询</span>
          </el-button>
          <el-button @click="handleReset">
            <el-icon><Refresh /></el-icon>
            <span style="margin-left: 4px">重置</span>
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <div class="table-toolbar">
        <span class="text-muted">共 {{ list.length }} 个货号 · 库存只读</span>
        <el-button :loading="loading" @click="load">
          <el-icon><Refresh /></el-icon>
          <span style="margin-left: 4px">刷新</span>
        </el-button>
      </div>

      <el-table v-loading="loading" :data="list" border stripe>
        <el-table-column prop="item_no" label="货号" width="160" />
        <el-table-column prop="product_name" label="商品名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="spec" label="规格" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.spec || '-' }}</template>
        </el-table-column>
        <el-table-column label="库存（只读）" min-width="220">
          <template #default="{ row }">
            可用 {{ formatCount(row.available_quantity) }} / 库存 {{ formatCount(row.quantity) }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { queryItems } from '@/api/basic'
import { formatCount } from '@/utils/format'

const keyword = ref('')
const list = ref([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    list.value = (await queryItems(keyword.value.trim())) || []
  } finally {
    loading.value = false
  }
}

function handleReset() {
  keyword.value = ''
  load()
}

onMounted(load)
</script>
