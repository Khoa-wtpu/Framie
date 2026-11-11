// bookings/static/bookings/js/han_dat_coc.js - C2: thanh đếm ngược HẠN ĐẶT CỌC (1 ngày) trên trang chi tiết Booking.
// Dùng chung cho trang Khách hàng (/bookings/cua-toi/<mã>/) và trang Nhiếp ảnh gia (/bookings/quan-ly/<mã>/).
// Nạp bằng <script src="{% static 'bookings/js/han_dat_coc.js' %}" defer></script> trong block extra_js.
//
// Trang nạp script này phải có các phần tử sau (đúng id) - xem bookings/includes/dem_nguoc_han_coc.html:
//   #han-coc         data-con-lai = số giây còn lại do SERVER tính (không tin đồng hồ máy khách); data-tong = tổng thời hạn (giây)
//   #han-coc-so      nơi hiện "giờ:phút:giây"
//   #han-coc-thanh   <progress> thanh tiến trình (giảm dần về 0)
//   #han-coc-het     đoạn chữ "Đã hết hạn..." (đang bị ẩn, hiện ra khi về 0)
(function () {                                                    // bọc trong hàm tự chạy để biến không rò ra ngoài
  var goc = document.getElementById('han-coc');                   // khối đếm ngược
  if (!goc) return;                                               // trang không có khối này (không ở "Chờ đặt cọc") thì thôi
  var so = document.getElementById('han-coc-so');                 // chỗ hiện số đếm ngược
  var thanh = document.getElementById('han-coc-thanh');           // thanh tiến trình
  var het = document.getElementById('han-coc-het');               // dòng báo đã hết hạn
  var tong = parseInt(goc.dataset.tong, 10) || 1;                 // tổng thời hạn (giây); mặc định 1 để tránh chia cho 0
  // Mốc kết thúc tính từ số giây SERVER gửi; performance.now() đo thời gian trôi qua ổn định, không phụ thuộc giờ máy người dùng.
  var hanChot = performance.now() + (parseInt(goc.dataset.conLai, 10) || 0) * 1000;
  var KHOA_TAI_LAI = 'han-coc-tai-lai-' + location.pathname;      // khóa nhớ "đã tải lại trang một lần" cho đúng Booking này

  // Số giây -> "HH:MM:SS" (3725 -> "01:02:05").
  function dinhDang(s) {
    var g = Math.floor(s / 3600), p = Math.floor((s % 3600) / 60), gi = s % 60;  // tách giờ, phút, giây
    function hai(n) { return (n < 10 ? '0' : '') + n; }                           // thêm số 0 đứng trước cho đủ 2 chữ số
    return hai(g) + ':' + hai(p) + ':' + hai(gi);
  }

  // Cập nhật số đếm, thanh tiến trình và màu cảnh báo mỗi nhịp.
  function nhay() {
    var con = Math.max(0, Math.ceil((hanChot - performance.now()) / 1000));  // số giây còn lại, không âm
    so.textContent = dinhDang(con);                                           // in số "HH:MM:SS"
    thanh.max = tong;                                                         // thanh dài bằng tổng thời hạn
    thanh.value = con;                                                        // phần còn lại của thanh
    goc.classList.toggle('is-gap', con > 0 && con <= 3600);                   // còn dưới 1 giờ: đổi sang màu đỏ cho dễ thấy
    if (con === 0) {                                                          // hết hạn
      goc.classList.add('is-het-han');                                        // đổi sang kiểu "đã hết hạn"
      if (het) het.hidden = false;                                            // hiện dòng báo hết hạn
      clearInterval(nhip);                                                    // dừng đồng hồ
      // Tải lại ĐÚNG MỘT LẦN để server chuyển Booking sang "Hết thời hạn đặt cọc"; có cờ để không tải lại vô hạn nếu server chưa kịp đổi.
      if (!sessionStorage.getItem(KHOA_TAI_LAI)) {
        sessionStorage.setItem(KHOA_TAI_LAI, '1');                            // đánh dấu đã tải lại
        setTimeout(function () { location.reload(); }, 3000);                 // chờ 3 giây cho người dùng kịp đọc rồi tải lại
      }
    }
  }

  nhay();                                                         // hiện ngay khi tải trang, không chờ nhịp đầu tiên
  var nhip = setInterval(nhay, 500);                              // 0,5 giây/lần để số chuyển giây mượt
})();
