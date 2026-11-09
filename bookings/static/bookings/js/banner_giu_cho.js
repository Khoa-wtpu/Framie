(function () { // Đếm ngược cho ô giữ chỗ dùng chung (số giây còn lại do server tính, không tin đồng hồ máy khách)
  'use strict';
  var o = document.getElementById('banner-giu-cho'); // ô đếm ngược
  if (!o) return; // trang không có ô thì dừng
  var phutEl = o.querySelector('[data-gc-phut]');
  var giayEl = o.querySelector('[data-gc-giay]');
  var nhoEl = o.querySelector('[data-gc-nho]'); // giờ rút gọn khi thu gọn
  var chu = o.querySelector('[data-gc-chu]'); // dòng khung giờ + Nhiếp ảnh gia
  var nut = o.querySelector('.gc-timer__nut'); // nút Tiếp tục đặt lịch
  var nutDong = o.querySelector('[data-gc-dong]'); // nút Đóng (chỉ hiện khi hết hạn)
  var nutThuGon = o.querySelector('[data-gc-thu-gon]');
  var dong = o.querySelector('[data-gc-dem]');
  var docEl = o.querySelector('[data-gc-doc]'); // vùng đọc cho trình đọc màn hình
  var conLai = parseInt(o.getAttribute('data-con-lai'), 10); // số giây còn lại lúc tải trang
  var tong = parseInt(o.getAttribute('data-tong'), 10); // tổng thời gian giữ chỗ (để vẽ thanh tiến độ)
  if (isNaN(conLai) || !phutEl || !giayEl) return;
  if (isNaN(tong) || tong < conLai || tong <= 0) tong = Math.max(conLai, 1);

  var hanChot = Date.now() + conLai * 1000; // mốc hết giờ theo đồng hồ trình duyệt, tính từ số giây server đưa
  var daHetHan = false;
  var timer = null;
  var giayCu = -1;
  var daBao = {}; // các mốc đã thông báo cho trình đọc màn hình

  function hai(n) { return (n < 10 ? '0' : '') + n; }
  function bao(chuoi) { if (docEl) docEl.textContent = chuoi; }

  function veTrangThai(con) { // đổi màu theo mức khẩn cấp: bình thường -> sắp hết (<=60s) -> gấp (<=30s)
    o.classList.toggle('is-sap-het', con <= 60 && con > 30);
    o.classList.toggle('is-gap', con <= 30);
    if (con <= 60 && !daBao[60]) { daBao[60] = true; bao('Còn dưới 1 phút để hoàn tất đặt lịch.'); }
    if (con <= 30 && !daBao[30]) { daBao[30] = true; bao('Còn 30 giây.'); }
  }

  function ve(con) { // vẽ giờ + thanh tiến độ
    phutEl.textContent = hai(Math.floor(con / 60));
    giayEl.textContent = hai(con % 60);
    if (nhoEl) nhoEl.textContent = hai(Math.floor(con / 60)) + ':' + hai(con % 60);
    o.style.setProperty('--tien-do', (Math.max(0, Math.min(1, con / tong)) * 100).toFixed(2) + '%');
    veTrangThai(con);
  }

  function hetHan() { // hết giờ: gọi API để server nhả slot, rồi báo cho Khách
    if (daHetHan) return;
    daHetHan = true;
    clearInterval(timer);
    var url = o.getAttribute('data-url-trang-thai');
    if (url && window.fetch) {
      fetch(url, { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } }).catch(function () {});
    }
    ve(0);
    var thongBao = o.getAttribute('data-het-han-chu');
    chu.textContent = thongBao; // textContent: không chèn HTML
    bao(thongBao);
    if (nut) nut.hidden = true;
    if (nutDong) nutDong.hidden = false;
    if (dong) dong.removeAttribute('aria-hidden');
    o.classList.remove('is-sap-het', 'is-gap', 'is-thu-gon');
    o.classList.add('is-het-han');
    if (nutThuGon) nutThuGon.hidden = true;
  }

  function chay() { // chạy 4 lần/giây để không bị lệch khi tab bị trình duyệt làm chậm; chỉ vẽ lại khi đổi giây
    var con = Math.ceil((hanChot - Date.now()) / 1000);
    if (con <= 0) { hetHan(); return; }
    if (con !== giayCu) { giayCu = con; ve(con); }
  }

  // ---- Thu gọn / mở rộng (nhớ trong phiên làm việc của tab) ----
  function datThuGon(thu) {
    o.classList.toggle('is-thu-gon', thu);
    if (nutThuGon) {
      nutThuGon.setAttribute('aria-expanded', thu ? 'false' : 'true');
      nutThuGon.setAttribute('aria-label', thu ? 'Mở rộng ô đếm ngược' : 'Thu gọn ô đếm ngược');
      nutThuGon.setAttribute('title', thu ? 'Mở rộng' : 'Thu gọn');
    }
    try { sessionStorage.setItem('gc-thu-gon', thu ? '1' : '0'); } catch (e) { /* trình duyệt chặn lưu: bỏ qua */ }
  }
  if (nutThuGon) {
    nutThuGon.addEventListener('click', function () { datThuGon(!o.classList.contains('is-thu-gon')); });
  }
  if (nutDong) {
    nutDong.addEventListener('click', function () { o.remove(); });
  }
  try { if (sessionStorage.getItem('gc-thu-gon') === '1') datThuGon(true); } catch (e) { /* bỏ qua */ }

  timer = setInterval(chay, 250);
  chay();
})();
