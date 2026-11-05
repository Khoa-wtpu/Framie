(function () { // N10: ô "Chọn tất cả"
  'use strict';
  var tat_ca = document.getElementById('chon-het'); // ô chọn tất cả
  var form = document.getElementById('form-tai-anh');
  if (!tat_ca || !form) return; // trang không có danh sách ảnh (hết hạn / chưa hoàn thành) thì dừng
  tat_ca.addEventListener('change', function () { // tick một lần là tick/bỏ tick mọi ảnh
    form.querySelectorAll('input[name="anh"]').forEach(function (o) { o.checked = tat_ca.checked; });
  });
})();
