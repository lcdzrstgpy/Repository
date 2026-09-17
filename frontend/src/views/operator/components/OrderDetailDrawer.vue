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
          <el-descriptions-item label="客户名称">{{ detail.customer_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="总数量">{{ formatCount(detail.total_count) }}</el-descriptions-item>
          <el-descriptions-item label="总金额">
            ￥{{ formatAmount(detail.total_price) }}
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
          <el-table-column type="index" label="序号" width="60" align="center" />
          <el-table-column label="SKU 图片" width="92" align="center">
            <template #default="{ row }">
              <el-image v-if="row.image_url" :src="row.image_url" :preview-src-list="[row.image_url]" fit="cover" class="sku-image" />
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column prop="sku_code" label="货号" width="130" />
          <el-table-column prop="product_name" label="商品名称" min-width="130" show-overflow-tooltip />
          <el-table-column prop="spec" label="规格" min-width="110" show-overflow-tooltip />
          <el-table-column prop="remark" label="备注" min-width="150" show-overflow-tooltip>
            <template #default="{ row }">{{ row.remark || '-' }}</template>
          </el-table-column>
          <el-table-column prop="count" label="数量" width="90" align="right">
            <template #default="{ row }">{{ formatCount(row.count) }}</template>
          </el-table-column>
          <el-table-column prop="out_count" label="已出库" width="90" align="right">
            <template #default="{ row }">{{ formatCount(row.out_count) }}</template>
          </el-table-column>
          <el-table-column prop="price" label="单价" width="100" align="right">
            <template #default="{ row }">￥{{ formatAmount(row.price) }}</template>
          </el-table-column>
          <el-table-column prop="total_price" label="小计" width="110" align="right">
            <template #default="{ row }">￥{{ formatAmount(row.total_price) }}</template>
          </el-table-column>
        </el-table>
        <div class="section-title">发货回传</div>
        <el-table :data="detail.shipments || []" border size="small">
          <el-table-column prop="out_no" label="出库单号" min-width="160" />
          <el-table-column prop="warehouse_name" label="发货仓库" min-width="120" />
          <el-table-column prop="count" label="发货数量" width="110" />
          <el-table-column prop="stock_after" label="发货后库存" width="120"><template #default="{ row }">{{ row.stock_after ?? '-' }}</template></el-table-column>
          <el-table-column prop="express_no" label="物流单号" min-width="160" />
          <el-table-column prop="shipped_at" label="发货时间" min-width="170" />
        </el-table>
      </template>

      <el-empty v-else-if="!loading" description="未获取到订单详情" />
    </div>
  </el-drawer>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { getOrderDetail } from '@/api/order'
import { ORDER_STEPS, orderStatusType } from '@/utils/constants'
import { formatAmount, formatCount } from '@/utils/format'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  orderId: { type: [Number, String], default: null }
})

const emit = defineEmits(['update:modelValue'])

const loading = ref(false)
const detail = ref(null)

const orderStatusText = computed(() => detail.value?.status_text || '-')

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
      detail.value = await getOrderDetail(id)
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

.sku-image {
  width: 44px;
  height: 44px;
  border-radius: 4px;
}
</style>
