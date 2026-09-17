<template>
  <div class="page-container">
    <!-- 查询条件 -->
    <el-card shadow="never" class="search-card">
      <div class="module-purpose">查询 / 追溯出库</div>
      <WarehouseFulfillmentTabs class="tabs" />
      <el-form :model="query" inline>
        <el-form-item label="关键词">
          <el-input
            v-model="query.keyword"
            placeholder="出库单号 / 订单号 / 物流单号"
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
      <div class="table-toolbar">
        <span class="text-muted">共 {{ total }} 条出库单</span>
        <el-button :loading="loading" @click="load">
          <el-icon><Refresh /></el-icon>
          <span style="margin-left: 4px">刷新</span>
        </el-button>
      </div>

      <el-table v-loading="loading" :data="list" border stripe>
        <el-table-column prop="no" label="出库单号" width="170" />
        <el-table-column prop="order_no" label="关联订单号" width="170">
          <template #default="{ row }">{{ row.order_no || '-' }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="outStatusType(row.status)" size="small">
              {{ row.status_text || outStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_count" label="数量" width="100" align="right">
          <template #default="{ row }">{{ formatCount(row.total_count) }}</template>
        </el-table-column>
        <el-table-column prop="total_price" label="金额" width="120" align="right">
          <template #default="{ row }">￥{{ formatAmount(row.total_price) }}</template>
        </el-table-column>
        <el-table-column prop="express_no" label="物流单号" width="150">
          <template #default="{ row }">{{ row.express_no || '-' }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170" />
        <el-table-column label="操作" width="180" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
            <el-button link type="primary" @click="handlePrint(row)">打印</el-button>
            <el-button v-if="row.status === 20" link type="danger" @click="handleCancel(row)">
              作废
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

    <!-- 出库单详情抽屉 -->
    <OutDetailDrawer v-model="detailVisible" :out-id="currentOutId" />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import WarehouseFulfillmentTabs from './components/WarehouseFulfillmentTabs.vue'
import { getOutList, cancelOut } from '@/api/stock'
import { outStatusType, outStatusLabel } from '@/utils/constants'
import { formatAmount, formatCount } from '@/utils/format'
import OutDetailDrawer from './components/OutDetailDrawer.vue'

/** 已完成状态值，仅该状态可作废（契约 9.4） */
const FINISHED_STATUS = 20

const router = useRouter()

const loading = ref(false)
const list = ref([])
const total = ref(0)

const query = reactive({
  page: 1,
  page_size: 20,
  keyword: ''
})

const detailVisible = ref(false)
const currentOutId = ref(null)

async function load() {
  loading.value = true
  try {
    const params = { page: query.page, page_size: query.page_size }
    if (query.keyword) params.keyword = query.keyword.trim()

    const data = await getOutList(params)
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
  currentOutId.value = row.id
  detailVisible.value = true
}

/** 打印出库单：新标签页打开独立打印页（契约 13） */
function handlePrint(row) {
  const { href } = router.resolve({ path: `/print/sales-out/${row.id}` })
  window.open(href, '_blank')
}

/** 作废出库单：二次确认，成功后回滚库存 */
async function handleCancel(row) {
  try {
    await ElMessageBox.confirm(
      `确认作废出库单「${row.no}」吗？作废后将回滚已出库库存，关联订单状态回退为「备货中」。`,
      '作废出库单',
      { type: 'warning', confirmButtonText: '确认作废', cancelButtonText: '取消' }
    )
  } catch (e) {
    return // 用户取消
  }

  await cancelOut(row.id)
  ElMessage.success('出库单已作废，库存已回滚')
  load()
}

onMounted(async () => {
  load()
})
</script>

<style scoped>
.module-purpose {
  margin-bottom: 14px;
  color: #409eff;
  font-size: 18px;
  font-weight: 600;
}

.tabs {
  margin-bottom: 14px;
}
</style>
