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
            <el-form-item label="订单号" prop="no">
              <el-input
                v-model="form.no"
                placeholder="请填写外部平台订单号"
                maxlength="32"
                clearable
              />
            </el-form-item>
          </el-col>
          <el-col :span="14">
            <el-form-item label="备注">
              <el-input
                v-model="form.remark"
                placeholder="选填，如：加急"
                maxlength="500"
                show-word-limit
              />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <el-alert
        class="rule-tip"
        type="info"
        :closable="false"
        show-icon
        title="每行商品需填写货号，或勾选「新品」由仓库新建货号，二者必选其一。"
      />

      <div class="table-toolbar">
        <span class="section-title">订单明细</span>
        <el-button type="primary" plain @click="addItem">
          <el-icon><Plus /></el-icon>
          <span style="margin-left: 4px">添加明细</span>
        </el-button>
      </div>

      <el-table :data="form.items" border>
        <el-table-column type="index" label="序号" width="60" align="center" />
        <el-table-column label="商品名" min-width="180">
          <template #default="{ row }">
            <el-input v-model="row.product_name" placeholder="请输入商品名" maxlength="200" />
          </template>
        </el-table-column>
        <el-table-column label="新品" width="80" align="center">
          <template #default="{ row }">
            <el-checkbox
              v-model="row.is_new"
              :true-value="1"
              :false-value="0"
              @change="handleNewChange(row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="货号" min-width="170">
          <template #default="{ row }">
            <el-input
              v-model="row.sku_code"
              :disabled="row.is_new === 1"
              :placeholder="row.is_new === 1 ? '新品由仓库新建货号' : '请输入货号'"
              maxlength="64"
            />
          </template>
        </el-table-column>
        <el-table-column label="数量" width="130">
          <template #default="{ row }">
            <el-input-number
              v-model="row.count"
              :min="1"
              :precision="0"
              :step="1"
              controls-position="right"
              style="width: 100%"
            />
          </template>
        </el-table-column>
        <el-table-column label="预计成本（元）" width="150">
          <template #default="{ row }">
            <el-input-number
              v-model="row.expect_price"
              :min="0.01"
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
        <span>合计预计成本：<b class="amount">￥{{ formatAmount(totalPrice) }}</b></span>
      </div>

      <div class="footer-actions">
        <el-button @click="router.push('/operator/orders')">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">提交订单</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createOrder } from '@/api/order'
import { formatAmount, formatCount } from '@/utils/format'

const router = useRouter()

const formRef = ref(null)
const submitting = ref(false)

const form = reactive({
  no: '',
  remark: '',
  // 明细行：product_name 商品名 / sku_code 货号 / is_new 是否新品 / count 数量 / expect_price 预计成本
  items: [createEmptyItem()]
})

const rules = {
  no: [{ required: true, message: '请填写外部平台订单号', trigger: 'blur' }]
}

function createEmptyItem() {
  return { product_name: '', sku_code: '', is_new: 0, count: 1, expect_price: null }
}

/** 勾选新品后，货号输入框禁用并清空（二选一） */
function handleNewChange(row) {
  if (row.is_new === 1) {
    row.sku_code = ''
  }
}

/** 明细行小计 = 数量 × 预计成本 */
function itemTotal(row) {
  const count = Number(row.count) || 0
  const price = Number(row.expect_price) || 0
  return count * price
}

/** 合计数量 */
const totalCount = computed(() =>
  form.items.reduce((sum, row) => sum + (Number(row.count) || 0), 0)
)

/** 合计预计成本 */
const totalPrice = computed(() => form.items.reduce((sum, row) => sum + itemTotal(row), 0))

function addItem() {
  form.items.push(createEmptyItem())
}

function removeItem(index) {
  form.items.splice(index, 1)
}

/** 提交前校验：商品名、货号/新品二选一、数量为正整数、预计成本 > 0、货号不重复 */
function validateItems() {
  if (!form.items.length) {
    ElMessage.warning('请至少添加一条订单明细')
    return false
  }
  for (let i = 0; i < form.items.length; i += 1) {
    const row = form.items[i]
    const line = `第 ${i + 1} 行`
    if (!row.product_name || !row.product_name.trim()) {
      ElMessage.warning(`${line}商品名不能为空`)
      return false
    }
    if (row.is_new === 1) {
      // 勾选新品：货号由仓库新建，前端无需填
    } else if (!row.sku_code || !row.sku_code.trim()) {
      ElMessage.warning(`${line}请填写货号，或勾选「新品」`)
      return false
    }
    if (!Number.isInteger(Number(row.count)) || Number(row.count) < 1) {
      ElMessage.warning(`${line}数量必须是大于 0 的整数`)
      return false
    }
    if (
      row.expect_price === null ||
      row.expect_price === undefined ||
      Number(row.expect_price) <= 0
    ) {
      ElMessage.warning(`${line}预计成本必须大于 0`)
      return false
    }
  }

  // 同一订单内货号不允许重复（新品行不参与比较）
  const codes = form.items
    .filter((row) => row.is_new !== 1 && row.sku_code && row.sku_code.trim())
    .map((row) => row.sku_code.trim())
  if (new Set(codes).size !== codes.length) {
    ElMessage.warning('同一订单内货号不能重复，请合并相同货号的数量')
    return false
  }
  return true
}

/** 转义 HTML，避免商品名里的特殊字符破坏确认弹窗结构 */
function escapeHtml(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/** 数量二次确认弹窗内容：逐行列出「商品名 × 数量」与合计 */
function buildConfirmHtml() {
  const lines = form.items
    .map(
      (row) =>
        `<li style="line-height:1.9">${escapeHtml(row.product_name.trim())} × ${formatCount(
          row.count
        )}</li>`
    )
    .join('')
  return `
    <div>
      <p style="margin:0 0 8px">请再次核对本次提交的商品数量：</p>
      <ul style="margin:0 0 12px;padding-left:20px">${lines}</ul>
      <p style="margin:0">
        合计：<b>${formatCount(totalCount.value)}</b> 件，
        预计成本：<b>￥${formatAmount(totalPrice.value)}</b>
      </p>
    </div>
  `
}

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  if (!validateItems()) return

  // 提交前二次确认数量（需求明确要求的环节）
  try {
    await ElMessageBox.confirm(buildConfirmHtml(), '请确认订单数量', {
      dangerouslyUseHTMLString: true,
      confirmButtonText: '确认提交',
      cancelButtonText: '再核对一下',
      type: 'warning'
    })
  } catch (e) {
    return // 运营放弃提交
  }

  submitting.value = true
  try {
    // total_count / total_price 由后端汇总，前端不传；每行 sku_code / is_new 二选一
    await createOrder({
      no: form.no.trim(),
      remark: form.remark,
      items: form.items.map((row) => {
        const item = {
          product_name: row.product_name.trim(),
          count: Number(row.count),
          expect_price: Number(row.expect_price)
        }
        if (row.is_new === 1) {
          item.is_new = 1
        } else {
          item.sku_code = row.sku_code.trim()
        }
        return item
      })
    })
    ElMessage.success('订单创建成功，已进入订单池等待仓储接单')
    router.push('/operator/orders')
  } finally {
    submitting.value = false
  }
}
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

.rule-tip {
  margin-bottom: 16px;
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
