// chat/static/chat/js/chat.js - P11: gửi tin (UC8.2), xem lịch sử và tải tin cũ (UC8.3), tự làm mới tin mỗi 2 giây.
(function () {  // bọc trong hàm để không làm rối biến toàn cục
  'use strict';  // bật chế độ nghiêm ngặt, bắt lỗi viết sai sớm hơn
  var khung = document.querySelector('[data-chat]');  // khối cuộc trò chuyện
  if (!khung) return;  // trang không phải màn hình chat (ví dụ danh sách) thì dừng
  var CHU_KY_MS = 2000;  // hỏi tin mới mỗi 2 giây, đúng yêu cầu "tin hiện trong khoảng 2 giây"
  var NGHI_TOI_DA_MS = 10 * 60 * 1000;  // 10 phút không thao tác thì tạm dừng polling (xem ghi chú về phiên đăng nhập 30 phút)
  var NGUONG_CUON_PX = 80;  // cách đáy dưới 80px thì coi là "đang ở cuối", tin mới sẽ tự cuộn xuống
  var LOI_GUI = 'Không thể gửi tin nhắn. Vui lòng thực hiện lại.';  // thông báo luồng ngoại lệ 5a
  var LOI_TAI = 'Không thể tải lịch sử trao đổi. Vui lòng thực hiện lại.';  // thông báo luồng ngoại lệ 2a

  var danhSach = khung.querySelector('[data-chat-list]');  // khung cuộn
  var thanTin = khung.querySelector('[data-chat-tin]');  // nơi chứa các bong bóng
  var form = khung.querySelector('[data-chat-form]');  // form soạn tin
  var oNhap = form.querySelector('textarea');  // ô nhập
  var nutGui = form.querySelector('button[type="submit"]');  // nút Gửi
  var hopLoi = khung.querySelector('[data-chat-loi]');  // dòng lỗi dưới khung
  var hopTrangThai = khung.querySelector('[data-chat-trang-thai]');  // thanh trạng thái (mất kết nối...)
  var nutTinMoi = khung.querySelector('[data-chat-tin-moi]');  // nút nổi "Có tin mới"
  var nutTaiCu = khung.querySelector('[data-chat-tai-cu]');  // nút "Xem tin cũ hơn" (có thể không tồn tại)
  var urlMoi = khung.dataset.urlMoi;  // địa chỉ lấy tin mới / tin cũ
  var urlDangNhap = khung.dataset.urlDangNhap;  // địa chỉ đăng nhập khi phiên hết hạn

  var idCuoi = parseInt(danhSach.dataset.idCuoi, 10) || 0;  // mã tin cuối đang hiện, mốc cho polling
  var idDau = parseInt(danhSach.dataset.idDau, 10) || 0;  // mã tin đầu đang hiện, mốc để tải tin cũ
  var conCu = danhSach.dataset.conCu === '1';  // còn tin cũ hơn trên server không
  var hen = null;  // bộ hẹn giờ của vòng polling
  var dung = false;  // true khi dừng hẳn (hết phiên, mất quyền)
  var tamDungVINghi = false;  // true khi tạm dừng vì lâu không thao tác
  var loiLienTiep = 0;  // số lần polling lỗi liên tiếp
  var dangGui = false;  // đang gửi tin, chặn bấm đúp
  var dangTaiCu = false;  // đang tải tin cũ, chặn gọi chồng
  var hoatDongCuoi = Date.now();  // lần cuối người dùng thao tác

  function ganDay() {  // người dùng có đang đọc ở đáy danh sách không
    return danhSach.scrollHeight - danhSach.scrollTop - danhSach.clientHeight < NGUONG_CUON_PX;  // khoảng cách tới đáy
  }

  function cuonXuong() {  // cuộn xuống tin mới nhất
    danhSach.scrollTop = danhSach.scrollHeight;  // đặt vị trí cuộn bằng tổng chiều cao
    nutTinMoi.hidden = true;  // ẩn nút "Có tin mới"
  }

  function hienLoi(noiDung) {  // hiện hoặc ẩn dòng lỗi dưới khung
    hopLoi.textContent = noiDung || '';  // textContent nên không bị chèn HTML
    hopLoi.hidden = !noiDung;  // rỗng thì ẩn
  }

  function hienTrangThai(noiDung) {  // hiện hoặc ẩn thanh trạng thái
    hopTrangThai.textContent = noiDung || '';  // ghi chữ
    hopTrangThai.hidden = !noiDung;  // rỗng thì ẩn
  }

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

  function chenCuoi(cacTin, ep) {  // thêm các tin MỚI vào cuối danh sách (cacTin đã sắp cũ trước mới sau)
    var html = '';  // gom HTML
    cacTin.forEach(function (t) {  // duyệt từng tin
      if (!thanTin.querySelector('[data-id="' + t.id + '"]')) html += t.html;  // chỉ thêm nếu chưa có (chống trùng khi hai lần polling chồng nhau)
      if (t.id > idCuoi) idCuoi = t.id;  // nâng mốc tin cuối
      if (idDau === 0 || t.id < idDau) idDau = t.id;  // danh sách đang trống thì đặt mốc tin đầu
    });
    if (!html) return;  // không có gì mới
    var trong = thanTin.querySelector('[data-chat-trong]');  // câu "Chưa có tin nhắn"
    if (trong) trong.remove();  // có tin rồi thì bỏ câu này
    var dangODay = ganDay();  // đo trước khi chèn
    thanTin.insertAdjacentHTML('beforeend', html);  // HTML này do Django render và đã escape nội dung
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
    var caoCu = danhSach.scrollHeight;  // chiều cao trước khi chèn
    thanTin.insertAdjacentHTML('afterbegin', html);  // chèn lên đầu
    danhSach.scrollTop += danhSach.scrollHeight - caoCu;  // bù phần chiều cao vừa tăng để người dùng vẫn đứng ở tin đang đọc
  }

  function layTinMoi(ep) {  // hỏi server các tin có mã lớn hơn idCuoi; trả về Promise
    return goi(urlMoi + '?sau=' + idCuoi).then(function (kq) {  // gọi polling
      if (kq.status === 401) {  // phiên đăng nhập đã hết hạn
        dung = true;  // dừng hẳn
        hienTrangThai('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.');  // báo người dùng
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
      if (kq.duLieu.tin_nhan && kq.duLieu.tin_nhan.length) chenCuoi(kq.duLieu.tin_nhan, ep);  // có tin mới thì chèn
    });
  }

  function henLai() {  // đặt lịch lần polling kế tiếp sau 2 giây
    clearTimeout(hen);  // hủy lịch cũ để không có hai vòng chạy song song
    hen = setTimeout(vong, CHU_KY_MS);  // hẹn giờ
  }

  function vong() {  // một vòng polling
    if (dung) return;  // đã dừng hẳn
    if (document.hidden) return;  // tab đang ẩn thì tạm nghỉ, visibilitychange sẽ gọi lại
    if (Date.now() - hoatDongCuoi > NGHI_TOI_DA_MS) {  // quá lâu không thao tác
      tamDungVINghi = true;  // tạm dừng để phiên đăng nhập có thể tự hết hạn
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

  function ghiNhanHoatDong() {  // người dùng vừa thao tác
    hoatDongCuoi = Date.now();  // cập nhật mốc
    if (tamDungVINghi && !dung) {  // đang tạm dừng vì nghỉ lâu
      tamDungVINghi = false;  // bỏ tạm dừng
      hienTrangThai('');  // ẩn thanh trạng thái
      clearTimeout(hen);  // hủy lịch cũ (nếu có)
      vong();  // hỏi tin mới ngay
    }
  }

  ['pointerdown', 'pointermove', 'keydown', 'touchstart', 'wheel'].forEach(function (ten) {  // các kiểu thao tác
    document.addEventListener(ten, ghiNhanHoatDong, { passive: true });  // lắng nghe, không chặn cuộn
  });

  document.addEventListener('visibilitychange', function () {  // người dùng chuyển tab
    if (!document.hidden && !dung && !tamDungVINghi) {  // quay lại tab
      clearTimeout(hen);  // hủy lịch cũ
      vong();  // hỏi tin mới ngay để thấy tin đã đến trong lúc vắng mặt
    }
  });

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
    if (ganDay()) nutTinMoi.hidden = true;  // xuống tới đáy thì ẩn nút "Có tin mới"
  });
  if (nutTaiCu) nutTaiCu.addEventListener('click', taiCu);  // bấm nút "Xem tin cũ hơn"
  nutTinMoi.addEventListener('click', cuonXuong);  // bấm "Có tin mới" thì cuộn xuống

  function tuCaoLen() {  // ô nhập tự cao lên theo số dòng, tối đa 9rem (CSS)
    oNhap.style.height = 'auto';  // đặt lại để đo đúng
    oNhap.style.height = oNhap.scrollHeight + 'px';  // cao đúng bằng nội dung
  }
  oNhap.addEventListener('input', tuCaoLen);  // mỗi lần gõ

  oNhap.addEventListener('keydown', function (e) {  // phím trong ô nhập
    if (e.key !== 'Enter' || e.shiftKey) return;  // chỉ xử lý Enter không kèm Shift
    if (e.isComposing || e.keyCode === 229) return;  // đang gõ dấu tiếng Việt bằng bộ gõ (Telex, VNI): Enter chỉ để chốt chữ, không gửi
    e.preventDefault();  // không xuống dòng
    form.requestSubmit();  // gửi form (đi qua trình xử lý submit bên dưới)
  });

  form.addEventListener('submit', function (e) {  // gửi tin
    e.preventDefault();  // gửi ngầm, không tải lại trang; app.js thấy defaultPrevented nên không thêm is-loading lần nữa
    var noiDung = oNhap.value.trim();  // bỏ khoảng trắng hai đầu
    if (!noiDung) { hienLoi('Vui lòng nhập nội dung tin nhắn.'); return; }  // tin rỗng thì không gửi
    if (dangGui) return;  // đang gửi thì bỏ qua lần bấm này
    dangGui = true;  // đánh dấu đang gửi
    nutGui.classList.add('is-loading');  // vòng quay trên nút Gửi
    ghiNhanHoatDong();  // gửi tin cũng là thao tác
    goi(form.action, { method: 'POST', body: new FormData(form) }).then(function (kq) {  // FormData đã có csrfmiddlewaretoken
      if (kq.ok) {  // lưu thành công
        oNhap.value = '';  // xóa ô nhập
        tuCaoLen();  // thu ô nhập về 1 dòng
        hienLoi('');  // xóa lỗi cũ
        return layTinMoi(true).catch(function () {});  // lấy ngay các tin mới (gồm cả tin vừa gửi), tự cuộn xuống; lỗi mạng ở đây để vòng polling lo
      }
      if (kq.status === 401) {  // phiên hết hạn
        hienLoi('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.');  // giữ nguyên chữ đã gõ
        return;  // kết thúc
      }
      hienLoi(kq.duLieu.loi || LOI_GUI);  // lỗi từ server, giữ nguyên chữ để bấm gửi lại
    }).catch(function () {  // lỗi mạng
      hienLoi(LOI_GUI);  // luồng ngoại lệ 5a
    }).then(function () {  // chạy sau cả thành công lẫn lỗi
      dangGui = false;  // cho phép gửi tiếp
      nutGui.classList.remove('is-loading');  // tắt vòng quay
      oNhap.focus();  // trả con trỏ về ô nhập
    });
  });

  cuonXuong();  // mở trang là cuộn xuống tin mới nhất
  henLai();  // bắt đầu vòng polling
})();