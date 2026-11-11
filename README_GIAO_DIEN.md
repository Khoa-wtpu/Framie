======================================================================
                     QUY ƯỚC GIAO DIỆN FRAMIE
======================================================================

Mục đích: cả nhóm làm giao diện ĐỒNG BỘ.
Trước khi tự viết CSS hoặc chọn màu, hãy đọc file này.

Xem thử mọi thành phần tại:
    http://127.0.0.1:8000/ui-kit/

MỤC LỤC
    1. Nguyên tắc chung
    2. Bảng màu chính
    3. Các loại nút
    4. Màu nhãn trạng thái và hộp thông báo
    5. Thẻ (card) và ảnh trong thẻ
    6. Thêm hoặc sửa giao diện
    7. Menu theo vai trò, menu điện thoại và xem thử
    8. Bản đồ file


----------------------------------------------------------------------
1. NGUYÊN TẮC CHUNG
----------------------------------------------------------------------

  1) KHÔNG gõ mã màu (như #1A1A1A hoặc black) trực tiếp
     trong template hay CSS. Luôn dùng biến, ví dụ:
         var(--color-black)

  2) Màu và font CHỈ khai báo ở một nơi:
         static/css/tokens.css
     Muốn đổi màu cho cả web thì sửa ở đó, không sửa rải rác.

  3) KHÔNG tự viết CSS cho nút.
     Dùng class có sẵn trong static/css/components.css

  4) Mỗi màn hình chỉ có 1 nút chính (btn--primary).
     Các nút còn lại dùng kiểu nhẹ hơn.

  5) Chữ trên nút phải rõ nghĩa, bắt đầu bằng động từ:
     "Đặt lịch", "Lưu thay đổi", "Hủy Booking".
     Không dùng "OK", "Click".


----------------------------------------------------------------------
2. BẢNG MÀU CHÍNH (cốt quét nhóm 5: trắng / đen / xám)
----------------------------------------------------------------------

  --color-white
      Mã: #FFFFFF
      Dùng cho: nền trang, nền thẻ

  --color-black
      Mã: #1A1A1A
      Dùng cho: chữ, nút chính

  --color-gray
      Mã: #D9D9D9
      Dùng cho: viền, đường kẻ

  --color-black-hover
      Mã: #3A3A3A
      Dùng cho: nút chính khi rê chuột

  --color-gray-soft
      Mã: #F3F3F3
      Dùng cho: nền nhạt khi rê chuột, nền phụ

  --color-text-muted
      Mã: #5C5C5C
      Dùng cho: chữ phụ, chú thích

  --gradient-white-gray
      Chuyển màu từ trắng sang xám
      Dùng cho: nền nút "soft"

  --gradient-white-black
      Chuyển màu từ trắng sang đen
      Dùng cho: trang trí

  Font: Be Vietnam Pro
      Tiêu đề: đậm 600.  Văn bản: thường 400.


----------------------------------------------------------------------
3. CÁC LOẠI NÚT
----------------------------------------------------------------------

  [1] NÚT CHÍNH
      Class    : btn btn--primary
      Hình dạng: nền đen, chữ trắng
      Dùng khi : hành động CHÍNH của màn hình (chỉ 1 nút)
      Ví dụ    : Đặt lịch, Gửi, Lưu, Đăng ký

  [2] NÚT PHỤ
      Class    : btn btn--secondary
      Hình dạng: nền trắng, viền đen
      Dùng khi : hành động quan trọng thứ hai, đi cạnh nút chính
      Ví dụ    : Xem chi tiết, Chỉnh sửa

  [3] NÚT GRADIENT XÁM
      Class    : btn btn--soft
      Hình dạng: nền chuyển từ trắng sang xám, viền xám
      Dùng khi : hành động phụ, nhấn vừa phải
      Ví dụ    : Lọc, Xem thêm, Tải thêm

  [4] NÚT GHOST
      Class    : btn btn--ghost
      Hình dạng: không nền, không viền, chỉ có chữ đen
      Dùng khi : hành động ít quan trọng, hoặc nút trong header
      Ví dụ    : Hủy, Quay lại, Đăng nhập (ở header)

  [5] NÚT NGUY HIỂM
      Class    : btn btn--danger
      Hình dạng: nền đỏ, chữ trắng
      Dùng khi : hành động nguy hiểm, khó hoàn tác
      Ví dụ    : Hủy Booking, Xóa tài khoản, Từ chối hồ sơ

  Ví dụ ghép nút trong một form:

      <button class="btn btn--ghost" type="button">
        Hủy
      </button>
      <button class="btn btn--primary" type="submit">
        Lưu thay đổi
      </button>

  QUY TẮC DÙNG MÀU ĐỎ (btn--danger)
    - Chỉ dùng cho hành động xóa, hủy, từ chối.
    - Không dùng đỏ để "làm nổi bật" một nút bình thường.
    - Nên có bước xác nhận trước khi thực hiện.

  KÍCH THƯỚC (thêm class vào sau chữ btn)
      btn--sm     Nhỏ: trong header, bảng, thẻ nhỏ
      (mặc định)  Hầu hết các nút
      btn--lg     Lớn: nổi bật ở trang chủ, trang đặt lịch
      btn--block  Rộng hết chiều ngang: điện thoại, form hẹp

      Ví dụ: class="btn btn--primary btn--lg"

  TRẠNG THÁI
      Vô hiệu    : thêm thuộc tính disabled
                   <button class="btn btn--primary" disabled>
      Đang xử lý : thêm class is-loading
                   <button class="btn btn--primary is-loading">

      Khi bấm gửi form, hãy dùng is-loading để người dùng
      không bấm hai lần.


----------------------------------------------------------------------
4. MÀU NHÃN TRẠNG THÁI VÀ HỘP THÔNG BÁO
----------------------------------------------------------------------

  Nhãn trạng thái (Chờ xác nhận, Đã đặt cọc, Hoàn thành...)
  và hộp thông báo dùng bảng "tông màu" --tone-* trong
  tokens.css. Mỗi tông có 3 màu:
      -bg   nền nhạt
      -fg   chữ đậm
      -dot  chấm nhấn

  Việc gán "trạng thái -> màu" nằm ở file:
      core/status_tones.py
  Muốn đổi màu một trạng thái thì sửa ở file này,
  không tự gán màu trong template.

  Quy ước chung:
      Vàng, cam                   : đang chờ
      Xanh dương, tím, xanh ngọc  : đang xử lý
      Xanh lá                     : hoàn tất
      Đỏ, nâu, xám                : thất bại hoặc đã hủy

  HỘP THÔNG BÁO (templates/includes/alert.html), 4 mức:
      level="success"  Xanh lá      Thao tác thành công
      level="danger"   Đỏ           Có lỗi
      level="warning"  Vàng         Cần lưu ý
      level="info"     Xanh dương   Thông tin thường

  THÔNG BÁO TỪ VIEW (messages.success / messages.error ...)
      Django đặt tên mức lỗi là "error", nhưng CSS chỉ có
      alert--danger. Vì vậy trong config/settings.py đã khai báo:
          MESSAGE_TAGS = {messages.ERROR: 'danger'}
      Nhờ đó messages.error(...) hiện đúng hộp ĐỎ.
      Đừng xóa dòng này, nếu không thông báo lỗi sẽ hiện màu xanh dương.


----------------------------------------------------------------------
5. THẺ (CARD) VÀ ẢNH TRONG THẺ
----------------------------------------------------------------------

  Mọi thẻ dùng chung MỘT mẫu:
      templates/includes/card.html
  Không tự viết lại HTML cho thẻ.

  Cách gọi (PHẢI viết trên MỘT dòng, không được xuống dòng):

      {% include "includes/card.html" with title="..." image="..." %}

  Các tham số (cái nào không cần thì bỏ qua):
      title   Tiêu đề thẻ
      meta    Dòng phụ (ví dụ: tên nhiếp ảnh gia)
      text    Mô tả ngắn
      image   Đường dẫn ảnh. Không truyền thì hiện khung xám
      href    Đường dẫn khi bấm vào thẻ.
              Không truyền thì thẻ không bấm được
      status  Nhãn trạng thái (ví dụ: "Đã đặt lịch")

  CÁCH THÊM ẢNH VÀO THẺ

  a) Ảnh mẫu (để xem thử trong /ui-kit/)
      - Bỏ ảnh vào thư mục static/img/
      - Truyền đường dẫn cố định vào image:
            image="/static/img/goi-chan-dung.jpg"
      - Lưu ý: trong phần "with" không viết được thẻ
        {% static %}, nên dùng đường dẫn /static/img/...
        như trên.

  b) Ảnh thật do nhiếp ảnh gia tải lên
      - Ảnh lưu trong thư mục media/ (đã cấu hình sẵn).
      - Model dùng trường ImageField, truyền .url của nó:
            image=goi.anh.url
        (goi.anh là tên trường ảnh trong model,
         đổi theo tên thật)
      - Nếu trường ảnh có thể để trống thì phải kiểm tra
        trước khi lấy .url, nếu không sẽ báo lỗi.
      - Dùng ImageField cần cài Pillow:
            pip install Pillow

  QUY ĐỊNH VỀ ẢNH
      - Ảnh NGANG, tỉ lệ 4:3, khoảng 800 x 600 px.
        Khung tự cắt cho vừa, ảnh dọc sẽ mất phần trên
        và phần dưới.
      - Dung lượng dưới 300 KB cho trang tải nhanh.
      - Tên file: chữ thường, không dấu, không khoảng
        trắng, nối bằng gạch ngang.
            Đúng: goi-chan-dung.jpg
            Sai : Gói chân dung 1.JPG
      - Ảnh không hiện? Mở thẳng địa chỉ:
            http://127.0.0.1:8000/static/img/ten-anh.jpg
        Thấy ảnh là đường dẫn đúng.
        Báo 404 là file đặt sai chỗ.


----------------------------------------------------------------------
6. THÊM HOẶC SỬA GIAO DIỆN: LÀM THẾ NÀO?
----------------------------------------------------------------------

  1) Cần thành phần đã có (nút, thẻ, ô nhập, thông báo)?
     -> DÙNG LẠI theo mẫu ở /ui-kit/

  2) Cần màu mới?
     -> Hỏi nhóm trước, rồi thêm vào static/css/tokens.css
        thành một biến có tên rõ nghĩa.

  3) Cần kiểu nút mới?
     -> Thêm vào static/css/components.css theo mẫu .btn--tên
     -> Cập nhật mục 3 trong file này
     -> Thêm một mẫu vào templates/ui_kit.html

  4) Trước khi gửi code, mở /ui-kit/ để chắc chắn mình
     không làm hỏng giao diện chung.


----------------------------------------------------------------------
7. MENU THEO VAI TRÒ, MENU ĐIỆN THOẠI VÀ XEM THỬ
----------------------------------------------------------------------

  DANH SÁCH MENU
      Khai báo trong core/navigation.py (biến MENUS).
      Menu được đưa vào mọi template bởi core/context_processors.py.
      Muốn thêm hoặc bớt mục menu thì sửa ở navigation.py.

  NHIẾP ẢNH GIA CHƯA ĐƯỢC DUYỆT
      Nhiếp ảnh gia có trạng thái hồ sơ "Chờ duyệt" hoặc
      "Đã từ chối" CHỈ thấy mục "Hồ sơ của tôi" (theo kế hoạch P5
      và wireframe). Chỉ khi hồ sơ "Đã duyệt" mới thấy đủ menu
      (Portfolio, Gói dịch vụ, Lịch của tôi, Quản lý Booking, Tin nhắn).
      Logic lọc nằm trong core/context_processors.py,
      ngay trước dòng "nav_items".
      Nếu đổi tên URL "photographer_profile" thì phải sửa cả chỗ lọc này.

  MENU TRÊN ĐIỆN THOẠI (dưới 960px)
      - Menu ẨN mặc định, chỉ hiện khi bấm nút ba gạch.
      - Bấm nút thì static/js/app.js thêm class is-open vào header,
        và static/css/base.css hiện menu thành bảng thả xuống
        ngay dưới header.
      - Từ 960px trở lên, menu nằm ngang trong header, không có nút ba gạch.
      - Đừng đặt display: block cho .site-nav ở phần CSS mặc định,
        vì sẽ làm menu luôn hiện trên điện thoại.

  XEM THỬ MENU KHI DEBUG
      Mở /ui-kit/ rồi bấm link ở dòng "Xem thử menu theo vai trò".
      Chỉ chạy khi DEBUG = True, không cần đăng nhập.

      ?xem_voi_vai_tro=khach                    Khách
      ?xem_voi_vai_tro=khach_hang               Khách hàng
      ?xem_voi_vai_tro=nhiep_anh_gia            Nhiếp ảnh gia (đã duyệt)
      ?xem_voi_vai_tro=nhiep_anh_gia_cho_duyet  Nhiếp ảnh gia chưa duyệt
      ?xem_voi_vai_tro=quan_tri_vien            Quản trị viên

      Muốn thêm kiểu xem thử mới thì sửa PREVIEW_KEYS trong
      core/navigation.py và thêm link vào templates/ui_kit.html.


----------------------------------------------------------------------
8. BẢN ĐỒ FILE
----------------------------------------------------------------------

  static/css/tokens.css
      Màu, font, khoảng cách (nơi DUY NHẤT khai báo màu)

  static/css/base.css
      Bố cục chung, header, footer, menu điện thoại

  static/css/components.css
      Nút, thẻ, ô nhập, nhãn trạng thái, thông báo

  static/img/
      Logo và ảnh mẫu

  templates/includes/
      Header, footer, thông báo, ô nhập, phân trang

  templates/includes/card.html
      Mẫu thẻ (nhận tham số image)

  templates/ui_kit.html
      Trang xem thử mọi thành phần

  core/status_tones.py
      Gán trạng thái -> màu

  core/navigation.py
      Danh sách menu theo vai trò, khóa xem thử

  core/context_processors.py
      Đưa menu vào template, lọc menu Nhiếp ảnh gia chưa duyệt

  config/settings.py
      Có MESSAGE_TAGS để thông báo lỗi hiện màu đỏ

======================================================================
