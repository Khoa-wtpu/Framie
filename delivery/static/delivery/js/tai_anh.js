(function () {  // bọc code trong hàm tự chạy để không lẫn biến toàn cục
  'use strict';  // bật chế độ nghiêm ngặt để bắt lỗi cú pháp sớm
  var form = document.getElementById('form-tai-anh');  // lấy form tải ảnh
  if (!form) return;  // trang không có form này thì dừng
  var thanh = document.getElementById('thanh-tien-trinh');  // thanh tiến trình
  var chu = document.getElementById('chu-tien-trinh');  // dòng chữ tiến trình
  var khungLoi = document.getElementById('khung-loi');  // khung hiện lỗi
  var nut = document.getElementById('nut-tai');  // nút "Tải ảnh lên"

  function hienLoi(ds) {  // hàm hiện danh sách lỗi
    khungLoi.innerHTML = '';  // xóa lỗi cũ
    ds.forEach(function (noiDung) {  // duyệt từng câu lỗi
      var p = document.createElement('p');  // tạo thẻ p cho câu lỗi
      p.className = 'alert alert--danger';  // dùng kiểu cảnh báo màu đỏ
      p.textContent = noiDung;  // gán nội dung lỗi
      khungLoi.appendChild(p);  // đưa vào khung lỗi
    });
  }

  function khoiPhucNut() {  // HÀM MỚI: trả nút và form về trạng thái bình thường
    thanh.hidden = true;  // ẩn thanh tiến trình
    chu.textContent = '';  // xóa dòng chữ tiến trình
    nut.disabled = false;  // cho bấm nút lại
    nut.classList.remove('is-loading');  // gỡ vòng xoay do app.js thêm vào (nguyên nhân lỗi)
    delete form.dataset.submitting;  // gỡ cờ chặn gửi lại do app.js đặt (nguyên nhân lỗi)
  }

  form.addEventListener('submit', function (e) {  // khi bấm nút tải ảnh
    e.preventDefault();  // không cho trình duyệt gửi form kiểu thường
    var oTep = form.querySelector('input[type="file"]');  // ô chọn tệp
    var toiDa = Number(form.dataset.soAnhToiDa || 100);  // số ảnh tối đa mỗi lần
    if (oTep && oTep.files.length > toiDa) {  // chọn quá số ảnh cho phép
      hienLoi(['Mỗi lần chỉ được tải tối đa ' + toiDa + ' ảnh (bạn chọn ' + oTep.files.length + ' ảnh).']);  // báo lỗi
      setTimeout(khoiPhucNut, 0);  // chờ app.js chạy xong rồi gỡ vòng xoay (lỗi này cũng bị kẹt xoay)
      return;  // dừng, không gửi
    }
    var xhr = new XMLHttpRequest();  // tạo yêu cầu gửi ngầm
    xhr.open('POST', window.location.href);  // gửi về chính trang này
    xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');  // báo cho server đây là yêu cầu ngầm
    xhr.timeout = 10 * 60 * 1000;  // MỚI: tối đa 10 phút, quá thì coi là lỗi để không xoay vĩnh viễn
    xhr.upload.onprogress = function (ev) {  // khi đang tải lên
      if (!ev.lengthComputable) return;  // chưa biết tổng dung lượng thì bỏ qua
      var phanTram = Math.round(ev.loaded * 100 / ev.total);  // tính phần trăm
      thanh.value = phanTram;  // cập nhật thanh tiến trình
      chu.textContent = phanTram < 100 ? 'Đang tải lên... ' + phanTram + '%' :  // chữ khi chưa xong
        'Đã tải xong, đang chèn watermark và lưu ảnh...';  // chữ khi đã đủ 100%
    };
    xhr.onload = function () {  // khi server trả lời
      var ketQua = null;  // nơi chứa kết quả JSON
      try { ketQua = JSON.parse(xhr.responseText); } catch (err) { ketQua = null; }  // đọc JSON, lỗi thì để null
      if (ketQua && ketQua.ok) { window.location.href = ketQua.url; return; }  // thành công thì chuyển trang
      hienLoi(ketQua && ketQua.loi ? ketQua.loi : ['Không thể tải ảnh lên, vui lòng thử lại.']);  // hiện lỗi
      khoiPhucNut();  // SỬA: trả lại nút bình thường (trước đây chỉ gỡ disabled)
    };
    xhr.onerror = function () {  // khi mất kết nối
      hienLoi(['Mất kết nối khi tải ảnh, vui lòng thử lại.']);  // hiện lỗi mạng
      khoiPhucNut();  // SỬA: trả lại nút bình thường
    };
    xhr.ontimeout = function () {  // MỚI: khi quá thời gian chờ
      hienLoi(['Tải ảnh quá lâu, vui lòng thử lại với ít ảnh hơn.']);  // hiện lỗi quá giờ
      khoiPhucNut();  // trả lại nút bình thường
    };
    xhr.onabort = function () { khoiPhucNut(); };  // MỚI: bị hủy giữa chừng cũng trả lại nút
    khungLoi.innerHTML = '';  // xóa lỗi cũ trước khi gửi
    thanh.hidden = false; thanh.value = 0; nut.disabled = true;  // hiện thanh tiến trình, khóa nút
    xhr.send(new FormData(form));  // bắt đầu gửi dữ liệu
  });
})();  // kết thúc hàm tự chạy