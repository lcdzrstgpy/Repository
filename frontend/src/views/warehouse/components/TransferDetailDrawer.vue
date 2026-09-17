<template>
  <el-drawer
    :model-value="modelValue"
    title="移库单详情"
    size="720px"
    :destroy-on-close="true"
    @update:model-value="(val) => emit('update:modelValue', val)"
  >
    <div v-loading="loading">
      <template v-if="detail">
        <!-- 基础信息 -->
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="移库单号">{{ detail.no }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="transferStatusType(detail.status)" size="small">
              {{ detail.status_text || transferStatusLabel(detail.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="出库仓库">
            {{ detail.from_warehouse_name || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="入库仓库">
            {{ detail.to_warehouse_name || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="合计数量">
            {{ formatCount(detail.total_count) }}
          </el-descriptions-item>
          <el-descriptions-item label="制单人">{{ detail.created_by_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ detail.created_at || '-' }}</el-descriptions-item>
          <el-descriptions-item label="完成时间">{{ detail.finished_at || '-' }}</el-descriptions-item>
          <el-descriptions-item label="备注" :span="2">{{ detail.remark || '-' }}</el-descriptions-item>
        </el-descriptions>

        <!-- 已作废提示 -->
        <el-alert
          v-if="detail.status === 90"
          class="cancel-alert"
          type="error"
          :closable="false"
          show-icon
          title="该移库单已作废，未产生库存变动"
        />

        <!-- 明细 -->
        <div class="section-title">移库明细</div>
        <el-table :data="detail.items || []" border size="small" show-summary :summary-method="summaryMethod">
          <el-table-column type="index" label="序号" width="60" align="center" />
          <el-table-column prop="sku_code" label="SKU 编码" width="120" />
          <el-table-column prop="product_name" label="商品名称" min-width="140" show-overflow-tooltip />
          <el-table-column prop="spec" label="规格" min-width="120" show-overflow-tooltip />
          <el-table-column prop="count" label="移库数量" width="110" align="right">
            <template #default="{ row }">{{ formatCount(row.count) }}</template>
          </el-table-column>
        </el-table>
      </template>

      <el-empty v-else-if="!loading" description="未获取到移库单详情" />
    </div>
  </el-drawer>
</template>

<script setup>
import { ref, watch } from 'vue'
import { getTransferDetail } from '@/api/ops'
import { transferStatusType, transferStatusLabel } from '@/utils/constants'
import { formatCount } from '@/utils/format'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  transferId: { type: [Number, String], default: null }
})

const emit = defineEmits(['update:modelValue'])

const loading = ref(false)
const detail = ref(null)

/** 明细表合计行 */
function summaryMethod({ columns }) {
  return columns.map((column, index) => {
    if (index === 0) return '合计'
    if (column.property === 'count') return formatCount(detail.value?.total_count)
    return ''
  })
}

/** 打开抽屉时拉取详情 */
watch(
  () => [props.modelValue, props.transferId],
  async ([visible, id]) => {
    if (!visible || !id) return
    loading.value = true
    detail.value = null
    try {
      detail.value = await getTransferDetail(id)
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

.cancel-alert {
  margin-top: 16px;
}
</style>
