<template>
  <div class="page-container">
    <!-- 查询条件 -->
    <el-card shadow="never" class="search-card">
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
        <el-form-item label="状态">
          <el-select v-model="query.status" placeholder="全部状态" clearable style="width: 160px">
            <el-option
              v-for="item in STOCK_TAKE_STATUS_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="关键词">
          <el-input
            v-model="query.keyword"
            placeholder="盘点单号 / 备注"
            clearable
            style="width: 220px"
            @keyup.enter="handleSearch"
          />
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
        <span class="text-muted">共 {{ total }} 条盘点单</span>
        <div>
          <el-button :loading="loading" @click="load">
            <el-icon><Refresh /></el-icon>
            <span style="margin-left: 4px">刷新</span>
          </el-button>
          <el-button type="primary" @click="router.push('/warehouse/stock-takes/create')">
            <el-icon><Plus /></el-icon>
            <span style="margin-left: 4px">新建盘点单</span>
          </el-button>
        </div>
      </div>

      <el-table v-loading="loading" :data="list" border stripe>
        <el-table-column prop="no" label="盘点单号" width="170" />
        <el-table-column prop="warehouse_name" label="盘点仓库" width="130">
          <template #default="{ row }">{{ row.warehouse_name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="stockTakeStatusType(row.status)" size="small">
              {{ row.status_text || stockTakeStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_count" label="账面数量" width="110" align="right">
          <template #default="{ row }">{{ formatCount(row.total_count) }}</template>
        </el-table-column>
        <el-table-column prop="diff_count" label="差异合计" width="110" align="right">
          <template #default="{ row }">
            <span :class="diffClass(row.diff_count)">{{ formatDiff(row.diff_count) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">{{ row.remark || '-' }}</template>
        </el-table-column>
        <el-table-column prop="created_by_name" label="制单人" width="110">
          <template #default="{ row }">{{ row.created_by_name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170" />
        <el-table-column prop="finished_at" label="完成时间" width="170">
          <template #default="{ row }">{{ row.finished_at || '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
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

    <!-- 盘点单详情抽屉：内含实盘录入 / 完成盘点 / 作废 -->
    <StockTakeDetailDrawer
      v-model="detailVisible"
      :stock-take-id="currentStockTakeId"
      @success="load"
    />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getStockTakeList } from '@/api/ops'
import { getWarehouseOptions } from '@/api/basic'
import {
  STOCK_TAKE_STATUS_OPTIONS,
  stockTakeStatusType,
  stockTakeStatusLabel
} from '@/utils/constants'
import { formatCount } from '@/utils/format'
import StockTakeDetailDrawer from './components/StockTakeDetailDrawer.vue'

const router = useRouter()

const loading = ref(false)
const list = ref([])
const total = ref(0)
const warehouseOptions = ref([])

const query = reactive({
  page: 1,
  page_size: 20,
  warehouse_id: '',
  status: '',
  keyword: ''
})

const detailVisible = ref(false)
const currentStockTakeId = ref(null)

/** 差异展示：正数带 + 号，0 显示 0 */
function formatDiff(value) {
  const num = Number(value) || 0
  return num > 0 ? `+${formatCount(num)}` : formatCount(num)
}

/** 差异颜色：盘盈绿、盘亏红 */
function diffClass(value) {
  const num = Number(value) || 0
  if (num > 0) return 'diff-plus'
  if (num < 0) return 'diff-minus'
  return ''
}

async function load() {
  loading.value = true
  try {
    const params = { page: query.page, page_size: query.page_size }
    if (query.warehouse_id !== '' && query.warehouse_id !== null) {
      params.warehouse_id = query.warehouse_id
    }
    if (query.status !== '' && query.status !== null) params.status = query.status
    if (query.keyword) params.keyword = query.keyword.trim()

    const data = await getStockTakeList(params)
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
  query.status = ''
  query.keyword = ''
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

function openDetail(row) {
  currentStockTakeId.value = row.id
  detailVisible.value = true
}

onMounted(async () => {
  load()
  warehouseOptions.value = (await getWarehouseOptions()) || []
})
</script>

<style scoped>
.diff-plus {
  color: #67c23a;
  font-weight: 600;
}

.diff-minus {
  color: #f56c6c;
  font-weight: 600;
}
</style>
