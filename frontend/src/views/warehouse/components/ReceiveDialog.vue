<template>
  <el-dialog
    :model-value="modelValue"
    title="收货入库"
    width="820px"
    :destroy-on-close="true"
    @update:model-value="(val) => emit('update:modelValue', val)"
    @closed="handleClosed"
  >
    <div v-loading="loading">
      <el-descriptions :column="2" border size="small" style="margin-bottom: 16px">
        <el-descriptions-item label="采购单号">{{ detail?.no || '-' }}</el-descriptions-item>
        <el-descriptions-item label="供应商">{{ detail?.supplier_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="关联销售订单">
          {{ detail?.sales_order_no || '无' }}
        </el-descriptions-item>
        <el-descriptions-item label="期望到货">{{ detail?.expect_date || '-' }}</el-descriptions-item>
      </el-descriptions>

      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="入库仓库" prop="warehouse_id">
              <el-select
                v-model="form.warehouse_id"
                placeholder="请选择入库仓库"
                filterable
                style="width: 100%"
              >
                <el-option
                  v-for="item in warehouseOptions"
                  :key="item.id"
                  :label="item.name"
                  :value="item.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="入库备注">
              <el-input
                v-model="form.remark"
                placeholder="选填，如：全部到货"
                maxlength="500"
                clearable
              />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <div class="section-title">入库明细（默认填满剩余量，可修改为部分入库）</div>
      <el-table :data="rows" border size="small">
        <el-table-column type="index" label="序号" width="60" align="center" />
        <el-table-column prop="sku_code" label="SKU 编码" width="110" />
        <el-table-column prop="product_name" label="商品名称" min-width="130" show-overflow-tooltip />
        <el-table-column prop="spec" label="规格" min-width="110" show-overflow-tooltip />
        <el-table-column label="采购数量" width="90" align="right">
          <template #default="{ row }">{{ formatCount(row.count) }}</template>
        </el-table-column>
        <el-table-column label="已入库" width="90" align="right">
          <template #default="{ row }">{{ formatCount(row.in_count) }}</template>
        </el-table-column>
        <el-table-column label="剩余可入库" width="100" align="right">
          <template #default="{ row }">
            <span :class="{ 'no-remain': row.remain <= 0 }">{{ formatCount(row.remain) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="本次入库数量" width="160">
          <template #default="{ row }">
            <el-input-number
              v-model="row.receiveCount"
              :min="0"
              :max="Number(row.remain)"
              :precision="2"
              :step="1"
              :disabled="row.remain <= 0"
              controls-position="right"
              style="width: 100%"
            />
          </template>
        </el-table-column>
      </el-table>

      <div class="summary-bar">
        <span>本次合计入库数量：<b>{{ formatCount(totalReceiveCount) }}</b></span>
      </div>
    </div>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">确认入库</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getPurchaseDetail, receivePurchaseOrder } from '@/api/purchase'
import { getWarehouseOptions } from '@/api/basic'
import { formatCount } from '@/utils/format'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  orderId: { type: [Number, String], default: null }
})

const emit = defineEmits(['update:modelValue', 'success'])

const loading = ref(false)
const submitting = ref(false)
const formRef = ref(null)
const detail = ref(null)
const rows = ref([])
const warehouseOptions = ref([])

const form = reactive({
  warehouse_id: null,
  remark: ''
})

const rules = {
  warehouse_id: [{ required: true, message: '请选择入库仓库', trigger: 'change' }]
}

/** 本次合计入库数量 */
const totalReceiveCount = computed(() =>
  rows.value.reduce((sum, row) => sum + (Number(row.receiveCount) || 0), 0)
)

/** 拉取采购单详情，按明细生成入库行（默认填满剩余量） */
async function loadDetail() {
  loading.value = true
  try {
    const data = await getPurchaseDetail(props.orderId)
    detail.value = data
    rows.value = (data?.items || []).map((item) => {
      const count = Number(item.count) || 0
      const inCount = Number(item.in_count) || 0
      const remain = Math.max(0, count - inCount)
      return {
        order_item_id: item.id,
        sku_code: item.sku_code,
        product_name: item.product_name,
        spec: item.spec,
        count,
        in_count: inCount,
        remain,
        receiveCount: remain
      }
    })
  } finally {
    loading.value = false
  }
}

function handleClosed() {
  formRef.value?.clearValidate()
  rows.value = []
  detail.value = null
}

/** 校验：至少一条大于 0，且不超过剩余可入库量 */
function validateRows() {
  const valid = rows.value.filter((row) => Number(row.receiveCount) > 0)
  if (!valid.length) {
    ElMessage.warning('请至少填写一条本次入库数量')
    return false
  }
  for (let i = 0; i < rows.value.length; i += 1) {
    const row = rows.value[i]
    const value = Number(row.receiveCount) || 0
    if (value < 0) {
      ElMessage.warning(`第 ${i + 1} 行入库数量不能为负数`)
      return false
    }
    if (value > row.remain) {
      ElMessage.warning(
        `第 ${i + 1} 行「${row.sku_code}」本次入库数量不能超过剩余可入库量 ${formatCount(row.remain)}`
      )
      return false
    }
  }
  return true
}

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  if (!validateRows()) return

  submitting.value = true
  try {
    await receivePurchaseOrder(props.orderId, {
      warehouse_id: form.warehouse_id,
      remark: form.remark,
      items: rows.value
        .filter((row) => Number(row.receiveCount) > 0)
        .map((row) => ({ order_item_id: row.order_item_id, count: Number(row.receiveCount) }))
    })
    ElMessage.success('收货入库成功，库存已增加')
    emit('update:modelValue', false)
    emit('success')
  } finally {
    submitting.value = false
  }
}

/** 打开弹窗时初始化数据 */
watch(
  () => [props.modelValue, props.orderId],
  async ([visible, id]) => {
    if (!visible || !id) return
    form.warehouse_id = null
    form.remark = ''
    await loadDetail()
  },
  { immediate: true }
)

// 仓库下拉只加载一次
getWarehouseOptions().then((data) => {
  warehouseOptions.value = data || []
})
</script>

<style scoped>
.section-title {
  margin: 4px 0 12px;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  border-left: 3px solid #409eff;
  padding-left: 8px;
}

.summary-bar {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
  font-size: 14px;
}

.no-remain {
  color: #909399;
}
</style>
