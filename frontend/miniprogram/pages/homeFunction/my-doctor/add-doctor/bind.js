export function computeBindingButtonText(bindingStatus, isBinding) {
  if (isBinding) {
    return '申请中...';
  }
  switch (bindingStatus) {
    case 'pending':
      return '申请中';
    case 'accepted':
      return '已绑定';
    case 'rejected':
      return '重新申请';
    case 'inactive':
      return '重新申请';
    case 'cancelled':
      return '重新申请';
    default:
      return '申请绑定';
  }
}