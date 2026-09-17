<template>
  <div class="page-container">
    <el-card shadow="never" class="search-card">
      <el-form :model="query" inline>
        <el-form-item label="关键词">
          <el-input
            v-model="query.keyword"
            placeholder="商品编码 / 名称"
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
        <span class="text-muted">共 {{ total }} 条商品记录</span>
        <div>
          <el-button v-if="userStore.isAdmin" :loading="exporting" @click="handleExport">
            <el-icon><Download /></el-icon>
            <span style="margin-left: 4px">导出 Excel</span>
          </el-button>
          <el-button v-if="userStore.isAdmin" type="success" plain @click="openImport">
            <el-icon><Upload /></el-icon>
            <span style="margin-left: 4px">导入 Excel</span>
          </el-button>
          <el-button type="primary" @click="openCreate">
            <el-icon><Plus /></el-icon>
            <span style="margin-left: 4px">新增商品</span>
          </el-button>
        </div>
      </div>

      <el-table v-loading="loading" :data="list" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="code" label="商品编码" width="150" />
        <el-table-column prop="name" label="商品名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="category" label="分类" width="140">
          <template #default="{ row }">{{ row.category || '-' }}</template>
        </el-table-column>
        <el-table-column prop="unit" label="单位" width="100">
          <template #default="{ row }">{{ row.unit || '-' }}</template>
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
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑商品' : '新增商品'" width="520px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="商品编码" prop="code">
          <el-input v-model="form.code" placeholder="如 P001" maxlength="64" />
        </el-form-item>
        <el-form-item label="商品名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入商品名称" maxlength="200" />
        </el-form-item>
        <el-form-item label="分类">
          <el-input v-model="form.category" placeholder="选填，如 五金" maxlength="50" />
        </el-form-item>
        <el-form-item label="单位">
          <el-input v-model="form.unit" placeholder="选填，如 个 / 箱" maxlength="20" />
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

    <!-- 导入 Excel 弹窗：仅 admin -->
    <el-dialog v-model="importVisible" title="导入商品" width="560px" @closed="handleImportClosed">
      <el-upload
        ref="uploadRef"
        drag
        :auto-upload="false"
        :limit="1"
        accept=".xlsx"
        :on-change="handleFileChange"
        :on-exceed="handleFileExceed"
        :on-remove="handleFileRemove"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">将 Excel 文件拖到此处，或<em>点击选择文件</em></div>
        <template #tip>
          <div class="el-upload__tip">
            仅支持 .xlsx 文件；第一行为表头，列顺序：商品编码 / 商品名称 / 分类 / 单位 / 状态（状态填
            1 或 0，留空默认 1）。商品编码已存在或必填项为空的行会被跳过。
          </div>
        </template>
      </el-upload>

      <template #footer>
        <el-button @click="importVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="importing"
          :disabled="!selectedFile"
          @click="handleImport"
        >
          开始导入
        </el-button>
      </template>
    </el-dialog>

    <!-- 导入结果弹窗 -->
    <ImportResultDialog v-model="importResultVisible" :result="importResult" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, genFileId } from 'element-plus'
import { productApi } from '@/api/basic'
import { exportProducts } from '@/api/export'
import { importProducts } from '@/api/import'
import { COMMON_STATUS_MAP, COMMON_STATUS_OPTIONS } from '@/utils/constants'
import { useCrud } from '@/utils/useCrud'
import { useUserStore } from '@/stores/user'
import ImportResultDialog from './components/ImportResultDialog.vue'

const userStore = useUserStore()

const defaultForm = { code: '', name: '', category: '', unit: '', status: 1 }

const rules = {
  code: [{ required: true, message: '请输入商品编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入商品名称', trigger: 'blur' }]
}

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
} = useCrud({ api: productApi, defaultForm, label: '商品' })

// ---------- 导出 Excel ----------
const exporting = ref(false)

/** 导出商品列表：成功后浏览器直接下载文件 */
async function handleExport() {
  if (exporting.value) return
  exporting.value = true
  try {
    const fileName = await exportProducts()
    ElMessage.success(`已导出「${fileName}」`)
  } catch (e) {
    // download.js 内部已弹出错误提示，这里不再重复提示
  } finally {
    exporting.value = false
  }
}

// ---------- 导入 Excel ----------
const importVisible = ref(false)
const importing = ref(false)
const uploadRef = ref(null)
/** 当前选中的待导入文件 */
const selectedFile = ref(null)

const importResultVisible = ref(false)
const importResult = ref(null)

function openImport() {
  selectedFile.value = null
  importVisible.value = true
}

/** 选择文件：先校验扩展名，不符合直接提示且不调接口 */
function handleFileChange(uploadFile) {
  const raw = uploadFile?.raw
  if (!raw) return

  if (!/\.xlsx$/i.test(raw.name)) {
    ElMessage.error('文件格式不正确，仅支持 .xlsx 文件')
    uploadRef.value?.clearFiles()
    selectedFile.value = null
    return
  }

  selectedFile.value = raw
}

/** 超出数量限制时用新文件替换旧文件（handleStart 会触发 on-change，无需重复校验） */
function handleFileExceed(files) {
  uploadRef.value?.clearFiles()
  const file = files[0]
  if (!file) return
  file.uid = genFileId()
  uploadRef.value?.handleStart(file)
}

function handleFileRemove() {
  selectedFile.value = null
}

function handleImportClosed() {
  uploadRef.value?.clearFiles()
  selectedFile.value = null
}

/** 上传并导入，导入完成后刷新列表并展示结果弹窗 */
async function handleImport() {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择要导入的 .xlsx 文件')
    return
  }

  importing.value = true
  try {
    const data = await importProducts(selectedFile.value)
    importResult.value = data
    importVisible.value = false
    importResultVisible.value = true

    // 有成功导入的行才刷新列表
    if ((data?.success || 0) > 0) {
      load()
    }
  } catch (e) {
    // request.js 已统一提示错误
  } finally {
    importing.value = false
  }
}

onMounted(load)
</script>
