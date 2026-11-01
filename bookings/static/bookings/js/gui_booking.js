// bookings/static/bookings/js/gui_booking.js - UC4.2: lọc ô "Gói dịch vụ" theo ô "Loại hình chụp" đã chọn.
// Nạp bằng <script src="{% static 'bookings/js/gui_booking.js' %}" defer></script> trong block extra_js của gui_booking.html.
// Mỗi <option> của gói có data-loai-hinh (do GoiSelect trong bookings/gui_booking.py gắn); ô "-- Chọn gói --" thì không có.
// Chọn ô theo name (loai_hinh, goi) nên không phụ thuộc id do Django sinh ra.
(function () {
  var form = document.getElementById('form-gui-booking');
  if (!form) return;
  var loaiHinh = form.elements['loai_hinh'];
  var goi = form.elements['goi'];
  if (!loaiHinh || !goi) return;

  // Giữ bản sao toàn bộ option ban đầu để lọc được nhiều lần (xóa option khỏi <select> là mất).
  var tatCaGoi = Array.prototype.slice.call(goi.options).map(function (o) {
    return o.cloneNode(true);
  });

  function locGoi() {
    var chon = goi.value;                              // nhớ gói đang chọn
    goi.innerHTML = '';
    tatCaGoi.forEach(function (o) {
      var lh = o.getAttribute('data-loai-hinh');
      // Giữ ô "-- Chọn --" (không có data-loai-hinh) và các gói đúng loại hình đang chọn.
      if (!lh || lh === loaiHinh.value) goi.appendChild(o.cloneNode(true));
    });
    goi.value = chon;                                  // khôi phục lựa chọn nếu gói đó còn trong danh sách
    if (goi.value !== chon) goi.value = '';            // không còn thì về trạng thái chưa chọn
  }

  loaiHinh.addEventListener('change', locGoi);
  locGoi();                                            // lọc ngay khi tải trang cho khớp loại hình hiện tại
})();
