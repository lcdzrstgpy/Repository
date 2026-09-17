<template>
  <div class="page-container">
    <el-card shadow="never">
      <div class="table-toolbar">
        <div>
          <span class="section-title">待接单订单</span>
          <span class="text-muted" style="margin-left: 12px">共 {{ total }} 条，仅显示「待接单」状态的订单</span>
        </div>
        <el-button :loading="loading" @click="load">
          <el-icon><Refresh /></el-icon>
          <span style="margin-left: 4px">刷新</span>
        </el-button>
      </div>

      <el-table v-loading="loading" :data="list" border stripe>
        <el-table-column prop="no" label="订单单号" width="170" />
        <el-table-column prop="customer_name" label="客户名称" min-width="150" show-overflow-tooltip />
        <el-table-column prop="total_count" label="总数量" width="100" align="right">
          <template #default="{ row }">{{ formatCount(row.total_count) }}</template>
        </el-table-column>
        <el-table-column prop="total_price" label="总金额" width="120" align="right">
          <template #default="{ row }">￥{{ formatAmount(row.total_price) }}</template>
        </el-table-column>
        <el-table-column prop="created_by_name" label="下单人" width="110" />
        <el-table-column prop="created_at" label="下单时间" width="170" />
        <el-table-column label="操作" width="120" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click="openClaim(row)">接单</el-button>
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
    <el-dialog v-model="claimVisible" title="接单" width="460px" @closed="handleDialogClosed">
      <el-descriptions :column="1" border size="small" style="margin-bottom: 16px">
        <el-descriptions-item label="订单单号">{{ currentRow?.no }}</el-descriptions-item>
        <el-descriptions-item label="客户名称">{{ currentRow?.customer_name }}</el-descriptions-item>
        <el-descriptions-item label="订单金额">
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
        <el-button type="primary" :loading="submitting" @click="handleClaim">确认接单</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getPendingOrders, claimOrder } from '@/api/warehouse'
import { getWarehouseOptions } from '@/api/basic'
import { formatAmount, formatCount } from '@/utils/format'

const loading = ref(false)
const submitting = ref(false)
const list = ref([])
const total = ref(0)
const warehouseOptions = ref([])

const query = reactive({
  page: 1,
  page_size: 20
})

const claimVisible = ref(false)
const claimFormRef = ref(null)
const currentRow = ref(null)
const claimForm = reactive({ warehouse_id: null })

const claimRules = {
  warehouse_id: [{ required: true, message: '请选择接单仓库', trigger: 'change' }]
}

async function load() {
  loading.value = true
  try {
    const data = await getPendingOrders({ page: query.page, page_size: query.page_size })
    list.value = data?.list || []
    total.value = data?.total || 0
  } finally {
    loading.value = false
  }
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

  submitting.value = true
  try {
    await claimOrder(currentRow.value.id, claimForm.warehouse_id)
    ElMessage.success('接单成功，订单状态已变更为「已接单」')
    claimVisible.value = false
    load()
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
</style>
