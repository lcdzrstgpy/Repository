<template>
  <div class="page-container">
    <el-card shadow="never">
      <el-tabs v-model="activeTab" @tab-change="handleTabChange">
        <el-tab-pane :label="`已接单`" name="20" />
        <el-tab-pane :label="`数量待确认`" name="25" />
        <el-tab-pane :label="`已发货`" name="40" />
        <el-tab-pane :label="`已完成`" name="50" />
      </el-tabs>

      <div class="table-toolbar">
        <span class="text-muted">共 {{ total }} 条记录</span>
        <el-button :loading="loading" @click="load">
          <el-icon><Refresh /></el-icon>
          <span style="margin-left: 4px">刷新</span>
        </el-button>
      </div>

      <el-table v-loading="loading" :data="list" border stripe>
        <el-table-column prop="no" label="订单号" width="170" />
        <el-table-column prop="item_count" label="商品行数" width="100" align="center">
          <template #default="{ row }">{{ formatCount(row.item_count) }}</template>
        </el-table-column>
        <el-table-column label="货号处理" width="120" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.unbound_count > 0" type="danger" size="small" effect="dark">
              待关联 {{ formatCount(row.unbound_count) }}
            </el-tag>
            <el-tag v-else type="success" size="small">已关联</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="orderStatusType(row.status)" size="small">
              {{ row.status_text || orderStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_count" label="总数量" width="100" align="right">
          <template #default="{ row }">{{ formatCount(row.total_count) }}</template>
        </el-table-column>
        <el-table-column prop="total_price" label="预计总成本" width="130" align="right">
          <template #default="{ row }">￥{{ formatAmount(row.total_price) }}</template>
        </el-table-column>
        <el-table-column prop="express_no" label="物流单号" width="150">
          <template #default="{ row }">{{ row.express_no || '-' }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="下单时间" width="170" />
        <el-table-column label="操作" width="110" fixed="right" align="center">
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

    <!-- 订单详情 · 货号处理区（已接单状态下可关联 / 新建货号，绑完自动提交运营确认数量） -->
    <WarehouseOrderDetailDrawer
      v-model="detailVisible"
      :order-id="currentOrderId"
      @updated="load"
    />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getOrderList } from '@/api/order'
import { orderStatusType, orderStatusLabel } from '@/utils/constants'
import { formatAmount, formatCount } from '@/utils/format'
import WarehouseOrderDetailDrawer from './components/WarehouseOrderDetailDrawer.vue'

const loading = ref(false)
const list = ref([])
const total = ref(0)

// 详情抽屉
const detailVisible = ref(false)
const currentOrderId = ref(null)

/** 当前页签：20 已接单 / 25 数量待确认 / 40 已发货 / 50 已完成 */
const activeTab = ref('20')

const query = reactive({
  page: 1,
  page_size: 20
})

async function load() {
  loading.value = true
  try {
    const data = await getOrderList({
      page: query.page,
      page_size: query.page_size,
      status: Number(activeTab.value)
    })
    list.value = data?.list || []
    total.value = data?.total || 0
  } finally {
    loading.value = false
  }
}

function handleTabChange() {
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

/** 打开详情抽屉（货号关联在抽屉内完成） */
function openDetail(row) {
  currentOrderId.value = row.id
  detailVisible.value = true
}

onMounted(load)
</script>
