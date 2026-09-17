<template>
  <div class="page-container">
    <el-card shadow="never" class="search-card">
      <el-form :model="query" inline>
        <el-form-item label="关键词">
          <el-input
            v-model="query.keyword"
            placeholder="货号 / 规格"
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
        <span class="text-muted">共 {{ total }} 条货号记录</span>
        <div>
          <el-button v-if="userStore.isAdmin" :loading="exporting" @click="handleExport">
            <el-icon><Download /></el-icon>
            <span style="margin-left: 4px">导出 Excel</span>
          </el-button>
          <el-button type="primary" @click="openCreate">
            <el-icon><Plus /></el-icon>
            <span style="margin-left: 4px">新增货号</span>
          </el-button>
        </div>
      </div>

      <el-table v-loading="loading" :data="list" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="sku_code" label="货号" width="150" />
        <el-table-column label="所属商品" min-width="170" show-overflow-tooltip>
          <template #default="{ row }">{{ productName(row) }}</template>
        </el-table-column>
        <el-table-column prop="spec" label="规格" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">{{ row.spec || '-' }}</template>
        </el-table-column>
        <el-table-column prop="price" label="售价（元）" width="120" align="right">
          <template #default="{ row }">￥{{ formatAmount(row.price) }}</template>
        </el-table-column>
        <el-table-column prop="min_stock" label="安全库存" width="110" align="right">
          <template #default="{ row }">{{ formatCount(row.min_stock) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
              {{ COMMON_STATUS_MAP[row.status] || '未知' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170" />
        <el-table-column label="操作" width="140" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
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

    <!-- 新增 / 编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑货号' : '新增货号'" width="520px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="所属商品" prop="product_id">
          <el-select
            v-model="form.product_id"
            placeholder="请选择所属商品"
            filterable
            style="width: 100%"
          >
            <el-option
              v-for="item in productOptions"
              :key="item.id"
              :label="`${item.code} ${item.name}`"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="货号" prop="sku_code">
          <el-input v-model="form.sku_code" placeholder="如 A001-B001-C001" maxlength="64" />
        </el-form-item>
        <el-form-item label="规格">
          <el-input v-model="form.spec" placeholder="选填，如 红色/大号" maxlength="200" />
        </el-form-item>
        <el-form-item label="售价" prop="price">
          <el-input-number
            v-model="form.price"
            :min="0"
            :precision="2"
            :step="1"
            controls-position="right"
            style="width: 200px"
          />
        </el-form-item>
        <el-form-item label="安全库存" prop="min_stock">
          <el-input-number
            v-model="form.min_stock"
            :min="0"
            :precision="2"
            :step="1"
            controls-position="right"
            style="width: 200px"
          />
          <div class="form-tip">0 表示不预警</div>
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="form.status">
            <el-radio v-for="item in COMMON_STATUS_OPTIONS" :key="item.value" :value="item.value">
              {{ item.label }}
            </el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { skuApi, productApi } from '@/api/basic'
import { exportSkus } from '@/api/export'
import { COMMON_STATUS_MAP, COMMON_STATUS_OPTIONS } from '@/utils/constants'
import { formatAmount, formatCount } from '@/utils/format'
import { useCrud } from '@/utils/useCrud'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

const defaultForm = { product_id: null, sku_code: '', spec: '', price: 0, min_stock: 0, status: 1 }

const rules = {
  product_id: [{ required: true, message: '请选择所属商品', trigger: 'change' }],
  sku_code: [{ required: true, message: '请输入货号', trigger: 'blur' }],
  price: [{ required: true, message: '请输入售价', trigger: 'blur' }],
  min_stock: [{ required: true, message: '请输入安全库存', trigger: 'blur' }]
}

const productOptions = ref([])

const {
  loading,
  submitting,
  list,
  total,
  query,
  form,
  formRef,
  dialogVisible,
  isEdit,
  load,
  handleSearch,
  handleReset,
  openCreate,
  openEdit,
  submit,
  handleDelete,
  handleSizeChange,
  handlePageChange
} = useCrud({ api: skuApi, defaultForm, label: '货号' })

/** 所属商品名称：优先用后端返回的 product_name，否则按 product_id 查本地商品列表 */
function productName(row) {
  if (row.product_name) return row.product_name
  const product = productOptions.value.find((item) => item.id === row.product_id)
  return product ? product.name : '-'
}

/** 加载商品下拉数据 */
async function loadProducts() {
  const data = await productApi.list({ page: 1, page_size: 200 })
  productOptions.value = data?.list || []
}

// ---------- 导出 Excel ----------
const exporting = ref(false)

/** 导出 SKU 列表：成功后浏览器直接下载文件 */
async function handleExport() {
  if (exporting.value) return
  exporting.value = true
  try {
    const fileName = await exportSkus()
    ElMessage.success(`已导出「${fileName}」`)
  } catch (e) {
    // download.js 内部已弹出错误提示，这里不再重复提示
  } finally {
    exporting.value = false
  }
}

onMounted(() => {
  load()
  loadProducts()
})
</script>

<style scoped>
.form-tip {
  margin-left: 8px;
  font-size: 12px;
  color: #909399;
}
</style>
