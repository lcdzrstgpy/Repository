<template>
  <div class="page-container">
    <!-- 查询条件：仅仓库筛选（契约 18.3） -->
    <el-card shadow="never" class="search-card">
      <div class="module-purpose">库存预警 / 补货提醒</div>
      <WarehouseInventoryTabs class="tabs" />
      <el-form :model="query" inline>
        <el-form-item label="仓库">
          <el-select
            v-model="query.warehouse_id"
            placeholder="全部仓库"
            clearable
            filterable
            style="width: 180px"
          >
            <el-option
              v-for="item in warehouseOptions"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">
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
      <el-alert
        class="tip-alert"
        type="warning"
        :closable="false"
        show-icon
        title="可用量低于安全库存的货号会出现在这里，按短缺量从大到小排序；建议采购量会自动补足安全库存。"
      />

      <div class="table-toolbar">
        <span class="text-muted">共 {{ total }} 条预警</span>
        <el-button :loading="loading" @click="load">
          <el-icon><Refresh /></el-icon>
          <span style="margin-left: 4px">刷新</span>
        </el-button>
      </div>

      <el-table v-loading="loading" :data="list" border stripe>
        <el-table-column prop="sku_code" label="货号" width="130" />
        <el-table-column prop="product_name" label="商品名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="spec" label="规格" min-width="130" show-overflow-tooltip>
          <template #default="{ row }">{{ row.spec || '-' }}</template>
        </el-table-column>
        <el-table-column prop="warehouse_name" label="仓库" width="130">
          <template #default="{ row }">{{ row.warehouse_name || '未入库' }}</template>
        </el-table-column>
        <el-table-column prop="quantity" label="现存数量" width="110" align="right">
          <template #default="{ row }">{{ formatCount(row.quantity) }}</template>
        </el-table-column>
        <el-table-column prop="reserved_quantity" label="预留数量" width="110" align="right">
          <template #default="{ row }">{{ formatCount(row.reserved_quantity) }}</template>
        </el-table-column>
        <el-table-column prop="available_quantity" label="可用数量" width="110" align="right">
          <template #default="{ row }">
            <span :class="{ 'low-stock': Number(row.available_quantity) <= 0 }">
              {{ formatCount(row.available_quantity) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="min_stock" label="安全库存" width="110" align="right">
          <template #default="{ row }">{{ formatCount(row.min_stock) }}</template>
        </el-table-column>
        <el-table-column prop="shortage" label="短缺量" width="110" align="right">
          <template #default="{ row }">
            <span class="shortage">{{ formatCount(row.shortage) }}</span>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.page_size"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getInventoryAlerts } from '@/api/inventory'
import { getWarehouseOptions } from '@/api/basic'
import { formatCount } from '@/utils/format'
import WarehouseInventoryTabs from './components/WarehouseInventoryTabs.vue'

const loading = ref(false)
const list = ref([])
const total = ref(0)
const warehouseOptions = ref([])

const query = reactive({
  page: 1,
  page_size: 20,
  warehouse_id: ''
})

async function load() {
  loading.value = true
  try {
    const params = { page: query.page, page_size: query.page_size }
    if (query.warehouse_id !== '' && query.warehouse_id !== null) {
      params.warehouse_id = query.warehouse_id
    }

    const data = await getInventoryAlerts(params)
    list.value = data?.list || []
    total.value = data?.total || 0
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  query.page = 1
  load()
}

function handleReset() {
  query.warehouse_id = ''
  query.page = 1
  load()
}

function handleSizeChange(size) {
  query.page_size = size
  query.page = 1
  load()
}

function handlePageChange(page) {
  query.page = page
  load()
}

onMounted(async () => {
  load()
  warehouseOptions.value = (await getWarehouseOptions()) || []
})
</script>

<style scoped>
.tip-alert {
  margin-bottom: 12px;
}

.low-stock {
  color: #f56c6c;
  font-weight: 600;
}

.shortage {
  color: #f56c6c;
  font-weight: 600;
}

.module-purpose { margin-bottom: 14px; color: #409eff; font-size: 18px; font-weight: 600; }
.tabs { margin-bottom: 14px; }
</style>
