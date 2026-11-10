// Lightbox xem ảnh dùng chung (cửa sổ phóng to ngay trong trang, không mở tab mới, không đổi link).
// Cách dùng: thêm thuộc tính data-xem-lon vào thẻ <a href="..."> hoặc <button data-xem-lon="đường dẫn ảnh">; mọi phần tử như vậy trong trang tạo thành 1 nhóm ảnh.
// Chế độ có ô nhận xét (chỉ trang "Yêu cầu chỉnh sửa"): thêm data-xem-lon-ghi-chu="id ô nhận xét của ảnh" và data-xem-lon-tick="id ô tick của ảnh";
// khi đó cửa sổ chia 2/1: bên trái là ảnh, bên phải là ô nhập nhận xét RIÊNG của ảnh đang xem, đồng bộ hai chiều với ô nhận xét ngoài trang.
(function () {
  'use strict'; // bật chế độ nghiêm ngặt để bắt lỗi sớm
  var nguon = Array.prototype.slice.call(document.querySelectorAll('[data-xem-lon]')); // tất cả ảnh có thể phóng to trong trang, theo thứ tự xuất hiện
  if (!nguon.length || !window.HTMLDialogElement) return; // không có ảnh hoặc trình duyệt quá cũ: giữ nguyên link mở tab mới như cũ

  function duongDan(el) { return el.getAttribute('data-xem-lon') || el.getAttribute('href') || ''; } // đường dẫn ảnh lớn: lấy từ data-xem-lon, không có thì lấy href
  function tenAnh(el) { var img = el.querySelector('img'); return el.getAttribute('data-ten') || (img && img.alt) || ''; } // tên hiển thị dưới ảnh: lấy từ data-ten hoặc alt của ảnh nhỏ
  var ds = nguon.map(function (el) { // danh sách ảnh của nhóm
    return { url: duongDan(el), ten: tenAnh(el), ghiChuId: el.getAttribute('data-xem-lon-ghi-chu') || '', tickId: el.getAttribute('data-xem-lon-tick') || '' }; // đường dẫn, tên, id ô nhận xét và ô tick (nếu có)
  });
  var coGhiChu = ds.some(function (a) { return a.ghiChuId; }); // có ảnh nào dùng chế độ nhận xét không
  var hop = null; // thẻ dialog, chỉ tạo khi mở lần đầu
  var anhLon, tenLon, nutDong, nutTruoc, nutSau, dai, cacNho = []; // các phần tử bên trong hộp
  var bang, bangTen, bangChon, bangO, bangDem, bangLoi; // các phần tử của bảng nhận xét bên phải (chế độ nhận xét)
  var viTri = 0; // vị trí ảnh đang xem trong danh sách
  var chamX = null; // vị trí chạm ngón tay lúc bắt đầu vuốt (điện thoại)

  function taoNut(lop, nhan, chu) { // hàm tiện ích tạo nút bấm có class và nhãn đọc màn hình
    var b = document.createElement('button'); // tạo thẻ button
    b.type = 'button'; b.className = lop; b.setAttribute('aria-label', nhan); b.textContent = chu || ''; // gán loại, class, nhãn, chữ
    return b; // trả về nút
  }

  function oNgoai() { var a = ds[viTri]; return a.ghiChuId ? document.getElementById(a.ghiChuId) : null; } // ô nhận xét ngoài trang của ảnh đang xem
  function tickNgoai() { var a = ds[viTri]; return a.tickId ? document.getElementById(a.tickId) : null; } // ô tick ngoài trang của ảnh đang xem
  function phatSuKien(el, ten) { el.dispatchEvent(new Event(ten, { bubbles: true })); } // bắn sự kiện giả để code của trang (đếm ký tự, tự tick, cập nhật nút gửi) chạy như người dùng thao tác

  function lamMoiTrangThaiBang() { // cập nhật đếm ký tự, ô tick và dòng đỏ trong bảng nhận xét (KHÔNG ghi đè nội dung đang gõ)
    var o = oNgoai(), tick = tickNgoai(); // ô ngoài trang tương ứng
    var toiDa = (o && o.maxLength > 0) ? o.maxLength : 500; // số ký tự tối đa
    bangDem.textContent = bangO.value.length + '/' + toiDa; // dòng đếm "n/500"
    bangChon.checked = !!(tick && tick.checked); // ô tick trong bảng giống ô tick ngoài trang
    bangChon.disabled = !tick; // không có ô tick ngoài trang thì khóa
    bangLoi.hidden = !(bangChon.checked && bangO.value.trim() === ''); // ảnh đã chọn mà chưa nhập nhận xét thì hiện dòng đỏ
  }

  function napBang() { // nạp bảng nhận xét theo ảnh đang xem (gọi mỗi lần đổi ảnh)
    var o = oNgoai(); // ô nhận xét ngoài trang của ảnh này
    hop.classList.toggle('xal--co-ghi-chu', !!o); // có ô nhận xét thì chia màn hình 2/1, không có thì ảnh chiếm hết
    bang.hidden = !o; // ẩn/hiện bảng bên phải
    if (!o) return; // ảnh này không có nhận xét: dừng
    bangTen.textContent = ds[viTri].ten; // tên ảnh đang xem
    bangO.value = o.value; // nội dung nhận xét hiện có
    bangO.maxLength = o.maxLength > 0 ? o.maxLength : 500; // giới hạn ký tự giống ô ngoài trang
    bangO.placeholder = o.placeholder || ''; // chữ gợi ý giống ô ngoài trang
    lamMoiTrangThaiBang(); // cập nhật đếm, tick, dòng đỏ
  }

  function taoBang() { // dựng bảng nhận xét bên phải
    bang = document.createElement('aside'); bang.className = 'xal__ghi-chu'; bang.hidden = true; // khung bảng, mặc định ẩn
    var tieuDe = document.createElement('h2'); tieuDe.className = 'xal__ghi-chu-tieu-de'; tieuDe.textContent = 'Nội dung cần chỉnh'; // tiêu đề bảng
    bangTen = document.createElement('p'); bangTen.className = 'xal__ghi-chu-ten'; // tên ảnh đang xem
    var nhanChon = document.createElement('label'); nhanChon.className = 'xal__ghi-chu-chon'; // nhãn bọc ô tick
    bangChon = document.createElement('input'); bangChon.type = 'checkbox'; // ô tick chọn ảnh này để chỉnh sửa
    nhanChon.appendChild(bangChon); nhanChon.appendChild(document.createTextNode(' Chọn ảnh này để chỉnh sửa')); // ghép ô tick và chữ
    bangO = document.createElement('textarea'); bangO.className = 'xal__ghi-chu-o'; bangO.rows = 8; bangO.setAttribute('aria-label', 'Nội dung cần chỉnh của ảnh đang xem'); // ô nhập nhận xét riêng của ảnh
    bangDem = document.createElement('div'); bangDem.className = 'xal__ghi-chu-dem'; // dòng đếm ký tự
    bangLoi = document.createElement('p'); bangLoi.className = 'xal__ghi-chu-loi'; bangLoi.textContent = 'Vui lòng nhập nhận xét'; bangLoi.hidden = true; bangLoi.setAttribute('role', 'alert'); // dòng đỏ nhắc nhập nhận xét
    [tieuDe, bangTen, nhanChon, bangO, bangDem, bangLoi].forEach(function (x) { bang.appendChild(x); }); // lắp các phần vào bảng
    bangO.addEventListener('input', function () { // gõ trong bảng
      var o = oNgoai(); // ô nhận xét ngoài trang
      if (o) { o.value = bangO.value; phatSuKien(o, 'input'); } // ghi sang ô ngoài trang và để code của trang tự tick, đếm, cập nhật nút gửi
      lamMoiTrangThaiBang(); // cập nhật đếm, tick, dòng đỏ (ô tick có thể vừa được tự tick)
    });
    bangChon.addEventListener('change', function () { // tick / bỏ tick trong bảng
      var tick = tickNgoai(); // ô tick ngoài trang
      if (tick) { tick.checked = bangChon.checked; phatSuKien(tick, 'change'); } // ghi sang ô tick ngoài trang
      lamMoiTrangThaiBang(); // cập nhật dòng đỏ
    });
  }

  function taoHop() { // dựng cửa sổ phóng to (chỉ làm một lần)
    hop = document.createElement('dialog'); hop.className = 'xal'; hop.setAttribute('aria-label', 'Xem ảnh phóng to'); // thẻ dialog dùng chung
    nutDong = taoNut('xal__dong', 'Đóng (phím Esc)', '✕'); // nút X tắt cửa sổ
    nutTruoc = taoNut('xal__chuyen xal__chuyen--truoc', 'Ảnh trước (phím ←)', '‹'); // nút < sang ảnh trước
    nutSau = taoNut('xal__chuyen xal__chuyen--sau', 'Ảnh sau (phím →)', '›'); // nút > sang ảnh sau
    var benAnh = document.createElement('div'); benAnh.className = 'xal__ben-anh'; // phần bên trái: nút < ảnh nút >
    var khung = document.createElement('figure'); khung.className = 'xal__khung'; // khung chứa ảnh lớn và chú thích
    anhLon = document.createElement('img'); anhLon.className = 'xal__anh'; anhLon.alt = ''; anhLon.draggable = false; // ảnh lớn
    tenLon = document.createElement('figcaption'); tenLon.className = 'xal__ten'; // dòng "3 / 8 · tên ảnh"
    khung.appendChild(anhLon); khung.appendChild(tenLon); // ghép ảnh và chú thích vào khung
    benAnh.appendChild(nutTruoc); benAnh.appendChild(khung); benAnh.appendChild(nutSau); // lắp phần bên trái
    dai = document.createElement('div'); dai.className = 'xal__dai'; dai.setAttribute('role', 'tablist'); dai.setAttribute('aria-label', 'Danh sách ảnh'); // dải ảnh nhỏ phía dưới
    ds.forEach(function (a, i) { // tạo một ảnh nhỏ cho từng ảnh trong nhóm
      var n = taoNut('xal__nho', 'Xem ảnh ' + (i + 1) + (a.ten ? ': ' + a.ten : '')); // nút bọc ảnh nhỏ
      var h = document.createElement('img'); h.src = a.url + (a.url.indexOf('?') < 0 ? '?nho=1' : '&nho=1'); h.alt = ''; h.loading = 'lazy'; h.draggable = false; // ảnh thu nhỏ (cỡ nhỏ cho nhẹ)
      n.appendChild(h); // gắn ảnh vào nút
      n.addEventListener('click', function () { chuyen(i); }); // bấm ảnh nhỏ thì chuyển tới ảnh đó
      dai.appendChild(n); cacNho.push(n); // thêm vào dải và nhớ lại để đổi trạng thái chọn
    });
    hop.appendChild(nutDong); hop.appendChild(benAnh); // lắp nút X và phần ảnh vào hộp
    if (coGhiChu) { taoBang(); hop.appendChild(bang); } // có chế độ nhận xét thì dựng thêm bảng bên phải
    hop.appendChild(dai); // lắp dải ảnh nhỏ cuối cùng
    nutDong.addEventListener('click', function () { hop.close(); }); // bấm X thì đóng
    nutTruoc.addEventListener('click', function () { chuyen(viTri - 1); }); // bấm < thì lùi 1 ảnh
    nutSau.addEventListener('click', function () { chuyen(viTri + 1); }); // bấm > thì tiến 1 ảnh
    hop.addEventListener('click', function (e) { if (e.target === hop) hop.close(); }); // bấm vào vùng tối ngoài ảnh thì đóng
    hop.addEventListener('keydown', function (e) { // phím tắt khi đang mở
      var dangGo = /^(TEXTAREA|INPUT)$/.test(e.target.tagName || ''); // đang gõ trong ô nhận xét thì mũi tên/Home/End phải dành cho con trỏ chữ, không đổi ảnh
      if (dangGo) return; // bỏ qua phím tắt chuyển ảnh (Esc vẫn đóng được vì trình duyệt tự xử lý)
      if (e.key === 'ArrowLeft') { e.preventDefault(); chuyen(viTri - 1); } // mũi tên trái: ảnh trước
      else if (e.key === 'ArrowRight') { e.preventDefault(); chuyen(viTri + 1); } // mũi tên phải: ảnh sau
      else if (e.key === 'Home') { e.preventDefault(); chuyen(0); } // Home: ảnh đầu
      else if (e.key === 'End') { e.preventDefault(); chuyen(ds.length - 1); } // End: ảnh cuối
    });
    hop.addEventListener('touchstart', function (e) { // điện thoại: nhớ chỗ bắt đầu chạm
      chamX = (e.target.closest && e.target.closest('.xal__ghi-chu')) ? null : e.changedTouches[0].clientX; // chạm trong bảng nhận xét thì không tính là vuốt đổi ảnh
    }, { passive: true });
    hop.addEventListener('touchend', function (e) { // điện thoại: vuốt ngang để chuyển ảnh
      if (chamX === null) return; // không có điểm bắt đầu thì bỏ qua
      var dx = e.changedTouches[0].clientX - chamX; chamX = null; // quãng vuốt ngang
      if (Math.abs(dx) > 50) chuyen(viTri + (dx < 0 ? 1 : -1)); // vuốt sang trái = ảnh sau, sang phải = ảnh trước
    }, { passive: true });
    hop.addEventListener('close', function () { anhLon.removeAttribute('src'); }); // đóng thì bỏ ảnh để giải phóng bộ nhớ
    document.body.appendChild(hop); // đưa hộp vào trang
  }

  function chuyen(i) { // hiển thị ảnh thứ i (đi vòng: hết ảnh cuối quay về ảnh đầu)
    viTri = (i + ds.length) % ds.length; // chuẩn hóa vị trí trong khoảng 0..n-1
    var a = ds[viTri]; // ảnh cần hiện
    anhLon.src = a.url + (a.url.indexOf('?') < 0 ? '?vua=1' : '&vua=1'); // nạp ảnh cỡ vừa (nhẹ hơn ảnh gốc, vẫn rõ khi phóng to)
    anhLon.alt = a.ten; // chữ thay thế cho người dùng đọc màn hình
    tenLon.textContent = (viTri + 1) + ' / ' + ds.length + (a.ten ? ' · ' + a.ten : ''); // dòng chú thích: số thứ tự và tên ảnh
    cacNho.forEach(function (n, k) { // cập nhật ảnh nhỏ nào đang được chọn
      n.classList.toggle('xal__nho--chon', k === viTri); // viền cam cho ảnh đang xem
      n.setAttribute('aria-current', k === viTri ? 'true' : 'false'); // báo cho trình đọc màn hình biết ảnh hiện tại
    });
    cacNho[viTri].scrollIntoView({ block: 'nearest', inline: 'center' }); // cuộn dải ảnh nhỏ để ảnh đang xem luôn nằm trong tầm nhìn
    nutTruoc.hidden = nutSau.hidden = ds.length < 2; // chỉ có 1 ảnh thì ẩn hai nút < >
    dai.hidden = ds.length < 2; // chỉ có 1 ảnh thì ẩn luôn dải ảnh nhỏ
    if (coGhiChu) napBang(); // chế độ nhận xét: nạp nhận xét của ảnh vừa chuyển tới
  }

  nguon.forEach(function (el, i) { // gắn sự kiện bấm cho từng ảnh trong trang
    el.addEventListener('click', function (e) {
      e.preventDefault(); // không mở link / không sang trang mới
      e.stopPropagation(); // không để thẻ label bên ngoài tick nhầm ô chọn ảnh
      if (!hop) taoHop(); // lần đầu mở thì dựng hộp
      chuyen(i); // hiện đúng ảnh vừa bấm
      if (!hop.open) hop.showModal(); // mở cửa sổ ngay trong trang
    });
  });
})();
