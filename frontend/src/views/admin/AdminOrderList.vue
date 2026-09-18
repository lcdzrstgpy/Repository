<template>
  <div class="page-container">
    <el-card shadow="never" class="search-card">
      <el-form :model="query" inline>
        <el-form-item label="关键词">
          <el-input
            v-model="query.keyword"
            placeholder="订单号 / 物流单号"
            clearable
            style="width: 240px"
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
      <el-tabs v-model="activeStatusTab" @tab-change="handleStatusTabChange">
        <el-tab-pane label="全部" :name="ALL_STATUS_TAB" />
        <el-tab-pane
          v-for="item in ORDER_STATUS_OPTIONS"
          :key="item.value"
          :label="item.label"
          :name="String(item.value)"
        />
      </el-tabs>

      <div class="table-toolbar">
        <span class="text-muted">共 {{ total }} 条订单</span>
        <el-button :loading="exporting" @click="handleExport">
          <el-icon><Download /></el-icon>
          <span style="margin-left: 4px">导出 Excel</span>
        </el-button>
      </div>

      <el-table v-loading="loading" :data="list" border stripe>
        <el-table-column prop="no" label="订单号" width="180" />
        <el-table-column prop="item_count" label="订单 SKU 数" width="115" align="center">
          <template #default="{ row }">{{ formatCount(row.item_count) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="orderStatusType(row.status)" size="small">
              {{ row.status_text || orderStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_count" label="总数量" width="110" align="right">
          <template #default="{ row }">{{ formatCount(row.total_count) }}</template>
        </el-table-column>
        <el-table-column prop="total_price" label="预计总成本" width="135" align="right">
          <template #default="{ row }">￥{{ formatAmount(row.total_price) }}</template>
        </el-table-column>
        <el-table-column prop="express_no" label="物流单号" min-width="160">
          <template #default="{ row }">{{ row.express_no || '-' }}</template>
        </el-table-column>
        <el-table-column prop="created_by_name" label="下单人" width="120">
          <template #default="{ row }">{{ row.created_by_name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="下单时间" width="170" />
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

    <OrderDetailDrawer v-model="detailVisible" :order-id="currentOrderId" readonly />
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getOrderList } from '@/api/order'
import { exportSalesOrders } from '@/api/export'
import { ORDER_STATUS_OPTIONS, orderStatusLabel, orderStatusType } from '@/utils/constants'
import { formatAmount, formatCount } from '@/utils/format'
import OrderDetailDrawer from '@/views/operator/components/OrderDetailDrawer.vue'

const loading = ref(false)
const exporting = ref(false)
const list = ref([])
const total = ref(0)
const detailVisible = ref(false)
const currentOrderId = ref(null)
const query = reactive({ page: 1, page_size: 20, status: '', keyword: '' })
const ALL_STATUS_TAB = 'all'

const activeStatusTab = computed({
  get: () => (query.status === '' ? ALL_STATUS_TAB : String(query.status)),
  set: (value) => { query.status = value === ALL_STATUS_TAB ? '' : Number(value) }
})

async function load() {
  loading.value = true
  try {
    const params = { page: query.page, page_size: query.page_size }
    if (query.status !== '') params.status = query.status
    if (query.keyword.trim()) params.keyword = query.keyword.trim()
    const data = await getOrderList(params)
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
  query.status = ''
  query.keyword = ''
  query.page = 1
  load()
}

function handleStatusTabChange() {
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
  currentOrderId.value = row.id
  detailVisible.value = true
}

async function handleExport() {
  if (exporting.value) return
  exporting.value = true
  try {
    const params = query.status === '' ? {} : { status: query.status }
    const fileName = await exportSalesOrders(params)
    ElMessage.success(`已导出「${fileName}」`)
  } finally {
    exporting.value = false
  }
}

onMounted(load)
</script>
