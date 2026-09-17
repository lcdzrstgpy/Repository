<template>
  <div class="page-container">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>新建移库单</span>
          <el-button @click="router.push('/warehouse/transfers')">
            <el-icon><Back /></el-icon>
            <span style="margin-left: 4px">返回移库单列表</span>
          </el-button>
        </div>
      </template>

      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="10">
            <el-form-item label="出库仓库" prop="from_warehouse_id">
              <el-select
                v-model="form.from_warehouse_id"
                placeholder="请选择出库仓库"
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
          <el-col :span="10">
            <el-form-item label="入库仓库" prop="to_warehouse_id">
              <el-select
                v-model="form.to_warehouse_id"
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
        </el-row>

        <el-form-item label="备注">
          <el-input
            v-model="form.remark"
            placeholder="选填，如：补货到备用仓"
            maxlength="500"
            show-word-limit
          />
        </el-form-item>
      </el-form>

      <div class="table-toolbar">
        <span class="section-title">移库明细</span>
        <el-button type="primary" plain @click="addItem">
          <el-icon><Plus /></el-icon>
          <span style="margin-left: 4px">添加明细</span>
        </el-button>
      </div>

      <el-table :data="form.items" border>
        <el-table-column type="index" label="序号" width="60" align="center" />
        <el-table-column label="SKU" min-width="240">
          <template #default="{ row }">
            <el-select v-model="row.sku_id" placeholder="请选择 SKU" filterable style="width: 100%">
              <el-option
                v-for="sku in skuOptions"
                :key="sku.id"
                :label="`${sku.sku_code} ${sku.name}`"
                :value="sku.id"
              >
                <span>{{ sku.sku_code }} · {{ sku.name }}</span>
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
        <el-table-column label="移库数量" width="160">
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

      <div class="summary-bar">
        <span>合计移库数量：<b>{{ formatCount(totalCount) }}</b></span>
      </div>

      <div class="footer-actions">
        <el-button @click="router.push('/warehouse/transfers')">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">提交移库单</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createTransfer } from '@/api/ops'
import { getSkuOptions, getWarehouseOptions } from '@/api/basic'
import { formatCount } from '@/utils/format'

const router = useRouter()

const formRef = ref(null)
const submitting = ref(false)
const warehouseOptions = ref([])
const skuOptions = ref([])

const form = reactive({
  from_warehouse_id: null,
  to_warehouse_id: null,
  remark: '',
  // 明细行：sku_id 关联 SKU，count 移库数量
  items: [createEmptyItem()]
})

const rules = {
  from_warehouse_id: [{ required: true, message: '请选择出库仓库', trigger: 'change' }],
  to_warehouse_id: [
    { required: true, message: '请选择入库仓库', trigger: 'change' },
    {
      // 契约 16.3 校验 1：出入库仓不能相同
      validator: (rule, value, callback) => {
        if (value && value === form.from_warehouse_id) {
          callback(new Error('不能移库到同一个仓库'))
          return
        }
        callback()
      },
      trigger: 'change'
    }
  ]
}

function createEmptyItem() {
  return { sku_id: null, count: 1 }
}

/** 根据 sku_id 找到 SKU 选项 */
function findSku(skuId) {
  return skuOptions.value.find((item) => item.id === skuId)
}

/** 合计移库数量 */
const totalCount = computed(() =>
  form.items.reduce((sum, row) => sum + (Number(row.count) || 0), 0)
)

function addItem() {
  form.items.push(createEmptyItem())
}

function removeItem(index) {
  form.items.splice(index, 1)
}

/** 校验明细行：非空、数量 > 0、同一 SKU 不重复 */
function validateItems() {
  if (!form.items.length) {
    ElMessage.warning('请至少添加一条移库明细')
    return false
  }
  for (let i = 0; i < form.items.length; i += 1) {
    const row = form.items[i]
    if (!row.sku_id) {
      ElMessage.warning(`第 ${i + 1} 行未选择 SKU`)
      return false
    }
    if (!row.count || Number(row.count) <= 0) {
      ElMessage.warning(`第 ${i + 1} 行移库数量必须大于 0`)
      return false
    }
  }

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
    // total_count 由后端按明细汇总，前端不传
    await createTransfer({
      from_warehouse_id: form.from_warehouse_id,
      to_warehouse_id: form.to_warehouse_id,
      remark: form.remark,
      items: form.items.map((row) => ({
        sku_id: row.sku_id,
        count: Number(row.count)
      }))
    })
    ElMessage.success('移库单创建成功，请到列表执行移库')
    router.push('/warehouse/transfers')
  } finally {
    submitting.value = false
  }
}

/** 加载仓库与 SKU 下拉数据 */
async function loadOptions() {
  const [warehouses, skus] = await Promise.all([getWarehouseOptions(), getSkuOptions()])
  warehouseOptions.value = warehouses || []
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

.summary-bar {
  display: flex;
  justify-content: flex-end;
  gap: 32px;
  margin-top: 16px;
  font-size: 14px;
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
