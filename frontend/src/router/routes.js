import Layout from '@/layout/index.vue'

/** 全部角色（首页对所有已登录角色开放，避免登录后无页可去） */
const ALL_ROLES = ['admin', 'operator', 'warehouse', 'approver']

/**
 * 路由表
 * meta 说明：
 *   title 页面标题 / 菜单名
 *   icon  菜单图标（Element Plus 图标组件名）
 *   roles 可访问角色数组，不在其中则被守卫拦截
 *   menu  是否显示在侧边栏
 *   group 侧边栏分组名，不填则直接展示为一级菜单
 */
export const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { title: '登录', public: true }
  },
  {
    path: '/',
    component: Layout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '首页', icon: 'HomeFilled', roles: ALL_ROLES, menu: true }
      },

      // ---------- 运营端 ----------
      {
        path: 'operator/orders',
        name: 'OperatorOrderList',
        component: () => import('@/views/operator/OrderList.vue'),
        meta: {
          title: '我的订单',
          icon: 'List',
          roles: ['operator'],
          menu: true,
          group: '运营管理'
        }
      },
      {
        path: 'operator/orders/create',
        name: 'OperatorOrderCreate',
        component: () => import('@/views/operator/OrderCreate.vue'),
        meta: {
          title: '新建订单',
          icon: 'DocumentAdd',
          roles: ['operator'],
          menu: true,
          group: '运营管理'
        }
      },
      {
        path: 'operator/items',
        name: 'OperatorItemQuery',
        component: () => import('@/views/operator/ItemQuery.vue'),
        meta: {
          title: '货号查询',
          icon: 'Search',
          roles: ['operator'],
          menu: true,
          group: '运营管理'
        }
      },

      // ---------- 仓储端 ----------
      {
        path: 'warehouse/pending',
        name: 'WarehousePending',
        component: () => import('@/views/warehouse/PendingOrders.vue'),
        meta: {
          title: '订单处理',
          icon: 'Bell',
          roles: ['warehouse'],
          menu: true,
          group: '仓储管理'
        }
      },
      {
        path: 'warehouse/preparing',
        name: 'WarehousePreparing',
        component: () => import('@/views/warehouse/PreparingOrders.vue'),
        meta: {
          title: '备货发货',
          icon: 'Box',
          roles: ['warehouse'],
          menu: true,
          group: '仓储管理'
        }
      },
      {
        path: 'warehouse/mine',
        name: 'WarehouseMine',
        component: () => import('@/views/warehouse/MyOrders.vue'),
        meta: {
          title: '我处理的单',
          icon: 'Tickets',
          roles: ['warehouse'],
          menu: false,
          group: '仓储管理'
        }
      },
      {
        path: 'warehouse/outs',
        name: 'WarehouseOutList',
        component: () => import('@/views/warehouse/OutList.vue'),
        meta: {
          title: '出库记录',
          icon: 'TakeawayBox',
          roles: ['warehouse'],
          menu: false,
          group: '仓储管理'
        }
      },
      {
        path: 'warehouse/purchase',
        name: 'WarehousePurchaseList',
        component: () => import('@/views/warehouse/PurchaseList.vue'),
        meta: {
          title: '采购单管理',
          icon: 'ShoppingCart',
          roles: ['warehouse'],
          menu: true,
          group: '仓储管理'
        }
      },
      {
        path: 'warehouse/purchase-summary',
        redirect: '/warehouse/purchase',
        meta: {
          title: '采购单管理',
          icon: 'ShoppingCart',
          roles: ['warehouse'],
          menu: false,
          group: '仓储管理'
        }
      },
      {
        path: 'warehouse/item-numbers',
        name: 'WarehouseItemNumberManage',
        redirect: '/warehouse/inventory',
        meta: {
          title: '货号管理',
          icon: 'Grid',
          roles: ['warehouse'],
          menu: false,
          group: '仓储管理'
        }
      },
      {
        path: 'warehouse/purchase/create',
        name: 'WarehousePurchaseCreate',
        component: () => import('@/views/warehouse/PurchaseCreate.vue'),
        meta: {
          title: '新建采购单',
          icon: 'DocumentAdd',
          roles: ['warehouse'],
          // 从采购单列表跳转，不占用侧边栏
          menu: false,
          group: '仓储管理'
        }
      },
      // ---------- 库存管理 ----------
      {
        path: 'warehouse/inventory',
        name: 'WarehouseInventory',
        component: () => import('@/views/warehouse/InventoryList.vue'),
        meta: {
          title: '货号库存',
          icon: 'Coin',
          roles: ['warehouse'],
          menu: true,
          group: '库存管理'
        }
      },
      {
        path: 'warehouse/inventory/history',
        name: 'WarehouseInventoryHistory',
        component: () => import('@/views/warehouse/InventoryHistory.vue'),
        meta: {
          title: '库存流水',
          icon: 'Clock',
          roles: ['warehouse'],
          menu: false,
          group: '库存管理'
        }
      },
      {
        path: 'warehouse/inventory-alerts',
        name: 'WarehouseInventoryAlerts',
        component: () => import('@/views/warehouse/InventoryAlerts.vue'),
        meta: {
          title: '库存预警',
          icon: 'Warning',
          roles: ['warehouse'],
          menu: false,
          group: '库存管理'
        }
      },

      // ---------- 管理员：全局查看与主数据维护，不参与运营 / 仓储执行 ----------
      {
        path: 'admin/orders',
        name: 'AdminOrderList',
        component: () => import('@/views/admin/AdminOrderList.vue'),
        meta: {
          title: '全部订单',
          icon: 'List',
          roles: ['admin'],
          menu: true
        }
      },
      {
        path: 'admin/purchases',
        name: 'AdminPurchaseList',
        component: () => import('@/views/warehouse/PurchaseList.vue'),
        meta: {
          title: '采购单',
          icon: 'ShoppingCart',
          roles: ['admin'],
          menu: true
        }
      },
      // ---------- 基础数据（仅管理员） ----------
      {
        path: 'basic/products',
        name: 'BasicProduct',
        component: () => import('@/views/basic/ProductManage.vue'),
        meta: {
          title: '商品名称维护',
          icon: 'Goods',
          roles: ['admin'],
          menu: false
        }
      },
      {
        path: 'basic/skus',
        name: 'BasicSku',
        component: () => import('@/views/basic/SkuManage.vue'),
        meta: {
          title: '货号管理',
          icon: 'Grid',
          roles: ['admin'],
          menu: true
        }
      },
      {
        path: 'basic/users',
        name: 'BasicUser',
        component: () => import('@/views/basic/UserManage.vue'),
        meta: {
          title: '人员与权限',
          icon: 'Avatar',
          roles: ['admin'],
          menu: true
        }
      }
    ]
  },
  {
    // ---------- 单据打印（独立布局，不套主布局，避免侧边栏 / 顶栏出现在打印内容里） ----------
    // 契约 13：/print/sales-out/:id 与 /print/purchase-order/:id
    path: '/print/sales-out/:id',
    name: 'PrintSalesOut',
    component: () => import('@/views/print/SalesOutPrint.vue'),
    meta: { title: '出库单打印', requiresAuth: true }
  },
  {
    path: '/print/purchase-order/:id',
    name: 'PrintPurchaseOrder',
    component: () => import('@/views/print/PurchaseOrderPrint.vue'),
    meta: { title: '采购单打印', requiresAuth: true }
  },
  {
    // 兜底：未匹配的路径回到首页
    path: '/:pathMatch(.*)*',
    redirect: '/dashboard'
  }
]
