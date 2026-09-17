<template>
  <div class="page-container">
    <el-card shadow="never" class="search-card">
      <div class="module-purpose">货号库存 / 自动生成货号</div>
      <WarehouseInventoryTabs class="tabs" />
      <el-form :model="query" inline>
        <el-form-item label="关键词">
          <el-input
            v-model="query.keyword"
            placeholder="货号 / 商品名称"
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
          <el-button v-if="canAdjust" @click="openCreateItem">自动生成货号</el-button>
          <el-button v-if="canAdjust" type="primary" @click="openInbound">采购入库</el-button>
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
        <el-table-column prop="sku_code" label="货号" width="130" />
        <el-table-column prop="product_name" label="商品名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="spec" label="规格" min-width="140" show-overflow-tooltip />
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.sku_status === 1 ? 'success' : 'info'" size="small">
              {{ row.sku_status === 1 ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
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
        <el-table-column label="操作" width="220" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click="openHistory(row)">库存流水</el-button>
            <el-button v-if="canAdjust" link type="warning" @click="openAdjust(row)">
              调整库存
            </el-button>
            <el-button v-if="canAdjust" link :type="row.sku_status === 1 ? 'danger' : 'success'" @click="toggleItemStatus(row)">
              {{ row.sku_status === 1 ? '停用' : '启用' }}
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

    <el-dialog v-model="createItemVisible" title="自动生成货号" width="520px" @closed="handleCreateItemClosed">
      <el-alert type="info" :closable="false" show-icon title="填写三级分类后自动生成 A001-B001-C001 格式货号；货号生成后不可修改。" style="margin-bottom: 16px" />
      <el-form ref="createItemFormRef" :model="createItemForm" :rules="createItemRules" label-width="95px">
        <el-form-item label="商品名称" prop="product_name"><el-input v-model="createItemForm.product_name" placeholder="如：玻璃杯" /></el-form-item>
        <el-form-item label="一级分类" prop="category_level1"><el-input v-model="createItemForm.category_level1" placeholder="如：杯子" /></el-form-item>
        <el-form-item label="二级分类"><el-input v-model="createItemForm.category_level2" placeholder="如：玻璃杯（选填）" /></el-form-item>
        <el-form-item label="三级分类"><el-input v-model="createItemForm.category_level3" placeholder="如：400ml（选填）" /></el-form-item>
        <el-form-item label="规格"><el-input v-model="createItemForm.spec" placeholder="如：透明/400ml（选填）" /></el-form-item>
        <el-form-item label="售价"><el-input-number v-model="createItemForm.price" :min="0" :precision="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createItemVisible = false">取消</el-button>
        <el-button type="primary" :loading="createItemSubmitting" @click="handleCreateItem">生成并确认</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="inboundVisible" title="采购入库" width="500px" @closed="handleInboundClosed">
      <el-alert type="info" :closable="false" show-icon title="用于提前备货或采购到货；本次数量会直接增加库存并写入库存流水。" style="margin-bottom: 16px" />
      <el-form ref="inboundFormRef" :model="inboundForm" :rules="inboundRules" label-width="90px">
        <el-form-item label="货号" prop="sku_id">
          <el-select v-model="inboundForm.sku_id" filterable placeholder="请选择货号" style="width: 100%">
            <el-option v-for="item in skuOptions" :key="item.id" :value="item.id" :label="`${item.sku_code} · ${item.name}${item.spec ? ' / ' + item.spec : ''}`" />
          </el-select>
        </el-form-item>
        <el-form-item label="入库数量" prop="quantity">
          <el-input-number v-model="inboundForm.quantity" :min="1" :precision="0" :step="1" controls-position="right" style="width: 100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="inboundForm.remark" type="textarea" :rows="3" maxlength="500" show-word-limit placeholder="如：提前备货、采购到货" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="inboundVisible = false">取消</el-button>
        <el-button type="primary" :loading="inboundSubmitting" @click="handleInbound">确认入库</el-button>
      </template>
    </el-dialog>

    <!-- 库存流水弹窗 -->
    <el-dialog v-model="historyVisible" title="库存流水" width="900px" @closed="handleHistoryClosed">
      <el-descriptions :column="2" border size="small" style="margin-bottom: 16px">
        <el-descriptions-item label="货号">{{ currentRow?.sku_code }}</el-descriptions-item>
        <el-descriptions-item label="商品名称">{{ currentRow?.product_name }}</el-descriptions-item>
        <el-descriptions-item label="规格">{{ currentRow?.spec || '-' }}</el-descriptions-item>
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

    <!-- 库存调整弹窗：仓储、管理员可用，quantity 为目标值 -->
    <el-dialog
      v-model="adjustVisible"
      title="调整库存"
      width="480px"
      @closed="handleAdjustClosed"
    >
      <el-descriptions v-if="adjustRow" :column="1" border size="small" style="margin-bottom: 16px">
        <el-descriptions-item label="货号">{{ adjustRow.sku_code }}</el-descriptions-item>
        <el-descriptions-item label="商品名称">{{ adjustRow.product_name }}</el-descriptions-item>
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
            placeholder="请输入调整原因"
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
import { adjustInventory, inboundInventory } from '@/api/stock'
import { getSkuOptions } from '@/api/basic'
import { exportInventory } from '@/api/export'
import { useUserStore } from '@/stores/user'
import { orderTypeLabel } from '@/utils/constants'
import { formatCount } from '@/utils/format'
import { createItemNumber, updateItemNumberStatus } from '@/api/warehouse'
import WarehouseInventoryTabs from './components/WarehouseInventoryTabs.vue'

const userStore = useUserStore()

/** 导出库存角色：warehouse / admin（契约 15） */
const canExport = computed(() => ['warehouse', 'admin'].includes(userStore.role))
const canAdjust = computed(() => ['warehouse', 'admin'].includes(userStore.role))

const loading = ref(false)
const list = ref([])
const total = ref(0)
const skuOptions = ref([])

const query = reactive({
  page: 1,
  page_size: 20,
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

const inboundVisible = ref(false)
const inboundSubmitting = ref(false)
const inboundFormRef = ref(null)
const inboundForm = reactive({ sku_id: null, quantity: 1, remark: '' })
const inboundRules = {
  sku_id: [{ required: true, message: '请选择货号', trigger: 'change' }],
  quantity: [{ required: true, message: '请输入入库数量', trigger: 'blur' }]
}

const createItemVisible = ref(false)
const createItemSubmitting = ref(false)
const createItemFormRef = ref(null)
const emptyItemForm = () => ({ product_name: '', category_level1: '', category_level2: '', category_level3: '', spec: '', price: 0 })
const createItemForm = reactive(emptyItemForm())
const createItemRules = {
  product_name: [{ required: true, message: '请输入商品名称', trigger: 'blur' }],
  category_level1: [{ required: true, message: '请输入一级分类', trigger: 'blur' }]
}

async function load() {
  loading.value = true
  try {
    const params = { page: query.page, page_size: query.page_size }
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

/** 导出当前库存。 */
async function handleExport() {
  if (exporting.value) return
  exporting.value = true
  try {
    const fileName = await exportInventory({})
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
      sku_id: currentRow.value.sku_id
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

function openCreateItem() {
  Object.assign(createItemForm, emptyItemForm())
  createItemVisible.value = true
}

function handleCreateItemClosed() {
  createItemFormRef.value?.clearValidate()
}

async function handleCreateItem() {
  const valid = await createItemFormRef.value.validate().catch(() => false)
  if (!valid) return
  createItemSubmitting.value = true
  try {
    const data = await createItemNumber({
      ...createItemForm,
      category_level2: createItemForm.category_level2 || null,
      category_level3: createItemForm.category_level3 || null,
      spec: createItemForm.spec || null
    })
    ElMessage.success(`已生成货号：${data.sku_code}，可继续采购入库`)
    createItemVisible.value = false
    skuOptions.value = (await getSkuOptions()) || []
  } finally {
    createItemSubmitting.value = false
  }
}

async function toggleItemStatus(row) {
  const nextStatus = row.sku_status === 1 ? 0 : 1
  const action = nextStatus === 1 ? '启用' : '停用'
  try {
    await ElMessageBox.confirm(
      `确认${action}货号「${row.sku_code}」吗？${nextStatus === 0 ? '停用后不能再关联订单或采购入库。' : ''}`,
      `${action}货号`,
      { type: 'warning', confirmButtonText: `确认${action}`, cancelButtonText: '取消' }
    )
  } catch (e) {
    return
  }
  await updateItemNumberStatus(row.sku_id, nextStatus)
  ElMessage.success(`货号已${action}`)
  load()
  skuOptions.value = (await getSkuOptions()) || []
}

function openInbound() {
  inboundForm.sku_id = null
  inboundForm.quantity = 1
  inboundForm.remark = ''
  inboundVisible.value = true
}

function handleInboundClosed() {
  inboundFormRef.value?.clearValidate()
}

async function handleInbound() {
  const valid = await inboundFormRef.value.validate().catch(() => false)
  if (!valid) return
  inboundSubmitting.value = true
  try {
    await inboundInventory({ ...inboundForm, remark: inboundForm.remark.trim() || null })
    ElMessage.success('采购入库成功')
    inboundVisible.value = false
    load()
  } finally {
    inboundSubmitting.value = false
  }
}

/** 提交库存调整：quantity 为目标值，后端算差异 */
async function handleAdjust() {
  const valid = await adjustFormRef.value.validate().catch(() => false)
  if (!valid) return

  try {
    await ElMessageBox.confirm(
      `确认将「${adjustRow.value.sku_code}」的库存由 ${formatCount(
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
  skuOptions.value = (await getSkuOptions()) || []
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

.module-purpose {
  margin-bottom: 14px;
  color: #409eff;
  font-size: 18px;
  font-weight: 600;
}

.tabs { margin-bottom: 14px; }

</style>
