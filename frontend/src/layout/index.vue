<template>
  <el-container class="layout-root">
    <!-- 侧边栏：菜单按当前角色过滤 -->
    <el-aside :width="isCollapse ? '64px' : '220px'" class="layout-aside">
      <div class="logo">
        <el-icon :size="22"><Van /></el-icon>
        <span v-show="!isCollapse" class="logo-text">仓储管理系统</span>
      </div>

      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapse"
        :collapse-transition="false"
        background-color="#001529"
        text-color="#c9d1d9"
        active-text-color="#ffffff"
        router
        unique-opened
      >
        <template v-for="group in menuGroups" :key="group.title">
          <!-- 无分组：直接渲染一级菜单 -->
          <el-menu-item v-if="!group.title" :index="group.items[0].path">
            <el-icon><component :is="group.items[0].icon" /></el-icon>
            <template #title>{{ group.items[0].title }}</template>
          </el-menu-item>

          <!-- 有分组：渲染子菜单 -->
          <el-sub-menu v-else :index="group.title">
            <template #title>
              <el-icon><component :is="group.icon" /></el-icon>
              <span>{{ group.title }}</span>
            </template>
            <el-menu-item v-for="item in group.items" :key="item.path" :index="item.path">
              <el-icon><component :is="item.icon" /></el-icon>
              <template #title>{{ item.title }}</template>
            </el-menu-item>
          </el-sub-menu>
        </template>
      </el-menu>
    </el-aside>

    <el-container>
      <!-- 顶栏 -->
      <el-header class="layout-header">
        <div class="header-left">
          <el-icon class="collapse-btn" :size="20" @click="isCollapse = !isCollapse">
            <component :is="isCollapse ? 'Expand' : 'Fold'" />
          </el-icon>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="currentGroup">{{ currentGroup }}</el-breadcrumb-item>
            <el-breadcrumb-item v-if="route.meta?.title !== '首页'">
              {{ route.meta?.title }}
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>

        <div class="header-right">
          <el-tag :type="roleTagType" size="small" effect="plain">{{ userStore.roleText }}</el-tag>
          <el-dropdown @command="handleCommand">
            <span class="user-info">
              <el-icon><UserFilled /></el-icon>
              <span class="user-name">{{ userStore.realName }}</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item disabled>账号：{{ userStore.username }}</el-dropdown-item>
                <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 内容区 -->
      <el-main class="layout-main">
        <router-view v-slot="{ Component }">
          <component :is="Component" />
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { routes } from '@/router/routes'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const isCollapse = ref(false)

/** 当前高亮菜单 */
const activeMenu = computed(() => route.path)

/** 角色对应的标签颜色 */
const roleTagType = computed(() => {
  const map = { admin: 'danger', operator: 'primary', warehouse: 'success', approver: 'warning' }
  return map[userStore.role] || 'info'
})

/** 当前页所属分组名，用于面包屑 */
const currentGroup = computed(() => route.meta?.group || '')

/**
 * 根据当前角色过滤路由，生成侧边栏菜单
 * 同一 group 的菜单合并成一个子菜单；无 group 的作为一级菜单
 */
const menuGroups = computed(() => {
  const layoutRoute = routes.find((item) => item.path === '/')
  const children = layoutRoute?.children || []
  const role = userStore.role

  const visible = children
    .filter((item) => item.meta?.menu && (item.meta.roles || []).includes(role))
    .map((item) => ({
      path: `/${item.path}`,
      title: item.meta.title,
      icon: item.meta.icon,
      group: item.meta.group || ''
    }))

  const groups = []
  // 分组图标：未配置时取该分组第一个菜单项的图标
  const groupIconMap = { 仓储管理: 'Box', 库存管理: 'Coin', 基础数据: 'Setting' }
  visible.forEach((item) => {
    const groupTitle = item.group
    let group = groups.find((g) => g.title === groupTitle)
    if (!group) {
      group = { title: groupTitle, icon: groupIconMap[groupTitle] || item.icon, items: [] }
      groups.push(group)
    }
    group.items.push(item)
  })
  return groups
})

/** 顶栏下拉菜单 */
async function handleCommand(command) {
  if (command !== 'logout') return

  try {
    await ElMessageBox.confirm('确认退出登录吗？', '提示', {
      type: 'warning',
      confirmButtonText: '确认退出',
      cancelButtonText: '取消'
    })
  } catch (e) {
    return
  }

  await userStore.logout()
  ElMessage.success('已退出登录')
  router.push('/login')
}
</script>

<style scoped>
.layout-root {
  height: 100%;
}

.layout-aside {
  background-color: #001529;
  transition: width 0.2s;
  overflow-x: hidden;
}

.logo {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 60px;
  padding: 0 18px;
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  white-space: nowrap;
  border-bottom: 1px solid #0b2740;
}

.logo-text {
  overflow: hidden;
}

.layout-aside :deep(.el-menu) {
  border-right: none;
}

.layout-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 60px;
  padding: 0 20px;
  background-color: #fff;
  border-bottom: 1px solid #e4e7ed;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.collapse-btn {
  cursor: pointer;
  color: #606266;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  color: #303133;
  outline: none;
}

.user-name {
  font-size: 14px;
}

.layout-main {
  padding: 0;
  background-color: #f0f2f5;
  overflow-y: auto;
}
</style>
