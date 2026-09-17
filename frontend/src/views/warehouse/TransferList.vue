<template>
  <div class="page-container">
    <!-- 查询条件 -->
    <el-card shadow="never" class="search-card">
      <el-form :model="query" inline>
        <el-form-item label="状态">
          <el-select v-model="query.status" placeholder="全部状态" clearable style="width: 160px">
            <el-option
              v-for="item in TRANSFER_STATUS_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="关键词">
          <el-input
            v-model="query.keyword"
            placeholder="移库单号 / 备注"
            clearable
            style="width: 240px"
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
        <span class="text-muted">共 {{ total }} 条移库单</span>
        <div>
          <el-button :loading="loading" @click="load">
            <el-icon><Refresh /></el-icon>
            <span style="margin-left: 4px">刷新</span>
          </el-button>
          <el-button type="primary" @click="router.push('/warehouse/transfers/create')">
            <el-icon><Plus /></el-icon>
            <span style="margin-left: 4px">新建移库单</span>
          </el-button>
        </div>
      </div>

      <el-table v-loading="loading" :data="list" border stripe>
        <el-table-column prop="no" label="移库单号" width="170" />
        <el-table-column prop="from_warehouse_name" label="出库仓" width="130">
          <template #default="{ row }">{{ row.from_warehouse_name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="to_warehouse_name" label="入库仓" width="130">
          <template #default="{ row }">{{ row.to_warehouse_name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="transferStatusType(row.status)" size="small">
              {{ row.status_text || transferStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_count" label="合计数量" width="110" align="right">
          <template #default="{ row }">{{ formatCount(row.total_count) }}</template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">{{ row.remark || '-' }}</template>
        </el-table-column>
        <el-table-column prop="created_by_name" label="制单人" width="110">
          <template #default="{ row }">{{ row.created_by_name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170" />
        <el-table-column prop="finished_at" label="完成时间" width="170">
          <template #default="{ row }">{{ row.finished_at || '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
            <!-- 草稿可执行移库 -->
            <el-button
              v-if="row.status === DRAFT_STATUS"
              link
              type="success"
              @click="handleFinish(row)"
            >
              执行移库
            </el-button>
            <!-- 草稿可作废 -->
            <el-button
              v-if="row.status === DRAFT_STATUS"
              link
              type="danger"
              @click="handleCancel(row)"
            >
              作废
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

    <!-- 移库单详情抽屉 -->
    <TransferDetailDrawer v-model="detailVisible" :transfer-id="currentTransferId" />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getTransferList, finishTransfer, cancelTransfer } from '@/api/ops'
import {
  TRANSFER_STATUS_OPTIONS,
  transferStatusType,
  transferStatusLabel
} from '@/utils/constants'
import { formatCount } from '@/utils/format'
import TransferDetailDrawer from './components/TransferDetailDrawer.vue'

/** 草稿状态值，仅该状态可执行移库 / 作废（契约 16.3） */
const DRAFT_STATUS = 10

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
const currentTransferId = ref(null)

async function load() {
  loading.value = true
  try {
    const params = { page: query.page, page_size: query.page_size }
    if (query.status !== '' && query.status !== null) params.status = query.status
    if (query.keyword) params.keyword = query.keyword.trim()

    const data = await getTransferList(params)
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
  currentTransferId.value = row.id
  detailVisible.value = true
}

/** 执行移库：二次确认，成功后出库仓扣减、入库仓增加 */
async function handleFinish(row) {
  try {
    await ElMessageBox.confirm(
      `确认执行移库单「${row.no}」吗？执行后「${row.from_warehouse_name || '出库仓'}」扣减、「${
        row.to_warehouse_name || '入库仓'
      }」增加，单据变为「已完成」且不可撤销。`,
      '执行移库',
      { type: 'warning', confirmButtonText: '确认执行', cancelButtonText: '取消' }
    )
  } catch (e) {
    return // 用户取消
  }

  await finishTransfer(row.id)
  ElMessage.success('移库已完成，库存已调整')
  load()
}

/** 作废移库单：仅草稿，不动库存 */
async function handleCancel(row) {
  try {
    await ElMessageBox.confirm(`确认作废移库单「${row.no}」吗？作废后不可恢复。`, '作废移库单', {
      type: 'warning',
      confirmButtonText: '确认作废',
      cancelButtonText: '取消'
    })
  } catch (e) {
    return // 用户取消
  }

  await cancelTransfer(row.id)
  ElMessage.success('移库单已作废')
  load()
}

onMounted(load)
</script>
