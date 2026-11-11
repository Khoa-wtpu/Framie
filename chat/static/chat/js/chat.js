// chat/static/chat/js/chat.js - P11 + nâng cấp bước 2 đến 6 (thêm: gửi ảnh, trang xem ảnh, panel Ảnh đã chia sẻ, thu hồi tin, trả lời tin): lọc danh sách (Tất cả / Chưa đọc / Đã ẩn / tìm tên), cột trái tự đồng bộ, ba chấm từng cuộc (ghim, ẩn, xóa), "Đã gửi / Đã xem", gửi tin, tải tin cũ, tự làm mới tin mỗi 2 giây.
(function () {  // bọc trong hàm để không làm rối biến toàn cục
  'use strict';  // bật chế độ nghiêm ngặt, bắt lỗi viết sai sớm hơn

  function boDau(chuoi) {  // đưa chữ về thường, không dấu, để gõ "phanh" vẫn tìm ra "Phanh/Phạm"
    return String(chuoi || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd').trim();  // NFD tách dấu ra rồi xóa; đ không tách được nên thay riêng
  }

  // ----- trạng thái hoạt động dùng chung cho vòng đồng bộ cột trái và vòng polling tin nhắn -----
  var NGHI_TOI_DA_MS = 10 * 60 * 1000;  // 10 phút không thao tác thì tạm dừng mọi vòng hỏi máy chủ (phiên đăng nhập 30 phút, polling không được giữ phiên sống mãi)
  var DS_CHU_KY_MS = 4000;  // cột trái hỏi thay đổi mỗi 4 giây
  var hoatDongCuoi = Date.now();  // lần cuối người dùng thao tác
  var dangNghi = false;  // true khi đang tạm dừng vì lâu không thao tác
  var hamTiepTuc = [];  // các hàm cần chạy lại khi người dùng quay lại thao tác

  function ghiNhanHoatDong() {  // người dùng vừa thao tác
    hoatDongCuoi = Date.now();  // cập nhật mốc
    if (dangNghi) {  // đang tạm dừng
      dangNghi = false;  // bỏ tạm dừng
      hamTiepTuc.forEach(function (f) { f(); });  // chạy lại các vòng đã dừng
    }
  }
  ['pointerdown', 'pointermove', 'keydown', 'touchstart', 'wheel'].forEach(function (ten) {  // các kiểu thao tác
    document.addEventListener(ten, ghiNhanHoatDong, { passive: true });  // lắng nghe, không chặn cuộn
  });

  function quaNghi() { return Date.now() - hoatDongCuoi > NGHI_TOI_DA_MS; }  // đã quá lâu không thao tác chưa

  function goi(url, tuyChon) {  // gọi server, luôn trả về {ok, status, duLieu} và không ném lỗi khi server trả 4xx/5xx
    tuyChon = tuyChon || {};  // tùy chọn mặc định
    tuyChon.credentials = 'same-origin';  // gửi kèm cookie phiên đăng nhập
    tuyChon.headers = Object.assign({ 'X-Requested-With': 'XMLHttpRequest' }, tuyChon.headers || {});  // báo cho view biết đây là yêu cầu ngầm
    return fetch(url, tuyChon).then(function (r) {  // gửi yêu cầu
      return r.json().catch(function () { return {}; }).then(function (d) {  // đọc JSON, trang lỗi HTML thì coi là {}
        return { ok: r.ok, status: r.status, duLieu: d };  // gói kết quả
      });
    });  // lỗi mạng sẽ ném ra và do nơi gọi bắt
  }

  // ===================================================================================
  // PHẦN A. CỘT TRÁI (dùng chung hộp thư và trang chi tiết): lọc, đồng bộ, ba chấm
  // ===================================================================================
  var cotTrai = document.querySelector('.chat-cot--ds');  // cột trái
  var vung = document.querySelector('[data-chat-vung]');  // vùng danh sách được đồng bộ
  var oTim = document.querySelector('[data-chat-tim]');  // ô "Tìm cuộc trò chuyện"
  var cacTab = Array.prototype.slice.call(document.querySelectorAll('[data-chat-loc]'));  // hai tab Tất cả / Chưa đọc
  var tongTab = document.querySelector('[data-chat-tong]');  // số hiện trên tab Chưa đọc
  var locDangChon = 'tat_ca';  // tab đang chọn (tab Đã ẩn cũng tính là 'tat_ca' vì danh sách do máy chủ trả sẵn)
  var cheDoAn = false;  // true khi đang xem tab Đã ẩn: hỏi máy chủ với ?an=1 và không tính số chưa đọc cho nhãn tab
  var vanTay = '';  // dấu vân tay (băm) của HTML cột trái đang hiện
  var dsDung = false;  // true khi dừng hẳn đồng bộ (hết phiên)
  var henDs = null;  // hẹn giờ của vòng đồng bộ cột trái

  function apDungLoc() {  // lọc danh sách theo tab và chữ trong ô tìm; gọi lại sau MỖI lần HTML cột trái bị thay
    if (!vung) return;  // trang không có cột trái
    var dsCuoc = vung.querySelector('[data-chat-ds]');  // danh sách (không có khi hộp thư trống)
    var cauTrong = vung.querySelector('[data-chat-ds-trong]');  // câu "Không tìm thấy cuộc trò chuyện phù hợp."
    var cacMuc = dsCuoc ? Array.prototype.slice.call(dsCuoc.querySelectorAll('li[data-ten]')) : [];  // các dòng
    var tuKhoa = boDau(oTim ? oTim.value : '');  // chữ cần tìm
    var thay = 0, soChuaDoc = 0;  // số dòng còn hiện, số cuộc chưa đọc
    cacMuc.forEach(function (li) {  // duyệt từng dòng
      var chuaDoc = li.dataset.chuaDoc === '1';  // dòng này đang chưa đọc
      if (chuaDoc) soChuaDoc += 1;  // đếm cho nhãn tab
      var khop = (!tuKhoa || boDau(li.dataset.ten).indexOf(tuKhoa) !== -1) && (locDangChon === 'tat_ca' || chuaDoc);  // khớp chữ tìm và khớp tab
      li.hidden = !khop;  // ẩn dòng không khớp
      if (khop) thay += 1;  // đếm dòng khớp
    });
    if (dsCuoc) dsCuoc.hidden = cacMuc.length > 0 && thay === 0;  // không dòng nào khớp thì ẩn khung danh sách
    if (cauTrong) cauTrong.hidden = !(cacMuc.length > 0 && thay === 0);  // và hiện câu thông báo
    if (tongTab && !cheDoAn) { tongTab.textContent = soChuaDoc; tongTab.hidden = soChuaDoc === 0; }  // số trên tab Chưa đọc (đang xem tab Đã ẩn thì giữ nguyên, vì danh sách lúc đó là các cuộc đã ẩn)
  }

  if (vung) vanTay = '';  // lần đồng bộ đầu tiên sẽ gửi vt rỗng nên luôn nhận bản mới một lần (rẻ, và đảm bảo khớp với máy chủ)
  if (oTim) {  // có ô tìm
    oTim.addEventListener('input', apDungLoc);  // lọc mỗi lần gõ
    oTim.addEventListener('keydown', function (e) {  // phím Esc xóa ô tìm
      if (e.key === 'Escape' && oTim.value) { oTim.value = ''; apDungLoc(); }  // xóa rồi hiện lại toàn bộ
    });
  }
  cacTab.forEach(function (nut) {  // bấm tab Tất cả / Chưa đọc / Đã ẩn
    nut.addEventListener('click', function () {
      var chonAn = nut.dataset.chatLoc === 'da_an';  // bấm tab Đã ẩn
      var doiChe = chonAn !== cheDoAn;  // có chuyển giữa danh sách thường và danh sách đã ẩn không
      cheDoAn = chonAn;  // ghi nhớ chế độ (vòng đồng bộ 4 giây cũng dùng giá trị này)
      locDangChon = chonAn ? 'tat_ca' : nut.dataset.chatLoc;  // ghi nhớ tab đang chọn (còn giữ khi cột trái được thay HTML)
      cacTab.forEach(function (n) {  // đổi trạng thái hai tab
        var chon = n === nut;  // tab này đang được chọn
        n.classList.toggle('is-active', chon);  // tô đậm tab chọn
        n.setAttribute('aria-selected', String(chon));  // cho trình đọc màn hình
      });
      apDungLoc();  // lọc lại
      if (doiChe && vung) {  // đổi chế độ: phải lấy danh sách khác từ máy chủ
        vanTay = '';  // buộc nhận bản mới
        vung.classList.add('is-dang-tai');  // làm mờ danh sách cũ trong lúc chờ
        dongBoDs().catch(function () { vung.classList.remove('is-dang-tai'); });  // lỗi mạng thì bỏ làm mờ, vòng đồng bộ sau sẽ thử lại
      }
    });
  });
  apDungLoc();  // đếm số chưa đọc và lọc lần đầu

  function menuDangMo() { return vung && vung.querySelector('.hop-thu__menu-ds:not([hidden])'); }  // menu ba chấm nào đang mở

  function dongMenu(ngoai) {  // đóng mọi menu ba chấm (trừ menu chứa phần tử vừa bấm)
    if (!vung) return;  // không có cột trái
    Array.prototype.forEach.call(vung.querySelectorAll('.hop-thu__menu'), function (m) {  // từng menu
      if (ngoai && m.contains(ngoai)) return;  // bấm bên trong thì giữ
      var ds = m.querySelector('.hop-thu__menu-ds');  // hộp thả
      var nut = m.querySelector('[data-chat-menu-nut]');  // nút ba chấm
      if (ds) ds.hidden = true;  // đóng
      if (nut) nut.setAttribute('aria-expanded', 'false');  // báo đã đóng
    });
  }

  function thayCotTrai(html) {  // thay HTML vùng danh sách (event delegation nên không cần gắn lại sự kiện)
    vung.innerHTML = html;  // thay toàn bộ
    apDungLoc();  // lọc lại theo tab và ô tìm đang có
  }

  function dongBoDs() {  // hỏi máy chủ cột trái có đổi không; trả về Promise
    if (!vung) return Promise.resolve();  // không có cột trái
    var cheDo = cheDoAn;  // chế độ lúc gửi yêu cầu (người dùng có thể đổi tab trong lúc chờ)
    var url = vung.dataset.urlDongBo + '?mo=' + encodeURIComponent(vung.dataset.mo || '0') + '&o_giua=' + (vung.dataset.oGiua || '0') + '&an=' + (cheDo ? '1' : '0') + '&vt=' + vanTay;  // gửi dấu vân tay đang có và chế độ danh sách
    return goi(url).then(function (kq) {  // gọi
      if (cheDo !== cheDoAn) return;  // đã đổi tab trong lúc chờ: bỏ kết quả của chế độ cũ (lần đồng bộ cho chế độ mới đã được gọi)
      vung.classList.remove('is-dang-tai');  // đã có phản hồi: hết làm mờ
      if (kq.status === 401 || kq.status === 403) { dsDung = true; return; }  // hết phiên hoặc mất quyền: dừng hẳn
      if (!kq.ok) return;  // lỗi tạm thời: giữ nguyên cột trái, lần sau thử lại
      vanTay = kq.duLieu.vt || vanTay;  // cập nhật dấu vân tay
      if (kq.duLieu.doi && kq.duLieu.html && !menuDangMo()) thayCotTrai(kq.duLieu.html);  // có thay đổi và không có menu đang mở thì mới thay
      else if (kq.duLieu.doi) vanTay = '';  // đang mở menu nên chưa thay: xóa vân tay để lần sau nhận lại bản mới
    });
  }

  function vongDs() {  // một vòng đồng bộ cột trái
    if (dsDung || !vung) return;  // đã dừng hẳn
    if (document.hidden) return;  // tab ẩn: tạm nghỉ, visibilitychange gọi lại
    if (quaNghi()) { dangNghi = true; return; }  // lâu không thao tác: dừng, ghiNhanHoatDong sẽ gọi lại
    dongBoDs().catch(function () {}).then(function () {  // lỗi mạng thì bỏ qua
      clearTimeout(henDs);  // không để hai vòng chạy song song
      henDs = setTimeout(vongDs, DS_CHU_KY_MS);  // hẹn vòng sau (setTimeout nối tiếp, không dùng setInterval)
    });
  }
  hamTiepTuc.push(function () { clearTimeout(henDs); vongDs(); });  // quay lại thao tác thì chạy lại ngay
  document.addEventListener('visibilitychange', function () {  // chuyển tab
    if (!document.hidden && !dsDung && !dangNghi) { clearTimeout(henDs); vongDs(); }  // quay lại tab thì đồng bộ ngay
  });
  henDs = setTimeout(vongDs, 1500);  // vòng đầu tiên sau 1,5 giây

  // ----- ba chấm của từng cuộc trò chuyện (event delegation: cột trái bị thay HTML liên tục) -----
  document.addEventListener('click', function (e) {  // mọi cú bấm trên trang
    var nutMenu = e.target.closest('[data-chat-menu-nut]');  // bấm nút ba chấm
    if (nutMenu) {  // mở/đóng menu của dòng đó
      var ds = nutMenu.parentNode.querySelector('.hop-thu__menu-ds');  // hộp thả của dòng
      var mo = ds.hidden;  // đang đóng thì sẽ mở
      dongMenu(null);  // đóng hết menu khác
      ds.hidden = !mo;  // đảo trạng thái
      nutMenu.setAttribute('aria-expanded', String(mo));  // báo cho trình đọc màn hình
      if (mo) {  // vừa mở: đặt hộp thả cạnh nút (position:fixed nên không bị khung cuộn cắt)
        var vt = nutMenu.getBoundingClientRect();  // vị trí nút ba chấm trên màn hình
        var rong = ds.offsetWidth, cao = ds.offsetHeight;  // kích thước hộp thả
        ds.style.left = Math.max(8, Math.min(vt.right - rong, window.innerWidth - rong - 8)) + 'px';  // canh mép phải theo nút, không tràn màn hình
        ds.style.top = (vt.bottom + 4 + cao > window.innerHeight ? Math.max(8, vt.top - 4 - cao) : vt.bottom + 4) + 'px';  // hết chỗ phía dưới thì mở lên trên
      }
      return;  // xong
    }
    var nutHanhDong = e.target.closest('[data-chat-hanh-dong]');  // bấm một lựa chọn trong menu
    if (nutHanhDong) {  // thực hiện hành động
      if (nutHanhDong.dataset.xacNhan && !window.confirm(nutHanhDong.dataset.xacNhan)) { dongMenu(null); return; }  // hành động nguy hiểm (xóa) phải được xác nhận
      var token = cotTrai ? cotTrai.dataset.csrf : '';  // CSRF token
      var loai = nutHanhDong.dataset.chatHanhDong;  // ghim / chua_doc / an / xoa
      nutHanhDong.disabled = true;  // chặn bấm đúp
      goi(nutHanhDong.dataset.url, { method: 'POST', headers: { 'X-CSRFToken': token } }).then(function (kq) {  // gửi POST
        dongMenu(null);  // đóng menu
        if (kq.status === 401) { dsDung = true; return; }  // hết phiên
        if (!kq.ok) { window.alert(kq.duLieu.loi || 'Không thể thực hiện. Vui lòng thử lại.'); return; }  // lỗi máy chủ hoặc cuộc không còn: báo cho người dùng biết
        var dangMo = vung && String(kq.duLieu.ma) === String(vung.dataset.mo || '0');  // hành động vừa làm trên đúng cuộc đang mở ở khung giữa
        if (dangMo && (loai === 'xoa' || (loai === 'an' && kq.duLieu.trang_thai === true))) {  // vừa xóa, hoặc vừa ẨN (không phải bỏ ẩn) cuộc đang mở
          window.location.href = vung.dataset.urlHopThu || '/';  // về hộp thư, vì cuộc này đã biến khỏi danh sách
          return;  // xong
        }
        vanTay = '';  // buộc lấy bản cột trái mới
        return dongBoDs();  // cập nhật cột trái ngay, không chờ 4 giây
      }).catch(function () { dongMenu(null); }).then(function () { nutHanhDong.disabled = false; });  // lỗi mạng: chỉ đóng menu
      return;  // xong
    }
    dongMenu(e.target);  // bấm chỗ khác thì đóng menu
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') dongMenu(null); });  // Esc cũng đóng menu
  document.addEventListener('scroll', function () { dongMenu(null); }, true);  // cuộn danh sách thì đóng menu (hộp thả cố định nên sẽ không đi theo dòng)
  window.addEventListener('resize', function () { dongMenu(null); });  // đổi cỡ cửa sổ cũng đóng

  var khung = document.querySelector('[data-chat]');  // khối cuộc trò chuyện
  if (!khung) return;  // trang Hộp thư (chưa mở cuộc nào) thì dừng ở đây

  // ===================================================================================
  // PHẦN B. CUỘC TRÒ CHUYỆN
  // ===================================================================================
  var CHU_KY_MS = 2000;  // hỏi tin mới mỗi 2 giây, đúng yêu cầu "tin hiện trong khoảng 2 giây"
  var NGUONG_CUON_PX = 80;  // cách đáy dưới 80px thì coi là "đang ở cuối", tin mới sẽ tự cuộn xuống
  var NHOM_GIAY = 5 * 60;  // hai tin cùng người cách nhau dưới 5 phút thì gộp thành một nhóm
  var LOI_GUI = 'Không thể gửi tin nhắn. Vui lòng thử lại.';  // thông báo luồng ngoại lệ 5a (đúng chữ wireframe)
  var LOI_TAI = 'Không thể tải lịch sử trao đổi. Vui lòng thực hiện lại.';  // thông báo luồng ngoại lệ 2a
  var LOI_PHIEN = 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.';  // phiên hết hạn

  var danhSach = khung.querySelector('[data-chat-list]');  // khung cuộn
  var thanTin = khung.querySelector('[data-chat-tin]');  // nơi chứa các bong bóng
  var form = khung.querySelector('[data-chat-form]');  // form soạn tin
  var oNhap = form.querySelector('textarea');  // ô nhập
  var nutGui = form.querySelector('button[type="submit"]');  // nút Gửi
  var hopLoi = khung.querySelector('[data-chat-loi]');  // hộp lỗi nét đứt ở đầu khung
  var hopTrangThai = khung.querySelector('[data-chat-trang-thai]');  // thanh trạng thái (mất kết nối...)
  var nutTinMoi = khung.querySelector('[data-chat-tin-moi]');  // nút nổi "Có tin mới"
  var nutTaiCu = khung.querySelector('[data-chat-tai-cu]');  // nút "Xem tin cũ hơn" (có thể không tồn tại)
  var urlMoi = khung.dataset.urlMoi;  // địa chỉ lấy tin mới / tin cũ
  var homNay = khung.dataset.homNay || '';  // ngày hôm nay theo giờ máy chủ, dạng YYYY-MM-DD (để ghi "Hôm nay", "Hôm qua")

  var idCuoi = parseInt(danhSach.dataset.idCuoi, 10) || 0;  // mã tin cuối đang hiện, mốc cho polling
  var idDau = parseInt(danhSach.dataset.idDau, 10) || 0;  // mã tin đầu đang hiện, mốc để tải tin cũ
  var conCu = danhSach.dataset.conCu === '1';  // còn tin cũ hơn trên server không
  var doiDaXem = parseInt(khung.dataset.doiDaXem, 10) || 0;  // mã tin lớn nhất đối phương đã xem
  var hen = null;  // bộ hẹn giờ của vòng polling
  var dung = false;  // true khi dừng hẳn (hết phiên, mất quyền)
  var loiLienTiep = 0;  // số lần polling lỗi liên tiếp
  var dangGui = false;  // đang gửi tin, chặn bấm đúp
  var dangTaiCu = false;  // đang tải tin cũ, chặn gọi chồng
  var giuDay = true;  // người dùng đang ở đáy danh sách: ảnh tải xong làm danh sách cao thêm thì cuộn xuống lại

  function ganDay() {  // người dùng có đang đọc ở đáy danh sách không
    return danhSach.scrollHeight - danhSach.scrollTop - danhSach.clientHeight < NGUONG_CUON_PX;  // khoảng cách tới đáy
  }

  function cuonXuong() {  // cuộn xuống tin mới nhất
    danhSach.scrollTop = danhSach.scrollHeight;  // đặt vị trí cuộn bằng tổng chiều cao
    giuDay = true;  // đang ở đáy
    nutTinMoi.hidden = true;  // ẩn nút "Có tin mới"
  }

  function hienLoi(noiDung) {  // hiện hoặc ẩn hộp lỗi
    hopLoi.textContent = noiDung || '';  // textContent nên không bị chèn HTML
    hopLoi.hidden = !noiDung;  // rỗng thì ẩn
  }

  function hienTrangThai(noiDung) {  // hiện hoặc ẩn thanh trạng thái
    hopTrangThai.textContent = noiDung || '';  // ghi chữ
    hopTrangThai.hidden = !noiDung;  // rỗng thì ẩn
  }

  // ----- nhóm tin và dòng ngày -----
  function ngayTruoc(chuoi) {  // lùi một ngày: '2026-03-01' -> '2026-02-28'
    var p = chuoi.split('-');  // tách năm, tháng, ngày
    return new Date(Date.UTC(+p[0], +p[1] - 1, +p[2] - 1)).toISOString().slice(0, 10);  // UTC nên không lệch múi giờ, tự xử lý qua tháng/năm
  }

  function nhanNgay(ngay) {  // chữ trên dòng phân cách ngày
    if (ngay === homNay) return 'Hôm nay';  // cùng ngày với hôm nay
    if (homNay && ngay === ngayTruoc(homNay)) return 'Hôm qua';  // ngày liền trước
    var p = ngay.split('-');  // còn lại: dd/mm/yyyy
    return p[2] + '/' + p[1] + '/' + p[0];  // đổi thứ tự cho đúng kiểu Việt Nam
  }

  function cungNhom(a, b) {  // hai tin liền nhau có thuộc cùng một nhóm không
    return a.dataset.nguoi === b.dataset.nguoi && a.dataset.ngay === b.dataset.ngay && Math.abs(b.dataset.ts - a.dataset.ts) < NHOM_GIAY;  // cùng người, cùng ngày, cách nhau dưới 5 phút
  }

  function capNhatTrangThaiTin() {  // hiện "Đã gửi" hoặc "Đã xem" dưới tin CUỐI CÙNG của mình (giống Messenger)
    Array.prototype.forEach.call(thanTin.querySelectorAll('.tn__trang-thai'), function (x) { x.remove(); });  // gỡ nhãn cũ
    var cuaToi = thanTin.querySelectorAll('.tn--cua-toi[data-id]');  // các tin đã lưu của mình (bong bóng lỗi không có data-id)
    if (!cuaToi.length) return;  // chưa gửi tin nào
    var cuoi = cuaToi[cuaToi.length - 1];  // tin cuối của mình
    var nhan = document.createElement('p');  // dòng nhãn
    nhan.className = 'tn__trang-thai';  // CSS chữ nhỏ, canh phải
    nhan.textContent = parseInt(cuoi.dataset.id, 10) <= doiDaXem ? 'Đã xem' : 'Đã gửi';  // đối phương đã xem tới tin này chưa
    cuoi.appendChild(nhan);  // gắn dưới tin
  }

  function phanLoai() {  // dựng lại dòng ngày và đánh dấu nhóm cho TOÀN BỘ tin (rẻ, vì chỉ vài chục tin)
    Array.prototype.forEach.call(thanTin.querySelectorAll('.chat__ngay'), function (x) { x.remove(); });  // xóa dòng ngày cũ để dựng lại cho đúng
    var tins = Array.prototype.slice.call(thanTin.querySelectorAll('.tn[data-id]'));  // chỉ tin đã lưu (bong bóng lỗi không có data-id)
    tins.forEach(function (t) { if (t.dataset.ngay > homNay) homNay = t.dataset.ngay; });  // trang mở qua nửa đêm: ngày mới nhất coi là hôm nay
    tins.forEach(function (t, i) {  // duyệt từng tin
      var truoc = tins[i - 1], sau = tins[i + 1];  // tin liền trước và liền sau
      if (!truoc || truoc.dataset.ngay !== t.dataset.ngay) {  // tin đầu tiên của một ngày
        var d = document.createElement('div');  // dòng phân cách
        d.className = 'chat__ngay';  // CSS vẽ hai đường kẻ hai bên chữ
        d.setAttribute('role', 'separator');  // cho trình đọc màn hình
        d.textContent = nhanNgay(t.dataset.ngay);  // Hôm nay / Hôm qua / dd/mm/yyyy
        thanTin.insertBefore(d, t);  // chèn ngay trước tin đó
      }
      t.classList.toggle('tn--lien-tiep', !!truoc && cungNhom(truoc, t));  // nối tiếp tin trước: nhích sát lên
      t.classList.toggle('tn--co-tiep', !!sau && cungNhom(t, sau));  // còn tin sau cùng nhóm: ẩn giờ và ảnh
    });
    capNhatTrangThaiTin();  // cập nhật nhãn Đã gửi / Đã xem
  }

  // ----- chèn tin -----
  function chenCuoi(cacTin, ep) {  // thêm các tin MỚI vào cuối danh sách (cacTin đã sắp cũ trước mới sau)
    var html = '';  // gom HTML
    var anhMoi = [];  // ảnh của các tin mới, để thêm vào panel "Ảnh đã chia sẻ"
    var lkMoi = [];  // link của các tin mới, để thêm vào mục "Liên kết" ở cột phải
    cacTin.forEach(function (t) {  // duyệt từng tin
      if (!thanTin.querySelector('[data-id="' + t.id + '"]')) { html += t.html; (t.anh || []).forEach(function (a) { anhMoi.push(a); }); (t.lk || []).forEach(function (l) { lkMoi.push({ ma: t.id, url: l.url, hien: l.hien_thi }); }); }  // chỉ thêm nếu chưa có (chống trùng khi hai lần polling chồng nhau)
      if (t.id > idCuoi) idCuoi = t.id;  // nâng mốc tin cuối
      if (idDau === 0 || t.id < idDau) idDau = t.id;  // danh sách đang trống thì đặt mốc tin đầu
    });
    if (!html) return;  // không có gì mới
    themAnhVaoPanel(anhMoi);  // ảnh mới lên đầu panel bên phải
    themLienKetVaoPanel(lkMoi);  // link mới lên đầu mục "Liên kết" bên phải
    var trong = thanTin.querySelector('[data-chat-trong]');  // câu "Cuộc trò chuyện đã được khởi tạo"
    if (trong) trong.remove();  // có tin rồi thì bỏ câu này
    var dangODay = ganDay();  // đo trước khi chèn
    var tinLoi = thanTin.querySelector('.tn--loi');  // tin chưa gửi được luôn nằm cuối cùng
    if (tinLoi) tinLoi.insertAdjacentHTML('beforebegin', html);  // chèn tin thật phía trên tin lỗi
    else thanTin.insertAdjacentHTML('beforeend', html);  // không có tin lỗi thì chèn cuối
    phanLoai();  // dựng lại nhóm và dòng ngày
    if (ep || dangODay) cuonXuong();  // tin của mình hoặc đang ở đáy thì cuộn xuống
    else nutTinMoi.hidden = false;  // đang đọc phía trên thì chỉ hiện nút báo
  }

  function chenDau(cacTin) {  // thêm các tin CŨ vào đầu danh sách mà không làm nhảy vị trí đọc
    var html = '';  // gom HTML
    cacTin.forEach(function (t) {  // duyệt từng tin
      if (!thanTin.querySelector('[data-id="' + t.id + '"]')) html += t.html;  // bỏ tin đã có
    });
    if (cacTin.length) idDau = cacTin[0].id;  // mốc tin đầu mới
    if (!html) return;  // không có gì để thêm
    var caoCu = danhSach.scrollHeight, cuonCu = danhSach.scrollTop;  // đo trước khi chèn
    thanTin.insertAdjacentHTML('afterbegin', html);  // chèn lên đầu
    phanLoai();  // dựng lại nhóm và dòng ngày
    danhSach.scrollTop = cuonCu + (danhSach.scrollHeight - caoCu);  // bù phần chiều cao vừa tăng để người dùng vẫn đứng ở tin đang đọc
  }

  // ----- polling -----
  function layTinMoi(ep) {  // hỏi server các tin có mã lớn hơn idCuoi; trả về Promise
    var dangXem = !document.hidden && document.hasFocus();  // người dùng đang nhìn tab này
    return goi(urlMoi + '?sau=' + idCuoi + '&tu=' + idDau + (dangXem ? '&xem=' + idCuoi : '')).then(function (kq) {  // gọi polling; ?xem= báo đã xem tới tin cuối đang hiện
      if (kq.status === 401) {  // phiên đăng nhập đã hết hạn
        dung = true;  // dừng hẳn
        hienTrangThai(LOI_PHIEN);  // báo người dùng
        return;  // kết thúc
      }
      if (kq.status === 403 || kq.status === 404) {  // không còn quyền xem cuộc này
        dung = true;  // dừng hẳn
        hienTrangThai('Bạn không còn quyền xem cuộc trò chuyện này.');  // báo người dùng
        return;  // kết thúc
      }
      if (!kq.ok) throw new Error('loi may chu');  // lỗi 5xx: để nơi gọi xử lý như mất kết nối
      loiLienTiep = 0;  // thành công thì xóa đếm lỗi
      hienTrangThai('');  // ẩn thanh trạng thái
      if (typeof kq.duLieu.doi_da_xem === 'number' && kq.duLieu.doi_da_xem > doiDaXem) { doiDaXem = kq.duLieu.doi_da_xem; capNhatTrangThaiTin(); }  // đối phương vừa xem thêm: đổi "Đã gửi" thành "Đã xem"
      if (kq.duLieu.tin_nhan && kq.duLieu.tin_nhan.length) chenCuoi(kq.duLieu.tin_nhan, ep);  // có tin mới thì chèn
      if (kq.duLieu.thu_hoi && kq.duLieu.thu_hoi.length) thuHoiTrenTrang(kq.duLieu.thu_hoi);  // có tin vừa bị thu hồi thì đổi bong bóng tương ứng (server chỉ gửi mã tin, không gửi nội dung)
    });
  }

  function henLai() {  // đặt lịch lần polling kế tiếp sau 2 giây
    clearTimeout(hen);  // hủy lịch cũ để không có hai vòng chạy song song
    hen = setTimeout(vong, CHU_KY_MS);  // hẹn giờ
  }

  function vong() {  // một vòng polling
    if (dung) return;  // đã dừng hẳn
    if (document.hidden) return;  // tab đang ẩn thì tạm nghỉ, visibilitychange sẽ gọi lại
    if (quaNghi()) {  // quá lâu không thao tác
      dangNghi = true;  // tạm dừng để phiên đăng nhập có thể tự hết hạn (cờ dùng chung với cột trái)
      hienTrangThai('Đã tạm dừng cập nhật vì bạn lâu không thao tác. Di chuột hoặc bấm phím để tiếp tục.');  // báo người dùng
      return;  // không hẹn lại
    }
    layTinMoi(false).then(function () {  // hỏi tin mới
      henLai();  // xong thì hẹn vòng sau (setTimeout nối tiếp, không dùng setInterval để các lần gọi không chồng nhau)
    }).catch(function () {  // lỗi mạng hoặc lỗi máy chủ
      loiLienTiep += 1;  // đếm lỗi
      if (loiLienTiep >= 3) hienTrangThai('Mất kết nối. Đang thử lại…');  // từ 3 lần lỗi liên tiếp mới báo
      henLai();  // vẫn thử lại
    });
  }

  hamTiepTuc.push(function () {  // quay lại thao tác sau khi tạm dừng vì nghỉ lâu
    if (dung) return;  // đã dừng hẳn thì thôi
    hienTrangThai('');  // ẩn thanh trạng thái
    clearTimeout(hen);  // hủy lịch cũ (nếu có)
    vong();  // hỏi tin mới ngay
  });
  function quayLaiXem() {  // tab hiện lại hoặc cửa sổ được chọn lại
    if (!document.hidden && !dung && !dangNghi) {  // đang chạy bình thường
      clearTimeout(hen);  // hủy lịch cũ
      vong();  // hỏi tin mới ngay, đồng thời báo "đã xem" cho đối phương
    }
  }
  document.addEventListener('visibilitychange', quayLaiXem);  // người dùng chuyển tab
  window.addEventListener('focus', quayLaiXem);  // người dùng bấm lại vào cửa sổ trình duyệt

  // ----- tải tin cũ -----
  function taiCu() {  // kéo lên đầu danh sách: tải 30 tin cũ hơn
    if (!conCu || dangTaiCu || idDau === 0) return;  // hết tin cũ, đang tải, hoặc chưa có mốc
    dangTaiCu = true;  // đánh dấu đang tải
    if (nutTaiCu) nutTaiCu.classList.add('is-loading');  // hiện vòng quay trên nút
    goi(urlMoi + '?truoc=' + idDau).then(function (kq) {  // gọi server
      if (!kq.ok) throw new Error('loi');  // lỗi thì nhảy xuống catch
      chenDau(kq.duLieu.tin_nhan || []);  // chèn tin cũ lên đầu
      conCu = !!kq.duLieu.con_cu;  // cập nhật còn tin cũ không
      if (nutTaiCu && !conCu) nutTaiCu.hidden = true;  // hết tin cũ thì ẩn nút
      hienLoi('');  // xóa lỗi cũ
    }).catch(function () {  // luồng ngoại lệ 2a
      hienLoi(LOI_TAI);  // báo không tải được
    }).then(function () {  // chạy sau cả thành công lẫn lỗi
      dangTaiCu = false;  // cho phép tải lại
      if (nutTaiCu) nutTaiCu.classList.remove('is-loading');  // tắt vòng quay
    });
  }

  danhSach.addEventListener('scroll', function () {  // người dùng cuộn danh sách
    if (danhSach.scrollTop < 40) taiCu();  // chạm đầu danh sách thì tải tin cũ
    giuDay = ganDay();  // ghi nhớ người dùng có đang ở đáy không
    if (giuDay) nutTinMoi.hidden = true;  // xuống tới đáy thì ẩn nút "Có tin mới"
  });
  if (nutTaiCu) nutTaiCu.addEventListener('click', taiCu);  // bấm nút "Xem tin cũ hơn"
  nutTinMoi.addEventListener('click', cuonXuong);  // bấm "Có tin mới" thì cuộn xuống

  // ----- ảnh: chọn, xem trước, gửi (bước 5) -----
  var oAnh = form.querySelector('[data-chat-chon-anh]');  // ô chọn file ẩn
  var nutAnh = form.querySelector('[data-chat-nut-anh]');  // nút đính kèm ảnh
  var khungXemTruoc = form.querySelector('[data-chat-xem-truoc]');  // dải ảnh nhỏ sắp gửi
  var TOI_DA_ANH = parseInt(form.dataset.toiDaAnh, 10) || 5;  // số ảnh tối đa mỗi tin (lấy từ server)
  var TOI_DA_BYTE = 5 * 1024 * 1024;  // 5 MB mỗi ảnh, đúng với server
  var KIEU_ANH = ['image/jpeg', 'image/png', 'image/webp'];  // định dạng được nhận, đúng với server
  var dsAnh = [];  // các ảnh đang chọn: { tep: File, url: địa chỉ xem trước }
  if (oAnh) oAnh.removeAttribute('name');  // JavaScript tự đưa ảnh vào dữ liệu gửi đi (dsAnh) để bỏ được từng ảnh; không có JavaScript thì ô này vẫn gửi bình thường

  function veXemTruoc() {  // vẽ lại dải ảnh nhỏ theo dsAnh
    if (!khungXemTruoc) return;  // trang không có ô ảnh
    khungXemTruoc.textContent = '';  // xóa cũ
    dsAnh.forEach(function (a, i) {  // mỗi ảnh một ô
      var o = document.createElement('div');
      o.className = 'chat__xt-o';
      var hinh = document.createElement('img');
      hinh.src = a.url;  // địa chỉ blob: tạm trong trình duyệt
      hinh.alt = a.tep.name;
      var bo = document.createElement('button');  // nút bỏ ảnh này
      bo.type = 'button';
      bo.className = 'chat__xt-bo';
      bo.setAttribute('aria-label', 'Bỏ ảnh ' + a.tep.name);
      bo.textContent = '×';
      bo.addEventListener('click', function () { boAnh(i); });
      o.appendChild(hinh);
      o.appendChild(bo);
      khungXemTruoc.appendChild(o);
    });
    khungXemTruoc.hidden = dsAnh.length === 0;  // không có ảnh thì ẩn dải
    capNhatNutGui();  // có ảnh thì được gửi dù ô chữ trống
  }

  function boAnh(i) {  // bỏ một ảnh khỏi danh sách chọn
    URL.revokeObjectURL(dsAnh[i].url);  // giải phóng bộ nhớ
    dsAnh.splice(i, 1);  // xóa khỏi danh sách
    hienLoi('');  // xóa lỗi cũ (ví dụ vượt số ảnh)
    veXemTruoc();
  }

  function xoaHetAnh() {  // gửi xong: bỏ toàn bộ ảnh đã chọn
    dsAnh.forEach(function (a) { URL.revokeObjectURL(a.url); });
    dsAnh = [];
    veXemTruoc();
  }

  function themAnh(cacTep) {  // thêm ảnh vừa chọn / dán vào danh sách, kiểm tra trước khi gửi (server vẫn kiểm lại)
    var loi = '';  // lỗi cuối cùng gặp phải
    Array.prototype.forEach.call(cacTep, function (t) {
      if (KIEU_ANH.indexOf(t.type) === -1) { loi = 'Chỉ nhận ảnh JPG, PNG hoặc WEBP.'; return; }  // sai định dạng
      if (t.size > TOI_DA_BYTE) { loi = 'Mỗi ảnh tối đa 5 MB: ' + t.name; return; }  // quá nặng
      if (dsAnh.length >= TOI_DA_ANH) { loi = 'Mỗi tin nhắn tối đa ' + TOI_DA_ANH + ' ảnh.'; return; }  // quá nhiều
      dsAnh.push({ tep: t, url: URL.createObjectURL(t) });  // hợp lệ
    });
    hienLoi(loi);  // có lỗi thì báo, không thì xóa lỗi cũ
    veXemTruoc();
  }

  if (oAnh && nutAnh) {
    nutAnh.addEventListener('click', function () { oAnh.click(); });  // nút mở hộp chọn file
    oAnh.addEventListener('change', function () { themAnh(oAnh.files); oAnh.value = ''; });  // chọn xong thì thêm; xóa giá trị để chọn lại cùng một ảnh được
  }

  oNhap.addEventListener('paste', function (e) {  // dán ảnh từ bộ nhớ tạm (Ctrl+V sau khi chụp màn hình)
    var cacTep = [];
    Array.prototype.forEach.call((e.clipboardData && e.clipboardData.items) || [], function (muc) {
      if (muc.kind === 'file' && muc.type.indexOf('image/') === 0) { var t = muc.getAsFile(); if (t) cacTep.push(t); }
    });
    if (cacTep.length) { e.preventDefault(); themAnh(cacTep); }  // chỉ chặn khi thật sự có ảnh, dán chữ vẫn bình thường
  });

  // ----- panel "File phương tiện" ở cột phải: ảnh chia theo tháng, mới nhất trên cùng -----
  function capNhatPanelRong() {  // hiện câu "Chưa có file phương tiện nào" khi không còn ảnh, ngược lại hiện lưới
    var goc = document.querySelector('[data-chat-anh-cac-thang]');  // khối chứa các tháng
    var rong = document.querySelector('[data-chat-anh-rong]');  // câu trạng thái rỗng
    if (!goc) return;  // cột phải không có panel
    Array.prototype.slice.call(goc.querySelectorAll('[data-chat-anh-thang]')).forEach(function (t) {  // duyệt từng tháng
      if (!t.querySelector('[data-chat-anh]')) t.remove();  // tháng không còn ảnh nào thì bỏ cả tiêu đề
    });
    var coAnh = !!goc.querySelector('[data-chat-anh]');  // còn ảnh nào không
    goc.hidden = !coAnh;  // ẩn khối khi không có ảnh
    if (rong) rong.hidden = coAnh;  // hiện câu rỗng khi không có ảnh
  }

  function taoNhomThang(khoa, thang) {  // dựng nhóm tháng mới (ảnh vừa gửi luôn thuộc tháng hiện tại của năm nay)
    var nhom = document.createElement('section');  // khối một tháng
    nhom.className = 'chat-anh-thang';  // giống phần server dựng
    nhom.setAttribute('data-chat-anh-thang', khoa);  // khóa tháng, vd 2026-11
    var tieuDe = document.createElement('h3');  // tiêu đề tháng
    tieuDe.className = 'chat-anh-thang__ten';
    tieuDe.textContent = 'Tháng ' + thang;  // vd "Tháng 11"
    var luoi = document.createElement('div');  // lưới ảnh 3 cột
    luoi.className = 'chat-anh-luoi';
    luoi.setAttribute('data-chat-anh-luoi', '');
    nhom.appendChild(tieuDe);  // ghép tiêu đề
    nhom.appendChild(luoi);  // ghép lưới
    return nhom;  // trả về nhóm
  }

  function themAnhVaoPanel(cacAnh) {  // cacAnh: [{ma, url}] cũ trước mới sau; ảnh mới nhất nằm đầu panel, trong tháng hiện tại
    var goc = document.querySelector('[data-chat-anh-cac-thang]');  // khối chứa các tháng
    if (!goc) return;  // cột phải không có panel
    var bay = new Date();  // ảnh vừa gửi / vừa nhận nên thuộc tháng hiện tại
    var khoa = bay.getFullYear() + '-' + ('0' + (bay.getMonth() + 1)).slice(-2);  // cùng cách đặt khóa với server (2026-11)
    cacAnh.forEach(function (a) {  // từng ảnh
      if (goc.querySelector('[data-ma="' + a.ma + '"]')) return;  // đã có
      var thang = goc.querySelector('[data-chat-anh-thang]');  // nhóm đầu tiên là tháng mới nhất
      if (!thang || thang.getAttribute('data-chat-anh-thang') !== khoa) {  // chưa có nhóm tháng này
        thang = taoNhomThang(khoa, bay.getMonth() + 1);  // dựng nhóm mới
        goc.insertBefore(thang, goc.firstChild);  // đặt lên đầu
      }
      var luoi = thang.querySelector('[data-chat-anh-luoi]');  // lưới của tháng
      var nut = document.createElement('button');  // ô ảnh
      nut.type = 'button';
      nut.className = 'chat-anh-luoi__o';
      nut.setAttribute('data-chat-anh', '');
      nut.setAttribute('aria-label', 'Xem ảnh');
      nut.dataset.ma = a.ma;
      nut.dataset.url = a.url;
      var hinh = document.createElement('img');  // ảnh thu nhỏ
      hinh.src = a.url + '?nho=1';
      hinh.alt = 'Ảnh trong cuộc trò chuyện';
      nut.appendChild(hinh);
      luoi.insertBefore(nut, luoi.firstChild);  // mới nhất lên đầu tháng
    });
    capNhatPanelRong();  // cập nhật trạng thái rỗng
  }

  function capNhatLienKetRong() {  // hiện danh sách khi có link, ngược lại hiện câu "Chưa có liên kết nào"
    var ds = document.querySelector('[data-chat-lien-ket]');  // danh sách link ở cột phải
    var rong = document.querySelector('[data-chat-lk-rong]');  // câu trạng thái rỗng
    if (!ds) return;  // cột phải không có mục này
    var coLink = !!ds.querySelector('[data-chat-lk]');  // còn link nào không
    ds.hidden = !coLink;  // ẩn danh sách khi trống
    if (rong) rong.hidden = coLink;  // hiện câu rỗng khi trống
  }

  function themLienKetVaoPanel(cacLk) {  // cacLk: [{ma, url, hien}] cũ trước mới sau; link mới nhất nằm đầu danh sách
    var ds = document.querySelector('[data-chat-lien-ket]');  // danh sách link ở cột phải
    if (!ds) return;  // cột phải không có mục này
    cacLk.forEach(function (lk) {  // từng link
      var daCo = Array.prototype.some.call(ds.querySelectorAll('[data-chat-lk]'), function (o) { return o.dataset.url === lk.url; });  // link này đã có trong danh sách chưa
      if (daCo) return;  // có rồi thì bỏ qua
      var li = document.createElement('li');  // một dòng link
      li.className = 'chat-lien-ket__muc';  // giống phần server dựng
      li.setAttribute('data-chat-lk', '');  // đánh dấu để tìm lại
      li.dataset.maTin = lk.ma;  // mã tin chứa link, để gỡ khi tin bị thu hồi
      li.dataset.url = lk.url;  // địa chỉ, để chống trùng
      var a = document.createElement('a');  // thẻ link
      a.href = lk.url;  // server chỉ đưa ra link http hoặc https
      a.target = '_blank';  // mở tab mới
      a.rel = 'noopener noreferrer nofollow';  // an toàn như phần server dựng
      a.title = lk.url;  // rê chuột xem địa chỉ đầy đủ
      a.textContent = lk.hien;  // textContent nên không bị chèn HTML
      li.appendChild(a);  // ghép link vào dòng
      ds.insertBefore(li, ds.firstChild);  // mới nhất lên đầu
    });
    capNhatLienKetRong();  // cập nhật trạng thái rỗng
  }

  function goLienKetKhoiPanel(maTin) {  // bỏ các link của tin vừa thu hồi khỏi mục "Liên kết"
    var ds = document.querySelector('[data-chat-lien-ket]');  // danh sách link ở cột phải
    if (!ds) return;  // cột phải không có mục này
    Array.prototype.slice.call(ds.querySelectorAll('[data-chat-lk][data-ma-tin="' + maTin + '"]')).forEach(function (o) { o.remove(); });  // gỡ từng link của tin đó
    capNhatLienKetRong();  // hết link thì hiện câu rỗng
  }

  // ----- trang xem ảnh (lightbox): bấm ảnh trong tin hoặc trong panel -----
  var hopXem = null;  // hộp xem ảnh (tạo khi bấm lần đầu)
  var anhXem = [];  // các nút ảnh cùng bộ với ảnh đang xem
  var viTriXem = 0;  // đang xem ảnh thứ mấy
  var nutTruocKhiMo = null;  // phần tử đang được chọn trước khi mở, để trả lại tiêu điểm khi đóng

  function dungHopXem() {  // dựng hộp xem ảnh bằng DOM
    var h = document.createElement('div');
    h.className = 'chat-xem-anh';
    h.hidden = true;
    h.setAttribute('role', 'dialog');
    h.setAttribute('aria-modal', 'true');
    h.setAttribute('aria-label', 'Xem ảnh');
    h.innerHTML = '<button type="button" class="chat-xem-anh__nut chat-xem-anh__dong" data-xem="dong" aria-label="Đóng">×</button>' +
      '<button type="button" class="chat-xem-anh__nut chat-xem-anh__truoc" data-xem="truoc" aria-label="Ảnh trước">‹</button>' +
      '<img class="chat-xem-anh__anh" alt="Ảnh trong cuộc trò chuyện">' +
      '<button type="button" class="chat-xem-anh__nut chat-xem-anh__sau" data-xem="sau" aria-label="Ảnh sau">›</button>' +
      '<p class="chat-xem-anh__dem" aria-live="polite"></p>';  // nội dung cố định, không chứa dữ liệu người dùng
    h.addEventListener('click', function (e) {
      var nut = e.target.closest('[data-xem]');
      if (nut) { var v = nut.dataset.xem; if (v === 'dong') dongXem(); else chuyenAnh(v === 'truoc' ? -1 : 1); }
      else if (e.target === h) dongXem();  // bấm nền tối thì đóng
    });
    document.body.appendChild(h);
    return h;
  }

  function hienAnhXem() {  // hiện ảnh thứ viTriXem
    var anh = hopXem.querySelector('.chat-xem-anh__anh');
    anh.src = anhXem[viTriXem].dataset.url;  // ảnh đầy đủ
    hopXem.querySelector('.chat-xem-anh__dem').textContent = anhXem.length > 1 ? (viTriXem + 1) + ' / ' + anhXem.length : '';
    hopXem.querySelector('.chat-xem-anh__truoc').hidden = anhXem.length < 2;
    hopXem.querySelector('.chat-xem-anh__sau').hidden = anhXem.length < 2;
  }

  function chuyenAnh(buoc) {  // sang ảnh trước / sau, quay vòng
    viTriXem = (viTriXem + buoc + anhXem.length) % anhXem.length;
    hienAnhXem();
  }

  function moXem(nut) {  // mở hộp xem ảnh cho ảnh vừa bấm
    var nhom = nut.closest('[data-chat-nhom-anh]');  // bộ ảnh: toàn bộ tin trong khung chat, hoặc cả panel bên phải
    anhXem = Array.prototype.slice.call((nhom || document).querySelectorAll('[data-chat-anh]'));
    viTriXem = Math.max(0, anhXem.indexOf(nut));
    if (!hopXem) hopXem = dungHopXem();
    nutTruocKhiMo = document.activeElement;  // nhớ để trả tiêu điểm
    hienAnhXem();
    hopXem.hidden = false;
    document.body.style.overflow = 'hidden';  // không cuộn trang nền
    hopXem.querySelector('.chat-xem-anh__dong').focus();  // đưa tiêu điểm vào hộp
  }

  function dongXem() {  // đóng hộp xem ảnh
    if (!hopXem || hopXem.hidden) return;
    hopXem.hidden = true;
    hopXem.querySelector('.chat-xem-anh__anh').removeAttribute('src');  // dừng tải ảnh
    document.body.style.overflow = '';  // cho cuộn lại
    if (nutTruocKhiMo && document.contains(nutTruocKhiMo)) nutTruocKhiMo.focus();  // trả tiêu điểm về chỗ cũ
  }

  document.addEventListener('click', function (e) {  // bấm vào bất kỳ ảnh nào (event delegation vì tin mới được chèn liên tục)
    var nut = e.target.closest('[data-chat-anh]');
    if (nut) { e.preventDefault(); moXem(nut); }
  });
  document.addEventListener('keydown', function (e) {  // phím khi hộp đang mở
    if (!hopXem || hopXem.hidden) return;
    if (e.key === 'Escape') { dongXem(); return; }  // Esc đóng
    if (e.key === 'ArrowLeft' && anhXem.length > 1) chuyenAnh(-1);  // mũi tên trái: ảnh trước
    if (e.key === 'ArrowRight' && anhXem.length > 1) chuyenAnh(1);  // mũi tên phải: ảnh sau
    if (e.key === 'Tab') {  // giữ tiêu điểm trong hộp
      var cacNut = Array.prototype.filter.call(hopXem.querySelectorAll('button'), function (b) { return !b.hidden; });
      var dau = cacNut[0], cuoi = cacNut[cacNut.length - 1];
      if (e.shiftKey && document.activeElement === dau) { e.preventDefault(); cuoi.focus(); }
      else if (!e.shiftKey && document.activeElement === cuoi) { e.preventDefault(); dau.focus(); }
    }
  });
  thanTin.addEventListener('load', function (e) {  // ảnh trong tin tải xong làm khung cao thêm: đang ở đáy thì cuộn xuống lại
    if (e.target.tagName === 'IMG' && giuDay) danhSach.scrollTop = danhSach.scrollHeight;
  }, true);  // load không nổi bọt lên nên phải bắt ở giai đoạn capture

  // ----- thu hồi và trả lời tin (bước 6) -----
  var maTraLoi = 0;  // mã tin đang được trả lời (0 = không trả lời ai)
  var thanhTraLoi = form.querySelector('[data-chat-tra-loi-bar]');  // thanh "Đang trả lời ..." phía trên ô nhập
  var tenDoi = khung.dataset.tenDoi || '';  // tên đối phương, để ghi vào thanh trả lời
  var CHU_THU_HOI_MINH = 'Bạn đã thu hồi một tin nhắn';  // câu thay thế ở phía người gửi
  var CHU_THU_HOI_DOI = 'Tin nhắn đã bị thu hồi';  // câu thay thế ở phía người nhận

  function huyTraLoi() {  // bỏ trạng thái đang trả lời
    maTraLoi = 0;
    if (thanhTraLoi) thanhTraLoi.hidden = true;
  }

  function batDauTraLoi(tin) {  // bấm nút Trả lời ở một tin
    var nd = tin.querySelector('.tn__noi-dung');  // bong bóng chữ của tin (không tính khối trích dẫn)
    var chu = nd ? nd.textContent.trim() : (tin.querySelector('[data-chat-anh]') ? '[Ảnh]' : '');  // tin chỉ có ảnh thì ghi [Ảnh]
    if (chu.length > 80) chu = chu.slice(0, 80) + '…';  // cắt gọn
    maTraLoi = parseInt(tin.dataset.id, 10);  // ghi nhớ mã tin gốc
    thanhTraLoi.querySelector('[data-chat-tl-ten]').textContent = tin.dataset.nguoi === 'toi' ? 'chính mình' : tenDoi;  // textContent nên không bị chèn HTML
    thanhTraLoi.querySelector('[data-chat-tl-nd]').textContent = chu;
    thanhTraLoi.hidden = false;
    oNhap.focus();  // gõ trả lời ngay
  }

  function goAnhKhoiPanel(cacUrl) {  // bỏ các ảnh của tin vừa thu hồi khỏi panel "File phương tiện"
    var goc = document.querySelector('[data-chat-anh-cac-thang]');  // khối chứa các tháng
    if (!goc) return;  // không có panel
    Array.prototype.slice.call(goc.querySelectorAll('[data-chat-anh]')).forEach(function (o) {  // duyệt từng ảnh trong panel
      if (cacUrl.indexOf(o.dataset.url) !== -1) o.remove();  // ảnh thuộc tin vừa thu hồi thì gỡ
    });
    capNhatPanelRong();  // tháng hết ảnh thì bỏ tiêu đề, hết sạch thì hiện câu rỗng
  }

  function thuHoiTrenTrang(cacId) {  // đổi các bong bóng đã thu hồi thành câu thay thế, gỡ ảnh, gỡ nút, sửa các trích dẫn
    cacId.forEach(function (id) {
      goLienKetKhoiPanel(id);  // link của tin bị thu hồi biến mất khỏi mục "Liên kết" (kể cả khi tin không nằm trên trang)
      Array.prototype.forEach.call(thanTin.querySelectorAll('[data-chat-di-den="' + id + '"] .tn__tl-nd'), function (x) { x.textContent = CHU_THU_HOI_DOI; });  // các tin trả lời tin này không còn hiện nội dung gốc
      if (maTraLoi === id) huyTraLoi();  // đang định trả lời đúng tin vừa bị thu hồi thì hủy
      var tin = thanTin.querySelector('.tn[data-id="' + id + '"]');  // bong bóng của tin
      if (!tin || tin.querySelector('.tn__noi-dung--thu-hoi')) return;  // không có trên trang, hoặc đã đổi rồi
      goAnhKhoiPanel(Array.prototype.map.call(tin.querySelectorAll('[data-chat-anh]'), function (a) { return a.dataset.url; }));  // ảnh của tin khỏi panel
      Array.prototype.forEach.call(tin.querySelectorAll('.tn__anh-luoi, .tn__tra-loi-goc, .tn__hanh-dong'), function (x) { x.remove(); });  // gỡ ảnh, trích dẫn, nút
      var cha = tin.querySelector('.tn__khoi') || tin;  // ruột tin nằm trong .tn__khoi (cả tin của mình lẫn của đối phương)
      var nd = cha.querySelector('.tn__noi-dung');  // bong bóng chữ (tin chỉ có ảnh thì chưa có)
      if (!nd) { nd = document.createElement('p'); cha.insertBefore(nd, cha.firstChild); }
      nd.className = 'tn__noi-dung tn__noi-dung--thu-hoi';
      nd.textContent = tin.dataset.nguoi === 'toi' ? CHU_THU_HOI_MINH : CHU_THU_HOI_DOI;  // textContent: nội dung cũ biến mất khỏi trang
    });
  }

  function thuHoi(nut) {  // bấm nút Thu hồi ở tin của mình
    if (!window.confirm('Thu hồi tin nhắn này? Cả hai bên sẽ không còn thấy nội dung tin.')) return;  // hỏi xác nhận
    var tin = nut.closest('.tn');
    var id = parseInt(tin.dataset.id, 10);
    var oToken = form.querySelector('[name="csrfmiddlewaretoken"]');  // CSRF token có sẵn trong form soạn tin
    nut.disabled = true;  // chặn bấm đúp
    ghiNhanHoatDong();
    goi(nut.dataset.url, { method: 'POST', headers: { 'X-CSRFToken': oToken ? oToken.value : '' } }).then(function (kq) {
      if (kq.status === 401) { hienLoi(LOI_PHIEN); nut.disabled = false; return; }  // hết phiên
      if (!kq.ok) { hienLoi(kq.duLieu.loi || 'Không thể thu hồi tin nhắn. Vui lòng thử lại.'); nut.disabled = false; return; }  // bị từ chối hoặc lỗi máy chủ
      hienLoi('');
      thuHoiTrenTrang([id]);  // đổi ngay trên trang, không chờ polling
      vanTay = '';  // dòng xem trước ở cột trái cũng đổi thành "Bạn đã thu hồi..."
      dongBoDs().catch(function () {});
    }).catch(function () { hienLoi('Không thể thu hồi tin nhắn. Vui lòng thử lại.'); nut.disabled = false; });  // lỗi mạng
  }

  function diDen(ma) {  // bấm khối trích dẫn: cuộn tới tin gốc (nếu đang có trên trang) và làm nổi bật
    var dich = thanTin.querySelector('.tn[data-id="' + ma + '"]');
    if (!dich) return;  // tin gốc còn nằm ở phần chưa tải
    dich.scrollIntoView({ block: 'center', behavior: 'smooth' });
    dich.classList.add('tn--noi-bat');
    setTimeout(function () { dich.classList.remove('tn--noi-bat'); }, 1600);
  }

  thanTin.addEventListener('click', function (e) {  // event delegation: tin mới được chèn liên tục
    var nutTl = e.target.closest('[data-chat-tra-loi]');
    if (nutTl) { batDauTraLoi(nutTl.closest('.tn')); return; }
    var nutTh = e.target.closest('[data-chat-thu-hoi]');
    if (nutTh) { thuHoi(nutTh); return; }
    var goc = e.target.closest('[data-chat-di-den]');
    if (goc) diDen(goc.dataset.chatDiDen);
  });
  if (thanhTraLoi) thanhTraLoi.querySelector('[data-chat-huy-tra-loi]').addEventListener('click', function () { huyTraLoi(); oNhap.focus(); });  // nút × hủy trả lời
  oNhap.addEventListener('keydown', function (e) { if (e.key === 'Escape' && maTraLoi) huyTraLoi(); });  // Esc trong ô nhập cũng hủy trả lời

  // ----- soạn và gửi tin -----
  function tuCaoLen() {  // ô nhập tự cao lên theo số dòng, tối đa 9rem (CSS)
    oNhap.style.height = 'auto';  // đặt lại để đo đúng
    oNhap.style.height = oNhap.scrollHeight + 'px';  // cao đúng bằng nội dung
  }

  function capNhatNutGui() {  // khóa nút Gửi khi ô trống hoặc đang gửi (đúng wireframe: nút xám)
    nutGui.disabled = dangGui || (!oNhap.value.trim() && !dsAnh.length);  // vừa trống chữ vừa không có ảnh thì khóa (chỉ có khoảng trắng cũng tính là trống)
    nutGui.classList.toggle('is-loading', dangGui);  // đang gửi thì hiện vòng quay
  }

  function themTinLoi(noiDung) {  // thêm bong bóng nét đứt "Không gửi được. Gửi lại" ở cuối danh sách
    var tin = document.createElement('article');  // một tin
    tin.className = 'tn tn--cua-toi tn--loi';  // nằm bên phải như tin của mình, kiểu lỗi
    if (maTraLoi) tin.dataset.traLoi = maTraLoi;  // nhớ tin đang trả lời để bấm Gửi lại vẫn đúng như cũ
    var hang = document.createElement('div');  // hàng: dấu ! + bong bóng
    hang.className = 'tn__hang';
    var icon = document.createElement('span');  // dấu ! trong vòng tròn
    icon.className = 'tn__icon-loi';
    icon.setAttribute('aria-hidden', 'true');
    icon.textContent = '!';
    var nd = document.createElement('p');  // nội dung chưa gửi được
    nd.className = 'tn__noi-dung';
    nd.textContent = noiDung;  // textContent nên an toàn trước XSS; xuống dòng giữ bằng CSS white-space
    hang.appendChild(icon);
    hang.appendChild(nd);
    var chu = document.createElement('p');  // dòng "Không gửi được. Gửi lại"
    chu.className = 'tn__loi-chu';
    chu.appendChild(document.createTextNode('Không gửi được. '));
    var nutLai = document.createElement('button');  // nút Gửi lại
    nutLai.type = 'button';  // không phải nút submit của form
    nutLai.className = 'tn__gui-lai';
    nutLai.textContent = 'Gửi lại';
    nutLai.addEventListener('click', function () { guiTin(noiDung, tin); });  // gửi lại đúng nội dung này
    chu.appendChild(nutLai);
    tin.appendChild(hang);
    tin.appendChild(chu);
    var trong = thanTin.querySelector('[data-chat-trong]');  // có bong bóng rồi thì bỏ câu "đã được khởi tạo"
    if (trong) trong.remove();
    thanTin.appendChild(tin);  // luôn ở cuối
    cuonXuong();  // cho người dùng thấy ngay
  }

  function guiTin(noiDung, tinLoi) {  // gửi một tin; tinLoi = bong bóng lỗi đang được gửi lại (null nếu gửi từ ô nhập)
    if (dangGui) return;  // đang gửi thì bỏ qua lần bấm này
    dangGui = true;  // đánh dấu đang gửi
    capNhatNutGui();  // khóa nút Gửi
    ghiNhanHoatDong();  // gửi tin cũng là thao tác
    var nutLai = tinLoi ? tinLoi.querySelector('.tn__gui-lai') : null;  // nút Gửi lại của bong bóng (nếu có)
    if (nutLai) nutLai.disabled = true;  // chặn bấm đúp
    var fd = new FormData(form);  // FormData đã có csrfmiddlewaretoken
    fd.set('noi_dung', noiDung);  // đặt đúng nội dung cần gửi (khi gửi lại, ô nhập có thể đang chứa chữ khác)
    var tl = tinLoi ? (tinLoi.dataset.traLoi || '') : (maTraLoi || '');  // tin đang trả lời (bong bóng lỗi thì lấy cái đã nhớ)
    if (tl) fd.set('tra_loi', tl);  // gửi kèm mã tin gốc
    if (!tinLoi) dsAnh.forEach(function (a) { fd.append('anh', a.tep, a.tep.name); });  // đính các ảnh đã chọn (bong bóng "Gửi lại" chỉ dành cho tin chữ nên không kèm ảnh)
    goi(form.action, { method: 'POST', body: fd }).then(function (kq) {  // gửi ngầm
      if (kq.ok) {  // lưu thành công
        hienLoi('');  // xóa lỗi cũ
        if (tinLoi) tinLoi.remove();  // gửi lại thành công: bỏ bong bóng lỗi
        else { oNhap.value = ''; tuCaoLen(); xoaHetAnh(); huyTraLoi(); }  // gửi từ ô nhập: xóa ô nhập, thu về 1 dòng, bỏ ảnh đã chọn và bỏ trạng thái trả lời
        return layTinMoi(true).catch(function () {});  // lấy ngay các tin mới (gồm tin vừa gửi), tự cuộn xuống; lỗi mạng ở đây để vòng polling lo
      }
      if (kq.status === 401) { hienLoi(LOI_PHIEN); return; }  // phiên hết hạn: giữ nguyên chữ
      if (kq.status === 403 || kq.status === 404) {  // không còn quyền trong cuộc này
        dung = true;  // dừng polling
        hienLoi('Bạn không còn quyền gửi tin trong cuộc trò chuyện này.');
        return;
      }
      if (kq.status === 400) { hienLoi(kq.duLieu.loi || LOI_GUI); return; }  // nội dung không hợp lệ (quá dài...): giữ chữ để sửa
      thatBai(noiDung, tinLoi);  // lỗi máy chủ 5xx: luồng ngoại lệ 5a
    }).catch(function () {  // lỗi mạng
      thatBai(noiDung, tinLoi);  // luồng ngoại lệ 5a
    }).then(function () {  // chạy sau cả thành công lẫn lỗi
      dangGui = false;  // cho phép gửi tiếp
      if (nutLai) nutLai.disabled = false;  // mở lại nút Gửi lại
      capNhatNutGui();  // cập nhật trạng thái nút Gửi
      if (!tinLoi) oNhap.focus();  // gửi từ ô nhập thì trả con trỏ về ô nhập
    });
  }

  function thatBai(noiDung, tinLoi) {  // gửi không được (5xx hoặc mất mạng)
    hienLoi(LOI_GUI);  // hộp lỗi nét đứt ở đầu khung
    if (!tinLoi && dsAnh.length) return;  // tin có ảnh: giữ nguyên chữ và ảnh trong ô nhập để bấm Gửi lại (bong bóng "Gửi lại" chỉ dành cho tin chữ)
    if (!tinLoi) {  // gửi từ ô nhập: chuyển chữ xuống thành bong bóng lỗi để khỏi mất
      oNhap.value = '';  // xóa ô nhập như wireframe
      tuCaoLen();  // thu ô nhập về 1 dòng
      themTinLoi(noiDung);  // bong bóng "Không gửi được. Gửi lại"
      huyTraLoi();  // bong bóng lỗi đã nhớ tin trả lời nên thanh trả lời không còn cần
    }
  }

  oNhap.addEventListener('input', function () { tuCaoLen(); capNhatNutGui(); });  // mỗi lần gõ: tự cao + khóa/mở nút Gửi

  oNhap.addEventListener('keydown', function (e) {  // phím trong ô nhập
    if (e.key !== 'Enter' || e.shiftKey) return;  // chỉ xử lý Enter không kèm Shift
    if (e.isComposing || e.keyCode === 229) return;  // đang gõ dấu tiếng Việt bằng bộ gõ (Telex, VNI): Enter chỉ để chốt chữ, không gửi
    e.preventDefault();  // không xuống dòng
    if (!nutGui.disabled) form.requestSubmit();  // nút đang khóa (trống hoặc đang gửi) thì Enter không làm gì
  });

  form.addEventListener('submit', function (e) {  // gửi tin
    e.preventDefault();  // gửi ngầm, không tải lại trang; app.js thấy defaultPrevented nên không thêm is-loading lần nữa
    var noiDung = oNhap.value.trim();  // bỏ khoảng trắng hai đầu
    if (!noiDung && !dsAnh.length) { capNhatNutGui(); return; }  // không chữ cũng không ảnh thì không gửi (nút đã khóa sẵn)
    guiTin(noiDung, null);  // gửi từ ô nhập
  });

  // ----- nút "i": mở / đóng cột thông tin bên phải, khung giữa tự kéo dài khi đóng -----
  var luoiChat = document.querySelector('.chat-luoi');  // lưới 3 cột của trang
  var nutThongTin = khung.querySelector('[data-chat-nut-thong-tin]');  // nút "i" ở đầu cuộc trò chuyện
  var KHOA_COT_PHAI = 'framie_chat_cot_phai';  // tên khóa nhớ lựa chọn trong trình duyệt (cho cả Khách hàng và Nhiếp ảnh gia)

  function docCotPhai() {  // lần trước để cột phải mở hay đóng; chưa chọn thì mở
    try { return window.localStorage.getItem(KHOA_COT_PHAI) !== '0'; } catch (e) { return true; }  // trình duyệt chặn lưu trữ thì coi như mở
  }

  function datCotPhai(mo, luu) {  // mở hoặc đóng cột phải
    if (!luoiChat || !nutThongTin) return;  // thiếu phần tử thì thôi
    luoiChat.classList.toggle('chat-luoi--dong-phai', !mo);  // đóng: lưới còn 2 cột, khung giữa dài ra
    nutThongTin.setAttribute('aria-pressed', mo ? 'true' : 'false');  // nút sáng khi đang mở
    if (luu) { try { window.localStorage.setItem(KHOA_COT_PHAI, mo ? '1' : '0'); } catch (e) { /* không lưu được thì bỏ qua */ } }  // nhớ lựa chọn
    if (giuDay) cuonXuong();  // đổi bề rộng làm tin xuống dòng khác đi, giữ người dùng ở cuối
  }

  if (nutThongTin) {  // có nút i
    datCotPhai(docCotPhai(), false);  // áp dụng lựa chọn lần trước
    nutThongTin.addEventListener('click', function () {  // bấm nút i
      datCotPhai(nutThongTin.getAttribute('aria-pressed') !== 'true', true);  // đảo trạng thái và nhớ lại
    });
  }

  // ----- bước 7: tìm trong cuộc trò chuyện -----
  function boDauKyTu(ky) {  // một ký tự thành đúng MỘT ký tự thường không dấu (giữ độ dài chuỗi, giống _bo_dau_ky_tu ở server)
    if (ky === 'đ' || ky === 'Đ') return 'd';  // đ riêng vì không tách dấu được
    var goc = ky.normalize('NFD').replace(/[\u0300-\u036f]/g, '');  // tách dấu rồi bỏ
    return (goc || ky).charAt(0).toLowerCase();  // lấy đúng 1 ký tự thường
  }

  function boDauChuoi(chuoi) {  // "Phạnh" -> "phanh"
    var kq = '';  // kết quả
    for (var i = 0; i < chuoi.length; i++) kq += boDauKyTu(chuoi.charAt(i));  // từng ký tự
    return kq;
  }

  function boTonTu(goc) {  // gỡ mọi chỗ đã tô sáng trong một phần tử
    Array.prototype.slice.call(goc.querySelectorAll('mark.tn__tim')).forEach(function (m) {  // từng chỗ tô
      var cha = m.parentNode;  // phần tử chứa
      cha.replaceChild(document.createTextNode(m.textContent), m);  // trả về chữ thường
      cha.normalize();  // gộp các đoạn chữ liền nhau
    });
  }

  function tonTu(goc, tuKhoa) {  // tô sáng mọi chỗ khớp từ khóa (không phân biệt hoa thường và dấu); chỉ dùng textContent nên không chèn HTML
    boTonTu(goc);  // gỡ lần tô cũ
    var chuan = boDauChuoi(tuKhoa.trim());  // từ khóa không dấu
    if (!chuan) return;  // từ khóa rỗng
    var duyet = document.createTreeWalker(goc, NodeFilter.SHOW_TEXT, null);  // duyệt các đoạn chữ (bỏ qua thẻ <br>)
    var cacNut = [];  // gom trước vì sẽ thay nút trong lúc duyệt
    while (duyet.nextNode()) cacNut.push(duyet.currentNode);
    cacNut.forEach(function (nut) {  // từng đoạn chữ
      var chu = nut.nodeValue;  // chữ gốc
      var khongDau = boDauChuoi(chu);  // bản không dấu cùng độ dài
      var vt = khongDau.indexOf(chuan);  // chỗ khớp đầu tiên
      if (vt === -1) return;  // không khớp
      var manh = document.createDocumentFragment();  // thay thế cả đoạn một lần
      var dau = 0;  // vị trí đã xử lý tới
      while (vt !== -1) {  // mọi chỗ khớp
        manh.appendChild(document.createTextNode(chu.slice(dau, vt)));  // chữ trước chỗ khớp
        var danhDau = document.createElement('mark');  // phần tô sáng
        danhDau.className = 'tn__tim';
        danhDau.textContent = chu.slice(vt, vt + chuan.length);  // giữ nguyên chữ gốc có dấu
        manh.appendChild(danhDau);
        dau = vt + chuan.length;
        vt = khongDau.indexOf(chuan, dau);  // chỗ khớp kế
      }
      manh.appendChild(document.createTextNode(chu.slice(dau)));  // phần chữ còn lại
      nut.parentNode.replaceChild(manh, nut);  // thay đoạn chữ cũ
    });
  }

  var thanhTim = khung.querySelector('[data-chat-tim-cuoc]');  // thanh tìm (ẩn cho tới khi bấm kính lúp)
  var nutMoTim = khung.querySelector('[data-chat-nut-tim]');  // nút kính lúp
  if (thanhTim && nutMoTim) {  // đủ phần tử mới chạy
    var oTimTrong = thanhTim.querySelector('[data-chat-tim-o]');  // ô gõ từ khóa
    var oDemTim = thanhTim.querySelector('[data-chat-tim-dem]');  // chữ 1/12
    var dsTim = thanhTim.querySelector('[data-chat-tim-ds]');  // danh sách đoạn trích
    var urlTim = khung.dataset.urlTim;  // địa chỉ tìm
    var urlDen = khung.dataset.urlDen;  // địa chỉ tải tin cũ để nhảy tới
    var ketQuaTim = [];  // kết quả mới nhất trước
    var viTriTim = -1;  // kết quả đang chọn
    var biCatTim = false;  // server báo còn nhiều hơn 100
    var tuKhoaTim = '';  // từ khóa của lượt tìm hiện tại
    var soLuotTim = 0;  // số thứ tự lượt tìm, bỏ kết quả của lượt cũ về muộn
    var henTim = null;  // hẹn giờ chờ người dùng gõ xong
    var tinDangTo = null;  // tin đang được tô sáng

    function boToTinDich() {  // gỡ tô sáng của tin đang chọn
      if (!tinDangTo) return;  // chưa có
      var nd = tinDangTo.querySelector('.tn__noi-dung');  // bong bóng chữ
      if (nd) boTonTu(nd);  // gỡ chữ tô sáng
      tinDangTo.classList.remove('tn--noi-bat');  // gỡ viền
      tinDangTo = null;  // quên
    }

    function capNhatDemTim() {  // chữ ở cạnh ô tìm
      if (!tuKhoaTim) oDemTim.textContent = '';  // chưa gõ gì
      else if (!ketQuaTim.length) oDemTim.textContent = 'Không có kết quả';  // không khớp
      else oDemTim.textContent = (viTriTim + 1) + '/' + ketQuaTim.length + (biCatTim ? '+' : '');  // vd 3/12, hoặc 3/100+
    }

    function xoaKetQuaTim() {  // xóa sạch kết quả
      ketQuaTim = []; viTriTim = -1; biCatTim = false;  // về trạng thái đầu
      dsTim.textContent = '';  // xóa danh sách
      dsTim.hidden = true;  // ẩn danh sách
      boToTinDich();  // gỡ tô sáng
      capNhatDemTim();  // xóa chữ đếm
    }

    function hienTinDich(ma, tuKhoa, muot) {  // cuộn tới tin, tô sáng chữ khớp; trả về false nếu tin chưa có trên trang
      var dich = thanTin.querySelector('.tn[data-id="' + ma + '"]');  // bong bóng của tin
      if (!dich) return false;  // chưa tải
      boToTinDich();  // gỡ tin trước
      tinDangTo = dich;  // ghi nhớ tin mới
      var nd = dich.querySelector('.tn__noi-dung:not(.tn__noi-dung--het-han)');  // bong bóng chữ (bỏ qua câu "ảnh đã hết hạn")
      if (nd) tonTu(nd, tuKhoa);  // tô sáng chữ khớp
      dich.classList.add('tn--noi-bat');  // viền nổi bật
      giuDay = false;  // không để ảnh tải xong kéo danh sách xuống đáy
      dich.scrollIntoView({ block: 'center', behavior: muot ? 'smooth' : 'auto' });  // cuộn tới giữa khung
      return true;
    }

    function nhayToiTin(ma, tuKhoa) {  // nhảy tới một tin, tải thêm tin cũ nếu tin chưa có trên trang
      if (hienTinDich(ma, tuKhoa, true)) return;  // đã có trên trang
      if (dangTaiCu || idDau === 0 || ma >= idDau) return;  // đang tải dở, hoặc không có gì để tải
      dangTaiCu = true;  // chặn gọi chồng với tải tin cũ khi kéo lên
      goi(urlDen + '?tin=' + ma + '&truoc=' + idDau).then(function (kq) {  // xin các tin từ gần tin cần tới đến trước tin đầu hiện tại
        if (kq.status === 401) { hienLoi(LOI_PHIEN); return; }  // hết phiên
        if (!kq.ok) { hienLoi(kq.duLieu.loi || LOI_TAI); return; }  // quá xa hoặc lỗi máy chủ
        chenDau(kq.duLieu.tin_nhan || []);  // chèn lên đầu danh sách, danh sách vẫn liền mạch
        conCu = !!kq.duLieu.con_cu;  // còn tin cũ hơn nữa không
        if (nutTaiCu && !conCu) nutTaiCu.hidden = true;  // hết tin cũ thì ẩn nút
        hienLoi('');  // xóa lỗi cũ
        hienTinDich(ma, tuKhoa, false);  // giờ tin đã có, cuộn tới
      }).catch(function () { hienLoi(LOI_TAI); }).then(function () { dangTaiCu = false; });  // lỗi mạng, và luôn mở khóa
    }

    function veKetQuaTim() {  // vẽ danh sách đoạn trích
      dsTim.textContent = '';  // xóa cũ
      ketQuaTim.forEach(function (k, i) {  // từng kết quả
        var li = document.createElement('li');  // một dòng
        var nut = document.createElement('button');  // bấm để nhảy tới tin
        nut.type = 'button';
        nut.className = 'chat__tim-muc';
        nut.dataset.viTri = i;  // thứ tự trong kết quả
        if (k.cua_toi) {  // tin của mình ghi "Bạn:"
          var ai = document.createElement('span');
          ai.className = 'chat__tim-ai';
          ai.textContent = 'Bạn:';
          nut.appendChild(ai);
        }
        var trich = document.createElement('span');  // đoạn trích
        trich.className = 'chat__tim-trich';
        trich.textContent = k.trich;  // textContent nên an toàn trước XSS
        tonTu(trich, tuKhoaTim);  // tô sáng từ khóa trong đoạn trích
        var luc = document.createElement('span');  // giờ gửi
        luc.className = 'chat__tim-luc';
        luc.textContent = k.luc;
        nut.appendChild(trich);
        nut.appendChild(luc);
        li.appendChild(nut);
        dsTim.appendChild(li);
      });
      dsTim.hidden = !ketQuaTim.length;  // không có kết quả thì ẩn danh sách
    }

    function chonKetQuaTim(i) {  // chọn kết quả thứ i và nhảy tới tin
      if (i < 0 || i >= ketQuaTim.length) return;  // ngoài phạm vi thì đứng yên
      viTriTim = i;  // ghi nhớ
      Array.prototype.forEach.call(dsTim.children, function (li, j) {  // đánh dấu dòng đang chọn
        li.firstChild.setAttribute('aria-current', j === i ? 'true' : 'false');
      });
      if (dsTim.children[i]) dsTim.children[i].scrollIntoView({ block: 'nearest' });  // dòng đang chọn luôn nằm trong vùng nhìn thấy của danh sách
      capNhatDemTim();  // cập nhật 3/12
      nhayToiTin(ketQuaTim[i].id, tuKhoaTim);  // nhảy tới tin
    }

    function timKiem() {  // gửi từ khóa lên server
      var tuKhoa = oTimTrong.value.trim();  // bỏ khoảng trắng hai đầu
      tuKhoaTim = tuKhoa;  // ghi nhớ
      var luot = ++soLuotTim;  // lượt tìm này
      if (!tuKhoa) { xoaKetQuaTim(); return; }  // ô trống thì xóa kết quả
      goi(urlTim + '?q=' + encodeURIComponent(tuKhoa)).then(function (kq) {  // gọi server
        if (luot !== soLuotTim) return;  // đã có lượt tìm mới hơn
        if (kq.status === 401) { hienLoi(LOI_PHIEN); return; }  // hết phiên
        if (!kq.ok) { oDemTim.textContent = 'Không tìm được'; return; }  // lỗi
        ketQuaTim = kq.duLieu.ket_qua || [];  // kết quả
        biCatTim = !!kq.duLieu.bi_cat;  // còn nhiều hơn 100 không
        veKetQuaTim();  // vẽ danh sách
        if (ketQuaTim.length) chonKetQuaTim(0);  // tự nhảy tới kết quả mới nhất
        else { viTriTim = -1; boToTinDich(); capNhatDemTim(); }  // không có kết quả
      }).catch(function () { if (luot === soLuotTim) oDemTim.textContent = 'Không tìm được'; });  // lỗi mạng
    }

    function moThanhTim() {  // bấm kính lúp: mở thanh tìm
      thanhTim.hidden = false;  // hiện
      nutMoTim.setAttribute('aria-expanded', 'true');
      oTimTrong.focus();  // gõ ngay
      oTimTrong.select();  // chọn sẵn chữ cũ nếu có
      if (giuDay) cuonXuong();  // khung bị thấp đi, giữ ở cuối
    }

    function dongThanhTim() {  // đóng thanh tìm, trả mọi thứ về như cũ
      clearTimeout(henTim);  // hủy lượt tìm đang chờ
      soLuotTim++;  // bỏ kết quả đang về
      oTimTrong.value = '';  // xóa từ khóa
      tuKhoaTim = '';
      xoaKetQuaTim();  // xóa kết quả và tô sáng
      thanhTim.hidden = true;  // ẩn
      nutMoTim.setAttribute('aria-expanded', 'false');
      nutMoTim.focus();  // trả tiêu điểm về kính lúp
      if (giuDay) cuonXuong();
    }

    nutMoTim.addEventListener('click', function () {  // kính lúp bật / tắt thanh tìm
      if (thanhTim.hidden) moThanhTim(); else dongThanhTim();
    });
    thanhTim.querySelector('[data-chat-tim-dong]').addEventListener('click', dongThanhTim);  // nút ×
    thanhTim.querySelector('[data-chat-tim-cu]').addEventListener('click', function () { chonKetQuaTim(viTriTim < 0 ? 0 : viTriTim + 1); });  // mũi tên lên: kết quả cũ hơn
    thanhTim.querySelector('[data-chat-tim-moi]').addEventListener('click', function () { chonKetQuaTim(viTriTim - 1); });  // mũi tên xuống: kết quả mới hơn
    oTimTrong.addEventListener('input', function () {  // gõ chữ
      clearTimeout(henTim);  // chờ người dùng gõ xong
      henTim = setTimeout(timKiem, 300);  // 0,3 giây sau mới gửi
    });
    oTimTrong.addEventListener('keydown', function (e) {  // phím trong ô tìm
      if (e.key === 'Escape') { e.preventDefault(); dongThanhTim(); return; }  // Esc đóng
      if (e.key !== 'Enter') return;  // chỉ xử lý Enter
      e.preventDefault();  // không gửi form
      if (oTimTrong.value.trim() !== tuKhoaTim) { clearTimeout(henTim); timKiem(); return; }  // vừa gõ xong, chưa tìm thì tìm ngay
      chonKetQuaTim(e.shiftKey ? viTriTim - 1 : viTriTim + 1);  // Enter: cũ hơn; Shift+Enter: mới hơn
    });
    dsTim.addEventListener('click', function (e) {  // bấm một dòng kết quả
      var nut = e.target.closest('.chat__tim-muc');  // dòng được bấm
      if (nut) chonKetQuaTim(parseInt(nut.dataset.viTri, 10));  // nhảy tới tin
    });
  }

  phanLoai();  // dựng nhóm tin và dòng ngày cho các tin có sẵn trên trang
  capNhatNutGui();  // ô trống lúc mới mở nên nút Gửi khóa
  cuonXuong();  // mở trang là cuộn xuống tin mới nhất
  henLai();  // bắt đầu vòng polling
})();
