<template>
  <div class="page-container">
    <el-card shadow="never" class="search-card">
      <el-form :model="query" inline>
        <el-form-item label="单位类型">
          <el-select v-model="query.type" placeholder="全部类型" clearable style="width: 160px">
            <el-option
              v-for="item in PARTNER_TYPE_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="关键词">
          <el-input
            v-model="query.keyword"
            placeholder="名称 / 联系人 / 电话"
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
        <span class="text-muted">共 {{ total }} 条往来单位记录</span>
        <el-button type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon>
          <span style="margin-left: 4px">新增往来单位</span>
        </el-button>
      </div>

      <el-table v-loading="loading" :data="list" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="name" label="单位名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="type" label="类型" width="130" align="center">
          <template #default="{ row }">
            <el-tag :type="row.type === 1 ? 'primary' : row.type === 2 ? 'warning' : 'success'" size="small">
              {{ PARTNER_TYPE_MAP[row.type] || '未知' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="contact" label="联系人" width="120">
          <template #default="{ row }">{{ row.contact || '-' }}</template>
        </el-table-column>
        <el-table-column prop="phone" label="联系电话" width="150">
          <template #default="{ row }">{{ row.phone || '-' }}</template>
        </el-table-column>
        <el-table-column prop="address" label="地址" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.address || '-' }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
              {{ COMMON_STATUS_MAP[row.status] || '未知' }}
            </el-tag>
          </template>
        </el-table-column>
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
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑往来单位' : '新增往来单位'"
      width="560px"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="单位名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入单位名称" maxlength="200" />
        </el-form-item>
        <el-form-item label="类型" prop="type">
          <el-select v-model="form.type" placeholder="请选择类型" style="width: 100%">
            <el-option
              v-for="item in PARTNER_TYPE_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="联系人">
          <el-input v-model="form.contact" placeholder="选填" maxlength="50" />
        </el-form-item>
        <el-form-item label="联系电话">
          <el-input v-model="form.phone" placeholder="选填" maxlength="30" />
        </el-form-item>
        <el-form-item label="地址">
          <el-input v-model="form.address" placeholder="选填" maxlength="255" />
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
import { onMounted } from 'vue'
import { partnerApi } from '@/api/basic'
import {
  PARTNER_TYPE_MAP,
  PARTNER_TYPE_OPTIONS,
  COMMON_STATUS_MAP,
  COMMON_STATUS_OPTIONS
} from '@/utils/constants'
import { useCrud } from '@/utils/useCrud'

const defaultForm = {
  name: '',
  type: 1,
  contact: '',
  phone: '',
  address: '',
  status: 1
}

const rules = {
  name: [{ required: true, message: '请输入单位名称', trigger: 'blur' }],
  type: [{ required: true, message: '请选择类型', trigger: 'change' }]
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
} = useCrud({
  api: partnerApi,
  defaultQuery: { type: '' },
  defaultForm,
  label: '往来单位'
})

onMounted(load)
</script>
