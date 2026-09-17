<template>
  <div class="page-container">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>新建盘点单</span>
          <el-button @click="router.push('/warehouse/stock-takes')">
            <el-icon><Back /></el-icon>
            <span style="margin-left: 4px">返回盘点单列表</span>
          </el-button>
        </div>
      </template>

      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="10">
            <el-form-item label="盘点仓库" prop="warehouse_id">
              <el-select
                v-model="form.warehouse_id"
                placeholder="请选择盘点仓库"
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

        <el-form-item label="盘点 SKU">
          <el-select
            v-model="form.sku_ids"
            multiple
            filterable
            clearable
            collapse-tags
            collapse-tags-tooltip
            placeholder="不选则盘点该仓库全部有库存的 SKU"
            style="width: 100%"
          >
            <el-option
              v-for="sku in skuOptions"
              :key="sku.id"
              :label="`${sku.sku_code} ${sku.name}`"
              :value="sku.id"
            >
              <span>{{ sku.sku_code }} · {{ sku.name }}</span>
              <span class="option-extra">{{ sku.spec || '-' }}</span>
            </el-option>
          </el-select>
          <div class="form-tip">
            不选任何 SKU 时，将对该仓库所有已有库存记录的 SKU 建单（整仓盘点）。
          </div>
        </el-form-item>

        <el-form-item label="备注">
          <el-input
            v-model="form.remark"
            type="textarea"
            :rows="3"
            placeholder="选填，如：月末盘点"
            maxlength="500"
            show-word-limit
          />
        </el-form-item>
      </el-form>

      <div class="footer-actions">
        <el-button @click="router.push('/warehouse/stock-takes')">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">提交盘点单</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createStockTake } from '@/api/ops'
import { getSkuOptions, getWarehouseOptions } from '@/api/basic'

const router = useRouter()

const formRef = ref(null)
const submitting = ref(false)
const warehouseOptions = ref([])
const skuOptions = ref([])

const form = reactive({
  warehouse_id: null,
  remark: '',
  // 选填：不选或为空数组表示整仓盘点（契约 17.3）
  sku_ids: []
})

const rules = {
  warehouse_id: [{ required: true, message: '请选择盘点仓库', trigger: 'change' }]
}

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const payload = {
      warehouse_id: form.warehouse_id,
      remark: form.remark
    }
    // 未选择 SKU 时不传 sku_ids，由后端取该仓库全部库存 SKU
    if (form.sku_ids.length) payload.sku_ids = form.sku_ids

    await createStockTake(payload)
    ElMessage.success('盘点单创建成功，请到详情录入实盘数量')
    router.push('/warehouse/stock-takes')
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

.option-extra {
  float: right;
  color: #909399;
  font-size: 12px;
}

.form-tip {
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
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
