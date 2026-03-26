function formatTime(timeStr) {
  const date = typeof timeStr === 'string' ? new Date(timeStr) : timeStr;
  const now = new Date();

  const Y = date.getFullYear(),
    M = date.getMonth() + 1,
    D = date.getDate(),
    h = date.getHours(),
    m = date.getMinutes();

  const Y0 = now.getFullYear(),
    M0 = now.getMonth() + 1,
    D0 = now.getDate();

  if (Y === Y0) {
    if (M === M0 && D === D0)
      return `今天 ${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
    if (M === M0 && D === D0 - 1)
      return `昨天 ${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
    return `${M}月${D}日 ${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
  }

  return `${Y}年${M}月${D}日 ${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
}

module.exports = { formatTime };