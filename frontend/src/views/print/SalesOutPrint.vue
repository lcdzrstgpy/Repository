<template>
  <div class="print-page">
    <!-- 操作条：打印时通过 .no-print 隐藏 -->
    <div class="print-toolbar no-print">
      <el-button type="primary" :disabled="!detail || loading" @click="handlePrint">
        <el-icon><Printer /></el-icon>
        <span style="margin-left: 4px">打印</span>
      </el-button>
      <el-button @click="handleBack">
        <el-icon><Back /></el-icon>
        <span style="margin-left: 4px">返回</span>
      </el-button>
    </div>

    <!-- A4 纸张内容区 -->
    <div v-loading="loading" class="paper">
      <template v-if="detail">
        <h1 class="doc-title">出 库 单</h1>

        <div class="doc-meta">
          <div class="meta-item">
            <span class="meta-label">出库单号：</span>
            <span class="meta-value">{{ detail.no || '-' }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">单据日期：</span>
            <span class="meta-value">{{ detail.created_at || '-' }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">出库仓库：</span>
            <span class="meta-value">{{ detail.warehouse_name || '-' }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">关联订单号：</span>
            <span class="meta-value">{{ detail.order_no || '-' }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">物流单号：</span>
            <span class="meta-value">{{ detail.express_no || '-' }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">制单人：</span>
            <span class="meta-value">{{ detail.created_by_name || '-' }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">单据状态：</span>
            <span class="meta-value">{{ detail.status_text || outStatusLabel(detail.status) }}</span>
          </div>
        </div>

        <table class="detail-table">
          <colgroup>
            <col style="width: 8%" />
            <col style="width: 17%" />
            <col style="width: 25%" />
            <col style="width: 18%" />
            <col style="width: 10%" />
            <col style="width: 10%" />
            <col style="width: 12%" />
          </colgroup>
          <thead>
            <tr>
              <th>序号</th>
              <th>SKU 编码</th>
              <th>商品名称</th>
              <th>规格</th>
              <th>数量</th>
              <th>单价</th>
              <th>小计</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(item, index) in detail.items || []" :key="item.id || index">
              <td class="cell-center">{{ index + 1 }}</td>
              <td>{{ item.sku_code || '-' }}</td>
              <td>{{ item.product_name || '-' }}</td>
              <td>{{ item.spec || '-' }}</td>
              <td class="cell-right">{{ formatCount(item.count) }}</td>
              <td class="cell-right">￥{{ formatMoney(item.price) }}</td>
              <td class="cell-right">￥{{ formatMoney(item.total_price) }}</td>
            </tr>
            <tr v-if="!detail.items || !detail.items.length">
              <td class="cell-center empty-cell" colspan="7">暂无出库明细</td>
            </tr>
            <!-- 合计行 -->
            <tr class="summary-row">
              <td class="cell-center" colspan="4">合 计</td>
              <td class="cell-right">{{ formatCount(detail.total_count) }}</td>
              <td class="cell-right">—</td>
              <td class="cell-right">￥{{ formatMoney(detail.total_price) }}</td>
            </tr>
          </tbody>
        </table>

        <div class="amount-line">
          合计数量：<span class="amount-strong">{{ formatCount(detail.total_count) }}</span>
          <span class="amount-gap"></span>
          合计金额：<span class="amount-strong">￥{{ formatMoney(detail.total_price) }}</span>
        </div>

        <div class="remark-line">备注：{{ detail.remark || '无' }}</div>

        <div class="sign-row">
          <div class="sign-item">制单人：<span class="sign-blank"></span></div>
          <div class="sign-item">审核人：<span class="sign-blank"></span></div>
          <div class="sign-item">收货人：<span class="sign-blank"></span></div>
        </div>

        <div class="doc-footer">打印时间：{{ printTime }}</div>
      </template>

      <el-empty
        v-else-if="!loading"
        description="未获取到该出库单数据，请确认单据是否存在或已被删除"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getOutDetail } from '@/api/stock'
import { outStatusLabel } from '@/utils/constants'
import { formatCount, formatMoney } from '@/utils/format'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const detail = ref(null)

/** 打印时间：进入页面时固定，避免打印过程中变化 */
const printTime = ref('')

/** 拉取出库单详情（复用已有详情接口，契约 13） */
async function load() {
  loading.value = true
  try {
    detail.value = await getOutDetail(route.params.id)
  } catch (e) {
    // request.js 已统一提示错误，这里保持空状态展示友好提示
    detail.value = null
  } finally {
    loading.value = false
  }
}

/** 数据加载完成后才能打印 */
function handlePrint() {
  if (!detail.value) return
  window.print()
}

/** 返回：优先回上一页，新标签页打开时回退到出库单列表 */
function handleBack() {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/warehouse/outs')
  }
}

onMounted(() => {
  printTime.value = new Date().toLocaleString('zh-CN')
  load()
})
</script>

<style scoped>
.print-page {
  min-height: 100vh;
  padding: 16px 0 32px;
  background-color: #f0f2f5;
}

/* 操作条 */
.print-toolbar {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-bottom: 16px;
}

/* A4 纸张：宽 210mm，四周留内边距 */
.paper {
  width: 210mm;
  min-height: 297mm;
  margin: 0 auto;
  padding: 14mm 16mm;
  background-color: #fff;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.12);
}

.doc-title {
  margin: 0 0 6mm;
  font-size: 26px;
  font-weight: 700;
  letter-spacing: 8px;
  text-align: center;
  color: #000;
}

/* 单据信息区：两列布局 */
.doc-meta {
  display: flex;
  flex-wrap: wrap;
  margin-bottom: 4mm;
  border-top: 2px solid #000;
  border-left: 1px solid #000;
}

.meta-item {
  display: flex;
  align-items: center;
  width: 50%;
  min-height: 10mm;
  padding: 2mm 3mm;
  border-right: 1px solid #000;
  border-bottom: 1px solid #000;
  font-size: 13px;
  line-height: 1.5;
}

.meta-label {
  flex: none;
  color: #000;
}

.meta-value {
  flex: 1;
  word-break: break-all;
}

/* 明细表格 */
.detail-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 13px;
}

.detail-table th,
.detail-table td {
  padding: 2.5mm 2mm;
  border: 1px solid #000;
  word-break: break-all;
}

.detail-table th {
  font-weight: 600;
  text-align: center;
  background-color: #f5f5f5;
}

.cell-center {
  text-align: center;
}

.cell-right {
  text-align: right;
}

.empty-cell {
  color: #909399;
}

.summary-row td {
  font-weight: 600;
  background-color: #fafafa;
}

/* 金额与备注 */
.amount-line {
  margin-top: 4mm;
  font-size: 13px;
  line-height: 1.8;
  text-align: right;
}

.amount-strong {
  font-weight: 600;
}

.amount-gap {
  display: inline-block;
  width: 32px;
}

.remark-line {
  margin-top: 2mm;
  font-size: 13px;
  line-height: 1.8;
  word-break: break-all;
}

/* 签字栏 */
.sign-row {
  display: flex;
  justify-content: space-between;
  margin-top: 12mm;
  font-size: 13px;
}

.sign-item {
  display: flex;
  align-items: flex-end;
  flex: 1;
}

.sign-blank {
  display: inline-block;
  flex: 1;
  max-width: 120px;
  margin-left: 4px;
  border-bottom: 1px solid #000;
}

.doc-footer {
  margin-top: 10mm;
  font-size: 12px;
  text-align: right;
  color: #606266;
}

/* 打印时：去掉阴影与背景，按纸张铺满 */
@media print {
  .print-page {
    min-height: auto;
    padding: 0;
    background-color: #fff;
  }

  .paper {
    width: auto;
    min-height: auto;
    margin: 0;
    padding: 0;
    box-shadow: none;
  }
}
</style>
