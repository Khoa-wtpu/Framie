(function () { // Đếm ngược cho banner giữ chỗ dùng chung (số giây còn lại do server tính, không tin đồng hồ máy khách)
  'use strict';
  var banner = document.getElementById('banner-giu-cho'); // khung banner
  if (!banner) return; // trang không có banner thì dừng
  var dem = banner.querySelector('[data-gc-dem]'); // chỗ hiện mm:ss
  var chu = banner.querySelector('.gc-banner__chu'); // dòng chữ chính
  var nut = banner.querySelector('.gc-banner__nut'); // nút Tiếp tục đặt lịch
  var tong = parseInt(banner.getAttribute('data-con-lai'), 10); // số giây còn lại lúc tải trang
  if (isNaN(tong) || !dem) return;
  var batDau = Date.now(); // mốc lúc tải trang
  var daHetHan = false;
  var dongHo = null;
  function dinhDang(giay) { // 125 -> "02:05"
    var p = Math.floor(giay / 60), g = giay % 60;
    return (p < 10 ? '0' : '') + p + ':' + (g < 10 ? '0' : '') + g;
  }
  function hetHan() { // hết giờ: gọi API để server nhả slot, rồi báo cho Khách
    if (daHetHan) return;
    daHetHan = true;
    clearInterval(dongHo);
    var url = banner.getAttribute('data-url-trang-thai');
    if (url && window.fetch) {
      fetch(url, { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } }).catch(function () {});
    }
    chu.textContent = banner.getAttribute('data-het-han-chu'); // textContent: không chèn HTML
    if (nut) nut.hidden = true;
    banner.classList.add('is-het-han');
  }
  function chay() {
    var con = tong - Math.round((Date.now() - batDau) / 1000);
    if (con <= 0) { hetHan(); return; }
    dem.textContent = dinhDang(con);
  }
  dongHo = setInterval(chay, 1000);
  chay();
})();
