(function () {
  'use strict';
  var form = document.getElementById('form-tai-anh');
  if (!form) return;
  var thanh = document.getElementById('thanh-tien-trinh');
  var chu = document.getElementById('chu-tien-trinh');
  var khungLoi = document.getElementById('khung-loi');
  var nut = document.getElementById('nut-tai');

  function hienLoi(ds) {
    khungLoi.innerHTML = '';
    ds.forEach(function (noiDung) {
      var p = document.createElement('p');
      p.className = 'alert alert--danger';
      p.textContent = noiDung;
      khungLoi.appendChild(p);
    });
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var oTep = form.querySelector('input[type="file"]');
    var toiDa = Number(form.dataset.soAnhToiDa || 100);
    if (oTep && oTep.files.length > toiDa) {
      hienLoi(['Mỗi lần chỉ được tải tối đa ' + toiDa + ' ảnh (bạn chọn ' + oTep.files.length + ' ảnh).']);
      return;
    }
    var xhr = new XMLHttpRequest();
    xhr.open('POST', window.location.href);
    xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
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
      if (ketQua && ketQua.ok) { window.location.href = ketQua.url; return; }
      hienLoi(ketQua && ketQua.loi ? ketQua.loi : ['Không thể tải ảnh lên, vui lòng thử lại.']);
      thanh.hidden = true; chu.textContent = ''; nut.disabled = false;
    };
    xhr.onerror = function () {
      hienLoi(['Mất kết nối khi tải ảnh, vui lòng thử lại.']);
      thanh.hidden = true; chu.textContent = ''; nut.disabled = false;
    };
    khungLoi.innerHTML = '';
    thanh.hidden = false; thanh.value = 0; nut.disabled = true;
    xhr.send(new FormData(form));
  });
})();
