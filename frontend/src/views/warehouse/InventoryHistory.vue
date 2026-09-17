<template>
  <div class="page-container">
    <!-- 查询条件 -->
    <el-card shadow="never" class="search-card">
      <el-form :model="query" inline>
        <el-form-item label="SKU">
          <el-select
            v-model="query.sku_id"
            placeholder="全部 SKU"
            clearable
            filterable
            style="width: 260px"
          >
            <el-option
              v-for="item in skuOptions"
              :key="item.id"
              :label="`${item.sku_code} ${item.name}`"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
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
      <div class="table-toolbar">
        <span class="text-muted">共 {{ total }} 条库存流水</span>
        <el-button :loading="loading" @click="load">
          <el-icon><Refresh /></el-icon>
          <span style="margin-left: 4px">刷新</span>
        </el-button>
      </div>

      <el-table v-loading="loading" :data="list" border stripe>
        <el-table-column prop="created_at" label="变动时间" width="170" />
        <el-table-column prop="sku_code" label="SKU 编码" width="130" />
        <el-table-column prop="product_name" label="商品名称" min-width="150" show-overflow-tooltip />
        <el-table-column prop="warehouse_name" label="仓库" width="120">
          <template #default="{ row }">{{ row.warehouse_name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="quantity" label="变动量" width="100" align="right">
          <template #default="{ row }">
            <span :class="Number(row.quantity) >= 0 ? 'in-stock' : 'out-stock'">
              {{ Number(row.quantity) >= 0 ? '+' : '' }}{{ formatCount(row.quantity) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="before_quantity" label="变动前" width="100" align="right">
          <template #default="{ row }">{{ formatCount(row.before_quantity) }}</template>
        </el-table-column>
        <el-table-column prop="after_quantity" label="变动后" width="100" align="right">
          <template #default="{ row }">{{ formatCount(row.after_quantity) }}</template>
        </el-table-column>
        <el-table-column prop="order_type" label="单据类型" width="110">
          <template #default="{ row }">
            {{ row.order_type_text || orderTypeLabel(row.order_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="order_no" label="关联单号" width="170">
          <template #default="{ row }">{{ row.order_no || '-' }}</template>
        </el-table-column>
        <el-table-column prop="created_by_name" label="操作人" width="110">
          <template #default="{ row }">{{ row.created_by_name || '-' }}</template>
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
import { getInventoryHistory } from '@/api/inventory'
import { getSkuOptions, getWarehouseOptions } from '@/api/basic'
import { orderTypeLabel } from '@/utils/constants'
import { formatCount } from '@/utils/format'

const loading = ref(false)
const list = ref([])
const total = ref(0)
const skuOptions = ref([])
const warehouseOptions = ref([])

const query = reactive({
  page: 1,
  page_size: 20,
  sku_id: '',
  warehouse_id: ''
})

async function load() {
  loading.value = true
  try {
    const params = { page: query.page, page_size: query.page_size }
    if (query.sku_id !== '' && query.sku_id !== null) params.sku_id = query.sku_id
    if (query.warehouse_id !== '' && query.warehouse_id !== null) {
      params.warehouse_id = query.warehouse_id
    }

    const data = await getInventoryHistory(params)
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
  query.sku_id = ''
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
  const [skus, warehouses] = await Promise.all([getSkuOptions(), getWarehouseOptions()])
  skuOptions.value = skus || []
  warehouseOptions.value = warehouses || []
})
</script>

<style scoped>
.in-stock {
  color: #67c23a;
}

.out-stock {
  color: #f56c6c;
}
</style>
