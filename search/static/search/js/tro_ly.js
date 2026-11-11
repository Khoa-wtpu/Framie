// search/static/search/js/tro_ly.js - E4: JS nhẹ cho Trợ lý (lịch chọn ngày, ngày chọn nhanh, giới hạn + bộ đếm phong cách).
// Không có JS vẫn dùng được: ô ngày gốc (type=date) và hộp tích vẫn gửi form bình thường; máy chủ luôn kiểm tra lại.
(function () {  // bọc trong hàm để không làm bẩn biến toàn cục
  'use strict';  // bật chế độ nghiêm ngặt để báo lỗi sớm
  var goc = document.querySelector('[data-tro-ly]');  // khối ngoài cùng của trang form
  if (!goc) { return; }  // trang không phải form (ví dụ trang kết quả) thì thôi

  // ---------- tiện ích ngày ----------
  var hai = function (n) { return (n < 10 ? '0' : '') + n; };  // 5 -> "05"
  var toIso = function (d) { return d.getFullYear() + '-' + hai(d.getMonth() + 1) + '-' + hai(d.getDate()); };  // Date -> "YYYY-MM-DD"
  var tuIso = function (s) {  // "YYYY-MM-DD" -> Date giờ địa phương (không dùng new Date(chuỗi) vì bị lệch múi giờ)
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s || '');  // tách năm, tháng, ngày
    return m ? new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])) : null;  // không đúng dạng thì null
  };
  var hienNgay = function (d) { return hai(d.getDate()) + '/' + hai(d.getMonth() + 1) + '/' + d.getFullYear(); };  // Date -> "12/11/2026" để khách đọc

  // ---------- Bước 4: ô ngày, lịch tự vẽ, hàng 7 ngày chọn nhanh ----------
  var oNgay = goc.querySelector('input[type="date"]');  // ô chọn ngày gốc
  var nhanh = goc.querySelector('[data-ngay-nhanh]');  // hàng nút ngày (đang hidden)
  if (oNgay) {  // chỉ có ở bước 4
    var nho = tuIso(oNgay.getAttribute('min'));  // ngày sớm nhất được chọn (view đặt vào thuộc tính min)
    var lon = tuIso(oNgay.getAttribute('max'));  // ngày xa nhất được chọn (thuộc tính max)

    // nút hiện ngày đã chọn, thay cho ô gốc
    var nut = document.createElement('button');  // tạo nút
    nut.type = 'button';  // không gửi form
    nut.id = 'tro-ly-nut-ngay';  // để nhãn trỏ vào
    nut.className = 'input tro-ly__o-ngay';  // kiểu ô nhập chung + kiểu riêng
    nut.setAttribute('aria-expanded', 'false');  // lịch đang đóng
    nut.setAttribute('aria-controls', 'tro-ly-lich');  // nút điều khiển bảng lịch
    var chu = document.createElement('span');  // chỗ hiện ngày
    nut.appendChild(chu);  // gắn vào nút
    nut.insertAdjacentHTML('beforeend', '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="3"/><path d="M8 3v4M16 3v4M3 10h18"/></svg>');  // biểu tượng lịch (cố định, không chứa dữ liệu người dùng)

    var lich = document.createElement('div');  // bảng lịch
    lich.id = 'tro-ly-lich';  // khớp aria-controls
    lich.className = 'tro-ly__lich';  // kiểu bảng lịch
    lich.hidden = true;  // đóng sẵn

    oNgay.classList.add('tro-ly__o-ngay--an');  // ẩn ô gốc nhưng vẫn gửi giá trị
    oNgay.tabIndex = -1;  // không cho Tab vào ô ẩn
    oNgay.setAttribute('aria-hidden', 'true');  // trình đọc màn hình bỏ qua ô ẩn
    oNgay.parentNode.insertBefore(nut, oNgay);  // nút nằm trước ô gốc
    oNgay.parentNode.insertBefore(lich, oNgay);  // bảng lịch nằm ngay dưới nút
    var nhan = goc.querySelector('label[for="' + oNgay.id + '"]');  // nhãn "Ngày chụp"
    if (nhan) { nhan.setAttribute('for', nut.id); }  // bấm nhãn thì rơi vào nút mới

    var thang = null;  // ngày mùng 1 của tháng đang xem

    var capNhatHien = function () {  // đồng bộ chữ trên nút và màu các ô ngày nhanh với giá trị ô gốc
      var d = tuIso(oNgay.value);  // ngày đang chọn
      chu.textContent = d ? hienNgay(d) : 'Chọn ngày chụp';  // chưa chọn thì hiện gợi ý
      if (nhanh) {  // có hàng ngày nhanh
        nhanh.querySelectorAll('[data-ngay]').forEach(function (n) {  // duyệt từng nút
          var chon = n.getAttribute('data-ngay') === oNgay.value;  // nút này là ngày đang chọn?
          n.classList.toggle('is-chon', chon);  // bật/tắt kiểu đang chọn
          n.setAttribute('aria-pressed', String(chon));  // báo trình đọc màn hình
        });
      }
    };

    var datNgay = function (iso) {  // gán một ngày cho ô gốc
      oNgay.value = iso;  // giá trị YYYY-MM-DD gửi lên máy chủ
      capNhatHien();  // cập nhật giao diện
    };

    var taoNut = function (lop, chuNut, nhanAria) {  // tạo nút nhỏ trong lịch
      var b = document.createElement('button');  // nút
      b.type = 'button';  // không gửi form
      b.className = lop;  // kiểu
      b.textContent = chuNut;  // chữ hiện
      if (nhanAria) { b.setAttribute('aria-label', nhanAria); }  // nhãn cho trình đọc màn hình
      return b;  // trả nút
    };

    var ve = function () {  // vẽ lại bảng lịch của tháng đang xem
      lich.textContent = '';  // xóa nội dung cũ
      var nam = thang.getFullYear();  // năm đang xem
      var thg = thang.getMonth();  // tháng đang xem (0-11)

      var dau = document.createElement('div');  // hàng đầu: tên tháng + nút chuyển
      dau.className = 'tro-ly__lich-dau';  // kiểu
      var truoc = taoNut('tro-ly__lich-chuyen', '\u2039', 'Tháng trước');  // nút ‹
      var sau = taoNut('tro-ly__lich-chuyen', '\u203A', 'Tháng sau');  // nút ›
      truoc.disabled = !!nho && new Date(nam, thg, 0) < nho;  // tháng trước không còn ngày hợp lệ thì khóa
      sau.disabled = !!lon && new Date(nam, thg + 1, 1) > lon;  // tháng sau không còn ngày hợp lệ thì khóa
      truoc.addEventListener('click', function () { thang = new Date(nam, thg - 1, 1); ve(); });  // lùi một tháng
      sau.addEventListener('click', function () { thang = new Date(nam, thg + 1, 1); ve(); });  // tiến một tháng
      var tieuDe = document.createElement('p');  // tên tháng
      tieuDe.className = 'tro-ly__lich-thang';  // kiểu
      tieuDe.setAttribute('aria-live', 'polite');  // đổi tháng thì đọc lại
      tieuDe.textContent = 'Tháng ' + (thg + 1) + ' năm ' + nam;  // ví dụ "Tháng 11 năm 2026"
      dau.appendChild(truoc); dau.appendChild(tieuDe); dau.appendChild(sau);  // ghép hàng đầu
      lich.appendChild(dau);  // đưa vào bảng lịch

      var luoi = document.createElement('div');  // lưới 7 cột
      luoi.className = 'tro-ly__lich-luoi';  // kiểu
      ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'].forEach(function (t) {  // hàng tên thứ
        var o = document.createElement('span');  // một ô tên thứ
        o.className = 'tro-ly__lich-thu';  // kiểu
        o.textContent = t;  // chữ
        luoi.appendChild(o);  // thêm vào lưới
      });
      var lech = (new Date(nam, thg, 1).getDay() + 6) % 7;  // số ô trống đầu tháng (tuần bắt đầu từ thứ Hai)
      for (var i = 0; i < lech; i++) { luoi.appendChild(document.createElement('span')); }  // ô trống
      var soNgay = new Date(nam, thg + 1, 0).getDate();  // số ngày trong tháng
      var homNay = toIso(new Date());  // hôm nay để đánh dấu
      for (var ng = 1; ng <= soNgay; ng++) {  // mỗi ngày một nút
        var d = new Date(nam, thg, ng);  // ngày này
        var iso = toIso(d);  // dạng YYYY-MM-DD
        var b = taoNut('tro-ly__lich-ngay', String(ng), ng + '/' + (thg + 1) + '/' + nam);  // nút ngày
        b.disabled = (!!nho && d < nho) || (!!lon && d > lon);  // ngoài khoảng cho phép thì khóa
        if (iso === homNay) { b.classList.add('is-hom-nay'); }  // đánh dấu hôm nay
        if (iso === oNgay.value) { b.classList.add('is-chon'); b.setAttribute('aria-pressed', 'true'); }  // ngày đang chọn
        b.addEventListener('click', (function (giaTri) {  // bọc để mỗi nút nhớ đúng ngày của nó
          return function () { datNgay(giaTri); dong(true); };  // chọn xong thì đóng lịch và trả focus về nút
        })(iso));
        luoi.appendChild(b);  // thêm vào lưới
      }
      lich.appendChild(luoi);  // đưa lưới vào bảng lịch
    };

    var dong = function (traFocus) {  // đóng lịch
      lich.hidden = true;  // ẩn
      nut.setAttribute('aria-expanded', 'false');  // báo trạng thái đóng
      if (traFocus) { nut.focus(); }  // trả focus để dùng bàn phím tiếp
    };

    nut.addEventListener('click', function () {  // bấm nút ngày: mở/đóng lịch
      if (!lich.hidden) { dong(false); return; }  // đang mở thì đóng
      var goc0 = tuIso(oNgay.value) || nho || new Date();  // mở ở tháng của ngày đang chọn, không có thì tháng hôm nay
      thang = new Date(goc0.getFullYear(), goc0.getMonth(), 1);  // mùng 1 của tháng đó
      ve();  // vẽ lịch
      lich.hidden = false;  // hiện
      nut.setAttribute('aria-expanded', 'true');  // báo trạng thái mở
    });
    goc.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !lich.hidden) { dong(true); } });  // Esc đóng lịch

    if (nhanh) {  // hàng 7 ngày chọn nhanh
      nhanh.hidden = false;  // có JS thì mới hiện hàng nút
      nhanh.addEventListener('click', function (e) {  // bấm vào một nút ngày
        var n = e.target.closest('[data-ngay]');  // tìm nút được bấm
        if (!n) { return; }  // bấm ra ngoài nút thì bỏ qua
        datNgay(n.getAttribute('data-ngay'));  // gán ngày
        if (!lich.hidden) { dong(false); }  // lịch đang mở thì đóng cho gọn
      });
    }
    oNgay.addEventListener('change', capNhatHien);  // phòng khi giá trị ô gốc đổi bằng cách khác
    capNhatHien();  // hiện ngày ngay khi mở trang (đáp án cũ hoặc để trống)
  }

  // ---------- Bước 5: chọn tối đa N phong cách + bộ đếm ----------
  var nhom = goc.querySelector('[data-toi-da]');  // nhóm chip phong cách
  if (nhom) {  // chỉ có ở bước 5
    var toiDa = parseInt(nhom.getAttribute('data-toi-da'), 10) || 3;  // số tối đa lấy từ hằng của Khoa (đã truyền qua view)
    var cacHop = nhom.querySelectorAll('input[type="checkbox"]');  // các hộp tích
    var dem = goc.querySelector('[data-dem]');  // dòng "Đã chọn x/y"
    var capNhat = function () {  // đếm lại và khóa các hộp còn lại khi đủ số
      var so = nhom.querySelectorAll('input[type="checkbox"]:checked').length;  // số đã tích
      cacHop.forEach(function (h) { h.disabled = !h.checked && so >= toiDa; });  // đủ số thì khóa hộp chưa tích (hộp bị khóa không gửi lên, máy chủ vẫn kiểm tra)
      if (dem) {  // có dòng đếm
        dem.hidden = false;  // có JS thì hiện
        dem.textContent = 'Đã chọn ' + so + '/' + toiDa + ' phong cách';  // cập nhật chữ
      }
    };
    nhom.addEventListener('change', capNhat);  // mỗi lần tích hoặc bỏ tích
    capNhat();  // chạy ngay khi mở trang (đáp án cũ được tích sẵn)
  }
})();
