<template>
  <div class="page-container">
    <el-card shadow="never">
      <div class="module-purpose">关联 / 新建货号</div>
      <el-form :model="query" inline class="search-form">
        <el-form-item label="关键词">
          <el-input
            v-model="query.keyword"
            placeholder="订单号、商品名或备注"
            clearable
            style="width: 240px"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="query.status" placeholder="全部状态" clearable style="width: 150px">
            <el-option v-for="item in ORDER_STATUS_OPTIONS" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>

      <div class="table-toolbar">
        <div>
          <span class="section-title">全部订单</span>
          <span class="text-muted" style="margin-left: 12px">共 {{ total }} 条；仅「待接单」状态可接单</span>
        </div>
        <el-button :loading="loading" @click="load">
          <el-icon><Refresh /></el-icon>
          <span style="margin-left: 4px">刷新</span>
        </el-button>
      </div>

      <el-table v-loading="loading" :data="list" border stripe>
        <el-table-column prop="no" label="订单号" width="170" />
        <el-table-column prop="status_text" label="状态" width="105" align="center" />
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
        <el-table-column prop="total_count" label="总数量" width="100" align="right">
          <template #default="{ row }">{{ formatCount(row.total_count) }}</template>
        </el-table-column>
        <el-table-column prop="total_price" label="预计总成本" width="130" align="right">
          <template #default="{ row }">￥{{ formatAmount(row.total_price) }}</template>
        </el-table-column>
        <el-table-column prop="created_by_name" label="下单人" width="110" />
        <el-table-column prop="created_at" label="下单时间" width="170" />
        <el-table-column label="操作" width="140" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
            <el-button v-if="row.status === 10" link type="primary" @click="openClaim(row)">接单并关联货号</el-button>
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

    <!-- 接单弹窗：选择仓库 -->
    <el-dialog v-model="claimVisible" title="接单并关联货号" width="460px" @closed="handleDialogClosed">
      <el-descriptions :column="1" border size="small" style="margin-bottom: 16px">
        <el-descriptions-item label="订单号">{{ currentRow?.no }}</el-descriptions-item>
        <el-descriptions-item label="商品行数">{{ formatCount(currentRow?.item_count) }}</el-descriptions-item>
        <el-descriptions-item label="预计总成本">
          ￥{{ formatAmount(currentRow?.total_price) }}
        </el-descriptions-item>
      </el-descriptions>

      <el-form ref="claimFormRef" :model="claimForm" :rules="claimRules" label-width="80px">
        <el-form-item label="仓库" prop="warehouse_id">
          <el-select
            v-model="claimForm.warehouse_id"
            placeholder="请选择接单仓库"
            filterable
            style="width: 100%"
          >
            <el-option
              v-for="item in warehouseOptions"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="claimVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleClaim">接单并继续关联</el-button>
      </template>
    </el-dialog>

    <!-- 订单详情（待接单状态下仅查看；接单成功后自动打开，直接处理货号） -->
    <WarehouseOrderDetailDrawer
      v-model="detailVisible"
      :order-id="currentOrderId"
      @updated="load"
    />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getPendingOrders, claimOrder } from '@/api/warehouse'
import { getWarehouseOptions } from '@/api/basic'
import { ORDER_STATUS_OPTIONS } from '@/utils/constants'
import { formatAmount, formatCount } from '@/utils/format'
import WarehouseOrderDetailDrawer from './components/WarehouseOrderDetailDrawer.vue'

const loading = ref(false)
const submitting = ref(false)
const list = ref([])
const total = ref(0)
const warehouseOptions = ref([])

const query = reactive({
  page: 1,
  page_size: 20,
  keyword: '',
  status: null
})

const claimVisible = ref(false)
const claimFormRef = ref(null)
const currentRow = ref(null)
const claimForm = reactive({ warehouse_id: null })

// 详情抽屉
const detailVisible = ref(false)
const currentOrderId = ref(null)

const claimRules = {
  warehouse_id: [{ required: true, message: '请选择接单仓库', trigger: 'change' }]
}

async function load() {
  loading.value = true
  try {
    const params = { page: query.page, page_size: query.page_size }
    if (query.keyword.trim()) params.keyword = query.keyword.trim()
    if (query.status !== null) params.status = query.status
    const data = await getPendingOrders(params)
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
  query.status = null
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

async function loadWarehouses() {
  warehouseOptions.value = (await getWarehouseOptions()) || []
}

function openDetail(row) {
  currentOrderId.value = row.id
  detailVisible.value = true
}

function openClaim(row) {
  currentRow.value = row
  claimForm.warehouse_id = null
  claimVisible.value = true
}

function handleDialogClosed() {
  claimFormRef.value?.clearValidate()
}

async function handleClaim() {
  const valid = await claimFormRef.value.validate().catch(() => false)
  if (!valid) return

  const claimedId = currentRow.value.id
  submitting.value = true
  try {
    await claimOrder(claimedId, claimForm.warehouse_id)
    ElMessage.success('接单成功，请在当前详情中完成货号关联')
    claimVisible.value = false
    await load()

    // 接单成功后自动打开该订单的货号处理抽屉，仓储可直接接着绑货号
    currentOrderId.value = claimedId
    detailVisible.value = true
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  load()
  loadWarehouses()
})
</script>

<style scoped>
.section-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  border-left: 3px solid #409eff;
  padding-left: 8px;
}

.search-form {
  margin-bottom: 4px;
}

.module-purpose {
  margin-bottom: 14px;
  color: #409eff;
  font-size: 18px;
  font-weight: 600;
}
</style>
