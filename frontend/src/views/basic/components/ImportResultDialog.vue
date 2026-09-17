<template>
  <el-dialog
    :model-value="modelValue"
    title="导入结果"
    width="640px"
    :close-on-click-modal="false"
    @update:model-value="(val) => emit('update:modelValue', val)"
  >
    <template v-if="result">
      <!-- 统计：总数 / 成功 / 失败 -->
      <div class="stat-row">
        <div class="stat-card">
          <div class="stat-label">总行数</div>
          <div class="stat-value">{{ result.total ?? 0 }}</div>
        </div>
        <div class="stat-card is-success">
          <div class="stat-label">成功</div>
          <div class="stat-value">{{ result.success ?? 0 }}</div>
        </div>
        <div class="stat-card is-danger">
          <div class="stat-label">失败</div>
          <div class="stat-value">{{ result.failed ?? 0 }}</div>
        </div>
      </div>

      <!-- 全部成功：只展示成功提示 -->
      <el-alert
        v-if="!errorList.length"
        type="success"
        :closable="false"
        show-icon
        title="全部导入成功"
        description="所有数据均已成功导入，未发现错误行。"
      />

      <!-- 存在失败：展示失败明细 -->
      <template v-else>
        <div class="section-title">失败明细（{{ errorList.length }} 条）</div>
        <el-table :data="errorList" border size="small" max-height="320">
          <el-table-column prop="row" label="行号" width="90" align="center">
            <template #default="{ row }">第 {{ row.row }} 行</template>
          </el-table-column>
          <el-table-column prop="message" label="错误信息" min-width="320" show-overflow-tooltip />
        </el-table>
      </template>
    </template>

    <el-empty v-else description="暂无导入结果" :image-size="80" />

    <template #footer>
      <el-button type="primary" @click="emit('update:modelValue', false)">知道了</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** 导入接口返回的 data：{ total, success, failed, errors: [{ row, message }] } */
  result: { type: Object, default: null }
})

const emit = defineEmits(['update:modelValue'])

/** 失败明细列表，后端未返回 errors 时按空数组处理 */
const errorList = computed(() => props.result?.errors || [])
</script>

<style scoped>
.stat-row {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.stat-card {
  flex: 1;
  padding: 12px 16px;
  text-align: center;
  background-color: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
}

.stat-label {
  margin-bottom: 6px;
  font-size: 13px;
  color: #909399;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  line-height: 1.2;
  color: #303133;
}

.stat-card.is-success .stat-value {
  color: #67c23a;
}

.stat-card.is-danger .stat-value {
  color: #f56c6c;
}

.section-title {
  margin: 0 0 12px;
  padding-left: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  border-left: 3px solid #409eff;
}
</style>
