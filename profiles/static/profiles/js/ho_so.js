/* profiles/static/profiles/js/ho_so.js - xem trước ảnh vừa chọn trong ô tải ảnh (K3, Khoa). */
(function () {
  if (window.__hoSoJs) return;              // chỉ gắn một lần dù trang nhúng nhiều đoạn template
  window.__hoSoJs = true;
  document.addEventListener('change', function (e) {
    var o = e.target;
    if (!o.classList || !o.classList.contains('ho-so__tep')) return;
    var nhan = o.closest('.ho-so__tai-len');
    var tep = o.files && o.files[0];
    nhan.querySelector('.ho-so__ten-tep').textContent = tep ? tep.name : '';
    var khung = nhan.querySelector('.ho-so__xem-truoc');
    if (tep && tep.type.indexOf('image/') === 0) {
      khung.innerHTML = '';
      var anh = document.createElement('img');
      anh.src = URL.createObjectURL(tep);
      anh.alt = '';
      khung.appendChild(anh);
    }
  });
})();
