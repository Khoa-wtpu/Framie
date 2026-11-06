// accounts/static/accounts/js/quan_tri_tai_khoan.js - P7: hỏi xác nhận trước khi đổi vai trò / khóa tài khoản
document.addEventListener('submit', function (suKien) { // lắng nghe mọi lần gửi form trên trang
  var nut = suKien.submitter; // nút đã bấm để gửi form (có thể là null ở trình duyệt rất cũ)
  if (!nut) { return; } // không biết nút nào thì thôi, để form gửi bình thường
  var cauHoi = nut.getAttribute('data-xac-nhan-form'); // câu hỏi xác nhận ghi trong thuộc tính của nút
  if (cauHoi && !window.confirm(cauHoi)) { // nút có câu hỏi mà người dùng bấm Hủy
    suKien.preventDefault(); // chặn, không gửi form
  } // hết kiểm tra
}, true); // true = chạy ở giai đoạn bắt (capture), tức TRƯỚC bộ chống bấm đúp trong static/js/app.js; nhờ vậy khi bấm Hủy, app.js thấy form đã bị chặn và không thêm is-loading (nút khỏi xoay mãi)
