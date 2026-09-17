<template>
  <div class="page-container">
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
        <el-form-item label="关键词">
          <el-input
            v-model="query.keyword"
            placeholder="SKU 编码 / 商品名称"
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
        <span class="text-muted">共 {{ total }} 条库存记录</span>
        <div>
          <el-button v-if="canExport" :loading="exporting" @click="handleExport">
            <el-icon><Download /></el-icon>
            <span style="margin-left: 4px">导出 Excel</span>
          </el-button>
          <el-button :loading="loading" @click="load">
            <el-icon><Refresh /></el-icon>
            <span style="margin-left: 4px">刷新</span>
          </el-button>
        </div>
      </div>

      <el-table v-loading="loading" :data="list" border stripe>
        <el-table-column prop="sku_code" label="SKU 编码" width="130" />
        <el-table-column prop="product_name" label="商品名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="spec" label="规格" min-width="140" show-overflow-tooltip />
        <el-table-column prop="warehouse_name" label="仓库" width="130" />
        <el-table-column prop="quantity" label="库存数量" width="110" align="right">
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
        <el-table-column label="操作" width="150" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click="openHistory(row)">库存流水</el-button>
            <el-button v-if="userStore.isAdmin" link type="warning" @click="openAdjust(row)">
              调整库存
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

    <!-- 库存流水弹窗 -->
    <el-dialog v-model="historyVisible" title="库存流水" width="900px" @closed="handleHistoryClosed">
      <el-descriptions :column="2" border size="small" style="margin-bottom: 16px">
        <el-descriptions-item label="SKU 编码">{{ currentRow?.sku_code }}</el-descriptions-item>
        <el-descriptions-item label="商品名称">{{ currentRow?.product_name }}</el-descriptions-item>
        <el-descriptions-item label="规格">{{ currentRow?.spec || '-' }}</el-descriptions-item>
        <el-descriptions-item label="仓库">{{ currentRow?.warehouse_name }}</el-descriptions-item>
      </el-descriptions>

      <el-table v-loading="historyLoading" :data="historyList" border size="small" max-height="360">
        <el-table-column prop="created_at" label="变动时间" width="170" />
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
        <el-table-column prop="order_no" label="关联单号" width="160">
          <template #default="{ row }">{{ row.order_no || '-' }}</template>
        </el-table-column>
        <el-table-column prop="order_type" label="单据类型" width="110">
          <template #default="{ row }">
            {{ row.order_type_text || orderTypeLabel(row.order_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="created_by_name" label="操作人" width="110">
          <template #default="{ row }">{{ row.created_by_name || row.created_by || '-' }}</template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="historyQuery.page"
          v-model:page-size="historyQuery.page_size"
          :total="historyTotal"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          background
          small
          @size-change="handleHistorySizeChange"
          @current-change="handleHistoryPageChange"
        />
      </div>
    </el-dialog>

    <!-- 库存调整弹窗：仅管理员可见，quantity 为目标值 -->
    <el-dialog
      v-model="adjustVisible"
      title="调整库存"
      width="480px"
      @closed="handleAdjustClosed"
    >
      <el-descriptions v-if="adjustRow" :column="1" border size="small" style="margin-bottom: 16px">
        <el-descriptions-item label="SKU 编码">{{ adjustRow.sku_code }}</el-descriptions-item>
        <el-descriptions-item label="商品名称">{{ adjustRow.product_name }}</el-descriptions-item>
        <el-descriptions-item label="仓库">{{ adjustRow.warehouse_name }}</el-descriptions-item>
        <el-descriptions-item label="当前库存">
          {{ formatCount(adjustRow.quantity) }}
        </el-descriptions-item>
      </el-descriptions>

      <el-form ref="adjustFormRef" :model="adjustForm" :rules="adjustRules" label-width="90px">
        <el-form-item label="目标数量" prop="quantity">
          <el-input-number
            v-model="adjustForm.quantity"
            :min="0"
            :precision="2"
            :step="1"
            controls-position="right"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="调整备注" prop="remark">
          <el-input
            v-model="adjustForm.remark"
            type="textarea"
            :rows="3"
            placeholder="请输入调整原因，如：盘点差异"
            maxlength="500"
            show-word-limit
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="adjustVisible = false">取消</el-button>
        <el-button type="primary" :loading="adjustSubmitting" @click="handleAdjust">确认调整</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getInventoryList, getInventoryHistory } from '@/api/inventory'
import { adjustInventory } from '@/api/stock'
import { getWarehouseOptions } from '@/api/basic'
import { exportInventory } from '@/api/export'
import { useUserStore } from '@/stores/user'
import { orderTypeLabel } from '@/utils/constants'
import { formatCount } from '@/utils/format'

const userStore = useUserStore()

/** 导出库存角色：warehouse / admin（契约 15） */
const canExport = computed(() => ['warehouse', 'admin'].includes(userStore.role))

const loading = ref(false)
const list = ref([])
const total = ref(0)
const warehouseOptions = ref([])

const query = reactive({
  page: 1,
  page_size: 20,
  warehouse_id: '',
  keyword: ''
})

// ---------- 库存流水 ----------
const historyVisible = ref(false)
const historyLoading = ref(false)
const historyList = ref([])
const historyTotal = ref(0)
const currentRow = ref(null)
const historyQuery = reactive({ page: 1, page_size: 10 })

// ---------- 库存调整（仅 admin） ----------
const adjustVisible = ref(false)
const adjustSubmitting = ref(false)
const adjustFormRef = ref(null)
const adjustRow = ref(null)
const adjustForm = reactive({ quantity: 0, remark: '' })

const adjustRules = {
  quantity: [{ required: true, message: '请输入目标数量', trigger: 'blur' }],
  remark: [{ required: true, message: '请填写调整备注', trigger: 'blur' }]
}

async function load() {
  loading.value = true
  try {
    const params = { page: query.page, page_size: query.page_size }
    if (query.warehouse_id !== '' && query.warehouse_id !== null) {
      params.warehouse_id = query.warehouse_id
    }
    if (query.keyword) params.keyword = query.keyword.trim()

    const data = await getInventoryList(params)
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

// ---------- 导出 Excel ----------
const exporting = ref(false)

/** 导出库存：带上当前筛选条件（warehouse_id） */
async function handleExport() {
  if (exporting.value) return
  exporting.value = true
  try {
    const params = {}
    if (query.warehouse_id !== '' && query.warehouse_id !== null) {
      params.warehouse_id = query.warehouse_id
    }
    const fileName = await exportInventory(params)
    ElMessage.success(`已导出「${fileName}」`)
  } catch (e) {
    // download.js 内部已弹出错误提示，这里不再重复提示
  } finally {
    exporting.value = false
  }
}

/** 加载流水 */
async function loadHistory() {
  historyLoading.value = true
  try {
    const data = await getInventoryHistory({
      page: historyQuery.page,
      page_size: historyQuery.page_size,
      sku_id: currentRow.value.sku_id,
      warehouse_id: currentRow.value.warehouse_id
    })
    historyList.value = data?.list || []
    historyTotal.value = data?.total || 0
  } finally {
    historyLoading.value = false
  }
}

function openHistory(row) {
  currentRow.value = row
  historyQuery.page = 1
  historyVisible.value = true
  loadHistory()
}

function handleHistoryClosed() {
  historyList.value = []
  historyTotal.value = 0
}

function handleHistorySizeChange(size) {
  historyQuery.page_size = size
  historyQuery.page = 1
  loadHistory()
}

function handleHistoryPageChange(page) {
  historyQuery.page = page
  loadHistory()
}

/** 打开库存调整弹窗，默认带出当前库存作为目标值 */
function openAdjust(row) {
  adjustRow.value = row
  adjustForm.quantity = Number(row.quantity) || 0
  adjustForm.remark = ''
  adjustVisible.value = true
}

function handleAdjustClosed() {
  adjustFormRef.value?.clearValidate()
}

/** 提交库存调整：quantity 为目标值，后端算差异 */
async function handleAdjust() {
  const valid = await adjustFormRef.value.validate().catch(() => false)
  if (!valid) return

  try {
    await ElMessageBox.confirm(
      `确认将「${adjustRow.value.sku_code}」在「${adjustRow.value.warehouse_name}」的库存由 ${formatCount(
        adjustRow.value.quantity
      )} 调整为 ${formatCount(adjustForm.quantity)} 吗？`,
      '调整库存',
      { type: 'warning', confirmButtonText: '确认调整', cancelButtonText: '取消' }
    )
  } catch (e) {
    return // 用户取消
  }

  adjustSubmitting.value = true
  try {
    await adjustInventory({
      sku_id: adjustRow.value.sku_id,
      warehouse_id: adjustRow.value.warehouse_id,
      quantity: Number(adjustForm.quantity),
      remark: adjustForm.remark.trim()
    })
    ElMessage.success('库存调整成功')
    adjustVisible.value = false
    load()
  } finally {
    adjustSubmitting.value = false
  }
}

onMounted(async () => {
  load()
  warehouseOptions.value = (await getWarehouseOptions()) || []
})
</script>

<style scoped>
.low-stock {
  color: #f56c6c;
  font-weight: 600;
}

.in-stock {
  color: #67c23a;
}

.out-stock {
  color: #f56c6c;
}
</style>
