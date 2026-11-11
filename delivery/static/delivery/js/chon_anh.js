(function () { // bọc trong hàm để biến không rò ra ngoài
  'use strict'; // bật chế độ nghiêm ngặt, bắt lỗi sớm
  var form = document.getElementById('form-chon-anh'); // form chọn ảnh
  if (!form) return; // trang không có form (hết hạn, đã gửi...) thì dừng
  var soDaChon = document.getElementById('so-da-chon'); // chỗ hiện số ảnh đã chọn
  var canhBao = document.getElementById('canh-bao-vuot'); // dòng cảnh báo vượt giới hạn
  var toiDa = Number(form.dataset.soToiDa || 0); // số ảnh tối đa của gói (đọc từ data-so-toi-da)
  var oTick = form.querySelectorAll('input[type="checkbox"][name="anh"]'); // tất cả ô tick

  function capNhat() { // cập nhật bộ đếm, viền ô và cảnh báo
    var dem = 0; // số ảnh đang tick
    oTick.forEach(function (o) { // duyệt từng ô tick
      if (o.checked) dem += 1; // đang tick thì cộng 1
      var the = o.closest('.chon-anh__the'); // ô ảnh chứa ô tick này
      the.classList.toggle('chon-anh__the--chon', o.checked); // tick thì viền đậm
      the.classList.toggle('chon-anh__the--vuot', o.checked && toiDa > 0 && dem > toiDa); // tick nhưng vượt giới hạn thì viền đỏ
    }); // hết vòng duyệt
    if (soDaChon) soDaChon.textContent = dem; // hiện số ảnh đã chọn
    if (canhBao) canhBao.hidden = !(toiDa > 0 && dem > toiDa); // vượt giới hạn thì hiện cảnh báo
  } // hết hàm capNhat

  oTick.forEach(function (o) { // gắn sự kiện cho từng ô tick
    o.addEventListener('change', capNhat); // mỗi lần tick/bỏ tick thì cập nhật
  }); // hết vòng gắn sự kiện
  capNhat(); // chạy một lần khi mở trang (hiện đúng các ảnh đã lưu)
})(); // gọi hàm ngay
