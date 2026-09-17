<template>
  <div class="page-container">
    <!-- 查询条件 -->
    <el-card shadow="never" class="search-card">
      <el-form :model="query" inline>
        <el-form-item label="订单状态">
          <el-select v-model="query.status" placeholder="全部状态" clearable style="width: 160px">
            <el-option
              v-for="item in ORDER_STATUS_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="关键词">
          <el-input
            v-model="query.keyword"
            placeholder="订单单号 / 物流单号"
            clearable
            style="width: 220px"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>
            <span style="margin-left: 4px">查询</span>
          </el-button>
          <el-button @click="handleReset">
            <el-icon><Refresh /></el-icon>
            <span style="margin-left: 4px">重置</span>
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <div class="table-toolbar">
        <span class="text-muted">共 {{ total }} 条订单</span>
        <div>
          <el-button :loading="exporting" @click="handleExport">
            <el-icon><Download /></el-icon>
            <span style="margin-left: 4px">导出 Excel</span>
          </el-button>
          <el-button type="primary" @click="router.push('/operator/orders/create')">
            <el-icon><Plus /></el-icon>
            <span style="margin-left: 4px">新建订单</span>
          </el-button>
        </div>
      </div>

      <el-table v-loading="loading" :data="list" border stripe>
        <el-table-column prop="no" label="订单单号" width="170" />
        <el-table-column label="图片" width="86" align="center">
          <template #default="{ row }"><el-image v-if="row.image_url" :src="row.image_url" :preview-src-list="[row.image_url]" fit="cover" style="width:44px;height:44px;border-radius:4px" /><span v-else>-</span></template>
        </el-table-column>
        <el-table-column prop="product_name" label="商品名" min-width="150" show-overflow-tooltip />
        <el-table-column prop="item_no" label="货号" width="150" />
        <el-table-column prop="remark" label="备注" min-width="160" show-overflow-tooltip><template #default="{ row }">{{ row.remark || '-' }}</template></el-table-column>
        <el-table-column prop="estimated_cost" label="预计成本" width="120" align="right"><template #default="{ row }">￥{{ formatAmount(row.estimated_cost) }}</template></el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="orderStatusType(row.status)" size="small">
              {{ row.status_text || orderStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="230" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
            <el-button
              link
              type="danger"
              :disabled="!canCancel(row.status)"
              @click="handleCancel(row)"
            >
              取消订单
            </el-button>
            <el-button
              link
              type="success"
              :disabled="row.status !== 40"
              @click="handleConfirm(row)"
            >
              确认完成
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.page_size"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <!-- 订单详情抽屉 -->
    <OrderDetailDrawer v-model="detailVisible" :order-id="currentOrderId" />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getOrderList, cancelOrder, confirmOrder } from '@/api/order'
import { exportSalesOrders } from '@/api/export'
import {
  ORDER_STATUS_OPTIONS,
  CANCELABLE_STATUS,
  orderStatusType,
  orderStatusLabel
} from '@/utils/constants'
import { formatAmount, formatCount } from '@/utils/format'
import OrderDetailDrawer from './components/OrderDetailDrawer.vue'

const router = useRouter()

const loading = ref(false)
const list = ref([])
const total = ref(0)

const query = reactive({
  page: 1,
  page_size: 20,
  status: '',
  keyword: ''
})

const detailVisible = ref(false)
const currentOrderId = ref(null)

/** 仅 10 / 20 / 30 可取消 */
function canCancel(status) {
  return CANCELABLE_STATUS.includes(status)
}

async function load() {
  loading.value = true
  try {
    const params = { page: query.page, page_size: query.page_size }
    if (query.status !== '' && query.status !== null) params.status = query.status
    if (query.keyword) params.keyword = query.keyword.trim()

    const data = await getOrderList(params)
    list.value = data?.list || []
    total.value = data?.total || 0
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  query.page = 1
  load()
}

function handleReset() {
  query.status = ''
  query.keyword = ''
  query.page = 1
  load()
}

function handleSizeChange(size) {
  query.page_size = size
  query.page = 1
  load()
}

function handlePageChange(page) {
  query.page = page
  load()
}

function openDetail(row) {
  currentOrderId.value = row.id
  detailVisible.value = true
}

// ---------- 导出 Excel ----------
const exporting = ref(false)

/** 导出订单：带上当前筛选条件（status）；operator 只导出自己创建的（后端控制） */
async function handleExport() {
  if (exporting.value) return
  exporting.value = true
  try {
    const params = {}
    if (query.status !== '' && query.status !== null) params.status = query.status
    const fileName = await exportSalesOrders(params)
    ElMessage.success(`已导出「${fileName}」`)
  } catch (e) {
    // download.js 内部已弹出错误提示，这里不再重复提示
  } finally {
    exporting.value = false
  }
}

/** 取消订单：必须填写取消原因 */
async function handleCancel(row) {
  let reason = ''
  try {
    const result = await ElMessageBox.prompt(
      `确认取消订单「${row.no}」吗？请填写取消原因。`,
      '取消订单',
      {
        confirmButtonText: '确认取消',
        cancelButtonText: '再想想',
        inputPlaceholder: '请输入取消原因',
        inputValidator: (value) => (value && value.trim() ? true : '取消原因不能为空'),
        type: 'warning'
      }
    )
    reason = result.value.trim()
  } catch (e) {
    return // 用户放弃
  }

  await cancelOrder(row.id, reason)
  ElMessage.success('订单已取消')
  load()
}

/** 确认完成：仅已发货状态可用 */
async function handleConfirm(row) {
  try {
    await ElMessageBox.confirm(`确认订单「${row.no}」已完成收货吗？`, '确认完成', {
      type: 'warning',
      confirmButtonText: '确认完成',
      cancelButtonText: '取消'
    })
  } catch (e) {
    return
  }

  await confirmOrder(row.id)
  ElMessage.success('订单已完成')
  load()
}

onMounted(load)
</script>
