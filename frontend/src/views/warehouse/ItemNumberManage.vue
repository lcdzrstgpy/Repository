<template>
  <div class="page-container">
    <el-card shadow="never">
      <div class="module-purpose">查询 / 自动生成货号</div>
      <WarehouseItemTabs class="tabs" />
      <div class="toolbar"><span>货号管理</span><el-button type="primary" @click="visible = true">自动生成货号</el-button></div>
      <el-alert type="info" :closable="false" show-icon title="填写三级分类后自动生成 A001-B001-C001 格式货号；已生成的货号不可修改。" class="tip" />
      <el-table v-loading="loading" :data="list" border stripe>
        <el-table-column prop="sku_code" label="货号" width="180" />
        <el-table-column prop="product_name" label="商品名称" min-width="180" />
        <el-table-column prop="spec" label="规格" min-width="160"><template #default="{ row }">{{ row.spec || '-' }}</template></el-table-column>
        <el-table-column label="状态" width="100"><template #default="{ row }"><el-tag :type="row.status === 1 ? 'success' : 'info'">{{ row.status === 1 ? '启用' : '停用' }}</el-tag></template></el-table-column>
      </el-table>
    </el-card>
    <el-dialog v-model="visible" title="自动生成货号" width="520px" @closed="reset">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="95px">
        <el-form-item label="商品名称" prop="product_name"><el-input v-model="form.product_name" placeholder="如：玻璃杯" /></el-form-item>
        <el-form-item label="一级分类" prop="category_level1"><el-input v-model="form.category_level1" placeholder="如：杯子" /></el-form-item>
        <el-form-item label="二级分类"><el-input v-model="form.category_level2" placeholder="如：玻璃杯（选填）" /></el-form-item>
        <el-form-item label="三级分类"><el-input v-model="form.category_level3" placeholder="如：400ml（选填）" /></el-form-item>
        <el-form-item label="规格"><el-input v-model="form.spec" placeholder="如：透明/400ml（选填）" /></el-form-item>
        <el-form-item label="售价"><el-input-number v-model="form.price" :min="0" :precision="2" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="visible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submit">生成并确认</el-button></template>
    </el-dialog>
  </div>
</template>
<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { createItemNumber, getItemNumbers } from '@/api/warehouse'
import WarehouseItemTabs from './components/WarehouseItemTabs.vue'
const loading=ref(false), saving=ref(false), visible=ref(false), list=ref([]), formRef=ref()
const empty=()=>({product_name:'',category_level1:'',category_level2:'',category_level3:'',spec:'',price:0})
const form=reactive(empty()); const rules={product_name:[{required:true,message:'请输入商品名称',trigger:'blur'}],category_level1:[{required:true,message:'请输入一级分类',trigger:'blur'}]}
async function load(){loading.value=true;try{list.value=(await getItemNumbers())||[]}finally{loading.value=false}}
function reset(){Object.assign(form,empty());formRef.value?.clearValidate()}
async function submit(){if(!(await formRef.value.validate().catch(()=>false)))return;saving.value=true;try{const data=await createItemNumber({...form,category_level2:form.category_level2||null,category_level3:form.category_level3||null,spec:form.spec||null});ElMessage.success(`已生成货号：${data.sku_code}`);visible.value=false;load()}finally{saving.value=false}}
onMounted(load)
</script>
<style scoped>.toolbar{display:flex;align-items:center;justify-content:space-between;font-size:16px;font-weight:600}.tip{margin:16px 0}.module-purpose{margin-bottom:14px;color:#409eff;font-size:18px;font-weight:600}.tabs{margin-bottom:14px}</style>
