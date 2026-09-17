<template>
  <div class="page-container">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>新建采购单</span>
          <el-button @click="router.push('/warehouse/purchase')">
            <el-icon><Back /></el-icon>
            <span style="margin-left: 4px">返回采购单列表</span>
          </el-button>
        </div>
      </template>

      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="10">
            <el-form-item label="供应商" prop="supplier_id">
              <el-select
                v-model="form.supplier_id"
                placeholder="请选择供应商"
                filterable
                clearable
                style="width: 100%"
              >
                <el-option
                  v-for="item in supplierOptions"
                  :key="item.id"
                  :label="item.name"
                  :value="item.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="14">
            <el-form-item label="期望到货日期">
              <el-date-picker
                v-model="form.expect_date"
                type="date"
                placeholder="请选择期望到货日期"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="10">
            <el-form-item label="关联销售订单">
              <el-select
                v-model="form.sales_order_id"
                placeholder="从待备货订单中选择（选填）"
                filterable
                clearable
                style="width: 100%"
              >
                <el-option
                  v-for="item in salesOrderOptions"
                  :key="item.id"
                  :label="item.no"
                  :value="item.id"
                >
                  <span>{{ item.no }} · {{ formatCount(item.item_count) }} 行商品</span>
                  <span class="option-extra">{{ item.status_text || orderStatusLabel(item.status) }}</span>
                </el-option>
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="14">
            <el-form-item label="备注">
              <el-input
                v-model="form.remark"
                placeholder="选填，如：备货缺货补采"
                maxlength="500"
                show-word-limit
              />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <div class="table-toolbar">
        <span class="section-title">采购明细</span>
        <el-button type="primary" plain @click="addItem">
          <el-icon><Plus /></el-icon>
          <span style="margin-left: 4px">添加明细</span>
        </el-button>
      </div>

      <el-table :data="form.items" border>
        <el-table-column type="index" label="序号" width="60" align="center" />
        <el-table-column label="货号" min-width="230">
          <template #default="{ row }">
            <el-select
              v-model="row.sku_id"
              placeholder="请选择货号"
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
        <el-table-column label="采购数量" width="140">
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
        <el-table-column label="采购单价（元）" width="170">
          <template #default="{ row }">
            <el-input-number
              v-model="row.price"
              :min="0"
              :precision="2"
              :step="1"
              controls-position="right"
              style="width: 100%"
            />
            <!-- 关联销售订单时，提示该行运营填写的预计成本（采购价上限） -->
            <div
              v-if="priceCap(row) !== null"
              class="cap-tip"
              :class="{ 'cap-tip-over': isOverCap(row) }"
            >
              价格上限 ￥{{ formatAmount(priceCap(row)) }}
              <span v-if="isOverCap(row)">（已超出）</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="小计（元）" width="120" align="right">
          <template #default="{ row }">￥{{ formatAmount(itemTotal(row)) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="80" align="center">
          <template #default="{ $index }">
            <el-button
              link
              type="danger"
              :disabled="form.items.length === 1"
              @click="removeItem($index)"
            >
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
        <el-button @click="router.push('/warehouse/purchase')">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">提交采购单</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createPurchaseOrder } from '@/api/purchase'
import { getOrderList, getOrderDetail } from '@/api/order'
import { getPartnerOptions, getSkuOptions } from '@/api/basic'
import { orderStatusLabel } from '@/utils/constants'
import { formatAmount, formatCount } from '@/utils/format'

/** 待备货订单：已接单 / 数量待确认 / 备货中（契约 10.1：备货缺货时采购） */
const STOCK_NEEDED_STATUS = [20, 25, 30]

const router = useRouter()

const formRef = ref(null)
const submitting = ref(false)
const supplierOptions = ref([])
const skuOptions = ref([])
const salesOrderOptions = ref([])
/** 采购价上限：{ [sku_id]: expect_price }，取自所关联销售订单明细的预计成本 */
const priceCapMap = ref({})

const form = reactive({
  supplier_id: null,
  sales_order_id: null,
  expect_date: '',
  remark: '',
  // 明细行：sku_id 关联 SKU，count 采购数量，price 采购单价
  items: [createEmptyItem()]
})

const rules = {
  supplier_id: [{ required: true, message: '请选择供应商', trigger: 'change' }]
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

/** 取某行的采购价上限；未关联销售订单或该 SKU 无上限时返回 null */
function priceCap(row) {
  if (!row.sku_id) return null
  const cap = priceCapMap.value[row.sku_id]
  return cap === undefined || cap === null ? null : Number(cap)
}

/** 该行采购单价是否已超出运营填写的预计成本 */
function isOverCap(row) {
  const cap = priceCap(row)
  if (cap === null) return false
  return Number(row.price) > cap
}

/** 关联销售订单变化时，拉取订单详情构建价格上限表 */
async function loadPriceCaps(orderId) {
  if (!orderId) {
    priceCapMap.value = {}
    return
  }
  try {
    const detail = await getOrderDetail(orderId)
    const map = {}
    ;(detail?.items || []).forEach((item) => {
      // 仅已关联货号（有 sku_id）的行才有明确的价格上限
      if (item.sku_id && item.expect_price !== null && item.expect_price !== undefined) {
        map[item.sku_id] = Number(item.expect_price)
      }
    })
    priceCapMap.value = map
  } catch (e) {
    // 详情拉取失败时清空上限，不阻塞采购单填写
    priceCapMap.value = {}
  }
}

watch(() => form.sales_order_id, loadPriceCaps)

/** 选择 SKU 后自动带出参考单价 */
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
    ElMessage.warning('请至少添加一条采购明细')
    return false
  }
  for (let i = 0; i < form.items.length; i += 1) {
    const row = form.items[i]
    if (!row.sku_id) {
      ElMessage.warning(`第 ${i + 1} 行未选择货号`)
      return false
    }
    if (!row.count || Number(row.count) <= 0) {
      ElMessage.warning(`第 ${i + 1} 行采购数量必须大于 0`)
      return false
    }
    if (row.price === null || row.price === undefined || Number(row.price) < 0) {
      ElMessage.warning(`第 ${i + 1} 行采购单价不合法`)
      return false
    }
    // 关联销售订单时，采购价不得高于运营填写的预计成本（契约 17.3）
    const cap = priceCap(row)
    if (cap !== null && Number(row.price) > cap) {
      ElMessage.warning(
        `第 ${i + 1} 行采购单价 ${formatAmount(row.price)} 高于运营填写的预计成本 ${formatAmount(cap)}`
      )
      return false
    }
  }

  // 同一 SKU 不允许重复出现
  const skuIds = form.items.map((row) => row.sku_id)
  if (new Set(skuIds).size !== skuIds.length) {
    ElMessage.warning('同一货号不能重复添加，请合并数量')
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
    await createPurchaseOrder({
      supplier_id: form.supplier_id,
      sales_order_id: form.sales_order_id || null,
      expect_date: form.expect_date || null,
      remark: form.remark,
      items: form.items.map((row) => ({
        sku_id: row.sku_id,
        count: Number(row.count),
        price: Number(row.price)
      }))
    })
    ElMessage.success('采购单创建成功，等待审批')
    router.push('/warehouse/purchase')
  } finally {
    submitting.value = false
  }
}

/** 加载供应商、SKU 与待备货销售订单 */
async function loadOptions() {
  const [suppliers, skus] = await Promise.all([getPartnerOptions(2), getSkuOptions()])
  supplierOptions.value = suppliers || []
  skuOptions.value = skus || []

  // 待备货订单分三次拉取（已接单 / 数量待确认 / 备货中）后合并
  const results = await Promise.all(
    STOCK_NEEDED_STATUS.map((status) => getOrderList({ page: 1, page_size: 100, status }))
  )
  salesOrderOptions.value = results.flatMap((data) => data?.list || [])
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

.option-price,
.option-extra {
  float: right;
  color: #909399;
  font-size: 12px;
}

.cap-tip {
  margin-top: 2px;
  font-size: 12px;
  line-height: 1.4;
  color: #909399;
}

.cap-tip-over {
  color: #f56c6c;
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
