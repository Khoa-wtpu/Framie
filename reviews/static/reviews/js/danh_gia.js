(function () { // N11: đếm ký tự nhận xét
  'use strict';
  var o = document.getElementById('nhan-xet'); // ô nhận xét
  var dem = document.getElementById('dem-ky-tu'); // chỗ hiện số ký tự
  if (!o || !dem) return; // trang không có form (đã đánh giá / chưa Hoàn thành) thì dừng
  function capNhat() {
    var soKyTu = o.value.replace(/\r\n/g, '\n').length;
    dem.textContent = soKyTu;
    var khungDem = dem.closest('.dg-dem-ky-tu');
    if (khungDem) khungDem.classList.toggle('dg-dem-ky-tu--gioi-han', soKyTu >= Number(o.maxLength));
  }
  o.addEventListener('input', capNhat); // gõ tới đâu đếm tới đó
  capNhat(); // chạy một lần khi mở trang (giữ đúng số khi form báo lỗi)
})();
