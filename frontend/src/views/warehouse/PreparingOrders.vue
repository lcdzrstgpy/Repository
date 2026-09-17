<template>
  <div class="page-container">
    <el-card shadow="never">
      <div class="table-toolbar">
        <div>
          <span class="section-title">备货中订单</span>
          <span class="text-muted" style="margin-left: 12px">
            共 {{ total }} 条，发货后状态回传运营端
          </span>
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
        <el-table-column prop="claimed_by_name" label="接单人" width="110">
          <template #default="{ row }">{{ row.claimed_by_name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="下单时间" width="170" />
        <el-table-column label="操作" width="120" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click="openShip(row)">发货</el-button>
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

    <!-- 发货弹窗：填写物流单号 -->
    <el-dialog v-model="shipVisible" title="订单发货" width="460px" @closed="handleDialogClosed">
      <el-descriptions :column="1" border size="small" style="margin-bottom: 16px">
        <el-descriptions-item label="订单单号">{{ currentRow?.no }}</el-descriptions-item>
        <el-descriptions-item label="客户名称">{{ currentRow?.customer_name }}</el-descriptions-item>
        <el-descriptions-item label="总数量">{{ formatCount(currentRow?.total_count) }}</el-descriptions-item>
      </el-descriptions>

      <el-form ref="shipFormRef" :model="shipForm" :rules="shipRules" label-width="90px">
        <el-form-item label="物流单号" prop="express_no">
          <el-input
            v-model="shipForm.express_no"
            placeholder="请输入物流单号，如 SF1234567890"
            maxlength="64"
            clearable
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="shipVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleShip">确认发货</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getOrderList } from '@/api/order'
import { shipOrder } from '@/api/warehouse'
import { formatAmount, formatCount } from '@/utils/format'

/** 备货中状态值，来自契约 3.2 */
const PREPARING_STATUS = 30

const loading = ref(false)
const submitting = ref(false)
const list = ref([])
const total = ref(0)

const query = reactive({
  page: 1,
  page_size: 20
})

const shipVisible = ref(false)
const shipFormRef = ref(null)
const currentRow = ref(null)
const shipForm = reactive({ express_no: '' })

const shipRules = {
  express_no: [
    { required: true, message: '请输入物流单号', trigger: 'blur' },
    { min: 4, max: 64, message: '物流单号长度为 4 到 64 个字符', trigger: 'blur' }
  ]
}

async function load() {
  loading.value = true
  try {
    const data = await getOrderList({
      page: query.page,
      page_size: query.page_size,
      status: PREPARING_STATUS
    })
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

function openShip(row) {
  currentRow.value = row
  shipForm.express_no = ''
  shipVisible.value = true
}

function handleDialogClosed() {
  shipFormRef.value?.clearValidate()
}

async function handleShip() {
  const valid = await shipFormRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    await shipOrder(currentRow.value.id, shipForm.express_no.trim())
    ElMessage.success('发货成功，状态已回传运营端')
    shipVisible.value = false
    load()
  } finally {
    submitting.value = false
  }
}

onMounted(load)
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
