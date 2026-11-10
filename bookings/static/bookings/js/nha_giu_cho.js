// bookings/static/bookings/js/nha_giu_cho.js - UC4.1 + UC4.2: nhả slot đang giữ NGAY khi Khách rời trang đặt lịch,
// để đồng hồ đếm ngược 5 phút không còn treo ở trang khác. Dùng chung cho giu_cho.html và gui_booking.html.
//
// Trang nạp script này phải có <form id="form-huy-giu-cho" action="/bookings/giu-cho/<mã>/huy/"> (có csrf_token).
// Khách bấm "Chọn khung giờ khác" -> nút submit chính form đó (server nhả slot rồi chuyển về trang lịch).
// Khách đóng tab / gõ địa chỉ khác / bấm link khác -> sự kiện pagehide gửi form đó bằng sendBeacon (nhanh=1).
//
// KHÔNG nhả khi Khách đang đi tiếp trong luồng đặt lịch: phần tử có thuộc tính data-giu-tiep
// (nút "Tiếp tục gửi yêu cầu Booking", form gửi Booking) sẽ đặt cờ đang chuyển trang.
(function () {
  var form = document.getElementById('form-huy-giu-cho');
  if (!form) return;
  var dangDiTiep = false;                              // đang đi tiếp trong luồng đặt lịch: không nhả
  var daGui = false;                                   // chỉ gửi beacon một lần

  document.addEventListener('click', function (e) {
    if (e.target.closest && e.target.closest('[data-giu-tiep]')) dangDiTiep = true;
  });
  document.addEventListener('submit', function (e) {
    // form gửi Booking (data-giu-tiep) hoặc chính form nhả (server đã nhả rồi, khỏi gửi beacon nữa)
    if (e.target === form || e.target.hasAttribute('data-giu-tiep')) dangDiTiep = true;
  });

  window.addEventListener('pagehide', function () {
    if (dangDiTiep || daGui || !navigator.sendBeacon) return;
    daGui = true;
    var du_lieu = new FormData(form);                  // đã có csrfmiddlewaretoken
    du_lieu.append('nhanh', '1');                      // báo server chỉ cần trả 204
    navigator.sendBeacon(form.action, du_lieu);
  });

  // Quay lại bằng nút Back (trang lấy từ bộ nhớ đệm): tải lại để hiện trạng thái thật của lượt giữ chỗ.
  window.addEventListener('pageshow', function (e) {
    if (e.persisted) window.location.reload();
  });
})();
