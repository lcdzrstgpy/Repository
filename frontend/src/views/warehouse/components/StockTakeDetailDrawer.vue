<template>
  <el-drawer
    :model-value="modelValue"
    title="盘点单详情"
    size="820px"
    :destroy-on-close="true"
    @update:model-value="(val) => emit('update:modelValue', val)"
  >
    <div v-loading="loading">
      <template v-if="detail">
        <!-- 操作区：仅「盘点中」可录入 / 完成 / 作废（契约 17.3） -->
        <div class="detail-actions">
          <template v-if="editable">
            <el-button type="primary" :loading="saving" @click="handleSaveItems">
              <el-icon><Check /></el-icon>
              <span style="margin-left: 4px">保存实盘</span>
            </el-button>
            <el-button type="success" :loading="finishing" @click="handleFinish">
              <el-icon><Select /></el-icon>
              <span style="margin-left: 4px">完成盘点</span>
            </el-button>
            <el-button type="danger" plain :loading="canceling" @click="handleCancel">
              作废
            </el-button>
          </template>
          <el-tag v-else :type="stockTakeStatusType(detail.status)" size="large">
            {{ detail.status_text || stockTakeStatusLabel(detail.status) }}
          </el-tag>
        </div>

        <!-- 基础信息 -->
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="盘点单号">{{ detail.no }}</el-descriptions-item>
          <el-descriptions-item label="盘点状态">
            <el-tag :type="stockTakeStatusType(detail.status)" size="small">
              {{ detail.status_text || stockTakeStatusLabel(detail.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="盘点仓库">
            {{ detail.warehouse_name || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="账面数量合计">
            {{ formatCount(detail.total_count) }}
          </el-descriptions-item>
          <el-descriptions-item label="差异合计">
            <span :class="diffClass(detail.diff_count)">{{ formatDiff(detail.diff_count) }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="制单人">{{ detail.created_by_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ detail.created_at || '-' }}</el-descriptions-item>
          <el-descriptions-item label="完成时间">{{ detail.finished_at || '-' }}</el-descriptions-item>
          <el-descriptions-item label="备注" :span="2">{{ detail.remark || '-' }}</el-descriptions-item>
        </el-descriptions>

        <!-- 已作废提示 -->
        <el-alert
          v-if="detail.status === 90"
          class="status-alert"
          type="error"
          :closable="false"
          show-icon
          title="该盘点单已作废，未产生库存变动"
        />

        <!-- 已完成提示 -->
        <el-alert
          v-else-if="detail.status === 20"
          class="status-alert"
          type="success"
          :closable="false"
          show-icon
          title="该盘点单已完成，库存已按差异调整"
        />

        <!-- 明细：盘点中可直接录入实盘数量 -->
        <div class="section-title">
          盘点明细
          <span v-if="editable" class="section-tip">（可直接修改实盘数量与行备注）</span>
        </div>
        <el-table :data="rows" border size="small" show-summary :summary-method="summaryMethod">
          <el-table-column type="index" label="序号" width="56" align="center" />
          <el-table-column prop="sku_code" label="SKU 编码" width="110" />
          <el-table-column prop="product_name" label="商品名称" min-width="120" show-overflow-tooltip />
          <el-table-column prop="spec" label="规格" min-width="100" show-overflow-tooltip />
          <el-table-column label="账面数量" width="90" align="right">
            <template #default="{ row }">{{ formatCount(row.book_quantity) }}</template>
          </el-table-column>
          <el-table-column label="实盘数量" width="140">
            <template #default="{ row }">
              <el-input-number
                v-if="editable"
                v-model="row.actual_quantity"
                :min="0"
                :precision="2"
                :step="1"
                controls-position="right"
                style="width: 100%"
              />
              <span v-else>{{ formatCount(row.actual_quantity) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="差异" width="100" align="right">
            <template #default="{ row }">
              <span :class="diffClass(rowDiff(row))">{{ formatDiff(rowDiff(row)) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="行备注" min-width="150">
            <template #default="{ row }">
              <el-input
                v-if="editable"
                v-model="row.remark"
                placeholder="选填，如：破损 2 件"
                maxlength="255"
              />
              <span v-else>{{ row.remark || '-' }}</span>
            </template>
          </el-table-column>
        </el-table>

        <!-- 实时差异合计 -->
        <div class="summary-bar">
          <span>实盘数量合计：<b>{{ formatCount(totalActual) }}</b></span>
          <span>
            差异合计：<b :class="diffClass(totalDiff)">{{ formatDiff(totalDiff) }}</b>
          </span>
        </div>
      </template>

      <el-empty v-else-if="!loading" description="未获取到盘点单详情" />
    </div>
  </el-drawer>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getStockTakeDetail, updateStockTakeItems, finishStockTake, cancelStockTake } from '@/api/ops'
import { stockTakeStatusType, stockTakeStatusLabel } from '@/utils/constants'
import { formatCount } from '@/utils/format'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  stockTakeId: { type: [Number, String], default: null }
})

const emit = defineEmits(['update:modelValue', 'success'])

const loading = ref(false)
const saving = ref(false)
const finishing = ref(false)
const canceling = ref(false)
const detail = ref(null)
const rows = ref([])

/** 仅「盘点中」(10) 可录入实盘 / 完成 / 作废 */
const editable = computed(() => detail.value?.status === 10)

/** 单行差异 = 实盘 - 账面（未保存时实时计算） */
function rowDiff(row) {
  const actual = Number(row.actual_quantity) || 0
  const book = Number(row.book_quantity) || 0
  return actual - book
}

/** 实盘数量合计 */
const totalActual = computed(() =>
  rows.value.reduce((sum, row) => sum + (Number(row.actual_quantity) || 0), 0)
)

/** 差异合计（实时） */
const totalDiff = computed(() => rows.value.reduce((sum, row) => sum + rowDiff(row), 0))

/** 差异展示：正数带 + 号 */
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

/** 明细表合计行 */
function summaryMethod({ columns }) {
  return columns.map((column, index) => {
    if (index === 0) return '合计'
    if (column.label === '账面数量') return formatCount(detail.value?.total_count)
    if (column.label === '实盘数量') return formatCount(totalActual.value)
    if (column.label === '差异') return formatDiff(totalDiff.value)
    return ''
  })
}

/** 拉取详情并把明细转成可编辑行 */
async function loadDetail() {
  if (!props.stockTakeId) return
  loading.value = true
  try {
    const data = await getStockTakeDetail(props.stockTakeId)
    detail.value = data
    rows.value = (data?.items || []).map((item) => ({
      item_id: item.id,
      sku_code: item.sku_code,
      product_name: item.product_name,
      spec: item.spec,
      book_quantity: item.book_quantity,
      actual_quantity: Number(item.actual_quantity) || 0,
      diff_quantity: item.diff_quantity,
      remark: item.remark || ''
    }))
  } finally {
    loading.value = false
  }
}

/**
 * 把表格里的实盘数据落盘，成功后重新拉取详情。
 *
 * :param silent 为 true 时不弹「已保存」提示（供「完成盘点」前静默保存）
 * :return true 表示已成功落盘；false 表示本地校验没过、未提交
 */
async function persistItems({ silent = false } = {}) {
  for (let i = 0; i < rows.value.length; i += 1) {
    const value = rows.value[i].actual_quantity
    if (value === null || value === undefined || Number(value) < 0) {
      ElMessage.warning(`第 ${i + 1} 行实盘数量不能小于 0`)
      return false
    }
  }

  await updateStockTakeItems(props.stockTakeId, {
    items: rows.value.map((row) => ({
      item_id: row.item_id,
      actual_quantity: Number(row.actual_quantity) || 0,
      remark: (row.remark || '').trim()
    }))
  })
  await loadDetail()
  if (!silent) ElMessage.success('实盘数量已保存')
  return true
}

/** 保存实盘：逐行提交实盘数量与行备注 */
async function handleSaveItems() {
  saving.value = true
  try {
    await persistItems()
  } catch (e) {
    // 请求失败已由 axios 拦截器统一提示，这里只需停止后续流程
  } finally {
    saving.value = false
  }
}

/** 完成盘点：按差异调整库存，不可撤销 */
async function handleFinish() {
  // 关键：表格里的 el-input-number 直接双向绑定本地 rows，属于「未保存的编辑」。
  // 若不先落盘就完成，后端会按库里的旧值算差异 —— 用户刚改的实盘数量被静默丢弃，
  // 库存也不会按预期调整。所以必须先保存，再弹确认框（确认框读的是保存后的真实数据）。
  finishing.value = true
  try {
    let saved = false
    try {
      saved = await persistItems({ silent: true })
    } catch (e) {
      return // 保存失败（拦截器已提示），不继续完成盘点
    }
    if (!saved) return

    try {
      await ElMessageBox.confirm(
        `确认完成盘点单「${detail.value.no}」吗？将按差异合计 ${formatDiff(
          totalDiff.value
        )} 调整「${detail.value.warehouse_name || '该仓库'}」的库存，完成后不可修改。`,
        '完成盘点',
        { type: 'warning', confirmButtonText: '确认完成', cancelButtonText: '取消' }
      )
    } catch (e) {
      return // 用户取消
    }

    try {
      await finishStockTake(props.stockTakeId)
    } catch (e) {
      return
    }
    ElMessage.success('盘点已完成，库存已按差异调整')
    await loadDetail()
    emit('success')
  } finally {
    finishing.value = false
  }
}

/** 作废盘点单：不动库存 */
async function handleCancel() {
  try {
    await ElMessageBox.confirm(
      `确认作废盘点单「${detail.value.no}」吗？作废后不可恢复，且不会产生库存变动。`,
      '作废盘点单',
      { type: 'warning', confirmButtonText: '确认作废', cancelButtonText: '取消' }
    )
  } catch (e) {
    return // 用户取消
  }

  canceling.value = true
  try {
    await cancelStockTake(props.stockTakeId)
    ElMessage.success('盘点单已作废')
    await loadDetail()
    emit('success')
  } finally {
    canceling.value = false
  }
}

/** 打开抽屉时拉取详情 */
watch(
  () => [props.modelValue, props.stockTakeId],
  async ([visible, id]) => {
    if (!visible || !id) return
    detail.value = null
    rows.value = []
    await loadDetail()
  },
  { immediate: true }
)
</script>

<style scoped>
.detail-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-bottom: 12px;
}

.section-title {
  margin: 20px 0 12px;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  border-left: 3px solid #409eff;
  padding-left: 8px;
}

.section-tip {
  font-size: 12px;
  font-weight: 400;
  color: #909399;
}

.status-alert {
  margin-top: 16px;
}

.summary-bar {
  display: flex;
  justify-content: flex-end;
  gap: 32px;
  margin-top: 12px;
  font-size: 14px;
}

.diff-plus {
  color: #67c23a;
  font-weight: 600;
}

.diff-minus {
  color: #f56c6c;
  font-weight: 600;
}
</style>
