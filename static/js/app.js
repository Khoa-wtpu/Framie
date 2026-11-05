(function () {  // bọc toàn bộ code trong hàm tự chạy để không lẫn biến toàn cục
  var header = document.querySelector('.site-header');  // lấy phần đầu trang (thanh menu)
  var navBtn = document.querySelector('[data-nav-toggle]');  // lấy nút bật/tắt menu trên điện thoại
  if (navBtn && header) {  // chỉ chạy khi trang có cả menu và nút
    navBtn.addEventListener('click', function () {  // khi bấm nút menu
      var open = header.classList.toggle('is-open');  // bật/tắt class mở menu và lưu trạng thái
      navBtn.setAttribute('aria-expanded', String(open));  // báo trạng thái mở/đóng cho trình đọc màn hình
    });
  }

  function closeDropdowns(except) {  // hàm đóng tất cả menu thả xuống (trừ menu được chỉ định)
    document.querySelectorAll('[data-dropdown]').forEach(function (dd) {  // duyệt từng menu thả xuống
      if (dd === except) return;  // bỏ qua menu đang được mở
      dd.querySelector('[data-dropdown-menu]').hidden = true;  // ẩn danh sách menu
      dd.querySelector('[data-dropdown-toggle]').setAttribute('aria-expanded', 'false');  // báo là đang đóng
    });
  }
  document.querySelectorAll('[data-dropdown]').forEach(function (dd) {  // gắn sự kiện cho từng menu thả xuống
    var btn = dd.querySelector('[data-dropdown-toggle]');  // nút bấm để mở menu
    var menu = dd.querySelector('[data-dropdown-menu]');  // danh sách menu
    btn.addEventListener('click', function (e) {  // khi bấm nút menu
      e.stopPropagation();  // không cho sự kiện lan ra ngoài (tránh bị đóng ngay)
      closeDropdowns(dd);  // đóng các menu khác
      menu.hidden = !menu.hidden;  // đảo trạng thái ẩn/hiện của menu này
      btn.setAttribute('aria-expanded', String(!menu.hidden));  // cập nhật trạng thái mở/đóng
    });
  });
  document.addEventListener('click', function (e) {  // khi bấm bất kỳ chỗ nào trên trang
    if (!e.target.closest('[data-dropdown]')) closeDropdowns();  // bấm ra ngoài menu thì đóng hết menu
    var close = e.target.closest('[data-dismiss]');  // kiểm tra có bấm nút tắt thông báo không
    if (close) close.closest('.alert').remove();  // bấm nút tắt thì xóa khung thông báo
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeDropdowns(); });  // nhấn Esc thì đóng menu

  function khoiPhucNutGui(form) {  // HÀM MỚI: trả form về trạng thái bình thường (hết xoay, được gửi lại)
    delete form.dataset.submitting;  // gỡ cờ "đang gửi"
    form.querySelectorAll('.is-loading').forEach(function (b) { b.classList.remove('is-loading'); });  // gỡ vòng xoay trên các nút
  }
  window.khoiPhucNutGui = khoiPhucNutGui;  // MỚI: cho các file JS khác gọi lại khi cần

  // Chống bấm đúp nút gửi form: lần gửi đầu thêm is-loading cho nút, các lần bấm sau bị chặn.
  document.addEventListener('submit', function (e) {  // khi bất kỳ form nào được gửi
    var form = e.target;  // lấy form đang gửi
    if (e.defaultPrevented) return;  // MỚI: form đã bị chặn bởi code khác (vd: form tải ảnh gửi bằng XHR) thì không bật vòng xoay
    if (form.dataset.submitting === 'true') {   // đã gửi rồi -> chặn gửi lần nữa
      e.preventDefault();  // chặn lần gửi thứ hai
      return;  // dừng
    }
    form.dataset.submitting = 'true';  // đánh dấu form đang gửi
    var btn = e.submitter || form.querySelector('button[type="submit"]');  // tìm nút vừa bấm
    if (btn) btn.classList.add('is-loading');  // thêm vòng xoay cho nút
  });

  // Trang được hiện lại thì trả mọi form về trạng thái bình thường.
  window.addEventListener('pageshow', function () {  // SỬA: bỏ điều kiện e.persisted, trang nào hiện lại cũng khôi phục
    document.querySelectorAll('form[data-submitting]').forEach(khoiPhucNutGui);  // khôi phục tất cả form đang bị kẹt xoay
  });
})();  // kết thúc hàm tự chạy