<template>
  <div class="login-page">
    <el-card class="login-card" shadow="always">
      <div class="login-title">
        <el-icon :size="28" color="#409eff"><Van /></el-icon>
        <h2>仓储管理系统</h2>
        <p class="login-subtitle">运营出单 · 仓储接单 · 状态回传</p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        size="large"
        @keyup.enter="handleLogin"
      >
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="请输入用户名" clearable>
            <template #prefix>
              <el-icon><User /></el-icon>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            show-password
            clearable
          >
            <template #prefix>
              <el-icon><Lock /></el-icon>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" class="login-btn" :loading="loading" @click="handleLogin">
            登 录
          </el-button>
        </el-form-item>
      </el-form>

      <div class="login-tip">请使用管理员分配的账号登录，如忘记密码请联系系统管理员</div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const formRef = ref(null)
const loading = ref(false)

const form = reactive({
  username: '',
  password: ''
})

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 50, message: '用户名长度为 2 到 50 个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 50, message: '密码长度为 6 到 50 个字符', trigger: 'blur' }
  ]
}

async function handleLogin() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await userStore.login({ username: form.username.trim(), password: form.password })
    ElMessage.success(`欢迎回来，${userStore.realName}`)
    // 登录后跳回来源页，没有则去首页
    const redirect = route.query.redirect
    router.replace(typeof redirect === 'string' && redirect ? redirect : '/dashboard')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  background: linear-gradient(135deg, #1f3a5f 0%, #2c5282 50%, #1a365d 100%);
}

.login-card {
  width: 400px;
  padding: 8px 12px;
  border-radius: 8px;
}

.login-title {
  text-align: center;
  margin-bottom: 20px;
}

.login-title h2 {
  margin: 8px 0 4px;
  font-size: 22px;
  color: #303133;
}

.login-subtitle {
  margin: 0;
  font-size: 13px;
  color: #909399;
}

.login-btn {
  width: 100%;
}

.login-tip {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
  text-align: center;
  line-height: 1.6;
}
</style>
