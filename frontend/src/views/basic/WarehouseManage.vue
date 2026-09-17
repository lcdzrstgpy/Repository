<template>
  <div class="page-container">
    <el-card shadow="never" class="search-card">
      <el-form :model="query" inline>
        <el-form-item label="关键词">
          <el-input
            v-model="query.keyword"
            placeholder="仓库编码 / 名称"
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
        <span class="text-muted">共 {{ total }} 条仓库记录</span>
        <el-button type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon>
          <span style="margin-left: 4px">新增仓库</span>
        </el-button>
      </div>

      <el-table v-loading="loading" :data="list" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="code" label="仓库编码" width="140" />
        <el-table-column prop="name" label="仓库名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="address" label="地址" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">{{ row.address || '-' }}</template>
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
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑仓库' : '新增仓库'" width="520px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="仓库编码" prop="code">
          <el-input v-model="form.code" placeholder="如 WH001" maxlength="32" />
        </el-form-item>
        <el-form-item label="仓库名称" prop="name">
          <el-input v-model="form.name" placeholder="如 主仓" maxlength="100" />
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
import { warehouseApi } from '@/api/basic'
import { COMMON_STATUS_MAP, COMMON_STATUS_OPTIONS } from '@/utils/constants'
import { useCrud } from '@/utils/useCrud'

const defaultForm = { code: '', name: '', address: '', status: 1 }

const rules = {
  code: [{ required: true, message: '请输入仓库编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入仓库名称', trigger: 'blur' }]
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
} = useCrud({ api: warehouseApi, defaultForm, label: '仓库' })

onMounted(load)
</script>
