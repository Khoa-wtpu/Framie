// search/static/search/js/tim_kiem.js - K8: đổi cách sắp xếp thì tự tìm lại (không có JS thì dùng nút "Sắp xếp" trong <noscript>)
document.querySelectorAll('select[data-tu-gui]').forEach(function (o) {
  o.addEventListener('change', function () { o.form.submit(); });
});
