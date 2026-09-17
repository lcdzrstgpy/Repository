<template><div class="page-container"><el-card shadow="never"><el-form inline><el-form-item label="货号 / 商品"><el-input v-model="keyword" clearable @keyup.enter="load" /></el-form-item><el-button type="primary" @click="load">查询</el-button></el-form><el-table :data="list" v-loading="loading" border><el-table-column prop="item_no" label="货号" width="150"/><el-table-column prop="product_name" label="商品名称"/><el-table-column prop="spec" label="规格"/><el-table-column prop="remark" label="备注"/><el-table-column label="库存（只读）" min-width="260"><template #default="{row}"><div v-for="stock in row.stocks" :key="stock.warehouse_id">{{ stock.warehouse_name }}：可用 {{ stock.available_quantity }} / 库存 {{ stock.quantity }}</div><span v-if="!row.stocks.length">暂无库存</span></template></el-table-column></el-table></el-card></div></template>
<script setup>
import { onMounted, ref } from 'vue'
import { queryItems } from '@/api/basic'
const keyword=ref(''); const list=ref([]); const loading=ref(false)
async function load(){ loading.value=true; try{ list.value=await queryItems(keyword.value) }finally{ loading.value=false } }
onMounted(load)
</script>
