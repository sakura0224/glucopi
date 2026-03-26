function calcAge(birthday) {
  if (!birthday) return '未知';
  const birthDate = new Date(birthday);
  const today = new Date();
  let age = today.getFullYear() - birthDate.getFullYear();
  const m = today.getMonth() - birthDate.getMonth();
  if (m < 0 || (m === 0 && today.getDate() < birthDate.getDate())) {
    age--;
  }
  return age;
}

function formatGender(gender) {
  switch (gender) {
    case 0: return 'gender-male';
    case 1: return 'gender-female';
    case 2: return 'help';
    default: return 'gender-male';
  }
}

module.exports = {
  calcAge,
  formatGender,
};