(function () {
  'use strict';
  var form = document.getElementById('form-yeu-cau');
  if (!form) return; // trang không có form (đủ 3 lần, sai trạng thái...)

  var the = Array.prototype.slice.call(form.querySelectorAll('.yc-sua__the'));
  var nhanXet = document.getElementById('nhan-xet');
  var soChon = document.getElementById('yc-so-chon');
  var goiY = document.getElementById('yc-goi-y');
  var nutGui = document.getElementById('yc-gui');
  var nutTatCa = document.getElementById('yc-chon-tat-ca');

  function tick(t) { return t.querySelector('input[type="checkbox"]'); }
  function noiDung(t) { return t.querySelector('textarea'); }

  function dongLoi(t) { return t.querySelector('.yc-sua__loi-the'); } // dòng chữ đỏ "Vui lòng nhập nhận xét" của ô ảnh

  function capNhatDem(o) { // đếm ký tự cho ô textarea
    var dem = form.querySelector('[data-dem-cho="' + o.id + '"]');
    if (dem) dem.textContent = o.value.length + '/' + dem.getAttribute('data-toi-da');
  }

  function capNhat() { // tính lại số ảnh đã chọn, gợi ý còn thiếu, bật/tắt nút gửi
    var daChon = the.filter(function (t) { return tick(t).checked; });
    var thieuNoiDung = daChon.filter(function (t) { return noiDung(t).value.trim() === ''; });
    var thieu = [];
    if (daChon.length === 0) thieu.push('chọn ít nhất 1 ảnh');
    if (thieuNoiDung.length > 0) thieu.push('nhập nội dung chỉnh sửa cho ' + thieuNoiDung.length + ' ảnh đã chọn');
    // nhận xét tổng quát không còn bắt buộc nên không đưa vào danh sách "thiếu" nữa

    the.forEach(function (t) {
      var dangChon = tick(t).checked; // ô ảnh này có đang được tick không
      var chuaNhap = noiDung(t).value.trim() === ''; // ô nội dung của ảnh này còn trống không
      t.classList.toggle('yc-sua__the--chon', dangChon); // đổi nền tick + viền sang xanh lá khi được chọn
      dongLoi(t).hidden = !(dangChon && chuaNhap); // hiện dòng đỏ khi đã chọn mà chưa nhập, ngược lại ẩn
    });
    soChon.textContent = daChon.length;
    nutTatCa.textContent = (daChon.length === the.length) ? 'Bỏ chọn tất cả' : 'Chọn tất cả';

    nutGui.disabled = thieu.length > 0;
    goiY.hidden = thieu.length === 0;
    goiY.textContent = thieu.length ? 'Cần ' + thieu.join(', ') + '.' : '';
  }

  the.forEach(function (t) {
    var o = tick(t), nd = noiDung(t);
    o.addEventListener('change', capNhat);
    nd.addEventListener('input', function () {
      if (nd.value.trim() !== '' && !o.checked) o.checked = true; // gõ chữ thì tự tick ảnh
      capNhatDem(nd);
      capNhat();
    });
    capNhatDem(nd);
  });

  nhanXet.addEventListener('input', function () { capNhatDem(nhanXet); capNhat(); });
  capNhatDem(nhanXet);

  nutTatCa.addEventListener('click', function () {
    var tatCaDaChon = the.every(function (t) { return tick(t).checked; });
    the.forEach(function (t) { tick(t).checked = !tatCaDaChon; });
    capNhat();
  });

  capNhat(); // chạy một lần khi mở trang (giữ đúng dữ liệu khi server báo lỗi)
})();