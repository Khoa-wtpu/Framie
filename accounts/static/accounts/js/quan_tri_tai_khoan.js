// accounts/static/accounts/js/quan_tri_tai_khoan.js - P7: hỏi xác nhận trước khi khóa tài khoản
(function () { // bọc lại để biến không lọt ra ngoài
  document.addEventListener('submit', function (suKien) { // lắng nghe mọi lần gửi form trên trang
    var nut = suKien.submitter; // nút đã bấm để gửi form (có thể là null ở trình duyệt rất cũ)
    if (!nut) { return; } // không biết nút nào thì thôi, để form gửi bình thường
    var cauHoi = nut.getAttribute('data-xac-nhan-form'); // câu hỏi xác nhận ghi trong thuộc tính của nút
    if (cauHoi && !window.confirm(cauHoi)) { suKien.preventDefault(); } // bấm Hủy thì chặn, không gửi form
  }, true); // true = chạy ở giai đoạn bắt (capture), tức TRƯỚC bộ chống bấm đúp trong static/js/app.js; nhờ vậy khi bấm Hủy, app.js thấy form đã bị chặn và không thêm is-loading (nút khỏi xoay mãi)
})(); // hết
