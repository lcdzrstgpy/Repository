<template>
  <el-drawer
    :model-value="modelValue"
    title="订单详情"
    size="720px"
    :destroy-on-close="true"
    @update:model-value="(val) => emit('update:modelValue', val)"
  >
    <div v-loading="loading">
      <template v-if="detail">
        <!-- 基础信息 -->
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="订单单号">{{ detail.no }}</el-descriptions-item>
          <el-descriptions-item label="订单状态">
            <el-tag :type="orderStatusType(detail.status)" size="small">
              {{ orderStatusText }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="订单 SKU 数">{{ formatCount(detail.item_count) }}</el-descriptions-item>
          <el-descriptions-item label="总数量">{{ formatCount(displayTotalCount) }}</el-descriptions-item>
          <el-descriptions-item label="预计总成本">
            ￥{{ formatAmount(displayTotalPrice) }}
          </el-descriptions-item>
          <el-descriptions-item label="物流单号">
            {{ detail.express_no || '未发货' }}
          </el-descriptions-item>
          <el-descriptions-item label="下单人">{{ detail.created_by_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="接单人">{{ detail.claimed_by_name || '未接单' }}</el-descriptions-item>
          <el-descriptions-item label="下单时间">{{ detail.created_at || '-' }}</el-descriptions-item>
          <el-descriptions-item label="发货时间">{{ detail.shipped_at || '-' }}</el-descriptions-item>
          <el-descriptions-item label="指派仓库">{{ detail.warehouse_name || '未指派' }}</el-descriptions-item>
          <el-descriptions-item label="备注">{{ detail.remark || '-' }}</el-descriptions-item>
        </el-descriptions>

        <!-- 已取消提示 -->
        <el-alert
          v-if="detail.status === 90"
          class="cancel-alert"
          type="error"
          :closable="false"
          show-icon
          :title="`该订单已取消，取消原因：${detail.cancel_reason || '未填写'}`"
        />

        <!-- 状态时间线 -->
        <div class="section-title">流转进度</div>
        <el-steps :active="activeStep" align-center finish-status="success" class="status-steps">
          <el-step
            v-for="(step, index) in ORDER_STEPS"
            :key="step.status"
            :title="step.label"
            :description="stepTime(index)"
          />
        </el-steps>

        <!-- 明细 -->
        <div class="section-title">订单明细</div>
        <el-table :data="detail.items || []" border size="small" show-summary :summary-method="summaryMethod">
          <el-table-column type="index" label="序号" width="55" align="center" />
          <el-table-column prop="product_name" label="SKU 名" min-width="120" show-overflow-tooltip />
          <el-table-column label="货号" min-width="150">
            <template #default="{ row }">
              <!-- 已关联：显示仓库回填的实际货号 -->
              <template v-if="row.sku_id">
                <div>{{ row.sku_code_bound || '-' }}</div>
                <el-tag type="success" size="small">已关联</el-tag>
              </template>
              <!-- 未关联：显示运营录入的货号 / 新品标记 -->
              <template v-else-if="row.sku_code">
                <div>{{ row.sku_code }}</div>
                <el-tag type="warning" size="small">待仓库关联</el-tag>
              </template>
              <template v-else-if="row.is_new === 1">
                <div>—</div>
                <el-tag type="info" size="small">新品·待建货号</el-tag>
              </template>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column prop="spec" label="规格" min-width="100" show-overflow-tooltip>
            <template #default="{ row }">{{ row.spec || '-' }}</template>
          </el-table-column>
          <el-table-column prop="count" label="数量" width="80" align="right">
            <template #default="{ row }">
              <el-input-number
                v-if="detail.status === 25"
                v-model="quantityForm[row.id]"
                :min="1"
                :precision="0"
                :step="1"
                controls-position="right"
                size="small"
                style="width: 110px"
              />
              <span v-else>{{ formatCount(row.count) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="out_count" label="已出库" width="80" align="right">
            <template #default="{ row }">{{ formatCount(row.out_count) }}</template>
          </el-table-column>
          <el-table-column prop="expect_price" label="预计成本" width="95" align="right">
            <template #default="{ row }">￥{{ formatAmount(row.expect_price) }}</template>
          </el-table-column>
          <el-table-column prop="total_price" label="小计" width="100" align="right">
            <template #default="{ row }">
              ￥{{ formatAmount(detail.status === 25 ? quantityForm[row.id] * row.expect_price : row.total_price) }}
            </template>
          </el-table-column>
        </el-table>

        <!-- 数量待确认(25) 时运营填写最终数量，确认后由系统锁库并进入备货中(30) -->
        <div v-if="detail.status === 25" class="footer-actions">
          <span class="text-muted">请填写最终出库数量；确认后交由仓储备货或采购。</span>
          <el-button type="warning" :loading="confirming" @click="handleConfirmQuantity">
            确认数量并开始备货
          </el-button>
        </div>
      </template>

      <el-empty v-else-if="!loading" description="未获取到订单详情" />
    </div>
  </el-drawer>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getOrderDetail, confirmQuantity } from '@/api/order'
import { ORDER_STEPS, orderStatusType } from '@/utils/constants'
import { formatAmount, formatCount } from '@/utils/format'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  orderId: { type: [Number, String], default: null }
})

const emit = defineEmits(['update:modelValue', 'updated'])

const loading = ref(false)
const confirming = ref(false)
const detail = ref(null)
const quantityForm = reactive({})

const orderStatusText = computed(() => detail.value?.status_text || '-')
const displayTotalCount = computed(() => {
  if (detail.value?.status !== 25) return detail.value?.total_count || 0
  return (detail.value.items || []).reduce((total, row) => total + Number(quantityForm[row.id] || 0), 0)
})
const displayTotalPrice = computed(() => {
  if (detail.value?.status !== 25) return detail.value?.total_price || 0
  return (detail.value.items || []).reduce(
    (total, row) => total + Number(quantityForm[row.id] || 0) * Number(row.expect_price || 0),
    0
  )
})

/** 时间线当前步骤：已完成(50) 时全部走完，其余状态停在对应节点 */
const activeStep = computed(() => {
  const status = detail.value?.status
  const index = ORDER_STEPS.findIndex((step) => step.status === status)
  if (index === -1) return 0
  return status === 50 ? ORDER_STEPS.length : index
})

/** 每一步下方的说明文字，展示对应时间节点 */
function stepTime(index) {
  if (!detail.value) return ''
  const timeMap = {
    10: detail.value.created_at,
    20: detail.value.claimed_at,
    30: detail.value.prepare_at,
    40: detail.value.shipped_at,
    50: detail.value.finished_at
  }
  return timeMap[ORDER_STEPS[index].status] || ''
}

/** 明细表合计行 */
function summaryMethod({ columns }) {
  return columns.map((column, index) => {
    if (index === 0) return '合计'
    if (column.property === 'count') return formatCount(displayTotalCount.value)
    if (column.property === 'total_price') return `￥${formatAmount(displayTotalPrice.value)}`
    return ''
  })
}

function syncQuantityForm() {
  for (const key of Object.keys(quantityForm)) delete quantityForm[key]
  for (const row of detail.value?.items || []) {
    quantityForm[row.id] = Math.max(1, Math.round(Number(row.count) || 1))
  }
}

/**
 * 确认数量：仅「数量待确认」(25) 可用
 * 提交每一行的最终正整数数量。后端以此重算总数/总成本，库存由仓储备货或采购处理。
 */
async function handleConfirmQuantity() {
  const items = (detail.value?.items || []).map((row) => ({
    item_id: row.id,
    count: Number(quantityForm[row.id])
  }))
  if (items.some((item) => !Number.isInteger(item.count) || item.count < 1)) {
    ElMessage.error('每个商品的数量必须是大于 0 的整数')
    return
  }

  confirming.value = true
  try {
    await confirmQuantity(detail.value.id, { items })
    ElMessage.success('已确认数量，订单状态变更为「备货中」')
    detail.value = await getOrderDetail(props.orderId)
    syncQuantityForm()
    emit('updated')
  } finally {
    confirming.value = false
  }
}

/** 打开抽屉时拉取详情 */
watch(
  () => [props.modelValue, props.orderId],
  async ([visible, id]) => {
    if (!visible || !id) return
    loading.value = true
    detail.value = null
    try {
      detail.value = await getOrderDetail(id)
      syncQuantityForm()
    } finally {
      loading.value = false
    }
  },
  { immediate: true }
)
</script>

<style scoped>
.section-title {
  margin: 20px 0 12px;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  border-left: 3px solid #409eff;
  padding-left: 8px;
}

.status-steps {
  margin-top: 8px;
}

.cancel-alert {
  margin-top: 16px;
}

.footer-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
}

.text-muted {
  color: #909399;
  font-size: 13px;
}
</style>
