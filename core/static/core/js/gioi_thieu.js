/* core/static/core/js/gioi_thieu.js - Trang Giới thiệu. Không có JS thì trang vẫn dùng được (link # và câu hỏi mở bằng tay). */
/* 1) Tô sáng mục mục lục tương ứng phần đang đọc. 2) Mở câu hỏi (details) khi địa chỉ có # trỏ tới câu đó. */
(function () {
  'use strict';

  var links = document.querySelectorAll('[data-gt-muc-luc] a[href^="#"]');  // các link của thanh mục lục
  var muc = [];                                                             // cặp {link, phần tương ứng}
  links.forEach(function (a) {
    var phan = document.getElementById(a.getAttribute('href').slice(1));
    if (phan) { muc.push({ link: a, phan: phan }); }
  });

  function dat_dang_xem(phan) {                                             // chỉ link của phần đang xem được sáng
    muc.forEach(function (m) {
      var sang = m.phan === phan;
      m.link.classList.toggle('is-active', sang);
      if (sang) { m.link.setAttribute('aria-current', 'true'); } else { m.link.removeAttribute('aria-current'); }
    });
  }

  if ('IntersectionObserver' in window && muc.length) {
    // Dải quan sát nằm ở khoảng 25% đến 35% chiều cao màn hình: phần nào đang chạm dải đó là phần đang đọc.
    var theo_doi = new IntersectionObserver(function (cac_muc) {
      cac_muc.forEach(function (e) { if (e.isIntersecting) { dat_dang_xem(e.target); } });
    }, { rootMargin: '-25% 0px -65% 0px' });
    muc.forEach(function (m) { theo_doi.observe(m.phan); });
  }

  function mo_cau_hoi() {                                                   // link kiểu /gioi-thieu/#hoi-thoi-han thì mở sẵn câu đó
    var ma = decodeURIComponent(window.location.hash.slice(1));
    var phan_tu = ma ? document.getElementById(ma) : null;
    if (phan_tu && phan_tu.tagName === 'DETAILS') { phan_tu.open = true; }
  }
  window.addEventListener('hashchange', mo_cau_hoi);
  mo_cau_hoi();

  // Bấm link trong trang trỏ tới câu hỏi (vd. "Câu hỏi thường gặp" ở bước 5): hashchange sẽ mở câu đó.
})();
