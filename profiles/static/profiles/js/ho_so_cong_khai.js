// profiles/static/profiles/js/ho_so_cong_khai.js - K9
// (1) Trang hồ sơ: tô đậm mục đang xem trên thanh mục (Giới thiệu / Gói / Portfolio / Lịch / Đánh giá).
// (2) Trang project: xem ảnh phóng to (phím ← → Esc). Không có JS thì bấm ảnh sẽ mở bản gốc ở tab mới.
(function () {
  var tabs = document.querySelectorAll('.hscc__tabs a');
  if (tabs.length && 'IntersectionObserver' in window) {
    var theoMa = {};
    tabs.forEach(function (a) { theoMa[a.getAttribute('href').slice(1)] = a; });
    var quanSat = new IntersectionObserver(function (cacMuc) {
      cacMuc.forEach(function (m) {
        if (!m.isIntersecting) return;
        tabs.forEach(function (a) { a.removeAttribute('aria-current'); });
        var a = theoMa[m.target.id];
        if (a) a.setAttribute('aria-current', 'true');
      });
    }, { rootMargin: '-30% 0px -60% 0px' });
    Object.keys(theoMa).forEach(function (ma) { var el = document.getElementById(ma); if (el) quanSat.observe(el); });
  }

  var hop = document.getElementById('hscc-lightbox');
  var cacAnh = Array.prototype.slice.call(document.querySelectorAll('[data-lightbox]'));
  if (!hop || typeof hop.showModal !== 'function' || !cacAnh.length) return;
  var anh = document.getElementById('hscc-lightbox-anh');
  var so = document.getElementById('hscc-lightbox-so');
  var viTri = 0;
  function hien(i) {
    viTri = (i + cacAnh.length) % cacAnh.length;
    var a = cacAnh[viTri];
    anh.src = a.href;
    anh.alt = a.querySelector('img').alt;
    so.textContent = (viTri + 1) + ' / ' + cacAnh.length;
  }
  cacAnh.forEach(function (a, i) {
    a.addEventListener('click', function (e) { e.preventDefault(); hien(i); hop.showModal(); });
  });
  hop.querySelector('[data-lb-dong]').addEventListener('click', function () { hop.close(); });
  hop.querySelector('[data-lb-truoc]').addEventListener('click', function () { hien(viTri - 1); });
  hop.querySelector('[data-lb-sau]').addEventListener('click', function () { hien(viTri + 1); });
  hop.addEventListener('click', function (e) { if (e.target === hop) hop.close(); });       // bấm vùng tối thì đóng
  hop.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowLeft') hien(viTri - 1);
    if (e.key === 'ArrowRight') hien(viTri + 1);
  });
})();
