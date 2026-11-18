// search/static/search/js/tim_kiem.js - K8 v2
//  1) Nút "Bộ lọc" (nằm trong ô tìm kiếm) mở/đóng bảng bộ lọc; Esc hoặc bấm ra ngoài thì đóng.
//     Không có JS thì bảng luôn hiện sẵn (CSS chỉ ẩn nó khi form có class tim--js).
//  2) Đổi cách sắp xếp thì tự tìm lại (không có JS thì dùng nút "Sắp xếp" trong <noscript>).
//  3) Kiểm tra mức giá ngay khi nhập (giá tối thiểu, khoảng giá hợp lệ), lỗi hiện trong bảng bộ lọc.
(function () {
  var form = document.getElementById('form-tim-kiem');
  var nut = document.getElementById('nut-bo-loc');
  var bang = document.getElementById('bang-bo-loc');
  var dat_bang_mo = function () {};                                  // mở bảng bộ lọc (gán bên dưới khi có JS)
  if (form && nut && bang) {
    form.classList.add('tim--js');
    function dat(mo) {
      bang.hidden = !mo;
      nut.setAttribute('aria-expanded', mo ? 'true' : 'false');
    }
    dat_bang_mo = function () { dat(true); };
    dat(bang.getAttribute('data-mo') === '1');                        // mặc định thu gọn (có lỗi nhập thì mở sẵn)
    nut.addEventListener('click', function () { dat(bang.hidden); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !bang.hidden) { dat(false); nut.focus(); }
    });
    document.addEventListener('click', function (e) {
      if (!bang.hidden && !form.querySelector('.tim__tim-kiem').contains(e.target)) dat(false);
    });
  }

  // ---- Kiểm tra mức giá ngay khi nhập ----
  var oTu = document.getElementById('id_gia_tu');
  var oDen = document.getElementById('id_gia_den');
  var oLoi = document.getElementById('loi-gia');
  var nhomGia = document.getElementById('nhom-gia');
  if (form && oTu && oDen && oLoi && nhomGia) {
    var giaToiThieu = parseInt(nhomGia.getAttribute('data-gia-toi-thieu'), 10) || 1000;
    var daChamTu = !oLoi.hidden, daChamDen = !oLoi.hidden;   // server đã báo lỗi thì kiểm tra đủ ngay từ đầu
    function tien(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, '.'); }   // 1000 -> 1.000
    function so(o) { var v = o.value.trim(); return v === '' ? null : Number(v); }
    function hienLoi(cau, saiTu, saiDen) {
      oLoi.textContent = '';
      if (cau) { var p = document.createElement('p'); p.textContent = cau; oLoi.appendChild(p); }
      oLoi.hidden = !cau;
      [[oTu, saiTu], [oDen, saiDen]].forEach(function (c) {
        c[0].classList.toggle('is-invalid', c[1]);
        if (c[1]) { c[0].setAttribute('aria-invalid', 'true'); c[0].setAttribute('aria-describedby', 'loi-gia'); }
        else { c[0].removeAttribute('aria-invalid'); c[0].removeAttribute('aria-describedby'); }
      });
    }
    function kiemTraGia() {                                  // trả về true nếu hợp lệ
      var tu = so(oTu), den = so(oDen);
      if (daChamTu && tu !== null && tu < giaToiThieu) { hienLoi('Giá bắt đầu tối thiểu là ' + tien(giaToiThieu) + ' VNĐ.', true, false); return false; }
      if (daChamDen && den !== null && den < giaToiThieu) { hienLoi('Giá kết thúc tối thiểu là ' + tien(giaToiThieu) + ' VNĐ.', false, true); return false; }
      if (tu !== null && den !== null && tu > den) { hienLoi('Khoảng giá không hợp lệ: giá bắt đầu phải nhỏ hơn hoặc bằng giá kết thúc.', true, true); return false; }
      hienLoi('', false, false);
      return true;
    }
    // So sánh hai giá ngay mỗi lần gõ; giá tối thiểu thì kiểm tra khi rời ô (để gõ dở "5" rồi "50" chưa báo lỗi).
    oTu.addEventListener('input', kiemTraGia);
    oDen.addEventListener('input', kiemTraGia);
    oTu.addEventListener('focus', function () { daChamTu = false; });
    oDen.addEventListener('focus', function () { daChamDen = false; });
    oTu.addEventListener('blur', function () { daChamTu = true; kiemTraGia(); });
    oDen.addEventListener('blur', function () { daChamDen = true; kiemTraGia(); });
    form.addEventListener('submit', function (e) {
      daChamTu = daChamDen = true;
      if (!kiemTraGia()) {
        e.preventDefault();                                   // không gửi: lỗi đã hiện trong bảng, giữ bảng mở
        if (bang && bang.hidden) { dat_bang_mo(); }
        (oTu.classList.contains('is-invalid') ? oTu : oDen).focus();
      }
    });
  }

  document.querySelectorAll('select[data-tu-gui]').forEach(function (o) {
    o.addEventListener('change', function () { o.form.submit(); });
  });
})();