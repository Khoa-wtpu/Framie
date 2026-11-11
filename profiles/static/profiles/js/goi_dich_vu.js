// profiles/static/profiles/js/goi_dich_vu.js - K6
// 1) Đổi bộ lọc trạng thái thì tự tải lại danh sách (không có JS thì dùng nút "Lọc" trong <noscript>).
document.querySelectorAll('select[data-tu-gui]').forEach(function (o) {
  o.addEventListener('change', function () { o.form.submit(); });
});

// 2) Ô "Số ảnh hậu kỳ tối đa" chỉ hiện khi chọn "Giới hạn số lượng ảnh" (wireframe C1.7).
(function () {
  var oSoAnh = document.querySelector('[data-so-anh]');
  if (!oSoAnh) return;
  function capNhat() {
    var chon = document.querySelector('input[name=LoaiHauKy]:checked');
    oSoAnh.hidden = !chon || chon.value !== oSoAnh.dataset.gioiHan;
  }
  document.querySelectorAll('input[name=LoaiHauKy]').forEach(function (r) { r.addEventListener('change', capNhat); });
  capNhat();
})();

// 3) Popup xác nhận cho Ngừng áp dụng / Áp dụng lại / Ẩn / Hiện lại / Xóa. Không có JS hoặc <dialog> thì link vẫn mở trang xác nhận.
(function () {
  var hop = document.getElementById('gv-popup');
  if (!hop || typeof hop.showModal !== 'function') return;
  var form = document.getElementById('gv-popup-form');
  var nutXacNhan = document.getElementById('gv-popup-xac-nhan');
  document.querySelectorAll('a[data-xac-nhan]').forEach(function (a) {
    a.addEventListener('click', function (e) {
      e.preventDefault();
      form.action = a.href;
      document.getElementById('gv-popup-tieu-de').textContent = a.dataset.tieuDe;
      document.getElementById('gv-popup-hoi').textContent = a.dataset.cauHoi;
      nutXacNhan.textContent = a.dataset.nut;
      nutXacNhan.className = 'btn btn--' + (a.dataset.kieu === 'danger' ? 'danger' : 'primary');
      hop.showModal();
    });
  });
  hop.querySelectorAll('[data-dong]').forEach(function (n) { n.addEventListener('click', function () { hop.close(); }); });
  hop.addEventListener('click', function (e) { if (e.target === hop) hop.close(); });   // bấm ra ngoài khung thì đóng
  form.addEventListener('submit', function () { nutXacNhan.disabled = true; });          // tránh bấm 2 lần
})();

// 4) Menu thao tác: chỉ mở một menu một lúc, tự đóng khi bấm ra ngoài / Esc / cuộn; đặt vị trí fixed để không bị bảng cắt.
(function () {
  var cacMenu = document.querySelectorAll('details.gv-menu');
  function dong(tru) { cacMenu.forEach(function (m) { if (m !== tru) m.open = false; }); }
  cacMenu.forEach(function (m) {
    m.addEventListener('toggle', function () {
      var ds = m.querySelector('.gv-menu__ds');
      if (!m.open) { ds.classList.remove('is-fixed'); ds.style.top = ds.style.left = ''; return; }
      dong(m);
      var o = m.querySelector('summary').getBoundingClientRect();
      ds.classList.add('is-fixed');
      var r = ds.getBoundingClientRect();
      var trai = Math.min(Math.max(8, o.left + o.width / 2 - r.width / 2), window.innerWidth - r.width - 8);
      var duoi = o.bottom + 4;
      if (duoi + r.height > window.innerHeight - 8 && o.top - r.height - 4 > 8) duoi = o.top - r.height - 4;   // hết chỗ phía dưới thì mở lên trên
      ds.style.left = trai + 'px';
      ds.style.top = duoi + 'px';
    });
  });
  document.addEventListener('click', function (e) { if (!e.target.closest('details.gv-menu')) dong(null); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') dong(null); });
  window.addEventListener('scroll', function () { dong(null); }, { passive: true });
  window.addEventListener('resize', function () { dong(null); });
  // Chọn một mục có popup thì đóng menu trước khi mở popup.
  document.querySelectorAll('.gv-menu a[data-xac-nhan]').forEach(function (a) { a.addEventListener('click', function () { dong(null); }); });
})();
