/* static/js/theme.js - chuyển nền Trắng / Đen. Mặc định ĐEN; lựa chọn của người dùng nhớ trong trình duyệt.
   File này được nạp ĐỒNG BỘ ở đầu <head> (base.html) để đặt data-theme trước khi trang được vẽ, tránh chớp nền. */
(function () {
  'use strict';
  var KEY = 'framie-theme';
  var goc = document.documentElement;

  function doc() {                       // đọc lựa chọn đã lưu (có thể bị chặn ở chế độ riêng tư)
    try { return window.localStorage.getItem(KEY); } catch (loi) { return null; }
  }

  function ap(cheDo) {                   // đặt chế độ và cập nhật nút chuyển
    goc.setAttribute('data-theme', cheDo);
    document.querySelectorAll('[data-theme-toggle]').forEach(function (nut) {
      var den = cheDo !== 'light';
      nut.setAttribute('aria-checked', String(den));
      nut.setAttribute('aria-label', den ? 'Nền đen' : 'Nền trắng');
    });
  }

  ap(doc() === 'light' ? 'light' : 'dark');                                    // chưa chọn gì thì là Đen
  document.addEventListener('DOMContentLoaded', function () { ap(goc.getAttribute('data-theme')); });   // nút chuyển chỉ có sau khi trang dựng xong

  document.addEventListener('click', function (e) {
    var nut = e.target.closest('[data-theme-toggle]');
    if (!nut) return;
    var moi = goc.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
    ap(moi);
    try { window.localStorage.setItem(KEY, moi); } catch (loi) { /* không lưu được thì chỉ đổi cho lần xem này */ }
  });

  window.addEventListener('storage', function (e) {   // mở nhiều tab: đổi ở tab này thì tab kia đổi theo
    if (e.key === KEY) ap(e.newValue === 'light' ? 'light' : 'dark');
  });
})();
