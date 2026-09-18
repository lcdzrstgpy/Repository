<template>
  <div class="page-container">
    <!-- 查询条件（仅采购单页签可用） -->
    <el-card v-if="activeTab === 'order'" shadow="never" class="search-card">
      <el-form :model="query" inline>
        <el-form-item label="采购状态">
          <el-select v-model="query.status" placeholder="全部状态" clearable style="width: 160px">
            <el-option
              v-for="item in PURCHASE_STATUS_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="关键词">
          <el-input
            v-model="query.keyword"
            placeholder="采购单号 / 快递单号"
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
      <el-tabs v-model="activeTab" @tab-change="handleTabChange">
        <el-tab-pane label="采购单" name="order" />
        <el-tab-pane label="采购入库单" name="in" />
      </el-tabs>

      <!-- ---------- 采购单 ---------- -->
      <template v-if="activeTab === 'order'">
        <div class="table-toolbar">
          <span class="text-muted">共 {{ total }} 条采购单</span>
          <div>
            <el-button :loading="loading" @click="load">
              <el-icon><Refresh /></el-icon>
              <span style="margin-left: 4px">刷新</span>
            </el-button>
            <el-button v-if="canWarehouse" type="primary" @click="router.push('/warehouse/purchase/create')">
              <el-icon><Plus /></el-icon>
              <span style="margin-left: 4px">新建采购单</span>
            </el-button>
          </div>
        </div>

        <el-table v-loading="loading" :data="list" border stripe>
          <el-table-column prop="no" label="采购单号" width="170" />
          <el-table-column prop="sales_order_no" label="关联销售订单号" width="170">
            <template #default="{ row }">{{ row.sales_order_no || '-' }}</template>
          </el-table-column>
          <el-table-column prop="express_no" label="采购快递单号" width="170">
            <template #default="{ row }">{{ row.express_no || '-' }}</template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="purchaseStatusType(row.status)" size="small">
                {{ row.status_text || purchaseStatusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="total_count" label="数量" width="100" align="right">
            <template #default="{ row }">{{ formatCount(row.total_count) }}</template>
          </el-table-column>
          <el-table-column prop="total_price" label="金额" width="120" align="right">
            <template #default="{ row }">￥{{ formatAmount(row.total_price) }}</template>
          </el-table-column>
          <el-table-column prop="created_by_name" label="创建人" width="110">
            <template #default="{ row }">{{ row.created_by_name || '-' }}</template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="170" />
          <el-table-column label="操作" width="250" fixed="right" align="center">
            <template #default="{ row }">
              <el-button link type="primary" @click="openDetail(row)">详情</el-button>
              <el-button link type="primary" @click="handlePrint(row)">打印</el-button>
              <!-- 仓管采购完成后，统一入库并增加目标仓库存。 -->
              <el-button
                v-if="(row.status === 10 || row.status === 20) && canWarehouse"
                link
                type="success"
                @click="openReceive(row)"
              >
                采购完成
              </el-button>
              <!-- 待审批 / 已审批：取消（warehouse/admin） -->
              <el-button
                v-if="(row.status === 10 || row.status === 20) && canWarehouse"
                link
                type="danger"
                @click="handleCancel(row)"
              >
                取消
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
      </template>

      <!-- ---------- 采购入库单 ---------- -->
      <template v-else>
        <div class="table-toolbar">
          <span class="text-muted">共 {{ inTotal }} 条入库单</span>
          <el-button :loading="inLoading" @click="loadIns">
            <el-icon><Refresh /></el-icon>
            <span style="margin-left: 4px">刷新</span>
          </el-button>
        </div>

        <el-table v-loading="inLoading" :data="inList" border stripe>
          <el-table-column prop="no" label="入库单号" width="170" />
          <el-table-column prop="order_no" label="关联采购单号" width="170">
            <template #default="{ row }">{{ row.order_no || '-' }}</template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="PURCHASE_IN_STATUS[row.status]?.type || 'success'" size="small">
                {{ row.status_text || PURCHASE_IN_STATUS[row.status]?.label || '已完成' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="total_count" label="数量" width="100" align="right">
            <template #default="{ row }">{{ formatCount(row.total_count) }}</template>
          </el-table-column>
          <el-table-column prop="total_price" label="金额" width="120" align="right">
            <template #default="{ row }">￥{{ formatAmount(row.total_price) }}</template>
          </el-table-column>
          <el-table-column prop="created_by_name" label="创建人" width="110">
            <template #default="{ row }">{{ row.created_by_name || '-' }}</template>
          </el-table-column>
          <el-table-column prop="created_at" label="入库时间" width="170" />
          <el-table-column label="操作" width="90" fixed="right" align="center">
            <template #default="{ row }">
              <el-button link type="primary" @click="openInDetail(row)">详情</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination-wrapper">
          <el-pagination
            v-model:current-page="inQuery.page"
            v-model:page-size="inQuery.page_size"
            :total="inTotal"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next, jumper"
            background
            @size-change="handleInSizeChange"
            @current-change="handleInPageChange"
          />
        </div>
      </template>
    </el-card>

    <!-- 采购单详情抽屉 -->
    <PurchaseDetailDrawer v-model="detailVisible" :order-id="currentOrderId" />

    <!-- 采购入库单详情抽屉 -->
    <PurchaseInDetailDrawer v-model="inDetailVisible" :in-id="currentInId" />

    <!-- 收货入库弹窗 -->
    <ReceiveDialog v-model="receiveVisible" :order-id="currentOrderId" @success="load" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getPurchaseList,
  cancelPurchaseOrder,
  getPurchaseInList
} from '@/api/purchase'
import { useUserStore } from '@/stores/user'
import {
  PURCHASE_STATUS_OPTIONS,
  PURCHASE_IN_STATUS,
  purchaseStatusType,
  purchaseStatusLabel
} from '@/utils/constants'
import { formatAmount, formatCount } from '@/utils/format'
import PurchaseDetailDrawer from './components/PurchaseDetailDrawer.vue'
import PurchaseInDetailDrawer from './components/PurchaseInDetailDrawer.vue'
import ReceiveDialog from './components/ReceiveDialog.vue'

const router = useRouter()
const userStore = useUserStore()

/** 管理员只读；创建、取消、采购完成均由仓储执行。 */
const canWarehouse = computed(() => userStore.role === 'warehouse')

/** 当前页签：order 采购单 / in 采购入库单 */
const activeTab = ref('order')

const loading = ref(false)
const list = ref([])
const total = ref(0)

const query = reactive({
  page: 1,
  page_size: 20,
  status: '',
  keyword: ''
})

const inLoading = ref(false)
const inList = ref([])
const inTotal = ref(0)
const inQuery = reactive({ page: 1, page_size: 20 })

const detailVisible = ref(false)
const receiveVisible = ref(false)
const currentOrderId = ref(null)

const inDetailVisible = ref(false)
const currentInId = ref(null)

/** 采购单列表 */
async function load() {
  loading.value = true
  try {
    const params = { page: query.page, page_size: query.page_size }
    if (query.status !== '' && query.status !== null) params.status = query.status
    if (query.keyword) params.keyword = query.keyword.trim()

    const data = await getPurchaseList(params)
    list.value = data?.list || []
    total.value = data?.total || 0
  } finally {
    loading.value = false
  }
}

/** 入库单列表 */
async function loadIns() {
  inLoading.value = true
  try {
    const data = await getPurchaseInList({ page: inQuery.page, page_size: inQuery.page_size })
    inList.value = data?.list || []
    inTotal.value = data?.total || 0
  } finally {
    inLoading.value = false
  }
}

function handleTabChange() {
  if (activeTab.value === 'in' && !inList.value.length) {
    loadIns()
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

function handleInSizeChange(size) {
  inQuery.page_size = size
  inQuery.page = 1
  loadIns()
}

function handleInPageChange(page) {
  inQuery.page = page
  loadIns()
}

function openDetail(row) {
  currentOrderId.value = row.id
  detailVisible.value = true
}

/** 打印采购单：新标签页打开独立打印页（契约 13） */
function handlePrint(row) {
  const { href } = router.resolve({ path: `/print/purchase-order/${row.id}` })
  window.open(href, '_blank')
}

function openInDetail(row) {
  currentInId.value = row.id
  inDetailVisible.value = true
}

/** 收货入库 */
function openReceive(row) {
  currentOrderId.value = row.id
  receiveVisible.value = true
}

/** 取消采购单：status 10 / 20 → 90 */
async function handleCancel(row) {
  try {
    await ElMessageBox.confirm(`确认取消采购单「${row.no}」吗？`, '取消采购单', {
      type: 'warning',
      confirmButtonText: '确认取消',
      cancelButtonText: '再想想'
    })
  } catch (e) {
    return // 用户取消
  }

  await cancelPurchaseOrder(row.id)
  ElMessage.success('采购单已取消')
  load()
}

onMounted(load)
</script>
