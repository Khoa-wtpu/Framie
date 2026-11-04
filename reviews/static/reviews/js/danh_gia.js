(function () { // N11: đếm ký tự nhận xét
  'use strict';
  var o = document.getElementById('nhan-xet'); // ô nhận xét
  var dem = document.getElementById('dem-ky-tu'); // chỗ hiện số ký tự
  if (!o || !dem) return; // trang không có form (đã đánh giá / chưa Hoàn thành) thì dừng
  function capNhat() { dem.textContent = o.value.replace(/\r\n/g, '\n').length; } // xuống dòng tính 1 ký tự, giống server
  o.addEventListener('input', capNhat); // gõ tới đâu đếm tới đó
  capNhat(); // chạy một lần khi mở trang (giữ đúng số khi form báo lỗi)
})();
