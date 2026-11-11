// notifications/static/notifications/thong_bao.js - P8: bấm sao / đã đọc / xóa ở trang danh sách và chi tiết không tải lại cả trang
(function () {  // bọc trong hàm để biến không rò ra ngoài
 var vung = document.querySelector('[data-tb-vung]');  // vùng nội dung sẽ được thay (giữ nguyên thẻ này, chỉ thay ruột)
 if (!vung) return;  // trang này không có vùng thông báo thì thôi
 var dangGui = false;  // khóa: đang xử lý một lần bấm thì bỏ qua lần bấm dồn
 var hopXoa = document.querySelector('[data-xoa-hop]');  // hộp xác nhận xóa (chỉ có ở trang danh sách, trang chi tiết thì là null)
 var formXoaCho = null;  // form xóa đang chờ người dùng xác nhận


 // ---------- Menu thả xuống ("…" và "Lọc thông báo") trong vùng ----------
 // Vì ruột vùng bị thay bằng HTML mới, các nút mới sẽ không còn sự kiện do app.js gắn sẵn.
 // Nên file này tự lo việc mở/đóng menu TRONG vùng (nghe ở document nên nút mới vẫn chạy).
 function dongMenuTrongVung(tru) {  // đóng mọi menu trong vùng, trừ menu 'tru'
   vung.querySelectorAll('[data-dropdown]').forEach(function (dd) {  // duyệt từng khối dropdown
     if (dd === tru) return;  // giữ nguyên khối được chọn
     var m = dd.querySelector('[data-dropdown-menu]');  // phần menu
     var t = dd.querySelector('[data-dropdown-toggle]');  // nút mở menu
     if (m) m.hidden = true;  // ẩn menu
     if (t) t.setAttribute('aria-expanded', 'false');  // báo trình đọc màn hình là đã đóng
   });
 }


 document.addEventListener('click', function (e) {  // bắt ở giai đoạn capture: chạy trước app.js
   var nut = e.target.closest ? e.target.closest('[data-dropdown-toggle]') : null;  // có bấm trúng nút mở menu không
   if (nut && vung.contains(nut)) {  // nút nằm trong vùng thông báo
     e.preventDefault();  // chặn hành vi mặc định
     e.stopPropagation();  // chặn app.js xử lý thêm lần nữa (tránh mở rồi đóng ngay)
     var dd = nut.closest('[data-dropdown]');  // khối dropdown chứa nút
     var menu = dd && dd.querySelector('[data-dropdown-menu]');  // menu của khối đó
     if (!menu) return;  // không có menu thì thôi
     var seMo = menu.hidden;  // đang ẩn thì lần này sẽ mở
     document.querySelectorAll('[data-dropdown-menu]').forEach(function (m) {  // đóng các menu khác trên trang (menu tài khoản...)
       if (m !== menu) m.hidden = true;  // ẩn menu khác
     });
     dongMenuTrongVung(dd);  // đóng các menu khác trong vùng
     menu.hidden = !seMo;  // đảo trạng thái menu này
     nut.setAttribute('aria-expanded', seMo ? 'true' : 'false');  // cập nhật nhãn trình đọc màn hình
     return;  // xong
   }
   if (!e.target.closest || !e.target.closest('[data-tb-vung] [data-dropdown]')) dongMenuTrongVung(null);  // bấm ra ngoài thì đóng hết
 }, true);  // true = capture


 document.addEventListener('keydown', function (e) {  // phím bấm
   if (e.key === 'Escape') dongMenuTrongVung(null);  // Esc đóng menu
 });


 // ---------- Tải ngầm lại vùng nội dung ----------
 function lamMoi(url) {  // tải ngầm lại trang rồi thay đúng vùng nội dung
   return fetch(url, { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } })  // lấy HTML mới (url của trang chi tiết đã kèm giu=1 nên không tự đánh dấu đã đọc)
     .then(function (res) {  // nhận phản hồi
       if (!res.ok) throw new Error('HTTP ' + res.status);  // mã lỗi thì nhảy xuống catch
       return res.text();  // lấy nội dung HTML
     })
     .then(function (html) {  // có HTML mới
       var doc = new DOMParser().parseFromString(html, 'text/html');  // đọc HTML thành cây DOM (chưa hiện ra)
       var moi = doc.querySelector('[data-tb-vung]');  // vùng nội dung bản mới
       if (!moi) throw new Error('thiếu vùng nội dung');  // không tìm thấy thì coi như lỗi
       vung.innerHTML = moi.innerHTML;  // thay nội dung: danh sách, số nhóm, nút, nhãn đều được cập nhật
       var chuongMoi = doc.querySelector('[data-bell-toggle]');  // chuông bản mới (chứa số chưa đọc)
       var chuongCu = document.querySelector('[data-bell-toggle]');  // chuông đang hiện
       if (chuongMoi && chuongCu) {  // có cả hai
         chuongCu.innerHTML = chuongMoi.innerHTML;  // cập nhật chấm số đỏ (giữ nguyên thẻ <a> nên chuong.js vẫn chạy)
         chuongCu.setAttribute('aria-label', chuongMoi.getAttribute('aria-label') || '');  // cập nhật nhãn cho trình đọc màn hình
       }
       history.replaceState(null, '', url);  // địa chỉ trên thanh trình duyệt khớp trạng thái mới (F5 không tự đánh dấu đã đọc)
     });
 }


 document.addEventListener('submit', function (e) {  // bắt mọi form gửi đi (nghe ở document nên form mới thay vào vẫn chạy)
   var form = e.target;  // form vừa bấm
   if (!form.matches || !form.matches('form[data-tb-form]')) return;  // chỉ xử lý form sao / đã đọc / xóa của trang này
   e.preventDefault();  // chặn tải lại cả trang
   if (dangGui) return;  // đang xử lý lần trước thì bỏ qua
   if (form.hasAttribute('data-tb-xoa') && !form.dataset.daXacNhan) {  // form xóa mà chưa được xác nhận
     if (hopXoa && typeof hopXoa.showModal === 'function') {  // trình duyệt có hộp thoại <dialog>
       formXoaCho = form;  // nhớ form đang chờ xác nhận
       dongMenuTrongVung(null);  // đóng menu "…" cho gọn
       hopXoa.showModal();  // hiện hộp hỏi lại
       return;  // dừng ở đây, chờ người dùng bấm Xác nhận xóa hoặc Hủy
     }
     if (!window.confirm('Xóa thông báo này? Không thể khôi phục.')) return;  // dự phòng cho trình duyệt cũ hoặc trang thiếu hộp
   }
   dangGui = true;  // khóa
   var oNext = form.querySelector('[name="next"]');  // ô địa chỉ quay lại mà server đã điền sẵn
   var url = oNext && oNext.value ? oNext.value : window.location.href;  // trang cần tải lại
   fetch(form.action, { method: 'POST', body: new FormData(form), credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } })  // gửi ngầm (FormData đã có csrf token)
     .then(function (res) {  // nhận kết quả
       if (!res.ok) throw new Error('HTTP ' + res.status);  // server báo lỗi thì nhảy xuống catch
       return lamMoi(url);  // thành công: tải lại vùng nội dung
     })
     .catch(function () { form.submit(); })  // lỗi gì cũng quay về cách cũ: gửi form thường để hiện hộp lỗi đỏ
     .then(function () { dangGui = false; delete form.dataset.daXacNhan; });  // mở khóa và bỏ cờ xác nhận
 });


 // ---------- Hộp xác nhận xóa (cùng kiểu .modal với popup đăng xuất) ----------
 if (hopXoa) {  // chỉ chạy khi trang có hộp xác nhận
   hopXoa.addEventListener('click', function (e) {  // bấm bên trong hộp
     if (e.target.closest('[data-xoa-dong-y]') && formXoaCho) {  // bấm nút "Xác nhận xóa"
       var f = formXoaCho;  // lấy form đang chờ
       formXoaCho = null;  // xóa trạng thái chờ
       f.dataset.daXacNhan = '1';  // đánh dấu đã xác nhận để lần gửi sau không hỏi nữa
       hopXoa.close();  // đóng hộp
       f.requestSubmit();  // gửi form lại (chạy lại handler submit, lần này đi tiếp)
     } else if (e.target.closest('[data-xoa-huy]') || e.target === hopXoa) {  // bấm "Hủy" hoặc bấm vùng mờ
       formXoaCho = null;  // bỏ việc đang chờ
       hopXoa.close();  // đóng hộp, không xóa gì
     }
   });
   hopXoa.addEventListener('close', function () { formXoaCho = null; });  // Esc cũng hủy việc đang chờ
 }
})();
