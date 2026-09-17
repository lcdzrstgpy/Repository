<template>
  <el-drawer
    :model-value="modelValue"
    :title="canClaim ? '订单详情 · 接单并关联货号' : '订单详情 · 货号处理'"
    size="820px"
    :destroy-on-close="true"
    @update:model-value="(val) => emit('update:modelValue', val)"
  >
    <div v-loading="loading">
      <template v-if="detail">
        <!-- 基础信息 -->
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="订单号">{{ detail.no }}</el-descriptions-item>
          <el-descriptions-item label="订单状态">
            <el-tag :type="orderStatusType(detail.status)" size="small">
              {{ detail.status_text || orderStatusLabel(detail.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="关联进度">
            <el-tag :type="allBound ? 'success' : 'warning'" size="small">
              已关联 {{ boundCount }} / {{ itemCount }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="商品行数">{{ itemCount }}</el-descriptions-item>
          <el-descriptions-item label="总数量">{{ formatCount(detail.total_count) }}</el-descriptions-item>
          <el-descriptions-item label="预计总成本">
            ￥{{ formatAmount(detail.total_price) }}
          </el-descriptions-item>
          <el-descriptions-item label="下单人">{{ detail.created_by_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="接单人">{{ detail.claimed_by_name || '未接单' }}</el-descriptions-item>
          <el-descriptions-item label="指派仓库">{{ detail.warehouse_name || '未指派' }}</el-descriptions-item>
          <el-descriptions-item label="下单时间">{{ detail.created_at || '-' }}</el-descriptions-item>
          <el-descriptions-item label="备注" :span="2">{{ detail.remark || '-' }}</el-descriptions-item>
        </el-descriptions>

        <!-- 未关联提示 -->
        <el-alert
          v-if="detail.status === 20 && !allBound"
          class="bound-alert"
          type="warning"
          :closable="false"
          show-icon
          :title="`还有 ${unboundCount} 个商品未关联货号，全部关联后将自动提交运营确认数量`"
        />

        <!-- 数量待确认提示：等待运营确认后自动进入备货 -->
        <el-alert
          v-if="detail.status === 25"
          class="bound-alert"
          type="info"
          :closable="false"
          show-icon
          title="已提交运营确认数量，等待确认后自动进入备货"
        />

        <!-- 货号处理区 -->
        <div class="section-title">货号处理</div>
        <el-table :data="detail.items || []" border size="small">
          <el-table-column type="index" label="序号" width="60" align="center" />
          <el-table-column prop="product_name" label="商品名" min-width="130" show-overflow-tooltip />
          <el-table-column label="运营录入货号 / 新品" min-width="150">
            <template #default="{ row }">
              <template v-if="row.sku_code">{{ row.sku_code }}</template>
              <el-tag v-else-if="row.is_new === 1" type="warning" size="small">新品</el-tag>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="关联结果" min-width="170">
            <template #default="{ row }">
              <template v-if="row.sku_id">
                <div>{{ row.sku_code_bound || '-' }}</div>
                <div class="sub-text">{{ row.spec || '无规格' }}</div>
              </template>
              <el-tag v-else type="danger" size="small">待关联</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="count" label="数量" width="80" align="right">
            <template #default="{ row }">{{ formatCount(row.count) }}</template>
          </el-table-column>
          <el-table-column label="预计成本" width="100" align="right">
            <template #default="{ row }">￥{{ formatAmount(row.expect_price) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="130" align="center">
            <template #default="{ row }">
              <!-- 已关联的行锁定，不显示任何操作按钮 -->
              <template v-if="row.sku_id">
                <span class="text-muted">已关联</span>
              </template>
              <template v-else-if="detail.status === 20">
                <!-- 运营填了货号：按货号关联已有 SKU -->
                <el-button v-if="row.sku_code" link type="primary" @click="handleBind(row)">
                  关联
                </el-button>
                <!-- 勾了新品：新建货号 -->
                <el-button v-else-if="row.is_new === 1" link type="primary" @click="openNewSku(row)">
                  新建货号
                </el-button>
                <span v-else class="text-muted">-</span>
              </template>
              <span v-else class="text-muted">待接单</span>
            </template>
          </el-table-column>
        </el-table>
      </template>

      <el-empty v-else-if="!loading" description="未获取到订单详情" />
    </div>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">关闭</el-button>
      <el-button v-if="canClaim" type="primary" :loading="claiming" @click="openClaim">
        接单并关联货号
      </el-button>
    </template>

    <!-- 新建货号弹窗 -->
    <el-dialog v-model="newSkuVisible" title="自动生成货号" width="520px" append-to-body>
      <el-descriptions :column="1" border size="small" style="margin-bottom: 16px">
        <el-descriptions-item label="商品名">{{ newSkuRow?.product_name }}</el-descriptions-item>
        <el-descriptions-item label="数量">
          {{ formatCount(newSkuRow?.count) }}
        </el-descriptions-item>
      </el-descriptions>

      <el-form ref="newSkuFormRef" :model="newSkuForm" :rules="newSkuRules" label-width="90px">
        <el-form-item label="一级分类" prop="category_level1">
          <el-input v-model="newSkuForm.category_level1" placeholder="如：杯子" maxlength="100" />
        </el-form-item>
        <el-form-item label="二级分类">
          <el-input v-model="newSkuForm.category_level2" placeholder="如：玻璃杯（选填）" maxlength="100" />
        </el-form-item>
        <el-form-item label="三级分类">
          <el-input v-model="newSkuForm.category_level3" placeholder="如：400ml（选填）" maxlength="100" />
        </el-form-item>
        <el-form-item label="规格" prop="spec">
          <el-input v-model="newSkuForm.spec" placeholder="选填，如：黑色/大号" maxlength="200" />
        </el-form-item>
        <el-form-item label="售价（元）" prop="price">
          <el-input-number
            v-model="newSkuForm.price"
            :min="0"
            :precision="2"
            :step="1"
            controls-position="right"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="newSkuVisible = false">取消</el-button>
        <el-button type="primary" :loading="binding" @click="handleCreateSku">生成货号并关联</el-button>
      </template>
    </el-dialog>

    <!-- 接单：在详情抽屉内完成仓库选择，无需返回列表 -->
    <el-dialog
      v-model="claimVisible"
      title="接单并关联货号"
      width="460px"
      append-to-body
      @closed="handleClaimDialogClosed"
    >
      <el-form ref="claimFormRef" :model="claimForm" :rules="claimRules" label-width="80px">
        <el-form-item label="仓库" prop="warehouse_id">
          <el-select
            v-model="claimForm.warehouse_id"
            placeholder="请选择接单仓库"
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
      </el-form>

      <template #footer>
        <el-button @click="claimVisible = false">取消</el-button>
        <el-button type="primary" :loading="claiming" @click="handleClaim">接单并继续关联</el-button>
      </template>
    </el-dialog>
  </el-drawer>
</template>

<script setup>
import { ref, reactive, computed, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getOrderDetail } from '@/api/order'
import { getWarehouseOptions } from '@/api/basic'
import { bindSku, claimOrder } from '@/api/warehouse'
import { orderStatusType, orderStatusLabel } from '@/utils/constants'
import { formatAmount, formatCount } from '@/utils/format'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  orderId: { type: [Number, String], default: null }
})

const emit = defineEmits(['update:modelValue', 'updated'])

const loading = ref(false)
const binding = ref(false)
const claiming = ref(false)
const detail = ref(null)

const newSkuVisible = ref(false)
const newSkuFormRef = ref(null)
const newSkuRow = ref(null)
const newSkuForm = ref({ category_level1: '', category_level2: '', category_level3: '', spec: '', price: 0 })

const newSkuRules = {
  category_level1: [{ required: true, message: '请输入一级分类', trigger: 'blur' }]
}

const claimVisible = ref(false)
const claimFormRef = ref(null)
const warehouseOptions = ref([])
const claimForm = reactive({ warehouse_id: null })
const claimRules = {
  warehouse_id: [{ required: true, message: '请选择接单仓库', trigger: 'change' }]
}

const itemCount = computed(() => (detail.value?.items || []).length)
const canClaim = computed(() => detail.value?.status === 10)
/** 已关联行数：判断是否已关联看 sku_id 是否为空 */
const boundCount = computed(() => (detail.value?.items || []).filter((row) => !!row.sku_id).length)
const unboundCount = computed(() => itemCount.value - boundCount.value)
/** 以后端返回的 all_sku_bound 为准，缺失时按行数兜底 */
const allBound = computed(() =>
  typeof detail.value?.all_sku_bound === 'boolean'
    ? detail.value.all_sku_bound
    : itemCount.value > 0 && unboundCount.value === 0
)

async function load() {
  if (!props.orderId) return
  loading.value = true
  try {
    detail.value = await getOrderDetail(props.orderId)
  } finally {
    loading.value = false
  }
}

/** 详情抽屉内接单：成功后保持抽屉打开，直接进入货号处理。 */
async function openClaim() {
  if (!warehouseOptions.value.length) {
    warehouseOptions.value = (await getWarehouseOptions()) || []
  }
  claimForm.warehouse_id = null
  claimVisible.value = true
  nextTick(() => claimFormRef.value?.clearValidate())
}

function handleClaimDialogClosed() {
  claimFormRef.value?.clearValidate()
}

async function handleClaim() {
  const valid = await claimFormRef.value.validate().catch(() => false)
  if (!valid) return

  claiming.value = true
  try {
    await claimOrder(detail.value.id, claimForm.warehouse_id)
    claimVisible.value = false
    await load()
    ElMessage.success('接单成功，请在当前详情中完成货号关联')
    emit('updated')
  } finally {
    claiming.value = false
  }
}

/** 关联成功后刷新详情并通知列表刷新 */
async function reloadAfterBind(message) {
  await load()
  // 绑完所有货号后后端会自动把订单流转到「数量待确认」(25)
  ElMessage.success(
    detail.value?.status === 25
      ? '全部货号已关联，订单已提交运营确认数量'
      : message
  )
  emit('updated')
}

/** 关联已有货号：sku_code 模式 */
async function handleBind(row) {
  try {
    await ElMessageBox.confirm(
      `确认将货号「${row.sku_code}」关联到商品「${row.product_name}」吗？关联后不可修改。`,
      '关联货号',
      { type: 'warning', confirmButtonText: '确认关联', cancelButtonText: '取消' }
    )
  } catch (e) {
    return
  }

  binding.value = true
  try {
    await bindSku(detail.value.id, { items: [{ item_id: row.id, sku_code: row.sku_code }] })
    await reloadAfterBind('货号关联成功')
  } finally {
    binding.value = false
  }
}

/** 打开新建货号弹窗：售价默认取运营填写的预计成本 */
function openNewSku(row) {
  newSkuRow.value = row
  newSkuForm.value = {
    category_level1: '',
    category_level2: '',
    category_level3: '',
    spec: '',
    price: Number(row.expect_price) || 0
  }
  newSkuVisible.value = true
  nextTick(() => newSkuFormRef.value?.clearValidate())
}

/** 新建货号并关联：new_sku 模式 */
async function handleCreateSku() {
  const valid = await newSkuFormRef.value.validate().catch(() => false)
  if (!valid) return

  binding.value = true
  try {
    await bindSku(detail.value.id, {
      items: [
        {
          item_id: newSkuRow.value.id,
          new_sku: {
            product_name: newSkuRow.value.product_name,
            category_level1: newSkuForm.value.category_level1.trim(),
            category_level2: newSkuForm.value.category_level2.trim() || null,
            category_level3: newSkuForm.value.category_level3.trim() || null,
            spec: newSkuForm.value.spec,
            price: Number(newSkuForm.value.price) || 0
          }
        }
      ]
    })
    newSkuVisible.value = false
    await reloadAfterBind('货号新建并关联成功')
  } finally {
    binding.value = false
  }
}

/** 打开抽屉时拉取详情 */
watch(
  () => [props.modelValue, props.orderId],
  ([visible, id]) => {
    if (!visible || !id) return
    detail.value = null
    load()
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

.bound-alert {
  margin-top: 16px;
}

.sub-text {
  color: #909399;
  font-size: 12px;
}

.text-muted {
  color: #909399;
  font-size: 13px;
}
</style>
