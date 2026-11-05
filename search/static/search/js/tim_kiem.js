// search/static/search/js/tim_kiem.js - K8 v2
//  1) Nút "Bộ lọc" (nằm trong ô tìm kiếm) mở/đóng bảng bộ lọc; Esc hoặc bấm ra ngoài thì đóng.
//     Không có JS thì bảng luôn hiện sẵn (CSS chỉ ẩn nó khi form có class tim--js).
//  2) Đổi cách sắp xếp thì tự tìm lại (không có JS thì dùng nút "Sắp xếp" trong <noscript>).
(function () {
  var form = document.getElementById('form-tim-kiem');
  var nut = document.getElementById('nut-bo-loc');
  var bang = document.getElementById('bang-bo-loc');
  if (form && nut && bang) {
    form.classList.add('tim--js');
    function dat(mo) {
      bang.hidden = !mo;
      nut.setAttribute('aria-expanded', mo ? 'true' : 'false');
    }
    dat(bang.getAttribute('data-mo') === '1');                        // mặc định thu gọn (có lỗi nhập thì mở sẵn)
    nut.addEventListener('click', function () { dat(bang.hidden); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !bang.hidden) { dat(false); nut.focus(); }
    });
    document.addEventListener('click', function (e) {
      if (!bang.hidden && !form.querySelector('.tim__tim-kiem').contains(e.target)) dat(false);
    });
  }
  document.querySelectorAll('select[data-tu-gui]').forEach(function (o) {
    o.addEventListener('change', function () { o.form.submit(); });
  });
})();
