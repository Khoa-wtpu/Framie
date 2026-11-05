// bookings/static/bookings/js/gui_booking.js - UC4.2: ô "Gói dịch vụ" (đã nhóm theo loại hình).
//   1) Khóa các gói dài hơn khung giờ đang giữ (option có data-khoa; giá trị data-khoa là lý do, đã ghi trong chữ của option).
//   2) Khi chọn gói, hiện khung chi tiết (#goi-chi-tiet): mô tả, thời lượng, hậu kỳ, giá, giờ bắt đầu muộn nhất.
// Nạp bằng <script src="{% static 'bookings/js/gui_booking.js' %}" defer></script> trong block extra_js của gui_booking.html.
// Mỗi <option> của gói mang data-* do GoiSelect (bookings/gui_booking.py) gắn; ô "-- Chọn gói --" thì không có.
// Chọn ô theo name (goi) nên không phụ thuộc id do Django sinh ra. Nội dung điền bằng textContent (không dùng innerHTML)
// vì mô tả gói do Nhiếp ảnh gia nhập.
(function () {
  var form = document.getElementById('form-gui-booking');
  if (!form) return;
  var goi = form.elements['goi'];
  var chiTiet = document.getElementById('goi-chi-tiet');
  if (!goi) return;

  // Server đã gắn disabled cho gói bị khóa; làm lại ở đây để chắc chắn, và bỏ chọn nếu gói đang chọn là gói bị khóa
  // (xảy ra khi trang được vẽ lại sau lỗi và trình duyệt giữ lại lựa chọn cũ).
  function khoaGoiQuaDai() {
    Array.prototype.forEach.call(goi.options, function (o) {
      if (o.getAttribute('data-khoa')) o.disabled = true;
    });
    var dangChon = goi.options[goi.selectedIndex];
    if (dangChon && dangChon.disabled) goi.value = '';
  }

  function dien(truong, noiDung) {
    var el = chiTiet.querySelector('[data-truong="' + truong + '"]');
    if (el) el.textContent = noiDung;
  }

  function hienChiTiet() {
    if (!chiTiet) return;
    var o = goi.options[goi.selectedIndex];
    if (!o || !o.value) {                              // chưa chọn gói -> ẩn khung chi tiết
      chiTiet.hidden = true;
      return;
    }
    dien('ten', o.getAttribute('data-ten') || '');
    dien('loai-hinh', o.getAttribute('data-loai-hinh') ? '(' + o.getAttribute('data-loai-hinh') + ')' : '');
    dien('mo-ta', o.getAttribute('data-mo-ta') || 'Nhiếp ảnh gia chưa ghi mô tả cho gói này.');
    dien('thoi-luong', o.getAttribute('data-thoi-luong') || '');
    dien('hau-ky', o.getAttribute('data-hau-ky') || '');
    dien('gia', o.getAttribute('data-gia') || '');
    dien('gio-muon-nhat', o.getAttribute('data-gio-muon-nhat') || '');
    chiTiet.hidden = false;
  }

  goi.addEventListener('change', hienChiTiet);
  khoaGoiQuaDai();
  hienChiTiet();                                       // vẽ ngay khi tải trang (gói chọn sẵn từ ?goi= hoặc sau khi form báo lỗi)
})();
