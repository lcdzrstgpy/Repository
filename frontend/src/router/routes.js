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
          roles: ['operator', 'admin'],
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
          roles: ['operator', 'admin'],
          menu: true,
          group: '运营管理'
        }
      },
      {
        path: 'operator/items', name: 'OperatorItemQuery', component: () => import('@/views/operator/ItemQuery.vue'),
        meta: { title: '货号查询', icon: 'Search', roles: ['operator', 'admin'], menu: true, group: '运营管理' }
      },

      // ---------- 仓储端 ----------
      {
        path: 'warehouse/pending',
        name: 'WarehousePending',
        component: () => import('@/views/warehouse/PendingOrders.vue'),
        meta: {
          title: '待接单',
          icon: 'Bell',
          roles: ['warehouse', 'admin'],
          menu: true,
          group: '仓储管理'
        }
      },
      {
        path: 'warehouse/preparing',
        name: 'WarehousePreparing',
        component: () => import('@/views/warehouse/PreparingOrders.vue'),
        meta: {
          title: '备货中',
          icon: 'Box',
          roles: ['warehouse', 'admin'],
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
          roles: ['warehouse', 'admin'],
          menu: true,
          group: '仓储管理'
        }
      },
      {
        path: 'warehouse/outs',
        name: 'WarehouseOutList',
        component: () => import('@/views/warehouse/OutList.vue'),
        meta: {
          title: '出库单',
          icon: 'TakeawayBox',
          roles: ['warehouse', 'admin'],
          menu: true,
          group: '仓储管理'
        }
      },
      {
        path: 'warehouse/purchase',
        name: 'WarehousePurchaseList',
        component: () => import('@/views/warehouse/PurchaseList.vue'),
        meta: {
          title: '采购单',
          icon: 'ShoppingCart',
          // approver 需要进入列表完成审批（契约 11）
          roles: ['warehouse', 'admin', 'approver'],
          menu: true,
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
          roles: ['warehouse', 'admin'],
          // 从采购单列表跳转，不占用侧边栏
          menu: false,
          group: '仓储管理'
        }
      },
      {
        path: 'warehouse/transfers',
        name: 'WarehouseTransferList',
        component: () => import('@/views/warehouse/TransferList.vue'),
        meta: {
          title: '移库单',
          icon: 'Sort',
          roles: ['warehouse', 'admin'],
          menu: true,
          group: '仓储管理'
        }
      },
      {
        path: 'warehouse/transfers/create',
        name: 'WarehouseTransferCreate',
        component: () => import('@/views/warehouse/TransferCreate.vue'),
        meta: {
          title: '新建移库单',
          icon: 'DocumentAdd',
          roles: ['warehouse', 'admin'],
          // 从移库单列表跳转，不占用侧边栏
          menu: false,
          group: '仓储管理'
        }
      },
      {
        path: 'warehouse/stock-takes',
        name: 'WarehouseStockTakeList',
        component: () => import('@/views/warehouse/StockTakeList.vue'),
        meta: {
          title: '盘点单',
          icon: 'Histogram',
          roles: ['warehouse', 'admin'],
          menu: true,
          group: '仓储管理'
        }
      },
      {
        path: 'warehouse/stock-takes/create',
        name: 'WarehouseStockTakeCreate',
        component: () => import('@/views/warehouse/StockTakeCreate.vue'),
        meta: {
          title: '新建盘点单',
          icon: 'DocumentAdd',
          roles: ['warehouse', 'admin'],
          // 从盘点单列表跳转，不占用侧边栏
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
          title: '库存查询',
          icon: 'Coin',
          roles: ['warehouse', 'admin'], menu: true, group: '库存管理'
        }
      },
      {
        path: 'warehouse/inventory/history',
        name: 'WarehouseInventoryHistory',
        component: () => import('@/views/warehouse/InventoryHistory.vue'),
        meta: {
          title: '库存流水',
          icon: 'Clock',
          roles: ['warehouse', 'admin'],
          menu: true,
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
          // 预警查询：operator / warehouse / admin（契约 19）
          roles: ['warehouse', 'admin'],
          menu: true,
          group: '库存管理'
        }
      },

      // ---------- 基础数据（仅管理员） ----------
      {
        path: 'basic/warehouses',
        name: 'BasicWarehouse',
        component: () => import('@/views/basic/WarehouseManage.vue'),
        meta: {
          title: '仓库管理',
          icon: 'OfficeBuilding',
          roles: ['admin'],
          menu: true,
          group: '基础数据'
        }
      },
      {
        path: 'basic/products',
        name: 'BasicProduct',
        component: () => import('@/views/basic/ProductManage.vue'),
        meta: {
          title: '商品管理',
          icon: 'Goods',
          roles: ['admin'],
          menu: true,
          group: '基础数据'
        }
      },
      {
        path: 'basic/skus',
        name: 'BasicSku',
        component: () => import('@/views/basic/SkuManage.vue'),
        meta: {
          title: 'SKU 管理',
          icon: 'Grid',
          roles: ['admin'],
          menu: true,
          group: '基础数据'
        }
      },
      {
        path: 'basic/partners',
        name: 'BasicPartner',
        component: () => import('@/views/basic/PartnerManage.vue'),
        meta: {
          title: '往来单位',
          icon: 'User',
          roles: ['admin'],
          menu: true,
          group: '基础数据'
        }
      },
      {
        path: 'basic/users',
        name: 'BasicUser',
        component: () => import('@/views/basic/UserManage.vue'),
        meta: {
          title: '用户管理',
          icon: 'Avatar',
          roles: ['admin'],
          menu: true,
          group: '基础数据'
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
