import { ref, reactive, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

/**
 * 基础数据 CRUD 通用逻辑
 * 四组基础数据页面（仓库 / 商品 / SKU / 用户）结构一致，抽出来复用
 *
 * @param {Object} options
 * @param {Object} options.api          由 createCrudApi 生成的接口对象
 * @param {Object} options.defaultQuery 列表默认查询条件（如 { status: '' }）
 * @param {Object} options.defaultForm  表单默认值
 * @param {string} options.label        业务名称，用于提示文案，如「仓库」
 * @param {Function} options.beforeSubmit 提交前加工表单数据，(form, isEdit) => payload
 */
export function useCrud({
  api,
  defaultQuery = {},
  defaultForm = {},
  label = '数据',
  beforeSubmit
}) {
  const loading = ref(false)
  const submitting = ref(false)
  const list = ref([])
  const total = ref(0)
  const dialogVisible = ref(false)
  const isEdit = ref(false)
  const formRef = ref(null)

  const query = reactive({ page: 1, page_size: 20, keyword: '', ...defaultQuery })
  const form = reactive({ ...defaultForm })

  /** 当前编辑的记录 id */
  let currentId = null

  /** 去掉空值，避免把空字符串传给后端 */
  function buildParams() {
    const params = {}
    Object.keys(query).forEach((key) => {
      const value = query[key]
      if (value !== '' && value !== null && value !== undefined) {
        params[key] = value
      }
    })
    return params
  }

  /** 加载列表 */
  async function load() {
    loading.value = true
    try {
      const data = await api.list(buildParams())
      list.value = data?.list || []
      total.value = data?.total || 0
    } finally {
      loading.value = false
    }
  }

  /** 查询：回到第一页 */
  function handleSearch() {
    query.page = 1
    load()
  }

  /** 重置查询条件 */
  function handleReset() {
    Object.assign(query, { page: 1, page_size: 20, keyword: '' }, defaultQuery)
    load()
  }

  /** 重置表单为默认值 */
  function resetForm() {
    Object.keys(form).forEach((key) => {
      form[key] = defaultForm[key]
    })
  }

  /** 打开新增弹窗 */
  function openCreate() {
    resetForm()
    isEdit.value = false
    currentId = null
    dialogVisible.value = true
    nextTick(() => formRef.value?.clearValidate())
  }

  /** 打开编辑弹窗：只回填表单里声明过的字段 */
  function openEdit(row) {
    resetForm()
    Object.keys(form).forEach((key) => {
      if (row[key] !== undefined && row[key] !== null) {
        form[key] = row[key]
      }
    })
    isEdit.value = true
    currentId = row.id
    dialogVisible.value = true
    nextTick(() => formRef.value?.clearValidate())
  }

  /** 提交表单（新增 / 修改） */
  async function submit() {
    if (!formRef.value) return
    const valid = await formRef.value.validate().catch(() => false)
    if (!valid) return

    submitting.value = true
    try {
      const payload = beforeSubmit ? beforeSubmit({ ...form }, isEdit.value) : { ...form }
      if (isEdit.value) {
        await api.update(currentId, payload)
        ElMessage.success(`${label}修改成功`)
      } else {
        await api.create(payload)
        ElMessage.success(`${label}新增成功`)
      }
      dialogVisible.value = false
      load()
    } finally {
      submitting.value = false
    }
  }

  /** 删除（二次确认） */
  async function handleDelete(row) {
    try {
      await ElMessageBox.confirm(
        `确认删除${label}「${row.name || row.username || row.sku_code || row.id}」吗？删除后状态置为停用。`,
        '删除确认',
        { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
      )
    } catch (e) {
      return // 用户取消
    }

    await api.remove(row.id)
    ElMessage.success('删除成功')

    // 删掉当前页最后一条时回退一页
    if (list.value.length === 1 && query.page > 1) {
      query.page -= 1
    }
    load()
  }

  /** 分页：每页条数变化 */
  function handleSizeChange(size) {
    query.page_size = size
    query.page = 1
    load()
  }

  /** 分页：页码变化 */
  function handlePageChange(page) {
    query.page = page
    load()
  }

  return {
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
  }
}
