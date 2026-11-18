// core/static/core/js/khu_vuc.js - F3: ô tìm nhanh trong danh sách 34 tỉnh thành (không phân biệt dấu, hoa/thường).
// Không có JS vẫn dùng được: ô tìm bị ẩn, 34 mục luôn hiện, hộp tích/radio vẫn gửi form như thường.
(function () {
  'use strict';
  var boDau = function (s) {  // 'Đà Nẵng' -> 'da nang'
    return String(s).toLowerCase().replace(/đ/g, 'd').normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  };
  var danhSach = function (goc, chon) { return Array.prototype.slice.call(goc.querySelectorAll(chon)); };

  danhSach(document, '[data-loc-khu-vuc]').forEach(function (goc) {
    var khungTim = goc.querySelector('[data-loc-tim]');
    var o = goc.querySelector('[data-loc-o]');
    var trong = goc.querySelector('[data-loc-trong]');
    if (!khungTim || !o) { return; }
    khungTim.hidden = false;  // có JS mới hiện ô tìm
    var muc = danhSach(goc, '[data-loc-muc]');
    var mien = danhSach(goc, '[data-loc-mien]');

    var loc = function () {
      var tu = boDau(o.value.trim());
      var con = 0;
      muc.forEach(function (m) {
        var khop = !tu || boDau(m.textContent).indexOf(tu) !== -1;
        m.hidden = !khop;
        if (khop) { con += 1; }
      });
      mien.forEach(function (n) {  // ẩn tiêu đề miền khi không còn mục nào
        n.hidden = !n.querySelector('[data-loc-muc]:not([hidden])');
      });
      if (trong) { trong.hidden = con > 0; }
    };

    o.addEventListener('input', loc);
    o.addEventListener('keydown', function (e) {  // Enter trong ô tìm không được gửi cả form
      if (e.key === 'Enter') { e.preventDefault(); }
    });
  });
})();
