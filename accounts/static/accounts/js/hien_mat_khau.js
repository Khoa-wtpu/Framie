/* accounts/static/accounts/js/hien_mat_khau.js - thêm nút con mắt (hiện/ẩn chữ) vào các ô mật khẩu trong form có data-hien-mat-khau. */
(function () {
  var MAT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';
  var MAT_GACH = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M17.94 17.94A10.94 10.94 0 0 1 12 20C5 20 1 12 1 12a18.5 18.5 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.1 9.1 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><path d="M14.12 14.12a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>';

  function themNut(o) {
    var bao = document.createElement('div');
    bao.className = 'mk-bao';
    o.parentNode.insertBefore(bao, o);
    bao.appendChild(o);
    var nut = document.createElement('button');
    nut.type = 'button';
    nut.className = 'mk-nut';
    nut.setAttribute('aria-label', 'Hiện mật khẩu');
    nut.setAttribute('aria-pressed', 'false');
    nut.innerHTML = MAT;
    nut.addEventListener('click', function () {
      var dangAn = o.type === 'password';
      o.type = dangAn ? 'text' : 'password';
      nut.innerHTML = dangAn ? MAT_GACH : MAT;
      nut.setAttribute('aria-label', dangAn ? 'Ẩn mật khẩu' : 'Hiện mật khẩu');
      nut.setAttribute('aria-pressed', dangAn ? 'true' : 'false');
    });
    bao.appendChild(nut);
  }

  document.addEventListener('DOMContentLoaded', function () {
    var o = document.querySelectorAll('form[data-hien-mat-khau] input[type="password"]');
    for (var i = 0; i < o.length; i++) themNut(o[i]);
  });
})();