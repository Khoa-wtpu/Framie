(function () { // N10: chọn ảnh, đếm số ảnh đã chọn, đồng hồ đếm ngược hạn tải
  'use strict';

  // ----- Đồng hồ đếm ngược đến hạn tải -----
  var demNguoc = document.getElementById('tahc-dem-nguoc');
  if (demNguoc && demNguoc.dataset.han) {
    var han = new Date(demNguoc.dataset.han).getTime();
    var capNhatDem = function () {
      var con = han - Date.now();
      if (isNaN(han)) { demNguoc.textContent = '—'; return; }
      if (con <= 0) { demNguoc.textContent = 'Đã hết hạn'; return; }
      var phut = Math.floor(con / 60000);
      var ngay = Math.floor(phut / 1440);
      var gio = Math.floor((phut % 1440) / 60);
      var p = phut % 60;
      demNguoc.textContent = ngay > 0
        ? 'Còn ' + ngay + ' ngày ' + gio + ' giờ'
        : 'Còn ' + gio + ' giờ ' + p + ' phút';
    };
    capNhatDem();
    setInterval(capNhatDem, 60000);
  }

  // ----- Chọn ảnh -----
  var form = document.getElementById('form-tai-anh');
  var tatCa = document.getElementById('chon-het'); // ô chọn tất cả
  if (!form || !tatCa) return; // trang không có danh sách ảnh (hết hạn / chưa hoàn thành) thì dừng

  var oAnh = form.querySelectorAll('input[name="anh"]');
  var hienDem = document.getElementById('tahc-da-chon');
  var nutChon = document.getElementById('nut-tai-chon');

  function capNhat() {
    var n = 0;
    oAnh.forEach(function (o) {
      if (o.checked) n += 1;
      var the = o.closest('.tahc__anh');
      if (the) the.classList.toggle('is-chon', o.checked); // viền đen cho ảnh được chọn
    });
    if (hienDem) hienDem.textContent = n;
    if (nutChon) nutChon.disabled = (n === 0);             // chưa chọn ảnh nào thì tắt nút
    tatCa.checked = (n > 0 && n === oAnh.length);
    tatCa.indeterminate = (n > 0 && n < oAnh.length);      // chọn một phần thì ô tổng hiện dấu gạch
  }

  tatCa.addEventListener('change', function () { // tick một lần là tick/bỏ tick mọi ảnh
    oAnh.forEach(function (o) { o.checked = tatCa.checked; });
    capNhat();
  });
  oAnh.forEach(function (o) { o.addEventListener('change', capNhat); });
  capNhat();
})();