// schedule/static/schedule/js/lich.js - K10
// Popup xác nhận xóa khung giờ. Không có JS hoặc <dialog> thì nút "Xóa" vẫn mở trang xác nhận riêng.
(function () {
  var hop = document.getElementById('lich-popup');
  if (!hop || typeof hop.showModal !== 'function') return;
  var form = document.getElementById('lich-popup-form');
  var nutXacNhan = document.getElementById('lich-popup-xac-nhan');
  document.querySelectorAll('a[data-xac-nhan]').forEach(function (a) {
    a.addEventListener('click', function (e) {
      e.preventDefault();
      form.action = a.href;
      document.getElementById('lich-popup-tieu-de').textContent = a.dataset.tieuDe;
      document.getElementById('lich-popup-hoi').textContent = a.dataset.cauHoi;
      nutXacNhan.textContent = a.dataset.nut;
      nutXacNhan.disabled = false;
      hop.showModal();
    });
  });
  hop.querySelectorAll('[data-dong]').forEach(function (n) { n.addEventListener('click', function () { hop.close(); }); });
  hop.addEventListener('click', function (e) { if (e.target === hop) hop.close(); });   // bấm ra ngoài khung thì đóng
  form.addEventListener('submit', function () { nutXacNhan.disabled = true; });          // tránh bấm 2 lần
})();
