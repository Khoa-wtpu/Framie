// delivery/static/delivery/js/so_sanh_truoc_sau.js - E10: thanh kéo so sánh ảnh trước/sau (không dùng thư viện)
// Bấm nút "So sánh trước/sau" -> nạp hai ảnh vào hộp, ô range điều khiển biến CSS --vi-tri (CSS dùng clip-path cắt ảnh Trước).
// JS chỉ gán biến CSS (--vi-tri, --ti-le), không viết style trực tiếp.
(function () {
  'use strict';
  var hop = document.getElementById('so-sanh-hop');
  if (!hop) return; // trang không có ảnh nào có bản trước

  var khung = document.getElementById('so-sanh-khung');
  var thanh = document.getElementById('so-sanh-thanh');
  var ten = document.getElementById('so-sanh-ten');
  var loi = document.getElementById('so-sanh-loi');
  var anhTruoc = khung.querySelector('.so-sanh__anh--truoc');
  var anhSau = khung.querySelector('.so-sanh__anh--sau');

  function datViTri(giaTri) { // gán vị trí thanh kéo (0-100) cho CSS và cho trình đọc màn hình
    var v = Math.max(0, Math.min(100, Number(giaTri) || 0));
    khung.style.setProperty('--vi-tri', v + '%');
    thanh.setAttribute('aria-valuetext', 'Hiện ' + Math.round(v) + '% ảnh Trước, ' + Math.round(100 - v) + '% ảnh Sau');
  }

  function datTiLe() { // khung lấy tỉ lệ của ảnh Sau; ảnh Trước co vào cùng khung (object-fit: contain)
    if (anhSau.naturalWidth && anhSau.naturalHeight) {
      khung.style.setProperty('--ti-le', (anhSau.naturalWidth / anhSau.naturalHeight).toFixed(4));
    }
  }

  thanh.addEventListener('input', function () { datViTri(thanh.value); });
  anhSau.addEventListener('load', datTiLe);
  function baoLoi() { loi.hidden = false; }
  anhSau.addEventListener('error', baoLoi);
  anhTruoc.addEventListener('error', baoLoi);

  function mo(nut) { // nạp ảnh theo nút vừa bấm rồi mở hộp
    loi.hidden = true;
    ten.textContent = nut.getAttribute('data-so-sanh-ten') || '';
    khung.style.removeProperty('--ti-le'); // quay về tỉ lệ mặc định cho tới khi ảnh Sau tải xong
    thanh.value = 50;
    datViTri(50);
    anhSau.src = nut.getAttribute('data-so-sanh-sau');
    anhTruoc.src = nut.getAttribute('data-so-sanh-truoc');
    if (anhSau.complete) datTiLe(); // ảnh đã có trong bộ nhớ trình duyệt
    hop.showModal();
    thanh.focus(); // dùng được ngay bằng phím ← →
  }

  document.querySelectorAll('.so-sanh-mo').forEach(function (nut) {
    nut.addEventListener('click', function () { mo(nut); });
  });
  hop.querySelector('.so-sanh__dong').addEventListener('click', function () { hop.close(); });
  hop.addEventListener('click', function (e) { if (e.target === hop) hop.close(); }); // bấm nền tối để đóng
  hop.addEventListener('close', function () { // đóng thì bỏ ảnh để không giữ bộ nhớ
    anhSau.removeAttribute('src');
    anhTruoc.removeAttribute('src');
  });
})();
