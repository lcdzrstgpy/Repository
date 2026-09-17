-- =============================================================================
-- 仓储管理系统 · 初始化数据脚本（MySQL 8）
-- =============================================================================
-- 【重要说明 · 密码哈希】
--   下面 3 个用户的 password_hash 均为同一个 bcrypt 哈希值（cost = 12）：
--       $2b$12$dzZLerDkE/dvGfr052R2xOVPRQefzuD24ptUmxOF.iVrvLDlfGbCy
--   该哈希对应明文密码：admin123
--   （已用 bcrypt.checkpw 实测：admin123 -> True，secret -> False。）
--   ⚠ 此哈希为演示用固定值，真实生产环境请务必修改默认密码。
--   如需重新生成，可执行后端脚本（会把已存在用户的密码一并重置为 admin123）：
--       cd backend && python init_data.py
-- =============================================================================
-- 【执行方式】
--   mysql -uroot -proot < sql/init_data.sql
--   或由 docker-compose 在容器首次启动时自动执行（挂载为 02-init-data.sql）。
-- 【幂等性】
--   可重复执行，不会报错、不会产生重复数据。但**两类数据语义不同**，务必注意：
--     · 基础数据（sys_user / warehouse / product / product_sku / partner）：
--       走 INSERT ... ON DUPLICATE KEY UPDATE，重复执行会把种子字段刷回初始值
--       （sys_user 会重置密码为 admin123，这正是「忘记密码」的修复手段）。
--     · 业务数据（inventory / sales_order / sales_order_item）：
--       走 INSERT ... SELECT ... WHERE NOT EXISTS，**只在不存在时新建**。
--       绝不覆盖已有数据，否则重复执行会把真实库存重置回 100、
--       把已完成的示例订单打回待接单。
--   ⚠ 上述语义必须与 backend/init_data.py 保持一致（两条初始化路径等价）。
-- 【ID 约定】
--   为保证外键引用稳定，以下数据均显式指定主键 id。
-- =============================================================================

USE warehouse_erp;

-- -----------------------------------------------------------------------------
-- 1. 用户（契约第七节：admin / operator1 / warehouse1，密码统一 admin123）
-- -----------------------------------------------------------------------------
INSERT INTO `sys_user` (`id`, `username`, `password_hash`, `real_name`, `role`, `status`) VALUES
  (1, 'admin',      '$2b$12$dzZLerDkE/dvGfr052R2xOVPRQefzuD24ptUmxOF.iVrvLDlfGbCy', '管理员',   'admin',     1),
  (2, 'operator1',  '$2b$12$dzZLerDkE/dvGfr052R2xOVPRQefzuD24ptUmxOF.iVrvLDlfGbCy', '运营小王', 'operator',  1),
  (3, 'warehouse1', '$2b$12$dzZLerDkE/dvGfr052R2xOVPRQefzuD24ptUmxOF.iVrvLDlfGbCy', '仓管老李', 'warehouse', 1)
ON DUPLICATE KEY UPDATE
  `password_hash` = VALUES(`password_hash`),
  `real_name`     = VALUES(`real_name`),
  `role`          = VALUES(`role`),
  `status`        = VALUES(`status`);

-- -----------------------------------------------------------------------------
-- 2. 仓库（契约第七节：WH001 主仓、WH002 备用仓）
--    ⚠ 地址文案必须与 backend/init_data.py 的 init_warehouses() 保持一致
-- -----------------------------------------------------------------------------
INSERT INTO `warehouse` (`id`, `code`, `name`, `address`, `status`) VALUES
  (1, 'WH001', '主仓',   '上海市浦东新区张江路 1 号',       1),
  (2, 'WH002', '备用仓', '上海市嘉定区曹安公路 100 号',     1)
ON DUPLICATE KEY UPDATE
  `name`    = VALUES(`name`),
  `address` = VALUES(`address`),
  `status`  = VALUES(`status`);

-- -----------------------------------------------------------------------------
-- 3. 商品（3 个商品）
--    ⚠ 分类 / 单位文案必须与 backend/init_data.py 的 init_products() 保持一致
-- -----------------------------------------------------------------------------
INSERT INTO `product` (`id`, `code`, `name`, `category`, `unit`, `status`) VALUES
  (1, 'P001', '商品A', '日用品',   '个', 1),
  (2, 'P002', '商品B', '日用品',   '个', 1),
  (3, 'P003', '商品C', '办公用品', '箱', 1)
ON DUPLICATE KEY UPDATE
  `name`     = VALUES(`name`),
  `category` = VALUES(`category`),
  `unit`     = VALUES(`unit`),
  `status`   = VALUES(`status`);

-- -----------------------------------------------------------------------------
-- 4. SKU（3 个商品各 1 个 SKU：SKU001 ~ SKU003）
--    min_stock 为安全库存下限（契约第十八节），0 表示不预警：
--      SKU001 = 50 / SKU002 = 50 / SKU003 = 20
--    ⚠ spec / price / min_stock 必须与 backend/init_data.py 的 init_products() 一致
-- -----------------------------------------------------------------------------
INSERT INTO `product_sku` (`id`, `product_id`, `sku_code`, `spec`, `price`, `status`, `min_stock`) VALUES
  (1, 1, 'SKU001', '红色/大号', 25.00, 1, 50.00),
  (2, 2, 'SKU002', '蓝色/中号', 18.50, 1, 50.00),
  (3, 3, 'SKU003', '标准装',    99.00, 1, 20.00)
ON DUPLICATE KEY UPDATE
  `product_id` = VALUES(`product_id`),
  `spec`       = VALUES(`spec`),
  `price`      = VALUES(`price`),
  `status`     = VALUES(`status`),
  `min_stock`  = VALUES(`min_stock`);

-- -----------------------------------------------------------------------------
-- 5. 往来单位（2 个客户 type=1 + 2 个供应商 type=2）
--    ⚠ 名称 / 联系人 / 电话 / 地址必须与 backend/init_data.py 的 init_partners() 一致
-- -----------------------------------------------------------------------------
INSERT INTO `partner` (`id`, `name`, `type`, `contact`, `phone`, `address`, `status`) VALUES
  (1, '某某贸易',     1, '张经理', '13800000001', '上海市黄浦区南京东路 100 号',   1),
  (2, '华东商贸',     1, '王经理', '13800000002', '杭州市西湖区文三路 200 号',     1),
  (3, '某某供应商',   2, '李厂长', '13900000001', '苏州市工业园区星湖街 300 号',   1),
  (4, '南方供应链',   2, '赵主管', '13900000002', '广州市白云区机场路 400 号',     1)
ON DUPLICATE KEY UPDATE
  `name`    = VALUES(`name`),
  `type`    = VALUES(`type`),
  `contact` = VALUES(`contact`),
  `phone`   = VALUES(`phone`),
  `address` = VALUES(`address`),
  `status`  = VALUES(`status`);

-- -----------------------------------------------------------------------------
-- 6. 库存（主仓 WH001 为 3 个 SKU 各写 quantity=100、reserved_quantity=0）
--    ⚠ 幂等语义必须与 backend/init_data.py 的 init_inventory() 一致：
--      **只在库存行不存在时新建，已存在则完全不碰**。
--      这里不能用 ON DUPLICATE KEY UPDATE quantity=...，否则重复执行会把
--      已经发生出入库的真实库存强行重置回 100，造成数据丢失。
-- -----------------------------------------------------------------------------
INSERT INTO `inventory` (`sku_id`, `warehouse_id`, `quantity`, `reserved_quantity`)
SELECT 1, 1, 100.00, 0.00 WHERE NOT EXISTS (
  SELECT 1 FROM `inventory` WHERE `sku_id` = 1 AND `warehouse_id` = 1
);

INSERT INTO `inventory` (`sku_id`, `warehouse_id`, `quantity`, `reserved_quantity`)
SELECT 2, 1, 100.00, 0.00 WHERE NOT EXISTS (
  SELECT 1 FROM `inventory` WHERE `sku_id` = 2 AND `warehouse_id` = 1
);

INSERT INTO `inventory` (`sku_id`, `warehouse_id`, `quantity`, `reserved_quantity`)
SELECT 3, 1, 100.00, 0.00 WHERE NOT EXISTS (
  SELECT 1 FROM `inventory` WHERE `sku_id` = 3 AND `warehouse_id` = 1
);

-- -----------------------------------------------------------------------------
-- 7. 示例订单（status=10 待接单，供仓储端测试）
--    单号 TB20260917001，下单人 operator1（id=2）
--    明细（两行，分别覆盖「老品填货号」与「新品勾标记」两种分支）：
--      行 1：商品A     货号 SKU001（系统里真实存在，仓库端「关联货号」可直接匹配）
--             × 10 @25.00 = 250.00，sku_id 留空，待仓库关联
--      行 2：新品手机壳 未填货号、is_new = 1 ×  5 @18.50 =  92.50，sku_id 留空
--    汇总：total_count = 15.00，total_price = 342.50
--    ⚠ 单号 TB20260917001 同时是两条初始化路径的幂等键：
--       backend/init_data.py 的 SAMPLE_ORDER_NO 必须与本处保持一致，
--       remark 文案也统一为「示例订单，供仓储端接单测试」。
--    ⚠ 幂等语义必须与 backend/init_data.py 的 init_sample_order() 一致：
--      **只在订单不存在时新建，已存在则完全不碰**。
--      这里不能用 ON DUPLICATE KEY UPDATE status=...，否则重复执行会把
--      已经流转到「已完成 / 已取消」的示例订单强行打回「待接单」。
-- -----------------------------------------------------------------------------
INSERT INTO `sales_order` (
  `id`, `no`, `status`, `audit_status`,
  `total_count`, `total_price`, `remark`, `created_by`, `created_at`
)
SELECT 1, 'TB20260917001', 10, 0,
       15.00, 342.50, '示例订单，供仓储端接单测试', 2, '2026-09-17 10:00:00'
WHERE NOT EXISTS (SELECT 1 FROM `sales_order` WHERE `no` = 'TB20260917001');

-- -----------------------------------------------------------------------------
-- 8. 示例订单明细（2 条：老品行 + 新品行）
--    注：明细表无业务唯一键，用 INSERT ... SELECT ... WHERE NOT EXISTS 保证幂等
--    ⚠ sku_id 一律留空：示例订单用于测试仓库端「关联货号」流程，
--      行 1 的 sku_code = SKU001 在 product_sku 里真实存在，可直接匹配成功。
-- -----------------------------------------------------------------------------
INSERT INTO `sales_order_item` (
  `id`, `order_id`, `product_name`, `sku_code`, `is_new`, `sku_id`,
  `count`, `out_count`, `expect_price`, `total_price`
)
SELECT 1, 1, '商品A', 'SKU001', 0, NULL, 10.00, 0.00, 25.00, 250.00
WHERE NOT EXISTS (SELECT 1 FROM `sales_order_item` WHERE `id` = 1);

INSERT INTO `sales_order_item` (
  `id`, `order_id`, `product_name`, `sku_code`, `is_new`, `sku_id`,
  `count`, `out_count`, `expect_price`, `total_price`
)
SELECT 2, 1, '新品手机壳', NULL, 1, NULL, 5.00, 0.00, 18.50, 92.50
WHERE NOT EXISTS (SELECT 1 FROM `sales_order_item` WHERE `id` = 2);

-- =============================================================================
-- 初始化数据写入完成
--   用户 3 / 仓库 2 / 商品 3 / SKU 3 / 往来单位 4 / 库存 3 / 示例订单 1 + 明细 2
--   示例订单明细：1 行老品（货号 SKU001）+ 1 行新品（is_new=1），sku_id 均待仓库关联
-- 默认账号：admin、operator1、warehouse1，密码均为 admin123
-- =============================================================================
