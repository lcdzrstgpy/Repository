<template>
  <el-drawer
    :model-value="modelValue"
    title="采购入库单详情"
    size="720px"
    :destroy-on-close="true"
    @update:model-value="(val) => emit('update:modelValue', val)"
  >
    <div v-loading="loading">
      <template v-if="detail">
        <!-- 基础信息 -->
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="入库单号">{{ detail.no }}</el-descriptions-item>
          <el-descriptions-item label="单据状态">
            <el-tag type="success" size="small">
              {{ detail.status_text || '已完成' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="关联采购单">{{ detail.order_no || '-' }}</el-descriptions-item>
          <el-descriptions-item label="入库仓库">{{ detail.warehouse_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="总数量">{{ formatCount(detail.total_count) }}</el-descriptions-item>
          <el-descriptions-item label="总金额">
            ￥{{ formatAmount(detail.total_price) }}
          </el-descriptions-item>
          <el-descriptions-item label="制单人">{{ detail.created_by_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="入库时间">{{ detail.created_at || '-' }}</el-descriptions-item>
          <el-descriptions-item label="备注" :span="2">{{ detail.remark || '-' }}</el-descriptions-item>
        </el-descriptions>

        <!-- 明细 -->
        <div class="section-title">入库明细</div>
        <el-table
          :data="detail.items || []"
          border
          size="small"
          show-summary
          :summary-method="summaryMethod"
        >
          <el-table-column type="index" label="序号" width="60" align="center" />
          <el-table-column prop="sku_code" label="货号" width="120" />
          <el-table-column prop="product_name" label="商品名称" min-width="140" show-overflow-tooltip />
          <el-table-column prop="spec" label="规格" min-width="110" show-overflow-tooltip />
          <el-table-column prop="count" label="入库数量" width="100" align="right">
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

      <el-empty v-else-if="!loading" description="未获取到入库单详情" />
    </div>
  </el-drawer>
</template>

<script setup>
import { ref, watch } from 'vue'
import { getPurchaseInDetail } from '@/api/purchase'
import { formatAmount, formatCount } from '@/utils/format'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  inId: { type: [Number, String], default: null }
})

const emit = defineEmits(['update:modelValue'])

const loading = ref(false)
const detail = ref(null)

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
  () => [props.modelValue, props.inId],
  async ([visible, id]) => {
    if (!visible || !id) return
    loading.value = true
    detail.value = null
    try {
      detail.value = await getPurchaseInDetail(id)
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
</style>
