<template>
  <div class="page-container">
    <el-card shadow="never" class="welcome-card">
      <div class="welcome">
        <div>
          <div class="welcome-title">
            {{ greeting }}，{{ userStore.realName }}
          </div>
          <div class="welcome-sub">
            当前角色：{{ userStore.roleText }} · 数据统计时间 {{ updatedAt || '-' }}
          </div>
        </div>
        <el-button :loading="loading" @click="loadStats">
          <el-icon><Refresh /></el-icon>
          <span style="margin-left: 4px">刷新数据</span>
        </el-button>
      </div>
    </el-card>

    <el-row :gutter="16">
      <el-col v-for="card in statCards" :key="card.key" :xs="24" :sm="12" :md="6">
        <el-card
          shadow="hover"
          class="stat-card"
          :class="{ clickable: !!card.path }"
          v-loading="loading"
          @click="handleCardClick(card)"
        >
          <div class="stat-body">
            <div class="stat-icon" :style="{ backgroundColor: card.color }">
              <el-icon :size="24" color="#fff"><component :is="card.icon" /></el-icon>
            </div>
            <div class="stat-text">
              <div class="stat-value">{{ card.value }}</div>
              <div class="stat-label">{{ card.label }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="tip-card">
      <template #header>
        <span>业务说明</span>
      </template>
      <el-descriptions :column="1" border>
        <el-descriptions-item label="订单流转">
          运营下单（待接单 10）→ 仓储接单（已接单 20）→ 仓储绑完货号（数量待确认 25）→
          运营确认数量（备货中 30）→ 仓储发货并回传物流单号（已完成 50）
        </el-descriptions-item>
        <el-descriptions-item label="取消规则">
          仅「待接单 / 已接单 / 数量待确认 / 备货中」可取消，取消后状态为「已取消 90」，需填写取消原因
        </el-descriptions-item>
        <el-descriptions-item label="数据可见性">
          运营只能看到自己创建的订单；仓储可看到全部待接单订单；管理员可查看全部数据
        </el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getOrderList } from '@/api/order'
import { getInventoryAlerts } from '@/api/inventory'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

const loading = ref(false)
const updatedAt = ref('')

/** 各状态订单数 + 库存预警条数 */
const stats = ref({
  pending: 0,
  preparing: 0,
  finished: 0,
  total: 0,
  alerts: 0
})

/** 库存预警是仓储执行事项；管理员首页只显示全局订单统计。 */
const canViewAlerts = computed(() => userStore.role === 'warehouse')

/** 问候语按当前时间段变化 */
const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 6) return '凌晨好'
  if (hour < 12) return '上午好'
  if (hour < 14) return '中午好'
  if (hour < 18) return '下午好'
  return '晚上好'
})

const statCards = computed(() => {
  const cards = [
    { key: 'pending', label: '待接单', value: stats.value.pending, icon: 'Bell', color: '#909399' },
    { key: 'preparing', label: '备货中', value: stats.value.preparing, icon: 'Box', color: '#e6a23c' },
    { key: 'finished', label: '已完成', value: stats.value.finished, icon: 'Van', color: '#67c23a' },
    { key: 'total', label: '总订单数', value: stats.value.total, icon: 'Tickets', color: '#409eff' }
  ]
  // 库存预警卡：点击跳转预警页
  if (canViewAlerts.value) {
    cards.push({
      key: 'alerts',
      label: '库存预警',
      value: stats.value.alerts,
      icon: 'Warning',
      color: '#f56c6c',
      path: '/warehouse/inventory-alerts'
    })
  }
  return cards
})

/** 统计卡点击：带跳转路径的卡片才响应 */
function handleCardClick(card) {
  if (card.path) router.push(card.path)
}

/** 取某状态的订单总数（page_size=1 只取 total，减少数据传输） */
async function fetchTotal(status) {
  const params = { page: 1, page_size: 1 }
  if (status) params.status = status
  const data = await getOrderList(params)
  return data?.total || 0
}

/** 取库存预警条数 */
async function fetchAlertTotal() {
  const data = await getInventoryAlerts({ page: 1, page_size: 1 })
  return data?.total || 0
}

/** 加载统计数据：契约无统计接口，用列表的 total 汇总 */
async function loadStats() {
  loading.value = true
  try {
    const [pending, preparing, finished, total] = await Promise.all([
      fetchTotal(10),
      fetchTotal(30),
      fetchTotal(50),
      fetchTotal()
    ])
    const alerts = canViewAlerts.value ? await fetchAlertTotal() : 0
    stats.value = { pending, preparing, finished, total, alerts }
    updatedAt.value = new Date().toLocaleString('zh-CN', { hour12: false })
  } finally {
    loading.value = false
  }
}

onMounted(loadStats)
</script>

<style scoped>
.welcome-card {
  margin-bottom: 16px;
}

.welcome {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.welcome-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.welcome-sub {
  margin-top: 6px;
  font-size: 13px;
  color: #909399;
}

.stat-card {
  margin-bottom: 16px;
}

.stat-card.clickable {
  cursor: pointer;
}

.stat-body {
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 52px;
  height: 52px;
  border-radius: 8px;
}

.stat-value {
  font-size: 26px;
  font-weight: 600;
  line-height: 1.2;
  color: #303133;
}

.stat-label {
  margin-top: 2px;
  font-size: 13px;
  color: #909399;
}
</style>
