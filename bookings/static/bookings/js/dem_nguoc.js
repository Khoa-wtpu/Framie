// bookings/static/bookings/js/dem_nguoc.js - UC4.1 + UC4.2: đồng hồ đếm ngược thời gian giữ chỗ,
// dùng chung cho giu_cho.html (màn hình giữ chỗ) và gui_booking.html (trang gửi yêu cầu Booking).
// Nạp bằng <script src="{% static 'bookings/js/dem_nguoc.js' %}" defer></script> trong block extra_js.
//
// Trang nạp script này phải có các phần tử sau (đúng id):
//   #dem-nguoc         data-con-lai = số giây còn lại do SERVER tính (không tin đồng hồ máy khách)
//                      data-url     = URL API JSON trạng thái giữ chỗ (view trang_thai_giu_cho)
//                      data-an      = id khối cần ẨN khi hết hạn   (giu_cho: khoi-dang-giu, gui_booking: form-gui-booking)
//                      data-hien    = id khối cần HIỆN khi hết hạn (cả hai trang: khoi-het-han)
//   #dem-nguoc-so      nơi hiện số phút:giây
//   #dem-nguoc-thanh   <progress> thanh tiến trình
(function () {
  var goc = document.getElementById('dem-nguoc');
  if (!goc) return;                                    // trang không có đồng hồ thì thôi
  var so = document.getElementById('dem-nguoc-so');
  var thanh = document.getElementById('dem-nguoc-thanh');
  var url = goc.dataset.url;

  // Mốc kết thúc tính từ số giây server gửi. Dùng performance.now() để đo thời gian trôi qua ổn định,
  // không phụ thuộc việc người dùng chỉnh giờ máy tính.
  var hanChot = performance.now() + parseInt(goc.dataset.conLai, 10) * 1000;
  var dangHoi = false;                                 // đang có một yêu cầu gọi server: không gửi chồng thêm

  // Số giây -> "MM:SS" (65 -> "01:05").
  function dinhDang(s) {
    var p = Math.floor(s / 60), g = s % 60;
    return (p < 10 ? '0' : '') + p + ':' + (g < 10 ? '0' : '') + g;
  }

  // Server xác nhận đã hết hạn: dừng đồng hồ, ẩn khối đang thao tác, hiện thông báo hết hạn.
  function hetHan() {
    clearInterval(nhip);
    clearInterval(nhipDongBo);
    var an = document.getElementById(goc.dataset.an);
    var hien = document.getElementById(goc.dataset.hien);
    if (an) an.hidden = true;
    if (hien) hien.hidden = false;
  }

  // Hỏi server trạng thái thật của lượt giữ chỗ (việc nhả slot quá hạn xảy ra ở phía server).
  function hoiServer() {
    if (dangHoi) return;
    dangHoi = true;
    fetch(url, {credentials: 'same-origin', headers: {'Accept': 'application/json'}})
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.con_lai_giay > 0) {                      // còn thời gian: đồng bộ lại mốc đếm ngược theo server
          hanChot = performance.now() + d.con_lai_giay * 1000;
        } else if (d.het_han) {                        // server xác nhận hết hạn
          hetHan();
        } else {                                       // không còn "Đang giữ chỗ" vì lý do khác (vd đã gửi Booking): tải lại để trang cập nhật
          window.location.reload();
        }
      })
      .catch(function () {})                           // mất mạng: bỏ qua, lần đồng bộ sau thử lại
      .then(function () { dangHoi = false; });
  }

  // Cập nhật số đếm ngược và thanh tiến trình; về 0 thì hỏi server để xác nhận.
  function nhay() {
    var con = Math.max(0, Math.ceil((hanChot - performance.now()) / 1000));
    so.textContent = dinhDang(con);
    thanh.value = con;
    if (con === 0) hoiServer();
  }

  nhay();                                              // hiện ngay khi tải trang, không chờ nhịp đầu tiên
  var nhip = setInterval(nhay, 250);                   // 250 ms/lần để số chuyển giây mượt
  var nhipDongBo = setInterval(function () {           // cứ 30 giây đồng bộ với server, chỉ khi tab đang hiển thị
    if (!document.hidden) hoiServer();
  }, 30000);
})();
