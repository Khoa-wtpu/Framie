(function () { // bọc trong hàm để biến không rò ra ngoài
  'use strict'; // bật chế độ nghiêm ngặt, bắt lỗi sớm
  var form = document.getElementById('form-yeu-cau'); // form yêu cầu chỉnh sửa
  if (!form) return; // trang không có form (đủ 3 lần, sai trạng thái...) thì dừng

  function capNhat(muc) { // đổi viền dòng theo ô tick
    var oTick = muc.querySelector('input[type="checkbox"]'); // ô tick của dòng
    muc.classList.toggle('yc-sua__muc--chon', oTick.checked); // tick thì viền đậm
  } // hết hàm capNhat

  form.querySelectorAll('.yc-sua__muc').forEach(function (muc) { // duyệt từng dòng ảnh
    var oTick = muc.querySelector('input[type="checkbox"]'); // ô tick
    var oNoiDung = muc.querySelector('textarea'); // ô nội dung của dòng
    oTick.addEventListener('change', function () { capNhat(muc); }); // tick/bỏ tick thì cập nhật viền
    oNoiDung.addEventListener('input', function () { // khi gõ nội dung
      if (oNoiDung.value.trim() !== '' && !oTick.checked) { // có chữ mà chưa tick
        oTick.checked = true; // tự tick ảnh này
        capNhat(muc); // cập nhật viền
      } // hết if
    }); // hết sự kiện input
    capNhat(muc); // chạy một lần khi mở trang (hiện đúng ảnh đã tick)
  }); // hết vòng duyệt
})(); // gọi hàm ngay
