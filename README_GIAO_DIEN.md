==============================================================================
                        QUY ƯỚC GIAO DIỆN FRAMIE
==============================================================================

File này để cả nhóm làm giao diện ĐỒNG BỘ.
Trước khi tự viết CSS hoặc chọn màu, hãy đọc file này.

Xem thử mọi thành phần tại:  http://127.0.0.1:8000/ui-kit/


------------------------------------------------------------------------------
1. NGUYÊN TẮC CHUNG
------------------------------------------------------------------------------

  1) KHÔNG gõ mã màu (#1A1A1A, black...) trực tiếp trong template hoặc CSS.
     Luôn dùng biến, ví dụ:  var(--color-black)

  2) Màu và font CHỈ khai báo ở một nơi: static/css/tokens.css
     Muốn đổi màu cho cả web thì sửa ở đó, không sửa rải rác.

  3) KHÔNG tự viết CSS cho nút.
     Dùng class có sẵn trong static/css/components.css

  4) Mỗi màn hình chỉ có 1 nút chính (btn--primary).
     Các nút còn lại dùng kiểu nhẹ hơn.

  5) Chữ trên nút phải rõ nghĩa, bắt đầu bằng động từ:
     "Đặt lịch", "Lưu thay đổi", "Hủy Booking".
     Không dùng "OK", "Click".


------------------------------------------------------------------------------
2. BẢNG MÀU CHÍNH (cốt quét nhóm 5: trắng / đen / xám)
------------------------------------------------------------------------------

  Tên biến                 Mã màu              Dùng cho
  -----------------------  ------------------  -----------------------------
  --color-white            #FFFFFF             Nền trang, nền thẻ
  --color-black            #1A1A1A             Chữ, nút chính
  --color-gray             #D9D9D9             Viền, đường kẻ
  --color-black-hover      #3A3A3A             Nút chính khi rê chuột
  --color-gray-soft        #F3F3F3             Nền nhạt khi rê chuột, nền phụ
  --color-text-muted       #5C5C5C             Chữ phụ, chú thích
  --gradient-white-gray    trắng -> xám        Nền nút "soft"
  --gradient-white-black   trắng -> đen        Trang trí

  Font: Be Vietnam Pro (tiêu đề đậm 600, văn bản thường 400).


------------------------------------------------------------------------------
3. CÁC LOẠI NÚT
------------------------------------------------------------------------------

  [1] NÚT CHÍNH            class="btn btn--primary"
      Hình dạng : nền đen, chữ trắng
      Dùng khi  : hành động CHÍNH của màn hình (mỗi màn hình chỉ 1 nút)
      Ví dụ     : Đặt lịch, Gửi, Lưu, Đăng ký

  [2] NÚT PHỤ              class="btn btn--secondary"
      Hình dạng : nền trắng, viền đen
      Dùng khi  : hành động quan trọng thứ hai, đi cạnh nút chính
      Ví dụ     : Xem chi tiết, Chỉnh sửa

  [3] NÚT GRADIENT XÁM     class="btn btn--soft"
      Hình dạng : nền chuyển từ trắng sang xám, viền xám
      Dùng khi  : hành động phụ, nhấn vừa phải
      Ví dụ     : Lọc, Xem thêm, Tải thêm

  [4] NÚT GHOST            class="btn btn--ghost"
      Hình dạng : không nền, không viền, chỉ có chữ đen
      Dùng khi  : hành động ít quan trọng, hoặc nút nằm trong header, menu
      Ví dụ     : Hủy, Quay lại, Đăng nhập (ở header)

  [5] NÚT NGUY HIỂM        class="btn btn--danger"
      Hình dạng : nền đỏ, chữ trắng
      Dùng khi  : hành động nguy hiểm, khó hoàn tác
      Ví dụ     : Hủy Booking, Xóa tài khoản, Từ chối hồ sơ

  Ví dụ ghép trong một form:

      <button class="btn btn--ghost" type="button">Hủy</button>
      <button class="btn btn--primary" type="submit">Lưu thay đổi</button>


  QUY TẮC DÙNG MÀU ĐỎ (btn--danger)
  ---------------------------------
    - Chỉ dùng cho hành động xóa, hủy, từ chối.
    - Không dùng đỏ để "làm nổi bật" một nút bình thường.
    - Nên có bước xác nhận trước khi thực hiện.


  KÍCH THƯỚC (thêm class vào sau btn)
  -----------------------------------
    btn--sm      Nút nhỏ: trong header, bảng, thẻ nhỏ
    (mặc định)   Hầu hết các nút
    btn--lg      Nút lớn: nổi bật ở trang chủ, trang đặt lịch
    btn--block   Nút rộng hết chiều ngang: điện thoại, form hẹp

    Ví dụ:  class="btn btn--primary btn--lg"


  TRẠNG THÁI
  ----------
    Vô hiệu     : thêm thuộc tính disabled
                  <button class="btn btn--primary" disabled>
    Đang xử lý  : thêm class is-loading
                  <button class="btn btn--primary is-loading">

    Khi bấm gửi form, hãy dùng is-loading để tránh người dùng bấm hai lần.


------------------------------------------------------------------------------
4. MÀU CHO NHÃN TRẠNG THÁI VÀ HỘP THÔNG BÁO
------------------------------------------------------------------------------

  Nhãn trạng thái (Chờ xác nhận, Đã đặt cọc, Hoàn thành...) và hộp thông báo
  dùng bảng "tông màu" --tone-* trong tokens.css.
  Mỗi tông có 3 màu:  nền nhạt (-bg), chữ đậm (-fg), chấm nhấn (-dot).

  - Việc gán "trạng thái -> màu" nằm ở file core/status_tones.py
    Muốn đổi màu một trạng thái thì sửa ở file này,
    không tự gán màu trong template.

  - Quy ước chung:
      Vàng, cam                  : đang chờ
      Xanh dương, tím, xanh ngọc : đang xử lý
      Xanh lá                    : hoàn tất
      Đỏ, nâu, xám               : thất bại hoặc đã hủy

  HỘP THÔNG BÁO (templates/includes/alert.html) có 4 mức:

    level="success"   Xanh lá     Thao tác thành công
    level="danger"    Đỏ          Có lỗi
    level="warning"   Vàng        Cần lưu ý
    level="info"      Xanh dương  Thông tin thường


------------------------------------------------------------------------------
5. THÊM HOẶC SỬA GIAO DIỆN: LÀM THẾ NÀO?
------------------------------------------------------------------------------

  1) Cần một thành phần đã có (nút, thẻ, ô nhập, thông báo)?
     -> DÙNG LẠI theo mẫu ở /ui-kit/

  2) Cần màu mới?
     -> Hỏi nhóm trước, rồi thêm vào static/css/tokens.css
        thành một biến có tên rõ nghĩa.

  3) Cần kiểu nút mới?
     -> Thêm vào static/css/components.css theo mẫu .btn--tên
     -> Cập nhật mục 3 trong file này
     -> Thêm một mẫu vào templates/ui_kit.html

  4) Trước khi gửi code, mở /ui-kit/ để chắc chắn mình không làm hỏng
     giao diện chung.


------------------------------------------------------------------------------
6. BẢN ĐỒ FILE
------------------------------------------------------------------------------

  static/css/tokens.css       Màu, font, khoảng cách
                              (nơi DUY NHẤT khai báo màu)
  static/css/base.css         Bố cục chung, header, footer
  static/css/components.css   Nút, thẻ, ô nhập, nhãn trạng thái, thông báo
  static/img/logo.png         Logo
  templates/includes/         Header, footer, thẻ, thông báo, ô nhập,
                              phân trang
  templates/ui_kit.html       Trang xem thử mọi thành phần
  core/status_tones.py        Gán trạng thái -> màu

==============================================================================