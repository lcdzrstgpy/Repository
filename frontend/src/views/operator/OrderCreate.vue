<template>
  <div class="page-container">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>新建订单</span>
          <el-button @click="router.push('/operator/orders')">
            <el-icon><Back /></el-icon>
            <span style="margin-left: 4px">返回订单列表</span>
          </el-button>
        </div>
      </template>

      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-row :gutter="16">
          <el-col :span="10">
            <el-form-item label="客户" prop="customer_id">
              <el-select
                v-model="form.customer_id"
                placeholder="请选择客户"
                filterable
                clearable
                style="width: 100%"
              >
                <el-option
                  v-for="item in customerOptions"
                  :key="item.id"
                  :label="item.name"
                  :value="item.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="14">
            <el-form-item label="备注">
              <el-input v-model="form.remark" placeholder="选填，如：加急" maxlength="500" show-word-limit />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <div class="table-toolbar">
        <span class="section-title">订单明细</span>
        <el-button type="primary" plain @click="addItem">
          <el-icon><Plus /></el-icon>
          <span style="margin-left: 4px">添加明细</span>
        </el-button>
      </div>

      <el-table :data="form.items" border>
        <el-table-column type="index" label="序号" width="60" align="center" />
        <el-table-column label="SKU" min-width="230">
          <template #default="{ row }">
            <el-select
              v-model="row.sku_id"
              placeholder="请选择 SKU"
              filterable
              style="width: 100%"
              @change="(val) => handleSkuChange(row, val)"
            >
              <el-option
                v-for="sku in skuOptions"
                :key="sku.id"
                :label="`${sku.sku_code} ${sku.name}`"
                :value="sku.id"
              >
                <span>{{ sku.sku_code }} · {{ sku.name }}</span>
                <span class="option-price">￥{{ formatAmount(sku.price) }}</span>
              </el-option>
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="商品名称" min-width="140">
          <template #default="{ row }">{{ findSku(row.sku_id)?.name || '-' }}</template>
        </el-table-column>
        <el-table-column label="规格" min-width="120">
          <template #default="{ row }">{{ findSku(row.sku_id)?.spec || '-' }}</template>
        </el-table-column>
        <el-table-column label="数量" width="140">
          <template #default="{ row }">
            <el-input-number
              v-model="row.count"
              :min="0.01"
              :precision="2"
              :step="1"
              controls-position="right"
              style="width: 100%"
            />
          </template>
        </el-table-column>
        <el-table-column label="单价（元）" width="150">
          <template #default="{ row }">
            <el-input-number
              v-model="row.price"
              :min="0"
              :precision="2"
              :step="1"
              controls-position="right"
              style="width: 100%"
            />
          </template>
        </el-table-column>
        <el-table-column label="小计（元）" width="120" align="right">
          <template #default="{ row }">￥{{ formatAmount(itemTotal(row)) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="80" align="center">
          <template #default="{ $index }">
            <el-button link type="danger" :disabled="form.items.length === 1" @click="removeItem($index)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 合计 -->
      <div class="summary-bar">
        <span>合计数量：<b>{{ formatCount(totalCount) }}</b></span>
        <span>合计金额：<b class="amount">￥{{ formatAmount(totalPrice) }}</b></span>
      </div>

      <div class="footer-actions">
        <el-button @click="router.push('/operator/orders')">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">提交订单</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createOrder } from '@/api/order'
import { getPartnerOptions, getSkuOptions } from '@/api/basic'
import { formatAmount, formatCount } from '@/utils/format'

const router = useRouter()

const formRef = ref(null)
const submitting = ref(false)
const customerOptions = ref([])
const skuOptions = ref([])

const form = reactive({
  customer_id: null,
  remark: '',
  // 明细行：sku_id 关联 SKU，count 数量，price 单价
  items: [createEmptyItem()]
})

const rules = {
  customer_id: [{ required: true, message: '请选择客户', trigger: 'change' }]
}

function createEmptyItem() {
  return { sku_id: null, count: 1, price: 0 }
}

/** 根据 sku_id 找到 SKU 选项 */
function findSku(skuId) {
  return skuOptions.value.find((item) => item.id === skuId)
}

/** 明细行小计 */
function itemTotal(row) {
  const count = Number(row.count) || 0
  const price = Number(row.price) || 0
  return count * price
}

/** 总数量 */
const totalCount = computed(() =>
  form.items.reduce((sum, row) => sum + (Number(row.count) || 0), 0)
)

/** 总金额 */
const totalPrice = computed(() => form.items.reduce((sum, row) => sum + itemTotal(row), 0))

/** 选择 SKU 后自动带出单价 */
function handleSkuChange(row, skuId) {
  const sku = findSku(skuId)
  if (sku) {
    row.price = Number(sku.price) || 0
  }
}

function addItem() {
  form.items.push(createEmptyItem())
}

function removeItem(index) {
  form.items.splice(index, 1)
}

/** 校验明细行 */
function validateItems() {
  if (!form.items.length) {
    ElMessage.warning('请至少添加一条订单明细')
    return false
  }
  for (let i = 0; i < form.items.length; i += 1) {
    const row = form.items[i]
    if (!row.sku_id) {
      ElMessage.warning(`第 ${i + 1} 行未选择 SKU`)
      return false
    }
    if (!row.count || Number(row.count) <= 0) {
      ElMessage.warning(`第 ${i + 1} 行数量必须大于 0`)
      return false
    }
    if (row.price === null || row.price === undefined || Number(row.price) < 0) {
      ElMessage.warning(`第 ${i + 1} 行单价不合法`)
      return false
    }
  }

  // 同一 SKU 不允许重复出现
  const skuIds = form.items.map((row) => row.sku_id)
  if (new Set(skuIds).size !== skuIds.length) {
    ElMessage.warning('同一 SKU 不能重复添加，请合并数量')
    return false
  }
  return true
}

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  if (!validateItems()) return

  submitting.value = true
  try {
    // total_count / total_price 由后端汇总，前端不传
    await createOrder({
      customer_id: form.customer_id,
      remark: form.remark,
      items: form.items.map((row) => ({
        sku_id: row.sku_id,
        count: Number(row.count),
        price: Number(row.price)
      }))
    })
    ElMessage.success('订单创建成功，已进入订单池等待仓储接单')
    router.push('/operator/orders')
  } finally {
    submitting.value = false
  }
}

/** 加载客户与 SKU 下拉选项 */
async function loadOptions() {
  const [customers, skus] = await Promise.all([getPartnerOptions(1), getSkuOptions()])
  customerOptions.value = customers || []
  skuOptions.value = skus || []
}

onMounted(loadOptions)
</script>

<style scoped>
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  border-left: 3px solid #409eff;
  padding-left: 8px;
}

.option-price {
  float: right;
  color: #909399;
  font-size: 12px;
}

.summary-bar {
  display: flex;
  justify-content: flex-end;
  gap: 32px;
  margin-top: 16px;
  font-size: 14px;
}

.summary-bar .amount {
  color: #f56c6c;
  font-size: 18px;
}

.footer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
}
</style>
