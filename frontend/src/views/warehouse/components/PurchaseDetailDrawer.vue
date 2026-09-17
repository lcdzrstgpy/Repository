<template>
  <el-drawer
    :model-value="modelValue"
    title="采购单详情"
    size="760px"
    :destroy-on-close="true"
    @update:model-value="(val) => emit('update:modelValue', val)"
  >
    <div v-loading="loading">
      <template v-if="detail">
        <!-- 打印入口：新标签页打开独立打印页 -->
        <div class="detail-actions">
          <el-button type="primary" plain size="small" @click="handlePrint">
            <el-icon><Printer /></el-icon>
            <span style="margin-left: 4px">打印</span>
          </el-button>
        </div>

        <!-- 基础信息 -->
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="采购单号">{{ detail.no }}</el-descriptions-item>
          <el-descriptions-item label="采购状态">
            <el-tag :type="purchaseStatusType(detail.status)" size="small">
              {{ detail.status_text || purchaseStatusLabel(detail.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="采购快递单号">{{ detail.express_no || '-' }}</el-descriptions-item>
          <el-descriptions-item label="关联销售订单">
            {{ detail.sales_order_no || '无' }}
          </el-descriptions-item>
          <el-descriptions-item label="总数量">{{ formatCount(detail.total_count) }}</el-descriptions-item>
          <el-descriptions-item label="总金额">
            ￥{{ formatAmount(detail.total_price) }}
          </el-descriptions-item>
          <el-descriptions-item label="创建人">{{ detail.created_by_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="审批人">
            {{ detail.approved_by_name || '未审批' }}
          </el-descriptions-item>
          <el-descriptions-item label="审批时间">{{ detail.approved_at || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ detail.created_at || '-' }}</el-descriptions-item>
          <el-descriptions-item label="备注">{{ detail.remark || '-' }}</el-descriptions-item>
        </el-descriptions>

        <!-- 已取消提示 -->
        <el-alert
          v-if="detail.status === 90"
          class="cancel-alert"
          type="error"
          :closable="false"
          show-icon
          title="该采购单已取消"
        />

        <!-- 明细 -->
        <div class="section-title">采购明细</div>
        <el-table
          :data="detail.items || []"
          border
          size="small"
          show-summary
          :summary-method="summaryMethod"
        >
          <el-table-column type="index" label="序号" width="60" align="center" />
          <el-table-column prop="sku_code" label="货号" width="110" />
          <el-table-column prop="product_name" label="商品名称" min-width="130" show-overflow-tooltip />
          <el-table-column prop="spec" label="规格" min-width="110" show-overflow-tooltip />
          <el-table-column prop="count" label="采购数量" width="100" align="right">
            <template #default="{ row }">{{ formatCount(row.count) }}</template>
          </el-table-column>
          <el-table-column label="已入库 / 采购" min-width="160">
            <template #default="{ row }">
              <div class="progress-cell">
                <el-progress
                  :percentage="inPercent(row)"
                  :stroke-width="10"
                  :status="inPercent(row) >= 100 ? 'success' : undefined"
                />
                <span class="progress-text">
                  {{ formatCount(row.in_count) }} / {{ formatCount(row.count) }}
                </span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="price" label="单价" width="100" align="right">
            <template #default="{ row }">￥{{ formatAmount(row.price) }}</template>
          </el-table-column>
          <el-table-column prop="total_price" label="小计" width="110" align="right">
            <template #default="{ row }">￥{{ formatAmount(row.total_price) }}</template>
          </el-table-column>
        </el-table>
      </template>

      <el-empty v-else-if="!loading" description="未获取到采购单详情" />
    </div>
  </el-drawer>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { getPurchaseDetail } from '@/api/purchase'
import { purchaseStatusType, purchaseStatusLabel } from '@/utils/constants'
import { formatAmount, formatCount } from '@/utils/format'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  orderId: { type: [Number, String], default: null }
})

const emit = defineEmits(['update:modelValue'])

const router = useRouter()

const loading = ref(false)
const detail = ref(null)

/** 打印采购单：新标签页打开独立打印页（契约 13） */
function handlePrint() {
  if (!props.orderId) return
  const { href } = router.resolve({ path: `/print/purchase-order/${props.orderId}` })
  window.open(href, '_blank')
}

/** 入库进度百分比，采购数量为 0 时按 0 处理 */
function inPercent(row) {
  const count = Number(row.count) || 0
  const inCount = Number(row.in_count) || 0
  if (count <= 0) return 0
  return Math.min(100, Math.round((inCount / count) * 100))
}

/** 明细表合计行 */
function summaryMethod({ columns }) {
  return columns.map((column, index) => {
    if (index === 0) return '合计'
    if (column.property === 'count') return formatCount(detail.value?.total_count)
    if (column.property === 'total_price') return `￥${formatAmount(detail.value?.total_price)}`
    return ''
  })
}

/** 打开抽屉时拉取详情 */
watch(
  () => [props.modelValue, props.orderId],
  async ([visible, id]) => {
    if (!visible || !id) return
    loading.value = true
    detail.value = null
    try {
      detail.value = await getPurchaseDetail(id)
    } finally {
      loading.value = false
    }
  },
  { immediate: true }
)
</script>

<style scoped>
.detail-actions {
  display: flex;
  justify-content: flex-end;
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

.cancel-alert {
  margin-top: 16px;
}

.progress-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.progress-cell :deep(.el-progress) {
  flex: 1;
}

.progress-text {
  white-space: nowrap;
  color: #606266;
  font-size: 12px;
}
</style>
