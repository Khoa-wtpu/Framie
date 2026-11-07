// N4 / UC5.3: gửi ảnh bằng AJAX, hiện thanh tiến trình và lỗi ngay trên form.
// Quy tắc: MỌI nhánh kết thúc của việc gửi (400, lỗi mạng, hủy, quá thời gian, thiếu ảnh...) đều gọi ketThuc()
// để nút Tải ảnh lên hết xoay và bấm lại được. Chỉ nhánh thành công (chuyển trang) mới giữ nguyên trạng thái xoay.
(function () {
  'use strict';
  var form = document.getElementById('form-tai-anh');
  if (!form) return;
  var thanh = document.getElementById('thanh-tien-trinh');
  var chu = document.getElementById('chu-tien-trinh');
  var khungLoi = document.getElementById('khung-loi');
  var nut = document.getElementById('nut-tai');
  var dangGui = false;

  // Trả form về trạng thái bình thường: nút hết xoay, bấm lại được, ẩn thanh tiến trình.
  function ketThuc() {
    dangGui = false;
    nut.classList.remove('is-loading');
    nut.disabled = false;
    delete form.dataset.submitting;   // cờ chống bấm đúp của static/js/app.js
    thanh.hidden = true;
    thanh.value = 0;
    chu.textContent = '';
  }

  // Hộp thông báo đỏ giống includes/alert.html (level="danger"); nhiều lỗi thì liệt kê thành danh sách.
  function hienLoi(ds) {
    khungLoi.textContent = '';
    var hop = document.createElement('div');
    hop.className = 'alert alert--danger';
    hop.setAttribute('role', 'alert');
    var than = document.createElement('div');
    than.className = 'alert__body';
    if (ds.length === 1) {
      var chuLoi = document.createElement('span');
      chuLoi.className = 'alert__text';
      chuLoi.textContent = ds[0];
      than.appendChild(chuLoi);
    } else {
      var danhSach = document.createElement('ul');
      danhSach.className = 'tai-anh__ds-loi';
      ds.forEach(function (noiDung) {
        var li = document.createElement('li');
        li.textContent = noiDung;
        danhSach.appendChild(li);
      });
      than.appendChild(danhSach);
    }
    hop.appendChild(than);
    khungLoi.appendChild(hop);
    khungLoi.scrollIntoView({ block: 'nearest' });
  }

  // Báo lỗi rồi kết thúc. setTimeout(0) để chạy SAU mọi bộ lắng nghe submit khác trên trang.
  function baoLoiVaKetThuc(ds) {
    hienLoi(ds);
    setTimeout(ketThuc, 0);
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();               // bắt buộc: tự gửi bằng AJAX, không để trình duyệt gửi form
    if (dangGui) return;              // đang gửi thì bỏ qua lần bấm thêm
    var oTep = form.querySelector('input[type="file"]');
    var toiDa = Number(form.dataset.soAnhToiDa || 100);
    if (!oTep || oTep.files.length === 0) {
      baoLoiVaKetThuc(['Vui lòng chọn ít nhất một ảnh.']);
      return;
    }
    if (oTep.files.length > toiDa) {
      baoLoiVaKetThuc(['Mỗi lần chỉ được tải tối đa ' + toiDa + ' ảnh (bạn chọn ' + oTep.files.length + ' ảnh).']);
      return;
    }

    var xhr = new XMLHttpRequest();
    xhr.open('POST', window.location.href);
    xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');   // để view trả JSON thay vì dựng lại trang

    xhr.upload.onprogress = function (ev) {
      if (!ev.lengthComputable) return;
      var phanTram = Math.round(ev.loaded * 100 / ev.total);
      thanh.value = phanTram;
      chu.textContent = phanTram < 100 ? 'Đang tải lên... ' + phanTram + '%' :
        'Đã tải xong, đang chèn watermark và lưu ảnh...';
    };

    xhr.onload = function () {
      var ketQua = null;
      try { ketQua = JSON.parse(xhr.responseText); } catch (err) { ketQua = null; }
      if (ketQua && ketQua.ok) {                                   // thành công: chuyển trang, giữ nút xoay tới khi trang mới mở
        window.location.href = ketQua.url || window.location.href;
        return;
      }
      // HTTP 400 (view trả {"ok": false, "loi": [...]}) hoặc phản hồi lạ (hết phiên đăng nhập, lỗi máy chủ...)
      var ds = ketQua && ketQua.loi && ketQua.loi.length ? ketQua.loi : ['Không thể tải ảnh lên, vui lòng thử lại.'];
      hienLoi(ds);
      ketThuc();
    };
    xhr.onerror = function () { hienLoi(['Mất kết nối khi tải ảnh, vui lòng thử lại.']); ketThuc(); };
    xhr.ontimeout = function () { hienLoi(['Tải ảnh quá lâu, vui lòng thử lại.']); ketThuc(); };
    xhr.onabort = function () { ketThuc(); };

    dangGui = true;
    khungLoi.textContent = '';
    thanh.hidden = false;
    thanh.value = 0;
    nut.disabled = true;
    nut.classList.add('is-loading');   // app.js không còn tự thêm khi submit đã bị preventDefault, nên trang này tự thêm
    xhr.send(new FormData(form));
  });

  // Bấm nút Back của trình duyệt quay lại trang này (bộ nhớ đệm bfcache) thì trả form về bình thường.
  window.addEventListener('pageshow', function (e) { if (e.persisted) ketThuc(); });
})();
