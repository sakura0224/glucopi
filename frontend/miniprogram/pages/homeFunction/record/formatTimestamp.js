export function formatTimestamp(isoString) {
  if (!isoString) return '';

  const date = new Date(isoString); // 解析 UTC 时间
  // 显式设定中国标准时间显示
  return date.toLocaleString('zh-CN', {
    hour12: false,
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).replace(/\//g, '-'); // 统一格式为 2025-04-12 16:00
}

module.exports = { formatTimestamp };