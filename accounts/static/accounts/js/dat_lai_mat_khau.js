// =====================================================================
// accounts/static/accounts/js/dat_lai_mat_khau.js  -  P6: chống bấm đúp khi gửi form (Phanh)
// Theo README giao diện mục 3: khi bấm gửi form, nút chính thêm class is-loading để không bấm hai lần.
// Cách dùng: thêm thuộc tính data-chong-bam-doi vào thẻ <form>, file này tự lo phần còn lại.
// =====================================================================
(function () {  // bọc trong một hàm tự chạy để biến bên trong không lọt ra phạm vi toàn trang
  var cacForm = document.querySelectorAll('form[data-chong-bam-doi]');  // lấy mọi form có đánh dấu chống bấm đúp

  cacForm.forEach(function (form) {  // xử lý lần lượt từng form
    form.addEventListener('submit', function () {  // chạy đúng lúc người dùng gửi form
      var nut = form.querySelector('[type=submit]');  // nút gửi của form này
      if (nut) {  // phòng trường hợp form không có nút gửi
        nut.classList.add('is-loading');  // thêm class is-loading: components.css làm nút hiện vòng xoay và chặn bấm chuột lần hai
      }
    });
  });

  window.addEventListener('pageshow', function (suKien) {  // chạy mỗi khi trang hiện ra, kể cả khi người dùng bấm nút Back của trình duyệt
    if (!suKien.persisted) return;  // chỉ xử lý trang được khôi phục từ bộ nhớ đệm (Back/Forward)
    cacForm.forEach(function (form) {  // với từng form
      var nut = form.querySelector('[type=submit]');  // nút gửi
      if (nut) nut.classList.remove('is-loading');  // bỏ vòng xoay, nếu không nút sẽ kẹt ở trạng thái đang xử lý sau khi quay lại
    });
  });
})();