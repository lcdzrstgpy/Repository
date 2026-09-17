<template>
  <el-drawer
    :model-value="modelValue"
    title="出库单详情"
    size="720px"
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
          <el-descriptions-item label="出库单号">{{ detail.no }}</el-descriptions-item>
          <el-descriptions-item label="单据状态">
            <el-tag :type="outStatusType(detail.status)" size="small">
              {{ detail.status_text || outStatusLabel(detail.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="关联订单号">{{ detail.order_no || '-' }}</el-descriptions-item>
          <el-descriptions-item label="出库仓库">{{ detail.warehouse_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="总数量">{{ formatCount(detail.total_count) }}</el-descriptions-item>
          <el-descriptions-item label="总金额">
            ￥{{ formatAmount(detail.total_price) }}
          </el-descriptions-item>
          <el-descriptions-item label="物流单号">{{ detail.express_no || '-' }}</el-descriptions-item>
          <el-descriptions-item label="制单人">{{ detail.created_by_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ detail.created_at || '-' }}</el-descriptions-item>
          <el-descriptions-item label="备注">{{ detail.remark || '-' }}</el-descriptions-item>
        </el-descriptions>

        <!-- 已作废提示 -->
        <el-alert
          v-if="detail.status === 90"
          class="void-alert"
          type="error"
          :closable="false"
          show-icon
          title="该出库单已作废，出库库存已回滚，关联订单状态已回退"
        />

        <!-- 明细 -->
        <div class="section-title">出库明细</div>
        <el-table :data="detail.items || []" border size="small" show-summary :summary-method="summaryMethod">
          <el-table-column type="index" label="序号" width="60" align="center" />
          <el-table-column prop="sku_code" label="SKU 编码" width="120" />
          <el-table-column prop="product_name" label="商品名称" min-width="140" show-overflow-tooltip />
          <el-table-column prop="spec" label="规格" min-width="110" show-overflow-tooltip />
          <el-table-column prop="count" label="数量" width="90" align="right">
            <template #default="{ row }">{{ formatCount(row.count) }}</template>
          </el-table-column>
          <el-table-column prop="price" label="单价" width="100" align="right">
            <template #default="{ row }">￥{{ formatAmount(row.price) }}</template>
          </el-table-column>
          <el-table-column prop="total_price" label="小计" width="110" align="right">
            <template #default="{ row }">￥{{ formatAmount(row.total_price) }}</template>
          </el-table-column>
        </el-table>
      </template>

      <el-empty v-else-if="!loading" description="未获取到出库单详情" />
    </div>
  </el-drawer>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { getOutDetail } from '@/api/stock'
import { outStatusType, outStatusLabel } from '@/utils/constants'
import { formatAmount, formatCount } from '@/utils/format'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  outId: { type: [Number, String], default: null }
})

const emit = defineEmits(['update:modelValue'])

const router = useRouter()

const loading = ref(false)
const detail = ref(null)

/** 打印出库单：新标签页打开独立打印页（契约 13） */
function handlePrint() {
  if (!props.outId) return
  const { href } = router.resolve({ path: `/print/sales-out/${props.outId}` })
  window.open(href, '_blank')
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
  () => [props.modelValue, props.outId],
  async ([visible, id]) => {
    if (!visible || !id) return
    loading.value = true
    detail.value = null
    try {
      detail.value = await getOutDetail(id)
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

.void-alert {
  margin-top: 16px;
}
</style>
