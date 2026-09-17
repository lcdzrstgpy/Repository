<template>
  <div class="page-container">
    <el-card shadow="never" class="search-card">
      <div class="module-purpose">汇总需求 / 补货采购</div>
      <WarehouseFulfillmentTabs class="tabs" />
      <el-form inline>
        <el-form-item label="仓库">
          <el-select v-model="warehouseId" clearable filterable placeholder="全部仓库" style="width: 200px">
            <el-option v-for="warehouse in warehouses" :key="warehouse.id" :label="warehouse.name" :value="warehouse.id" />
          </el-select>
        </el-form-item>
        <el-button type="primary" @click="load">汇总</el-button>
        <el-button @click="reset">重置</el-button>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <template #header>
        <div class="header"><span>待备货采购汇总</span><el-button :loading="loading" @click="load">刷新</el-button></div>
      </template>
      <el-alert type="info" :closable="false" show-icon title="仅统计已确认数量、处于备货中且尚未发货的订单；建议采购量已扣除该仓库可用库存。" class="tip" />
      <el-table v-loading="loading" :data="list" border stripe show-summary :summary-method="summaryMethod">
        <el-table-column prop="warehouse_name" label="仓库" width="150" />
        <el-table-column prop="sku_code" label="货号" width="170" />
        <el-table-column prop="product_name" label="商品名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="spec" label="规格" min-width="140"><template #default="{ row }">{{ row.spec || '-' }}</template></el-table-column>
        <el-table-column prop="order_count" label="涉及订单" width="105" align="right" />
        <el-table-column prop="need_count" label="待备数量" width="120" align="right"><template #default="{ row }">{{ formatCount(row.need_count) }}</template></el-table-column>
        <el-table-column prop="min_stock" label="安全库存" width="110" align="right"><template #default="{ row }">{{ formatCount(row.min_stock) }}</template></el-table-column>
        <el-table-column prop="available_quantity" label="可用库存" width="120" align="right"><template #default="{ row }">{{ formatCount(row.available_quantity) }}</template></el-table-column>
        <el-table-column prop="suggested_purchase" label="建议采购量" width="130" align="right"><template #default="{ row }"><b :class="{ shortage: Number(row.suggested_purchase) > 0 }">{{ formatCount(row.suggested_purchase) }}</b></template></el-table-column>
      </el-table>
      <el-empty v-if="!loading && !list.length" description="当前没有需要备货的已确认订单" />
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { getPurchaseSummary } from '@/api/warehouse'
import { getWarehouseOptions } from '@/api/basic'
import { formatCount } from '@/utils/format'
import WarehouseFulfillmentTabs from './components/WarehouseFulfillmentTabs.vue'

const loading = ref(false)
const warehouseId = ref('')
const warehouses = ref([])
const list = ref([])

async function load() {
  loading.value = true
  try { list.value = (await getPurchaseSummary(warehouseId.value)) || [] } finally { loading.value = false }
}
function reset() { warehouseId.value = ''; load() }
function summaryMethod({ columns, data }) {
  return columns.map((column, index) => {
    if (index === 0) return '合计'
    if (column.property === 'need_count') return formatCount(data.reduce((sum, row) => sum + Number(row.need_count || 0), 0))
    if (column.property === 'suggested_purchase') return formatCount(data.reduce((sum, row) => sum + Number(row.suggested_purchase || 0), 0))
    return ''
  })
}
onMounted(async () => { warehouses.value = (await getWarehouseOptions()) || []; load() })
</script>

<style scoped>
.header { display:flex; align-items:center; justify-content:space-between }.tip { margin-bottom:16px }.shortage { color:#f56c6c; font-size:16px }.module-purpose { margin-bottom:14px; color:#409eff; font-size:18px; font-weight:600 }.tabs { margin-bottom:14px }
</style>
