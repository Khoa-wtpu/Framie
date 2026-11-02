// schedule/static/schedule/js/lich.js - K10
// (1) Ô khung giờ trong lưới tuần: bấm / Enter để hiện hoặc ẩn "Chỉnh sửa" và "Xóa" (rê chuột và Tab đã do CSS lo).
// (2) Popup xác nhận xóa. Không có JS hoặc <dialog> thì nút "Xóa" vẫn mở trang xác nhận riêng.
(function () {
  var cacO = document.querySelectorAll('[data-thao-tac]');
  function dongTatCa(tru) { cacO.forEach(function (o) { if (o !== tru) o.classList.remove('is-mo'); }); }
  cacO.forEach(function (o) {
    o.addEventListener('click', function (e) {
      if (e.target.closest('a')) return;                 // bấm vào nút Sửa / Xóa thì để liên kết tự chạy
      dongTatCa(o);
      o.classList.toggle('is-mo');
    });
    o.addEventListener('keydown', function (e) {
      if (e.target === o && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); dongTatCa(o); o.classList.toggle('is-mo'); }
    });
  });
  document.addEventListener('click', function (e) { if (!e.target.closest('[data-thao-tac]')) dongTatCa(null); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') dongTatCa(null); });

  var hop = document.getElementById('lich-popup');
  if (!hop || typeof hop.showModal !== 'function') return;
  var form = document.getElementById('lich-popup-form');
  var nutXacNhan = document.getElementById('lich-popup-xac-nhan');
  document.querySelectorAll('a[data-xac-nhan]').forEach(function (a) {
    a.addEventListener('click', function (e) {
      e.preventDefault();
      dongTatCa(null);
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
