// profiles/static/profiles/js/portfolio.js - K5: hiện số hình và ảnh xem trước khi chọn nhiều hình cho project.
(function () {
  document.addEventListener('change', function (e) {
    var o = e.target;
    if (!o.classList || !o.classList.contains('pf__tep')) return;
    var vung = o.closest('.field');
    var dem = vung.querySelector('.pf__so-tep');
    var khung = vung.querySelector('.pf__xem-truoc');
    var cac_tep = Array.prototype.filter.call(o.files || [], function (t) { return t.type.indexOf('image/') === 0; });
    dem.textContent = cac_tep.length ? 'Đã chọn ' + cac_tep.length + ' hình' : '';
    khung.innerHTML = '';
    cac_tep.slice(0, 12).forEach(function (tep) {
      var anh = document.createElement('img');
      anh.src = URL.createObjectURL(tep);
      anh.alt = '';
      khung.appendChild(anh);
    });
  });
})();

// ---- Sắp xếp hình trong project: kéo thả bằng chuột hoặc gõ số thứ tự ----
(function () {
  var danhSach = document.querySelector('[data-sap-xep]');
  if (!danhSach) return;
  var dangKeo = null;

  var thongBao = document.querySelector('[data-da-go]');
  function daGo(li) { return li.querySelector('input[name=xoa_hinh]').checked; }
  function cacMuc() {                          // chỉ tính các hình còn hiện (hình đã bấm × thì bỏ qua)
    return Array.prototype.slice.call(danhSach.children).filter(function (li) { return !daGo(li); });
  }
  function danhSoLai() {                       // số trong ô luôn khớp vị trí thật trên màn hình
    cacMuc().forEach(function (li, i) { li.querySelector('input[type=number]').value = i + 1; });
    var soGo = danhSach.children.length - cacMuc().length;
    if (thongBao) {
      thongBao.hidden = soGo === 0;
      thongBao.querySelector('[data-da-go-chu]').textContent =
        'Đã gỡ ' + soGo + ' hình khỏi danh sách, sẽ xóa hẳn khi bấm Lưu.';
    }
  }
  danhSach.addEventListener('change', function (e) {         // bấm × hoặc Hoàn tác: đánh số lại các hình còn lại
    if (e.target.name === 'xoa_hinh') danhSoLai();
  });
  if (thongBao) thongBao.querySelector('[data-hoan-tac]').addEventListener('click', function () {
    Array.prototype.forEach.call(danhSach.children, function (li) {
      li.querySelector('input[name=xoa_hinh]').checked = false;
    });
    danhSoLai();
  });
  danhSoLai();

  // Kéo thả: hình đang kéo chạy theo con trỏ, thả ở đâu thì nằm ở đó.
  danhSach.addEventListener('dragstart', function (e) {
    var li = e.target.closest && e.target.closest('.pf__o');
    if (!li || li.getAttribute('draggable') !== 'true') { e.preventDefault(); return; }
    dangKeo = li;
    li.classList.add('dang-keo');
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', '');  // Firefox cần dòng này mới cho kéo
  });
  danhSach.addEventListener('dragover', function (e) {
    if (!dangKeo) return;
    e.preventDefault();
    var dich = e.target.closest && e.target.closest('.pf__o');
    if (!dich || dich === dangKeo) return;
    var kich = dich.getBoundingClientRect();
    var sauDich = e.clientX > kich.left + kich.width / 2;     // nửa phải của ô thì chèn sau, nửa trái thì chèn trước
    danhSach.insertBefore(dangKeo, sauDich ? dich.nextSibling : dich);
  });
  danhSach.addEventListener('drop', function (e) { if (dangKeo) e.preventDefault(); });
  danhSach.addEventListener('dragend', function () {
    if (dangKeo) dangKeo.classList.remove('dang-keo');
    dangKeo = null;
    danhSoLai();
  });

  // Gõ số: hình nhảy tới đúng vị trí đó (số quá lớn thì về cuối, số nhỏ hơn 1 thì về đầu).
  function chuyenTheoSo(o) {
    var li = o.closest('.pf__o');
    var cac = cacMuc().filter(function (x) { return x !== li; });
    var so = parseInt(o.value, 10);
    if (isNaN(so)) { danhSoLai(); return; }
    var viTri = Math.min(Math.max(so, 1), cac.length + 1) - 1;
    danhSach.insertBefore(li, cac[viTri] || null);
    danhSoLai();
  }
  danhSach.addEventListener('change', function (e) {
    if (e.target.matches('input[type=number]')) chuyenTheoSo(e.target);
  });
  danhSach.addEventListener('keydown', function (e) {        // Enter trong ô số: áp dụng, không gửi form
    if (e.key === 'Enter' && e.target.matches('input[type=number]')) {
      e.preventDefault();
      chuyenTheoSo(e.target);
    }
  });
  // Đang gõ trong ô số thì tạm tắt kéo để chọn chữ được (Firefox).
  danhSach.addEventListener('focusin', function (e) {
    if (e.target.matches('input[type=number]')) e.target.closest('.pf__o').setAttribute('draggable', 'false');
  });
  danhSach.addEventListener('focusout', function (e) {
    if (e.target.matches('input[type=number]')) e.target.closest('.pf__o').setAttribute('draggable', 'true');
  });
})();
