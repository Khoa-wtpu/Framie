// notifications/static/notifications/chuong.js - P8: khung chuông thả xuống (tải bằng fetch khi bấm chuông)
(function () {  // bọc trong hàm để biến không rò ra ngoài
  var goc = document.querySelector('[data-bell]');  // khối chứa chuông trong header
  if (!goc) return;  // không có chuông (chưa đăng nhập) thì thôi
  var nut = goc.querySelector('[data-bell-toggle]');  // chính là thẻ <a> chuông (vẫn có href sang trang danh sách)
  var menu = goc.querySelector('[data-bell-menu]');  // khung thả xuống
  var url = goc.getAttribute('data-khung-url');  // địa chỉ lấy mảnh HTML (rỗng nếu chưa nối urls)
  if (!nut || !menu || !url) return;  // thiếu gì thì bỏ qua: chuông vẫn là link thường tới trang danh sách

  function dong() {  // đóng khung
    menu.hidden = true;  // ẩn menu
    nut.setAttribute('aria-expanded', 'false');  // báo trình đọc màn hình là đã đóng
  }

  function hienLoi() {  // tải lỗi: hiện dòng báo ngắn kèm nút Thử lại (đúng wireframe)
    menu.innerHTML = '<p class="tb-khung__loi">Không thể tải thông báo.' +  // dòng báo lỗi
      ' <button type="button" class="tb-khung__thu-lai" data-bell-retry>Thử lại</button></p>' +  // nút thử lại
      '<a class="tb-khung__chan" href="' + nut.getAttribute('href') + '">Xem tất cả thông báo</a>';  // vẫn có đường sang trang danh sách
  }

  function tai() {  // lấy danh sách mới nhất từ server
    menu.innerHTML = '<p class="tb-khung__rong muted">Đang tải...</p>';  // chữ chờ
    fetch(url, { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } })  // gọi server kèm cookie đăng nhập
      .then(function (res) {  // nhận phản hồi
        if (!res.ok) throw new Error('HTTP ' + res.status);  // mã lỗi thì nhảy xuống catch
        return res.text();  // lấy nội dung HTML
      })
      .then(function (html) { menu.innerHTML = html; })  // HTML do Django dựng và đã thoát ký tự nên an toàn khi gắn vào
      .catch(hienLoi);  // mọi lỗi (mạng, 401, 500) đều hiện câu báo lỗi
  }

  nut.addEventListener('click', function (e) {  // bấm chuông
    if (e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey) return;  // Ctrl/Shift/chuột giữa: để trình duyệt mở link bình thường
    e.preventDefault();  // chặn việc nhảy trang, thay bằng khung thả xuống
    if (!menu.hidden) { dong(); return; }  // đang mở thì bấm lần nữa là đóng
    menu.hidden = false;  // mở khung
    nut.setAttribute('aria-expanded', 'true');  // báo trình đọc màn hình là đang mở
    tai();  // lấy dữ liệu mới
  });

  menu.addEventListener('click', function (e) {  // bấm bên trong khung
    if (e.target.closest('[data-bell-retry]')) tai();  // bấm "Thử lại" thì tải lại
  });

  menu.addEventListener('submit', function (e) {  // bấm ★ trong khung: gửi ngầm rồi tải lại khung (sao lên đầu ngay)
    var form = e.target.closest('[data-bell-star]');  // chỉ xử lý form sao của khung chuông
    if (!form) return;  // form khác thì để yên
    e.preventDefault();  // chặn chuyển trang
    fetch(form.action, { method: 'POST', body: new FormData(form), credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } })  // FormData đã có csrfmiddlewaretoken
      .then(function (res) { if (!res.ok) throw new Error('HTTP ' + res.status); tai(); })  // xong thì lấy lại danh sách đã sắp xếp
      .catch(hienLoi);  // lỗi thì hiện dòng báo + nút Thử lại
  });

  document.addEventListener('click', function (e) {  // bấm ra ngoài
    if (!goc.contains(e.target)) dong();  // ngoài khối chuông thì đóng khung (kể cả khi bấm menu tài khoản)
  }, true);  // true = bắt ở giai đoạn capture: chạy TRƯỚC app.js, nên không bị e.stopPropagation() của menu tài khoản chặn mất

  document.addEventListener('keydown', function (e) {  // phím bấm
    if (e.key === 'Escape') dong();  // Esc đóng khung
  });
})();
