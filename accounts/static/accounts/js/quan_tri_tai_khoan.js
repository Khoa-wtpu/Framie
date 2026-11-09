// accounts/static/accounts/js/quan_tri_tai_khoan.js - P7: sửa vai trò ngay trong dòng (bấm dòng -> chọn vai trò -> Lưu/Hủy) và hỏi xác nhận trước khi đổi vai trò / khóa tài khoản
(function () { // bọc lại để biến không lọt ra ngoài
  function capNhatForm(form) { // tô sáng vai trò đang chọn; chỉ cho bấm Lưu khi chọn vai trò khác vai trò hiện tại
    var chon = form.querySelector('input[name="vai_tro"]:checked'); // radio đang chọn
    var nhan = form.querySelectorAll('.tk-chip'); // các nút vai trò
    for (var i = 0; i < nhan.length; i++) { // duyệt từng nút
      var o = nhan[i].querySelector('input'); // radio nằm trong nút
      nhan[i].classList.toggle('is-active', !!(o && o.checked)); // nút đang chọn thì sáng
    } // hết duyệt
    var nutLuu = form.querySelector('button[type="submit"]'); // nút Lưu vai trò
    if (nutLuu) { nutLuu.disabled = !chon || chon.value === form.getAttribute('data-vai-tro-hien-tai'); } // giống vai trò cũ thì khóa nút (server cũng chặn)
  } // hết capNhatForm

  function datCheDoSua(ma, dangSua) { // mở (true) hoặc đóng (false) hàng chỉnh sửa có id = ma
    var hangSua = document.getElementById(ma); // hàng chỉnh sửa (ẩn sẵn)
    var nutSua = document.querySelector('[data-sua-vai-tro="' + ma + '"]'); // nút chữ vai trò ở cột Vai trò
    if (!hangSua || !nutSua) { return; } // thiếu phần tử thì thôi
    var hang = nutSua.closest('tr'); // dòng tài khoản
    hangSua.hidden = !dangSua; // hiện/ẩn hàng chỉnh sửa
    nutSua.setAttribute('aria-expanded', dangSua ? 'true' : 'false'); // báo cho trình đọc màn hình
    hang.classList.toggle('is-editing', dangSua); // nền nhạt cho dòng đang sửa
    var khoaMo = hang.querySelector('[data-khoa-mo]'); // form Khóa/Mở của dòng
    if (khoaMo) { khoaMo.hidden = dangSua; } // đang sửa vai trò thì ẩn nút Khóa
    var nhanSua = hang.querySelector('[data-dang-sua]'); // chữ "Đang chỉnh sửa"
    if (nhanSua) { nhanSua.hidden = !dangSua; } // hiện khi đang sửa
    var form = hangSua.querySelector('form'); // form đổi vai trò
    if (!dangSua) { form.reset(); capNhatForm(form); } // Hủy: trả về vai trò cũ
    else { var dau = form.querySelector('input:checked'); if (dau) { dau.focus(); } } // mở: đưa con trỏ vào ô đang chọn
  } // hết datCheDoSua

  document.addEventListener('click', function (suKien) { // bấm dòng (hoặc chữ vai trò) hoặc Hủy
    var nutSua = suKien.target.closest('[data-sua-vai-tro]'); // bấm đúng chữ vai trò?
    if (!nutSua && !suKien.target.closest('a, button, input, label, form')) { // bấm chỗ trống trên dòng tài khoản?
      var dong = suKien.target.closest('tr'); // dòng vừa bấm
      nutSua = dong ? dong.querySelector('[data-sua-vai-tro]') : null; // dòng có nút vai trò (Khách hàng/QTV) thì dùng nó
    } // hết tìm theo dòng
    if (nutSua) { // bấm dòng/chữ vai trò: mở nếu đang đóng, đóng nếu đang mở
      var ma = nutSua.getAttribute('data-sua-vai-tro'); // id hàng chỉnh sửa
      var dangMo = nutSua.getAttribute('aria-expanded') === 'true'; // đang mở?
      datCheDoSua(ma, !dangMo); return; // đảo trạng thái
    } // hết xử lý dòng
    var nutHuy = suKien.target.closest('[data-huy-vai-tro]'); // bấm vào nút Hủy?
    if (nutHuy) { datCheDoSua(nutHuy.getAttribute('data-huy-vai-tro'), false); } // đóng hàng chỉnh sửa
  }); // hết lắng nghe click

  document.addEventListener('change', function (suKien) { // chọn vai trò khác
    var form = suKien.target.closest('[data-form-vai-tro]'); // radio nằm trong form đổi vai trò?
    if (form) { capNhatForm(form); } // cập nhật nút sáng và nút Lưu
  }); // hết lắng nghe change

  document.addEventListener('submit', function (suKien) { // lắng nghe mọi lần gửi form trên trang
    var nut = suKien.submitter; // nút đã bấm để gửi form (có thể là null ở trình duyệt rất cũ)
    if (!nut) { return; } // không biết nút nào thì thôi, để form gửi bình thường
    var cauHoi = nut.getAttribute('data-xac-nhan-form'); // câu hỏi xác nhận ghi trong thuộc tính của nút
    if (cauHoi) { // nút có câu hỏi xác nhận
      var chon = suKien.target.querySelector('input[name="vai_tro"]:checked'); // vai trò đang chọn (chỉ form đổi vai trò mới có)
      if (chon) { cauHoi = cauHoi.replace('{vai_tro}', chon.value); } // thay {vai_tro} bằng vai trò đã chọn
      if (!window.confirm(cauHoi)) { suKien.preventDefault(); } // bấm Hủy thì chặn, không gửi form
    } // hết xác nhận
  }, true); // true = chạy ở giai đoạn bắt (capture), tức TRƯỚC bộ chống bấm đúp trong static/js/app.js; nhờ vậy khi bấm Hủy, app.js thấy form đã bị chặn và không thêm is-loading (nút khỏi xoay mãi)
})(); // hết
