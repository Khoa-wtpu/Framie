// chat/static/chat/js/chat.js - P11: lọc danh sách (UC8.3), gửi tin + Gửi lại (UC8.2), xem lịch sử, tải tin cũ, nhóm tin + dòng ngày, tự làm mới tin mỗi 2 giây.
(function () {  // bọc trong hàm để không làm rối biến toàn cục
  'use strict';  // bật chế độ nghiêm ngặt, bắt lỗi viết sai sớm hơn

  // ===================================================================================
  // PHẦN A. DÙNG CHUNG CHO CẢ HỘP THƯ VÀ TRANG CHI TIẾT (không cần khối [data-chat])
  // ===================================================================================

  function boDau(chuoi) {  // đưa chữ về thường, không dấu, để gõ "phanh" vẫn tìm ra "Phanh/Phạm"
    return String(chuoi || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd').trim();  // NFD tách dấu ra rồi xóa; đ không tách được nên thay riêng
  }

  var oTim = document.querySelector('[data-chat-tim]');  // ô "Tìm cuộc trò chuyện" ở cột trái
  if (oTim) {  // có ô tìm
    var dsCuoc = document.querySelector('[data-chat-ds]');  // danh sách cuộc trò chuyện (không có khi hộp thư trống)
    var cauTrong = document.querySelector('[data-chat-ds-trong]');  // câu "Không tìm thấy cuộc trò chuyện phù hợp." (trường hợp 18)
    var cacMuc = dsCuoc ? Array.prototype.slice.call(dsCuoc.querySelectorAll('li[data-ten]')) : [];  // các dòng cuộc trò chuyện
    var locDanhSach = function () {  // lọc theo chữ đang gõ
      var tuKhoa = boDau(oTim.value);  // chữ cần tìm
      var thay = 0;  // số dòng còn hiện
      cacMuc.forEach(function (li) {  // duyệt từng dòng
        var khop = !tuKhoa || boDau(li.dataset.ten).indexOf(tuKhoa) !== -1;  // rỗng thì hiện hết
        li.hidden = !khop;  // ẩn dòng không khớp
        if (khop) thay += 1;  // đếm dòng khớp
      });
      if (dsCuoc) dsCuoc.hidden = cacMuc.length > 0 && thay === 0;  // không dòng nào khớp thì ẩn luôn khung danh sách
      if (cauTrong) cauTrong.hidden = !(cacMuc.length > 0 && thay === 0);  // và hiện câu thông báo
    };
    oTim.addEventListener('input', locDanhSach);  // lọc mỗi lần gõ
    oTim.addEventListener('keydown', function (e) {  // phím Esc xóa ô tìm
      if (e.key === 'Escape' && oTim.value) { oTim.value = ''; locDanhSach(); }  // xóa rồi hiện lại toàn bộ
    });
  }

  function dongMenu(ngoai) {  // đóng menu "···" đang mở (ngoai: phần tử vừa bấm, giữ menu nếu bấm bên trong nó)
    document.querySelectorAll('.chat__menu[open]').forEach(function (m) {  // các menu đang mở
      if (!ngoai || !m.contains(ngoai)) m.removeAttribute('open');  // đóng nếu bấm ra ngoài
    });
  }
  document.addEventListener('click', function (e) { dongMenu(e.target); });  // bấm ra ngoài thì đóng menu
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') dongMenu(null); });  // Esc cũng đóng

  var khung = document.querySelector('[data-chat]');  // khối cuộc trò chuyện
  if (!khung) return;  // trang Hộp thư (chưa mở cuộc nào) thì dừng ở đây

  // ===================================================================================
  // PHẦN B. CUỘC TRÒ CHUYỆN
  // ===================================================================================
  var CHU_KY_MS = 2000;  // hỏi tin mới mỗi 2 giây, đúng yêu cầu "tin hiện trong khoảng 2 giây"
  var NGHI_TOI_DA_MS = 10 * 60 * 1000;  // 10 phút không thao tác thì tạm dừng polling (phiên đăng nhập 30 phút)
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

  function hienLoi(noiDung) {  // hiện hoặc ẩn hộp lỗi
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
  }

  // ----- chèn tin -----
  function chenCuoi(cacTin, ep) {  // thêm các tin MỚI vào cuối danh sách (cacTin đã sắp cũ trước mới sau)
    var html = '';  // gom HTML
    cacTin.forEach(function (t) {  // duyệt từng tin
      if (!thanTin.querySelector('[data-id="' + t.id + '"]')) html += t.html;  // chỉ thêm nếu chưa có (chống trùng khi hai lần polling chồng nhau)
      if (t.id > idCuoi) idCuoi = t.id;  // nâng mốc tin cuối
      if (idDau === 0 || t.id < idDau) idDau = t.id;  // danh sách đang trống thì đặt mốc tin đầu
    });
    if (!html) return;  // không có gì mới
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
    return goi(urlMoi + '?sau=' + idCuoi).then(function (kq) {  // gọi polling
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
    if (ganDay()) nutTinMoi.hidden = true;  // xuống tới đáy thì ẩn nút "Có tin mới"
  });
  if (nutTaiCu) nutTaiCu.addEventListener('click', taiCu);  // bấm nút "Xem tin cũ hơn"
  nutTinMoi.addEventListener('click', cuonXuong);  // bấm "Có tin mới" thì cuộn xuống

  // ----- soạn và gửi tin -----
  function tuCaoLen() {  // ô nhập tự cao lên theo số dòng, tối đa 9rem (CSS)
    oNhap.style.height = 'auto';  // đặt lại để đo đúng
    oNhap.style.height = oNhap.scrollHeight + 'px';  // cao đúng bằng nội dung
  }

  function capNhatNutGui() {  // khóa nút Gửi khi ô trống hoặc đang gửi (đúng wireframe: nút xám)
    nutGui.disabled = dangGui || !oNhap.value.trim();  // trống chỉ có khoảng trắng cũng khóa
    nutGui.classList.toggle('is-loading', dangGui);  // đang gửi thì hiện vòng quay
  }

  function themTinLoi(noiDung) {  // thêm bong bóng nét đứt "Không gửi được. Gửi lại" ở cuối danh sách
    var tin = document.createElement('article');  // một tin
    tin.className = 'tn tn--cua-toi tn--loi';  // nằm bên phải như tin của mình, kiểu lỗi
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
    goi(form.action, { method: 'POST', body: fd }).then(function (kq) {  // gửi ngầm
      if (kq.ok) {  // lưu thành công
        hienLoi('');  // xóa lỗi cũ
        if (tinLoi) tinLoi.remove();  // gửi lại thành công: bỏ bong bóng lỗi
        else { oNhap.value = ''; tuCaoLen(); }  // gửi từ ô nhập: xóa ô nhập và thu về 1 dòng
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
    if (!tinLoi) {  // gửi từ ô nhập: chuyển chữ xuống thành bong bóng lỗi để khỏi mất
      oNhap.value = '';  // xóa ô nhập như wireframe
      tuCaoLen();  // thu ô nhập về 1 dòng
      themTinLoi(noiDung);  // bong bóng "Không gửi được. Gửi lại"
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
    if (!noiDung) { capNhatNutGui(); return; }  // tin rỗng thì không gửi (nút đã khóa sẵn)
    guiTin(noiDung, null);  // gửi từ ô nhập
  });

  phanLoai();  // dựng nhóm tin và dòng ngày cho các tin có sẵn trên trang
  capNhatNutGui();  // ô trống lúc mới mở nên nút Gửi khóa
  cuonXuong();  // mở trang là cuộn xuống tin mới nhất
  henLai();  // bắt đầu vòng polling
})();
