// utils/auth.js
export function isLoggedIn() {
  const token = wx.getStorageSync('access_token');
  const userId = wx.getStorageSync('user_id');
  return !!(token && userId);
}
