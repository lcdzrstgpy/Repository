<template>
  <div class="page-container">
    <el-card shadow="never">
      <el-tabs v-model="activeTab" @tab-change="handleTabChange">
        <el-tab-pane :label="`已接单`" name="20" />
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
        <el-table-column prop="no" label="订单单号" width="170" />
        <el-table-column prop="customer_name" label="客户名称" min-width="150" show-overflow-tooltip />
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
        <el-table-column prop="total_price" label="总金额" width="120" align="right">
          <template #default="{ row }">￥{{ formatAmount(row.total_price) }}</template>
        </el-table-column>
        <el-table-column prop="express_no" label="物流单号" width="150">
          <template #default="{ row }">{{ row.express_no || '-' }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="下单时间" width="170" />
        <el-table-column label="操作" width="120" fixed="right" align="center">
          <template #default="{ row }">
            <el-button
              link
              type="primary"
              :disabled="row.status !== 20"
              @click="handlePrepare(row)"
            >
              开始备货
            </el-button>
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
import { ElMessage, ElMessageBox } from 'element-plus'
import { getOrderList } from '@/api/order'
import { prepareOrder } from '@/api/warehouse'
import { orderStatusType, orderStatusLabel } from '@/utils/constants'
import { formatAmount, formatCount } from '@/utils/format'

const loading = ref(false)
const list = ref([])
const total = ref(0)

/** 当前页签：20 已接单 / 40 已发货 / 50 已完成 */
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

/** 开始备货：已接单(20) → 备货中(30) */
async function handlePrepare(row) {
  try {
    await ElMessageBox.confirm(`确认开始备货订单「${row.no}」吗？`, '开始备货', {
      type: 'warning',
      confirmButtonText: '确认',
      cancelButtonText: '取消'
    })
  } catch (e) {
    return
  }

  await prepareOrder(row.id)
  ElMessage.success('已开始备货，订单状态变更为「备货中」')
  load()
}

onMounted(load)
</script>
