(function () { // N10: ô "Chọn tất cả" + đếm số ảnh đã chọn
  'use strict';
  var tat_ca = document.getElementById('chon-het'); // ô chọn tất cả
  var form = document.getElementById('form-tai-anh');
  if (!tat_ca || !form) return; // trang không có danh sách ảnh (hết hạn / chưa hoàn thành) thì dừng
  var dem = document.getElementById('so-chon'); // chỗ hiện số ảnh đã chọn trên nút "Tải ảnh đã chọn"

// Hàm hỗ trợ thực hiện một bước xử lý phía trình duyệt.
  function cac_o() { return form.querySelectorAll('input[name="anh"]'); }

  function cap_nhat() { // đồng bộ ô "Chọn tất cả" và bộ đếm theo các ô đang tick
    var o = cac_o(), da_chon = 0;
// Hàm hỗ trợ thực hiện một bước xử lý phía trình duyệt.
    o.forEach(function (x) { if (x.checked) da_chon += 1; });
    tat_ca.checked = o.length > 0 && da_chon === o.length;
    tat_ca.indeterminate = da_chon > 0 && da_chon < o.length;
    if (dem) dem.textContent = da_chon > 0 ? '(' + da_chon + ')' : '';
  }

  tat_ca.addEventListener('change', function () { // tick một lần là tick/bỏ tick mọi ảnh
// Hàm hỗ trợ thực hiện một bước xử lý phía trình duyệt.
    cac_o().forEach(function (o) { o.checked = tat_ca.checked; });
    cap_nhat();
  });
// Đăng ký sự kiện để cập nhật giao diện khi người dùng thao tác.
  form.addEventListener('change', function (e) {
    if (e.target && e.target.name === 'anh') cap_nhat();
  });
  cap_nhat();
})();