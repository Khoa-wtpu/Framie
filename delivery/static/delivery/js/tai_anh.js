(function () { // bọc toàn bộ code trong một hàm tự chạy để biến không bị rò ra ngoài trang
  'use strict'; // bật chế độ nghiêm ngặt để trình duyệt bắt lỗi sớm
  var form = document.getElementById('form-tai-anh'); // lấy form tải ảnh
  if (!form) return; // trang không có form (chưa tới lúc tải ảnh) thì dừng luôn
  var thanh = document.getElementById('thanh-tien-trinh'); // thanh tiến trình tải lên
  var chu = document.getElementById('chu-tien-trinh'); // dòng chữ hiện phần trăm tiến trình
  var khungLoi = document.getElementById('khung-loi'); // khung hiện thông báo lỗi
  var nut = document.getElementById('nut-tai'); // nút "Tải ảnh lên"
  var oTep = form.querySelector('input[type="file"]'); // ô chọn tệp thật của form
  var khungXemTruoc = document.getElementById('khung-xem-truoc'); // khung xem trước (ban đầu đang ẩn)
  var luoi = document.getElementById('luoi-xem-truoc'); // lưới chứa các ảnh xem trước
  var chuDaChon = document.getElementById('chu-da-chon'); // dòng chữ "Đã chọn N ảnh"
  var nutXoaHet = document.getElementById('nut-xoa-het'); // nút xóa hết ảnh đã chọn
  var vungKeo = oTep ? oTep.closest('.field') : null; // vùng bao quanh ô chọn tệp, dùng làm vùng kéo thả
  var DUNG_LUONG_TOI_DA = 20 * 1024 * 1024; // mỗi ảnh tối đa 20 MB (giống quy định phía server)
  var DUOI_HOP_LE = /\.(jpe?g|png)$/i; // chỉ nhận đuôi .jpg, .jpeg, .png
  var dsTep = []; // danh sách ảnh đã chọn, mỗi phần tử gồm: tep (File), url (đường dẫn xem trước), loi (chữ báo lỗi)
  var khungChuaGhep = document.getElementById('khung-chua-ghep'); // khung "ảnh chưa ghép được" (ban đầu ẩn)
  var dsChuaGhep = document.getElementById('ds-chua-ghep'); // nơi vẽ từng dòng chọn tay
  var ghepTay = {}; // cặp đã chọn tay: { vị trí tệp trong danh sách : mã ảnh cần sửa }; gửi kèm ở mỗi lần tải

  function hienLoi(ds) { // hàm hiện một danh sách lỗi lên đầu form
    khungLoi.innerHTML = ''; // xóa các lỗi cũ
    ds.forEach(function (noiDung) { // duyệt từng câu lỗi
      var p = document.createElement('p'); // tạo thẻ p cho câu lỗi
      p.className = 'alert alert--danger'; // dùng kiểu thông báo đỏ có sẵn của dự án
      p.textContent = noiDung; // gán nội dung (textContent để tránh chèn mã độc)
      khungLoi.appendChild(p); // gắn câu lỗi vào khung lỗi
    }); // hết vòng lặp
  } // hết hàm hienLoi

  function dinhDang(byte) { // hàm đổi số byte thành chữ dễ đọc (KB hoặc MB)
    if (byte >= 1024 * 1024) return (byte / (1024 * 1024)).toFixed(1) + ' MB'; // từ 1 MB trở lên thì hiện MB
    return Math.max(1, Math.round(byte / 1024)) + ' KB'; // nhỏ hơn thì hiện KB, tối thiểu 1 KB
  } // hết hàm dinhDang

  function kiemTraTep(tep) { // hàm kiểm tra nhanh 1 tệp, trả về chữ báo lỗi (rỗng nếu ổn)
    if (!DUOI_HOP_LE.test(tep.name)) return 'Không phải JPG/PNG'; // sai đuôi tệp
    if (tep.size > DUNG_LUONG_TOI_DA) return 'Quá 20 MB'; // quá dung lượng
    return ''; // hợp lệ
  } // hết hàm kiemTraTep

  function xoaChuaGhep() { // đổi danh sách ảnh thì vị trí tệp thay đổi -> bỏ hết lựa chọn tay cũ
    ghepTay = {}; // quên các cặp đã chọn
    if (khungChuaGhep) { khungChuaGhep.hidden = true; } // ẩn khung chọn tay
    if (dsChuaGhep) { dsChuaGhep.innerHTML = ''; } // xóa các dòng cũ
  } // hết hàm xoaChuaGhep

  function dongBoOTep() { // hàm ghi danh sách ảnh đang giữ ngược vào ô chọn tệp thật
    xoaChuaGhep(); // danh sách đã đổi nên phải bỏ lựa chọn tay cũ
    var dt = new DataTransfer(); // tạo một "giỏ" tệp mới
    dsTep.forEach(function (m) { dt.items.add(m.tep); }); // bỏ từng ảnh vào giỏ
    oTep.files = dt.files; // gán giỏ cho ô chọn tệp, nhờ đó form gửi đúng các ảnh còn lại
  } // hết hàm dongBoOTep

  function ve() { // hàm vẽ lại toàn bộ lưới xem trước theo dsTep
    luoi.innerHTML = ''; // xóa lưới cũ
    khungXemTruoc.hidden = dsTep.length === 0; // không có ảnh thì ẩn cả khung
    var tong = 0; // biến cộng tổng dung lượng
    dsTep.forEach(function (m) { // duyệt từng ảnh đã chọn
      tong += m.tep.size; // cộng dung lượng vào tổng
      var o = document.createElement('figure'); // mỗi ảnh là một thẻ figure
      o.className = 'tai-anh__o' + (m.loi ? ' tai-anh__o--loi' : ''); // ảnh lỗi thì thêm viền đỏ
      var anh = document.createElement('img'); // thẻ ảnh thu nhỏ
      anh.src = m.url; // nguồn ảnh là đường dẫn xem trước tạm trên trình duyệt
      anh.alt = m.tep.name; // chữ thay thế là tên tệp
      anh.draggable = false; // không cho kéo ảnh ra ngoài
      var cap = document.createElement('figcaption'); // phần chú thích bên dưới ảnh
      cap.className = 'tai-anh__o-chu'; // class để CSS định dạng chú thích
      var ten = document.createElement('span'); // dòng tên tệp
      ten.className = 'tai-anh__o-ten'; // class cho dòng tên tệp
      ten.textContent = m.tep.name; // ghi tên tệp
      var phu = document.createElement('span'); // dòng dung lượng hoặc báo lỗi
      phu.className = m.loi ? 'tai-anh__o-bao-loi' : 'muted'; // lỗi thì tô đỏ, bình thường thì chữ mờ
      phu.textContent = m.loi || dinhDang(m.tep.size); // có lỗi thì hiện lỗi, không thì hiện dung lượng
      var xoa = document.createElement('button'); // nút xóa riêng từng ảnh
      xoa.type = 'button'; // type=button để không làm form bị gửi đi
      xoa.className = 'tai-anh__nut-xoa'; // class cho nút xóa tròn góc ảnh
      xoa.setAttribute('aria-label', 'Bỏ ảnh ' + m.tep.name); // mô tả cho người dùng đọc màn hình
      xoa.textContent = '×'; // dấu nhân làm biểu tượng xóa
      xoa.addEventListener('click', function () { // khi bấm nút xóa
        URL.revokeObjectURL(m.url); // giải phóng đường dẫn xem trước để đỡ tốn bộ nhớ
        dsTep.splice(dsTep.indexOf(m), 1); // bỏ ảnh này khỏi danh sách
        dongBoOTep(); // cập nhật lại ô chọn tệp thật
        ve(); // vẽ lại lưới
      }); // hết xử lý nút xóa
      cap.appendChild(ten); // gắn tên vào chú thích
      cap.appendChild(phu); // gắn dung lượng/lỗi vào chú thích
      o.appendChild(anh); // gắn ảnh vào thẻ
      o.appendChild(xoa); // gắn nút xóa vào thẻ
      o.appendChild(cap); // gắn chú thích vào thẻ
      luoi.appendChild(o); // gắn thẻ vào lưới
    }); // hết vòng lặp vẽ ảnh
    chuDaChon.textContent = 'Đã chọn ' + dsTep.length + ' ảnh · ' + dinhDang(tong); // ghi số ảnh và tổng dung lượng
  } // hết hàm ve

  function themTep(danhSach) { // hàm thêm các tệp mới chọn vào danh sách (cộng dồn, không ghi đè)
    Array.prototype.slice.call(danhSach).forEach(function (tep) { // đổi FileList thành mảng rồi duyệt
      var trung = dsTep.some(function (m) { // kiểm tra tệp này đã có trong danh sách chưa
        return m.tep.name === tep.name && m.tep.size === tep.size && m.tep.lastModified === tep.lastModified; // trùng tên + dung lượng + ngày sửa
      }); // hết kiểm tra trùng
      if (trung) return; // đã có rồi thì bỏ qua
      dsTep.push({ tep: tep, url: URL.createObjectURL(tep), loi: kiemTraTep(tep) }); // thêm mới kèm đường dẫn xem trước và kết quả kiểm tra
    }); // hết vòng lặp
    dongBoOTep(); // cập nhật ô chọn tệp thật
    ve(); // vẽ lại lưới
  } // hết hàm themTep

  if (oTep && khungXemTruoc && luoi) { // chỉ bật xem trước khi các phần tử cần thiết đều có
    oTep.addEventListener('change', function () { // khi người dùng chọn ảnh bằng hộp thoại
      themTep(oTep.files); // thêm các ảnh vừa chọn vào danh sách
    }); // hết xử lý chọn ảnh
    nutXoaHet.addEventListener('click', function () { // khi bấm "Xóa hết"
      dsTep.forEach(function (m) { URL.revokeObjectURL(m.url); }); // giải phóng toàn bộ đường dẫn xem trước
      dsTep = []; // làm rỗng danh sách
      dongBoOTep(); // cập nhật ô chọn tệp thật
      ve(); // vẽ lại (khung sẽ tự ẩn)
    }); // hết xử lý xóa hết
    if (vungKeo) { // nếu tìm được vùng bao quanh ô chọn tệp thì bật kéo thả
      ['dragenter', 'dragover'].forEach(function (ten) { // hai sự kiện: kéo vào và đang kéo trên vùng
        vungKeo.addEventListener(ten, function (e) { // khi có tệp kéo tới
          e.preventDefault(); // chặn trình duyệt tự mở ảnh ra
          vungKeo.classList.add('tai-anh__vung-keo'); // bật viền nét đứt báo "thả vào đây"
        }); // hết xử lý
      }); // hết vòng lặp sự kiện kéo
      ['dragleave', 'drop'].forEach(function (ten) { // hai sự kiện: kéo ra và thả
        vungKeo.addEventListener(ten, function () { // khi kéo ra hoặc thả
          vungKeo.classList.remove('tai-anh__vung-keo'); // tắt viền nét đứt
        }); // hết xử lý
      }); // hết vòng lặp sự kiện thả
      vungKeo.addEventListener('drop', function (e) { // khi thả tệp vào vùng
        e.preventDefault(); // chặn trình duyệt tự mở ảnh ra
        if (e.dataTransfer && e.dataTransfer.files.length) themTep(e.dataTransfer.files); // có tệp thì thêm vào danh sách
      }); // hết xử lý thả
    } // hết phần kéo thả
  } // hết phần xem trước

  function hienChuaGhep(kq) { // server báo có ảnh chưa tự ghép được: vẽ danh sách thả xuống cho Nhiếp ảnh gia chọn
    if (!khungChuaGhep || !dsChuaGhep) return; // thiếu khung thì thôi, vẫn hiện thông báo lỗi chung
    var dsAnh = kq.ds_anh || []; // các ảnh cần sửa còn lại, dùng làm nội dung danh sách thả xuống
    dsChuaGhep.innerHTML = ''; // xóa các dòng của lần trước
    kq.chua_ghep.forEach(function (c) { // mỗi ảnh chưa ghép là một dòng
      var m = dsTep[c.chi_so]; // ảnh người dùng đã chọn ở vị trí này
      if (!m) return; // vị trí lạ thì bỏ qua
      var dong = document.createElement('div'); // dòng: ảnh mới | danh sách thả xuống | ảnh cần sửa
      dong.className = 'tai-anh__cg-dong';
      var khungMoi = document.createElement('div'); // khối ảnh mới + tên tệp
      var anhMoi = document.createElement('img');
      anhMoi.className = 'tai-anh__cg-anh'; anhMoi.src = m.url; anhMoi.alt = m.tep.name; anhMoi.draggable = false;
      var tenMoi = document.createElement('span');
      tenMoi.className = 'tai-anh__cg-ten muted'; tenMoi.textContent = m.tep.name;
      khungMoi.appendChild(anhMoi); khungMoi.appendChild(tenMoi);
      var chon = document.createElement('select'); // danh sách thả xuống chọn ảnh cần sửa
      chon.className = 'input tai-anh__cg-chon'; // dùng chung kiểu ô chọn của cả trang web (mũi tên, bo góc, màu nền)
      chon.setAttribute('aria-label', 'Chọn ảnh cần sửa tương ứng với ' + m.tep.name);
      var trong = document.createElement('option'); trong.value = ''; trong.textContent = '— Chọn ảnh cần sửa —'; chon.appendChild(trong);
      var gocIds = {}; // nhớ ảnh nào đã là gợi ý để không lặp lại ở phần còn lại
      (c.ung_vien || []).forEach(function (ma) { // gợi ý gần nhất đứng đầu
        dsAnh.forEach(function (a) {
          if (a.ma !== ma) return;
          var op = document.createElement('option'); op.value = String(a.ma);
          op.textContent = a.ten; chon.appendChild(op); gocIds[a.ma] = true;
        });
      });
      dsAnh.forEach(function (a) { // các ảnh còn lại
        if (gocIds[a.ma]) return;
        var op = document.createElement('option'); op.value = String(a.ma); op.textContent = a.ten; chon.appendChild(op);
      });
      var anhCu = document.createElement('img'); // ảnh cần sửa đang chọn (hiện sau khi chọn)
      anhCu.className = 'tai-anh__cg-anh'; anhCu.hidden = true; anhCu.alt = ''; anhCu.draggable = false;
      chon.addEventListener('change', function () { // khi chọn một ảnh
        if (chon.value) {
          ghepTay[c.chi_so] = Number(chon.value); // ghi nhớ cặp này
          var a = dsAnh.filter(function (x) { return String(x.ma) === chon.value; })[0];
          anhCu.src = a ? a.url : ''; anhCu.alt = a ? a.ten : ''; anhCu.hidden = !a; // hiện ảnh cần sửa để so bằng mắt
        } else {
          delete ghepTay[c.chi_so]; anhCu.hidden = true; // bỏ chọn
        }
      });
      dong.appendChild(khungMoi); dong.appendChild(chon); dong.appendChild(anhCu);
      dsChuaGhep.appendChild(dong);
    });
    khungChuaGhep.hidden = false; // hiện khung
    khungChuaGhep.scrollIntoView({ block: 'nearest' }); // cuộn tới khung nếu đang nằm ngoài màn hình
  } // hết hàm hienChuaGhep

  form.addEventListener('submit', function (e) { // khi bấm "Tải ảnh lên"
    e.preventDefault(); // chặn gửi form kiểu thường, ta gửi bằng XMLHttpRequest để có thanh tiến trình
    var toiDa = Number(form.dataset.soAnhToiDa || 100); // số ảnh tối đa mỗi lần (server truyền xuống)
    if (oTep && oTep.files.length > toiDa) { // chọn nhiều hơn mức cho phép
      hienLoi(['Mỗi lần chỉ được tải tối đa ' + toiDa + ' ảnh (bạn chọn ' + oTep.files.length + ' ảnh).']); // báo lỗi
      return; // dừng, không gửi
    } // hết kiểm tra số ảnh
    if (dsTep.some(function (m) { return m.loi; })) { // còn ảnh bị đánh dấu lỗi
      hienLoi(['Hãy bỏ các ảnh viền đỏ (sai định dạng hoặc quá 20 MB) trước khi tải lên.']); // nhắc người dùng
      return; // dừng, không gửi
    } // hết kiểm tra ảnh lỗi
    var daChon = Object.keys(ghepTay).map(function (k) { return ghepTay[k]; }); // các ảnh cần sửa đã được chọn tay
    if (daChon.some(function (ma, i) { return daChon.indexOf(ma) !== i; })) { // hai tệp cùng chọn một ảnh
      hienLoi(['Hai ảnh không thể cùng ghép với một ảnh cần sửa, vui lòng chọn lại.']); // báo lỗi
      return; // dừng, không gửi
    } // hết kiểm tra trùng
    var xhr = new XMLHttpRequest(); // tạo yêu cầu gửi dữ liệu
    xhr.open('POST', window.location.href); // gửi POST về chính trang này
    xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest'); // báo cho server biết đây là yêu cầu AJAX
    xhr.upload.onprogress = function (ev) { // chạy liên tục khi đang tải lên
      if (!ev.lengthComputable) return; // chưa biết tổng dung lượng thì bỏ qua
      var phanTram = Math.round(ev.loaded * 100 / ev.total); // tính phần trăm đã tải
      thanh.value = phanTram; // cập nhật thanh tiến trình
      chu.textContent = phanTram < 100 ? 'Đang tải lên... ' + phanTram + '%' : 'Đã tải xong, đang chèn watermark và lưu ảnh...'; // đổi chữ theo tiến độ
    }; // hết onprogress
    xhr.onload = function () { // khi server trả lời xong
      var ketQua = null; // biến giữ kết quả server trả về
      try { ketQua = JSON.parse(xhr.responseText); } catch (err) { ketQua = null; } // đọc JSON, lỗi thì để null
      if (ketQua && ketQua.ok) { window.location.href = ketQua.url; return; } // thành công thì chuyển sang trang server chỉ định
      hienLoi(ketQua && ketQua.loi ? ketQua.loi : ['Không thể tải ảnh lên, vui lòng thử lại.']); // thất bại thì hiện lỗi
      if (ketQua && ketQua.chua_ghep && ketQua.chua_ghep.length) { hienChuaGhep(ketQua); } // có ảnh chưa ghép được thì mời chọn tay
      thanh.hidden = true; chu.textContent = ''; nut.disabled = false; // ẩn tiến trình và mở lại nút
    }; // hết onload
    xhr.onerror = function () { // khi mất kết nối
      hienLoi(['Mất kết nối khi tải ảnh, vui lòng thử lại.']); // báo lỗi mất mạng
      thanh.hidden = true; chu.textContent = ''; nut.disabled = false; // ẩn tiến trình và mở lại nút
    }; // hết onerror
    khungLoi.innerHTML = ''; // xóa lỗi cũ trước khi gửi
    thanh.hidden = false; thanh.value = 0; nut.disabled = true; // hiện thanh tiến trình và khóa nút để khỏi bấm 2 lần
    var duLieu = new FormData(form); // toàn bộ form (gồm các ảnh đã chọn)
    if (daChon.length) { duLieu.append('ghep_tay', JSON.stringify(ghepTay)); } // kèm các cặp đã chọn tay
    xhr.send(duLieu); // gửi đi
  }); // hết xử lý submit
})(); // gọi chạy hàm tự chạy