<template>
  <div class="page-container"><el-card shadow="never"><template #header>新建订单</template>
    <el-form ref="formRef" :model="form" :rules="rules" label-width="110px" style="max-width:720px">
      <el-form-item label="订单单号" prop="no"><el-input v-model="form.no" placeholder="填写店小秘订单号" /></el-form-item>
      <el-form-item label="已有货号" v-if="!form.noItem"><el-select v-model="form.sku_code" filterable clearable placeholder="按货号或商品名选择" style="width:100%"><el-option v-for="item in options" :key="item.id" :label="`${item.sku_code} · ${item.name} ${item.spec || ''}`" :value="item.sku_code" /></el-select></el-form-item>
      <el-form-item><el-checkbox v-model="form.noItem">无货号，自动建档</el-checkbox></el-form-item>
      <template v-if="form.noItem"><el-form-item label="商品名称"><el-input v-model="form.new_item.product_name" /></el-form-item><el-form-item label="三级分类"><el-input v-model="form.new_item.categories[0]" placeholder="大类" /><el-input v-model="form.new_item.categories[1]" placeholder="二类" style="margin:0 8px" /><el-input v-model="form.new_item.categories[2]" placeholder="具体规格分类" /></el-form-item><el-form-item label="规格"><el-input v-model="form.new_item.spec" placeholder="如 500ml" /></el-form-item><el-form-item label="图片链接"><el-input v-model="form.new_item.image_url" /></el-form-item><el-form-item label="货号备注"><el-input v-model="form.new_item.item_remark" /></el-form-item></template>
      <el-form-item label="数量" prop="count"><el-input-number v-model="form.count" :min="0.01" :precision="2" /></el-form-item>
      <el-form-item label="预计成本"><el-input-number v-model="form.estimated_cost" :min="0" :precision="2" /> <span style="margin-left:8px">整单成本</span></el-form-item>
      <el-form-item label="订单备注"><el-input v-model="form.remark" type="textarea" /></el-form-item>
      <el-form-item><el-button @click="router.back()">取消</el-button><el-button type="primary" :loading="saving" @click="submit">提交订单</el-button></el-form-item>
    </el-form>
  </el-card></div>
</template>
<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createOrder } from '@/api/order'
import { getSkuOptions } from '@/api/basic'
const router = useRouter(); const formRef = ref(); const saving = ref(false); const options = ref([])
const form = reactive({ no:'', sku_code:'', noItem:false, count:1, estimated_cost:0, remark:'', new_item:{ product_name:'', categories:['','',''], spec:'', image_url:'', item_remark:'' } })
const rules = { no:[{required:true,message:'请输入订单单号',trigger:'blur'}], count:[{required:true,message:'请输入数量',trigger:'change'}] }
onMounted(async()=>{ options.value = await getSkuOptions() })
async function submit(){ if(!await formRef.value.validate().catch(()=>false)) return; if(!form.noItem && !form.sku_code) return ElMessage.warning('请选择货号'); if(form.noItem && (!form.new_item.product_name || form.new_item.categories.some(x=>!x))) return ElMessage.warning('请填写商品名和三级分类'); saving.value=true; try { await createOrder({ no:form.no.trim(), sku_code:form.noItem?null:form.sku_code, new_item:form.noItem?form.new_item:null, count:Number(form.count), estimated_cost:Number(form.estimated_cost), remark:form.remark }); ElMessage.success('订单已创建'); router.push('/operator/orders') } finally { saving.value=false } }
</script>
