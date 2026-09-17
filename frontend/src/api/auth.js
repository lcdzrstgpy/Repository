import request from './request'

/** 登录 */
export function login(data) {
  return request.post('/api/auth/login', data)
}

/** 获取当前登录用户 */
export function getMe() {
  return request.get('/api/auth/me')
}

/** 退出登录 */
export function logout() {
  return request.post('/api/auth/logout')
}
