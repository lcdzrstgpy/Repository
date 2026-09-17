-- =============================================================================
-- 仓储管理系统 · 数据库建表脚本（MySQL 8）
-- =============================================================================
-- 说明：
--   1. 本文件严格对应《docs/接口契约.md》第四、九、十、二十一节「数据模型」，
--      共 15 张表。
--   2. 字段名、类型、长度、唯一键、索引均不得随意更改；如需变更先改契约文档。
--   3. 所有表使用 InnoDB 引擎 + utf8mb4 字符集，支持事务与外键级联语义。
--   4. 金额与数量字段统一 decimal(14,2)；时间字段统一 datetime。
--   5. 执行方式：
--        mysql -uroot -proot < sql/schema.sql
--      或由 docker-compose 在容器首次启动时自动执行（挂载为 01-schema.sql）。
--   6. 本脚本可重复执行（全部使用 CREATE TABLE IF NOT EXISTS）。
-- =============================================================================

-- 建库：字符集 utf8mb4，排序规则 utf8mb4_general_ci
CREATE DATABASE IF NOT EXISTS warehouse_erp DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_general_ci;
USE warehouse_erp;

-- -----------------------------------------------------------------------------
-- 4.1 sys_user 用户表
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `sys_user` (
  `id`            bigint       NOT NULL AUTO_INCREMENT              COMMENT '主键 ID',
  `username`      varchar(50)  NOT NULL                            COMMENT '登录名（唯一）',
  `password_hash` varchar(255) NOT NULL                            COMMENT '密码哈希（bcrypt）',
  `real_name`     varchar(50)  NULL     DEFAULT NULL               COMMENT '姓名',
  `role`          varchar(20)  NOT NULL DEFAULT 'operator'         COMMENT '角色：admin 管理员 / operator 运营 / warehouse 仓储 / approver 审批',
  `status`        tinyint      NOT NULL DEFAULT 1                  COMMENT '状态：1 启用 / 0 停用',
  `created_at`    datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '创建时间',
  `updated_at`    datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_sys_user_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='系统用户表';

-- -----------------------------------------------------------------------------
-- 4.2 warehouse 仓库表
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `warehouse` (
  `id`         bigint       NOT NULL AUTO_INCREMENT              COMMENT '主键 ID',
  `code`       varchar(32)  NOT NULL                             COMMENT '仓库编码（唯一），如 WH001',
  `name`       varchar(100) NOT NULL DEFAULT ''                  COMMENT '仓库名称',
  `address`    varchar(255) NULL     DEFAULT NULL                COMMENT '仓库地址',
  `status`     tinyint      NOT NULL DEFAULT 1                   COMMENT '状态：1 启用 / 0 停用',
  `created_at` datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP   COMMENT '创建时间',
  `updated_at` datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_warehouse_code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='仓库表';

-- -----------------------------------------------------------------------------
-- 4.3 product 商品表
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `product` (
  `id`         bigint       NOT NULL AUTO_INCREMENT              COMMENT '主键 ID',
  `code`       varchar(64)  NOT NULL                             COMMENT '商品编码（唯一）',
  `name`       varchar(200) NOT NULL DEFAULT ''                  COMMENT '商品名称',
  `category`   varchar(50)  NULL     DEFAULT NULL                COMMENT '商品分类',
  `unit`       varchar(20)  NULL     DEFAULT NULL                COMMENT '计量单位',
  `status`     tinyint      NOT NULL DEFAULT 1                   COMMENT '状态：1 启用 / 0 停用',
  `created_at` datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP   COMMENT '创建时间',
  `updated_at` datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_product_code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='商品表';

-- -----------------------------------------------------------------------------
-- 4.4 product_sku SKU 表
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `product_sku` (
  `id`         bigint        NOT NULL AUTO_INCREMENT              COMMENT '主键 ID',
  `product_id` bigint        NOT NULL                             COMMENT '所属商品 ID，关联 product.id',
  `sku_code`   varchar(64)   NOT NULL                             COMMENT 'SKU 编码（唯一），如 SKU001',
  `spec`       varchar(200)  NULL     DEFAULT NULL                COMMENT '规格描述，如 红色/大号',
  `price`      decimal(14,2) NOT NULL DEFAULT 0.00                COMMENT '售价',
  `status`     tinyint       NOT NULL DEFAULT 1                   COMMENT '状态：1 启用 / 0 停用',
  `min_stock`  decimal(14,2) NOT NULL DEFAULT 0.00                COMMENT '安全库存下限，0 表示不预警',
  `created_at` datetime      NOT NULL DEFAULT CURRENT_TIMESTAMP   COMMENT '创建时间',
  `updated_at` datetime      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_product_sku_sku_code` (`sku_code`),
  KEY `idx_product_sku_product_id` (`product_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='商品 SKU 表';

-- -----------------------------------------------------------------------------
-- 4.5 partner 往来单位表（客户 / 供应商一表两用，用 type 区分）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `partner` (
  `id`         bigint       NOT NULL AUTO_INCREMENT              COMMENT '主键 ID',
  `name`       varchar(200) NOT NULL DEFAULT ''                  COMMENT '单位名称',
  `type`       tinyint      NOT NULL DEFAULT 1                   COMMENT '类型：1 客户 / 2 供应商 / 3 两者都是',
  `contact`    varchar(50)  NULL     DEFAULT NULL                COMMENT '联系人',
  `phone`      varchar(30)  NULL     DEFAULT NULL                COMMENT '联系电话',
  `address`    varchar(255) NULL     DEFAULT NULL                COMMENT '地址',
  `status`     tinyint      NOT NULL DEFAULT 1                   COMMENT '状态：1 启用 / 0 停用',
  `created_at` datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP   COMMENT '创建时间',
  `updated_at` datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='往来单位表（客户/供应商）';

-- -----------------------------------------------------------------------------
-- 4.6 sales_order 销售订单表（主表，存汇总）
--     六阶段（契约 17.1）：`no` 语义变更为运营录入的外部平台订单号；
--     删除 `customer_id`（不再需要客户字段）。
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `sales_order` (
  `id`            bigint        NOT NULL AUTO_INCREMENT              COMMENT '主键 ID',
  `no`            varchar(32)   NOT NULL                             COMMENT '运营录入的订单号（外部平台单号，唯一）',
  `status`        tinyint       NOT NULL DEFAULT 10                  COMMENT '订单状态：10 待接单 / 20 已接单 / 25 数量待确认 / 30 备货中 / 50 已完成（仓储发货即完成）/ 90 已取消',
  `audit_status`  tinyint       NOT NULL DEFAULT 0                   COMMENT '审批状态：0 未审批 / 1 已审批',
  `warehouse_id`  bigint        NULL     DEFAULT NULL                COMMENT '指派仓库 ID，接单时写入',
  `claimed_by`    bigint        NULL     DEFAULT NULL                COMMENT '接单人 user_id',
  `claimed_at`    datetime      NULL     DEFAULT NULL                COMMENT '接单时间',
  `prepare_at`    datetime      NULL     DEFAULT NULL                COMMENT '开始备货时间',
  `shipped_at`    datetime      NULL     DEFAULT NULL                COMMENT '发货时间',
  `finished_at`   datetime      NULL     DEFAULT NULL                COMMENT '完成时间',
  `express_no`    varchar(64)   NULL     DEFAULT NULL                COMMENT '物流单号',
  `cancel_reason` varchar(255)  NULL     DEFAULT NULL                COMMENT '取消原因',
  `remark`        varchar(500)  NULL     DEFAULT NULL                COMMENT '备注',
  `total_count`   decimal(14,2) NOT NULL DEFAULT 0.00                COMMENT '总数量（由明细汇总）',
  `total_price`   decimal(14,2) NOT NULL DEFAULT 0.00                COMMENT '预计总成本（由明细 expect_price × count 汇总）',
  `created_by`    bigint        NOT NULL                             COMMENT '下单人 user_id',
  `created_at`    datetime      NOT NULL DEFAULT CURRENT_TIMESTAMP   COMMENT '创建时间',
  `updated_at`    datetime      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_sales_order_no` (`no`),
  KEY `idx_sales_order_status` (`status`),
  KEY `idx_sales_order_created_by` (`created_by`),
  KEY `idx_sales_order_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='销售订单主表';

-- -----------------------------------------------------------------------------
-- 4.7 sales_order_item 订单明细表
--     六阶段（契约 17.2）：新增 product_name / sku_code / is_new；
--     sku_id 改为可空（为空表示尚未关联货号）；price 重命名为 expect_price。
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `sales_order_item` (
  `id`           bigint        NOT NULL AUTO_INCREMENT              COMMENT '主键 ID',
  `order_id`     bigint        NOT NULL                             COMMENT '所属订单 ID，关联 sales_order.id',
  `product_name` varchar(200)  NOT NULL DEFAULT ''                  COMMENT '商品名（运营录入的自由文本）',
  `sku_code`     varchar(64)   NULL     DEFAULT NULL                COMMENT '货号（运营录入，与 is_new 二选一）',
  `is_new`       tinyint       NOT NULL DEFAULT 0                   COMMENT '是否新品：0 否 / 1 是（与 sku_code 二选一）',
  `sku_id`       bigint        NULL     DEFAULT NULL                COMMENT 'SKU ID，关联 product_sku.id；由仓库关联货号后回填，为空表示尚未关联',
  `count`        decimal(14,2) NOT NULL DEFAULT 0.00                COMMENT '下单数量',
  `out_count`    decimal(14,2) NOT NULL DEFAULT 0.00                COMMENT '已出库数量（支持部分发货）',
  `expect_price` decimal(14,2) NOT NULL DEFAULT 0.00                COMMENT '预计成本单价（运营填写）',
  `total_price`  decimal(14,2) NOT NULL DEFAULT 0.00                COMMENT '小计 = count × expect_price',
  `created_at`   datetime      NOT NULL DEFAULT CURRENT_TIMESTAMP   COMMENT '创建时间',
  `updated_at`   datetime      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_sales_order_item_order_id` (`order_id`),
  KEY `idx_sales_order_item_sku_id` (`sku_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='销售订单明细表';

-- -----------------------------------------------------------------------------
-- 4.8 inventory 库存余额表（一阶段建表，接口只读）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `inventory` (
  `id`                bigint        NOT NULL AUTO_INCREMENT              COMMENT '主键 ID',
  `sku_id`            bigint        NOT NULL                             COMMENT 'SKU ID，关联 product_sku.id',
  `warehouse_id`      bigint        NOT NULL                             COMMENT '仓库 ID，关联 warehouse.id',
  `quantity`          decimal(14,2) NOT NULL DEFAULT 0.00                COMMENT '当前库存数量',
  `reserved_quantity` decimal(14,2) NOT NULL DEFAULT 0.00                COMMENT '预留库存数量',
  `created_at`        datetime      NOT NULL DEFAULT CURRENT_TIMESTAMP   COMMENT '创建时间',
  `updated_at`        datetime      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_inventory_sku_warehouse` (`sku_id`, `warehouse_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='库存余额表（每个 SKU 在每个仓库一条记录）';

-- -----------------------------------------------------------------------------
-- 4.9 inventory_history 库存流水表（一阶段建表，暂不写入）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `inventory_history` (
  `id`              bigint        NOT NULL AUTO_INCREMENT              COMMENT '主键 ID',
  `sku_id`          bigint        NOT NULL                             COMMENT 'SKU ID，关联 product_sku.id',
  `warehouse_id`    bigint        NOT NULL                             COMMENT '仓库 ID，关联 warehouse.id',
  `quantity`        decimal(14,2) NOT NULL DEFAULT 0.00                COMMENT '变动量（正数入库，负数出库）',
  `before_quantity` decimal(14,2) NOT NULL DEFAULT 0.00                COMMENT '变动前库存',
  `after_quantity`  decimal(14,2) NOT NULL DEFAULT 0.00                COMMENT '变动后库存',
  `order_no`        varchar(32)   NULL     DEFAULT NULL                COMMENT '关联单据单号',
  `order_type`      varchar(20)   NULL     DEFAULT NULL                COMMENT '单据类型',
  `created_by`      bigint        NULL     DEFAULT NULL                COMMENT '操作人 user_id',
  `remark`          varchar(500)  NULL     DEFAULT NULL                COMMENT '备注',
  `created_at`      datetime      NOT NULL DEFAULT CURRENT_TIMESTAMP   COMMENT '创建时间',
  `updated_at`      datetime      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_inventory_history_sku_id` (`sku_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='库存流水表';

-- -----------------------------------------------------------------------------
-- 9.2 sales_out 出库单表（二阶段）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `sales_out` (
  `id`           bigint        NOT NULL AUTO_INCREMENT              COMMENT '主键 ID',
  `no`           varchar(32)   NOT NULL                             COMMENT '出库单号（唯一），格式 OUT+yyyyMMdd+4位流水',
  `order_id`     bigint        NOT NULL                             COMMENT '关联销售订单 ID',
  `order_no`     varchar(32)   NOT NULL DEFAULT ''                  COMMENT '冗余销售订单号',
  `warehouse_id` bigint        NOT NULL                             COMMENT '出库仓库 ID',
  `status`       tinyint       NOT NULL DEFAULT 20                  COMMENT '状态：10 草稿 / 20 已完成 / 90 已作废',
  `total_count`  decimal(14,2) NOT NULL DEFAULT 0.00                COMMENT '总数量',
  `total_price`  decimal(14,2) NOT NULL DEFAULT 0.00                COMMENT '总金额',
  `express_no`   varchar(64)   NULL     DEFAULT NULL                COMMENT '物流单号',
  `remark`       varchar(500)  NULL     DEFAULT NULL                COMMENT '备注',
  `created_by`   bigint        NOT NULL                             COMMENT '创建人 user_id',
  `created_at`   datetime      NOT NULL DEFAULT CURRENT_TIMESTAMP   COMMENT '创建时间',
  `updated_at`   datetime      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_sales_out_no` (`no`),
  KEY `idx_sales_out_order_id` (`order_id`),
  KEY `idx_sales_out_warehouse_id` (`warehouse_id`),
  KEY `idx_sales_out_created_by` (`created_by`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='出库单表';

-- -----------------------------------------------------------------------------
-- 9.2 sales_out_item 出库单明细表（二阶段）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `sales_out_item` (
  `id`            bigint        NOT NULL AUTO_INCREMENT              COMMENT '主键 ID',
  `out_id`        bigint        NOT NULL                             COMMENT '关联出库单 ID',
  `order_item_id` bigint        NOT NULL                             COMMENT '关联销售订单明细 ID',
  `sku_id`        bigint        NOT NULL                             COMMENT 'SKU ID',
  `count`         decimal(14,2) NOT NULL DEFAULT 0.00                COMMENT '出库数量',
  `price`         decimal(14,2) NOT NULL DEFAULT 0.00                COMMENT '单价',
  `total_price`   decimal(14,2) NOT NULL DEFAULT 0.00                COMMENT '小计',
  `created_at`    datetime      NOT NULL DEFAULT CURRENT_TIMESTAMP   COMMENT '创建时间',
  `updated_at`    datetime      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_sales_out_item_out_id` (`out_id`),
  KEY `idx_sales_out_item_order_item_id` (`order_item_id`),
  KEY `idx_sales_out_item_sku_id` (`sku_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='出库单明细表';

-- -----------------------------------------------------------------------------
-- 10.2 purchase_order 采购单表（三阶段）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `purchase_order` (
  `id`             bigint        NOT NULL AUTO_INCREMENT              COMMENT '主键 ID',
  `no`             varchar(32)   NOT NULL                             COMMENT '采购单号（唯一），格式 PO+yyyyMMdd+4位流水',
  `supplier_id`    bigint        NOT NULL                             COMMENT '供应商 ID（partner.type 含 2）',
  `sales_order_id` bigint        NULL     DEFAULT NULL                COMMENT '关联销售订单 ID（因缺货采购时写入）',
  `status`         tinyint       NOT NULL DEFAULT 10                  COMMENT '状态：10 待审批 / 20 已审批 / 30 已入库 / 90 已取消',
  `total_count`    decimal(14,2) NOT NULL DEFAULT 0.00                COMMENT '总数量',
  `total_price`    decimal(14,2) NOT NULL DEFAULT 0.00                COMMENT '总金额',
  `expect_date`    date          NULL     DEFAULT NULL                COMMENT '期望到货日期',
  `remark`         varchar(500)  NULL     DEFAULT NULL                COMMENT '备注',
  `created_by`     bigint        NOT NULL                             COMMENT '创建人 user_id',
  `approved_by`    bigint        NULL     DEFAULT NULL                COMMENT '审批人 user_id',
  `approved_at`    datetime      NULL     DEFAULT NULL                COMMENT '审批时间',
  `created_at`     datetime      NOT NULL DEFAULT CURRENT_TIMESTAMP   COMMENT '创建时间',
  `updated_at`     datetime      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_purchase_order_no` (`no`),
  KEY `idx_purchase_order_supplier_id` (`supplier_id`),
  KEY `idx_purchase_order_sales_order_id` (`sales_order_id`),
  KEY `idx_purchase_order_status` (`status`),
  KEY `idx_purchase_order_created_by` (`created_by`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='采购单表';

-- -----------------------------------------------------------------------------
-- 10.2 purchase_order_item 采购单明细表（三阶段）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `purchase_order_item` (
  `id`          bigint        NOT NULL AUTO_INCREMENT              COMMENT '主键 ID',
  `order_id`    bigint        NOT NULL                             COMMENT '关联采购单 ID',
  `sku_id`      bigint        NOT NULL                             COMMENT 'SKU ID',
  `count`       decimal(14,2) NOT NULL DEFAULT 0.00                COMMENT '采购数量',
  `in_count`    decimal(14,2) NOT NULL DEFAULT 0.00                COMMENT '已入库数量',
  `price`       decimal(14,2) NOT NULL DEFAULT 0.00                COMMENT '单价',
  `total_price` decimal(14,2) NOT NULL DEFAULT 0.00                COMMENT '小计',
  `created_at`  datetime      NOT NULL DEFAULT CURRENT_TIMESTAMP   COMMENT '创建时间',
  `updated_at`  datetime      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_purchase_order_item_order_id` (`order_id`),
  KEY `idx_purchase_order_item_sku_id` (`sku_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='采购单明细表';

-- -----------------------------------------------------------------------------
-- 10.2 purchase_in 采购入库单表（三阶段）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `purchase_in` (
  `id`           bigint        NOT NULL AUTO_INCREMENT              COMMENT '主键 ID',
  `no`           varchar(32)   NOT NULL                             COMMENT '入库单号（唯一），格式 IN+yyyyMMdd+4位流水',
  `order_id`     bigint        NOT NULL                             COMMENT '关联采购单 ID',
  `order_no`     varchar(32)   NOT NULL DEFAULT ''                  COMMENT '冗余采购单号',
  `warehouse_id` bigint        NOT NULL                             COMMENT '入库仓库 ID',
  `status`       tinyint       NOT NULL DEFAULT 20                  COMMENT '状态：20 已完成',
  `total_count`  decimal(14,2) NOT NULL DEFAULT 0.00                COMMENT '总数量',
  `total_price`  decimal(14,2) NOT NULL DEFAULT 0.00                COMMENT '总金额',
  `remark`       varchar(500)  NULL     DEFAULT NULL                COMMENT '备注',
  `created_by`   bigint        NOT NULL                             COMMENT '创建人 user_id',
  `created_at`   datetime      NOT NULL DEFAULT CURRENT_TIMESTAMP   COMMENT '创建时间',
  `updated_at`   datetime      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_purchase_in_no` (`no`),
  KEY `idx_purchase_in_order_id` (`order_id`),
  KEY `idx_purchase_in_warehouse_id` (`warehouse_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='采购入库单表';

-- -----------------------------------------------------------------------------
-- 10.2 purchase_in_item 采购入库单明细表（三阶段）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `purchase_in_item` (
  `id`            bigint        NOT NULL AUTO_INCREMENT              COMMENT '主键 ID',
  `in_id`         bigint        NOT NULL                             COMMENT '关联入库单 ID',
  `order_item_id` bigint        NOT NULL                             COMMENT '关联采购单明细 ID',
  `sku_id`        bigint        NOT NULL                             COMMENT 'SKU ID',
  `count`         decimal(14,2) NOT NULL DEFAULT 0.00                COMMENT '入库数量',
  `price`         decimal(14,2) NOT NULL DEFAULT 0.00                COMMENT '单价',
  `total_price`   decimal(14,2) NOT NULL DEFAULT 0.00                COMMENT '小计',
  `created_at`    datetime      NOT NULL DEFAULT CURRENT_TIMESTAMP   COMMENT '创建时间',
  `updated_at`    datetime      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_purchase_in_item_in_id` (`in_id`),
  KEY `idx_purchase_in_item_order_item_id` (`order_item_id`),
  KEY `idx_purchase_in_item_sku_id` (`sku_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='采购入库单明细表';

-- =============================================================================
-- 建表完成：共 15 张表
--   基础数据：sys_user / warehouse / product / product_sku / partner
--   订单库存：sales_order / sales_order_item / inventory / inventory_history
--   出库：    sales_out / sales_out_item
--   采购：    purchase_order / purchase_order_item / purchase_in / purchase_in_item
-- 变更：product_sku 新增 min_stock（安全库存下限，0 表示不预警）。
-- 变更（六阶段订单模型重构，契约第二十一节）：
--   sales_order 删除 customer_id，no 语义改为运营录入的外部平台订单号；
--   sales_order_item 新增 product_name / sku_code / is_new，sku_id 改为可空，
--   price 重命名为 expect_price。
-- 下一步执行 init_data.sql 写入初始化数据。
-- =============================================================================
