/** 金额格式化：保留两位小数，空值显示 0.00 */
export function formatAmount(value) {
  const num = Number(value)
  if (value === null || value === undefined || Number.isNaN(num)) {
    return '0.00'
  }
  return num.toFixed(2)
}

/** 数量格式化：整数不带小数，非整数保留两位小数 */
export function formatCount(value) {
  const num = Number(value)
  if (value === null || value === undefined || Number.isNaN(num)) {
    return '0'
  }
  return Number.isInteger(num) ? String(num) : num.toFixed(2)
}

/** 空值占位，避免表格里出现空白单元格 */
export function orDash(value) {
  return value === null || value === undefined || value === '' ? '-' : value
}

/** 金额格式化（带千分位）：用于单据打印等正式场景，如 1,234.50 */
export function formatMoney(value) {
  const num = Number(value)
  if (value === null || value === undefined || Number.isNaN(num)) {
    return '0.00'
  }
  return num.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })
}
