# =====================================================================
# core/views_trang_chu.py  -  B8: Trang chủ (trang đầu tiên khách thấy, không cần đăng nhập)
#
# Các khối (xen kẽ màu nền, xem core/static/core/css/trang_chu.css):
#   1. Banner + ô tìm kiếm nhanh   (nền tối)
#   2. Nhiếp ảnh gia nổi bật       (nền trắng)  <- hàm nhiep_anh_gia_noi_bat của Khoa (profiles/services.py)
#   3. Các bước đặt lịch           (nền xám nhạt)
#   4. Loại hình chụp              (nền trắng)
#   5. Lời mời đăng ký             (nền tối)
# =====================================================================
# ▸ ===== CHÚ THÍCH TỔNG QUAN (dành cho sếp) =====
# ▸ File này là "bộ não" của Trang chủ. Khi khách vào địa chỉ gốc của website ("/"),
# ▸ hệ thống gọi hàm trang_chu() ở cuối file. Hàm này làm 3 việc:
# ▸   (1) Lấy danh sách nhiếp ảnh gia nổi bật từ cơ sở dữ liệu.
# ▸   (2) Lấy danh sách loại hình chụp (Cưới, Chân dung...) kèm số nhiếp ảnh gia đang nhận.
# ▸   (3) Gom dữ liệu đó + 5 bước đặt lịch rồi giao cho file giao diện trang_chu.html để vẽ ra màn hình.
# ▸ Lưu ý: các dòng bắt đầu bằng "# ▸" là chú thích được thêm vào; code gốc giữ nguyên.

# ▸ Nạp công cụ Count của Django: dùng để ĐẾM số bản ghi trong cơ sở dữ liệu (ở đây là đếm số nhiếp ảnh gia).
from django.db.models import Count
# ▸ Nạp hàm render: ghép dữ liệu vào file giao diện (.html) để tạo ra trang web hoàn chỉnh trả cho khách.
from django.shortcuts import render
# ▸ Nạp reverse (từ tên trang -> địa chỉ URL) và NoReverseMatch (lỗi xảy ra khi tên trang đó chưa tồn tại).
from django.urls import NoReverseMatch, reverse

# ▸ Nạp 2 bảng dữ liệu: LoaiHinhChup (danh mục loại hình: Cưới, Chân dung...)
# ▸ và NhiepAnhGia_LoaiHinhChup (bảng nối: nhiếp ảnh gia nào nhận chụp loại hình nào).
from profiles.models import LoaiHinhChup, NhiepAnhGia_LoaiHinhChup
# ▸ Nạp hàm do bạn Khoa viết: trả về danh sách nhiếp ảnh gia nổi bật (điểm đánh giá cao...).
from profiles.services import nhiep_anh_gia_noi_bat
# ▸ Nạp hàm của module tìm kiếm: trả về các nhiếp ảnh gia ĐANG CÔNG KHAI (hồ sơ đã được duyệt).
from search.services import nhiep_anh_gia_cong_khai

# ▸ Hằng số cấu hình: Trang chủ chỉ hiện 3 nhiếp ảnh gia nổi bật. Muốn hiện nhiều/ít hơn chỉ cần sửa số 3 này.
SO_NHIEP_ANH_GIA_NOI_BAT = 3   # số thẻ ở khối "Nhiếp ảnh gia nổi bật"

# Các bước đặt lịch, đi theo quy trình Booking của FRAMIE (xem TrangThaiBooking trong core/constants.py)
# ▸ Danh sách 5 bước đặt lịch hiện ở khối số 3 của trang. Mỗi bước là một cặp (Tiêu đề, Mô tả ngắn).
# ▸ Nội dung viết cứng tại đây nên muốn đổi chữ trên trang chủ chỉ cần sửa trong danh sách này.
BUOC_DAT_LICH = [
    # ▸ Bước 1: khách tìm nhiếp ảnh gia theo nhiều tiêu chí.
    ('Tìm nhiếp ảnh gia', 'Tìm theo từ khóa, loại hình, khu vực hoặc mức giá, rồi xem hồ sơ và Portfolio.'),
    # ▸ Bước 2: chọn giờ trống; hệ thống giữ chỗ tạm 5 phút để không ai khác đặt trùng.
    ('Chọn lịch và giữ chỗ', 'Chọn khung giờ còn trống, FRAMIE giữ chỗ cho bạn trong 5 phút.'),
    # ▸ Bước 3: điền thông tin buổi chụp và gửi yêu cầu đặt lịch (Booking).
    ('Gửi yêu cầu Booking', 'Chọn gói dịch vụ, điền địa điểm, số người, concept và yêu cầu riêng.'),
    # ▸ Bước 4: nhiếp ảnh gia đồng ý, khách đặt cọc 40% để chốt lịch.
    ('Xác nhận và đặt cọc', 'Nhiếp ảnh gia chấp nhận yêu cầu, bạn đặt cọc 40% để chốt lịch.'),
    # ▸ Bước 5: chụp xong, khách chọn ảnh, kiểm tra ảnh đã chỉnh sửa và thanh toán phần còn lại để nhận ảnh.
    ('Chụp và nhận ảnh', 'Sau buổi chụp, bạn chọn ảnh, kiểm tra ảnh hậu kỳ và nhận ảnh sau khi thanh toán phần còn lại.'),
# ▸ Dấu ] đóng danh sách 5 bước.
]


# ▸ Hàm phụ (tên bắt đầu bằng dấu _ nghĩa là chỉ dùng nội bộ trong file này).
# ▸ Nhiệm vụ: nhận mã nhiếp ảnh gia (ma) và trả về địa chỉ trang hồ sơ của người đó.
def _duong_dan_ho_so(ma):
    # Trang hồ sơ công khai là K9 (name='photographer_detail'). Chưa có thì thẻ chưa bấm được, không báo lỗi.
    # ▸ try: thử chạy đoạn bên dưới; nếu có lỗi loại NoReverseMatch thì nhảy xuống except thay vì làm sập trang.
    try:
        # ▸ Hỏi Django: "trang tên 'photographer_detail' có địa chỉ là gì, với mã nhiếp ảnh gia = ma?" rồi trả kết quả.
        return reverse('photographer_detail', args=[ma])
    # ▸ Nếu trang hồ sơ (do bạn K9 làm) CHƯA được tạo thì Django báo lỗi này; ta bắt lỗi để trang chủ vẫn chạy bình thường.
    except NoReverseMatch:
        # ▸ Trả về chuỗi rỗng = "chưa có đường dẫn". Giao diện sẽ hiểu và không cho bấm vào thẻ.
        return ''


# ▸ Hàm phụ: chuẩn bị dữ liệu cho các thẻ "Nhiếp ảnh gia nổi bật".
def _the_noi_bat():
    """Kết quả hàm của Khoa + thêm 'href' (hồ sơ) và 'diem' (chuỗi '4.8', cùng cách hiển thị với trang tìm kiếm)."""
    # ▸ Tạo danh sách rỗng, sẽ lần lượt bỏ từng thẻ nhiếp ảnh gia vào đây.
    cac_the = []
    # ▸ Gọi hàm của Khoa lấy 3 nhiếp ảnh gia nổi bật, rồi duyệt từng người một (mỗi người tạm gọi là nag).
    for nag in nhiep_anh_gia_noi_bat(so_luong=SO_NHIEP_ANH_GIA_NOI_BAT):
        # ▸ Thêm vào danh sách một thẻ mới. Dấu ** nghĩa là "chép nguyên toàn bộ thông tin có sẵn của nag" rồi bổ sung thêm 2 mục:
        cac_the.append({**nag,
                        # ▸ Mục 'href': đường dẫn tới hồ sơ của người đó (nag['nhiep_anh_gia'].pk là mã định danh trong CSDL).
                        'href': _duong_dan_ho_so(nag['nhiep_anh_gia'].pk),
                        # ▸ Mục 'diem': điểm đánh giá trung bình làm tròn 1 chữ số thập phân (vd 4.8) dạng chữ, để hiển thị giống trang tìm kiếm.
                        'diem': f"{nag['diem_trung_binh']:.1f}"})
    # ▸ Trả danh sách các thẻ đã hoàn chỉnh về cho nơi gọi.
    return cac_the


# ▸ Hàm phụ: chuẩn bị danh sách loại hình chụp, mỗi loại kèm số nhiếp ảnh gia đang nhận.
def _loai_hinh_kem_so_nguoi():
    """Mỗi loại hình kèm số nhiếp ảnh gia công khai đang nhận loại hình đó (0 thì không hiện số)."""
    # ▸ Tính ra một "từ điển" dạng {mã loại hình: số nhiếp ảnh gia}. Ví dụ {1: 5, 2: 3} = loại hình 1 có 5 người, loại 2 có 3 người.
    so_nguoi = dict(
        # ▸ Bắt đầu từ bảng nối "nhiếp ảnh gia - loại hình chụp".
        NhiepAnhGia_LoaiHinhChup.objects
        # ▸ Chỉ giữ các dòng thuộc nhiếp ảnh gia ĐANG CÔNG KHAI (đã duyệt). Hồ sơ chờ duyệt bị loại, không tính vào số đếm.
        .filter(MaNhiepAnhGia__in=nhiep_anh_gia_cong_khai().values('pk'))
        # ▸ Lấy cột mã loại hình, gom nhóm theo từng loại và đếm số dòng trong mỗi nhóm (n) => ra các cặp (mã loại hình, số người).
        .values_list('MaLoaiHinh').annotate(n=Count('pk')))
    # ▸ Duyệt TOÀN BỘ loại hình trong CSDL, mỗi loại tạo ra một mục dữ liệu cho giao diện (kết quả là danh sách).
    return [{'ma': lh.pk, 'ten': lh.TenLoaiHinh, 'so_nguoi': so_nguoi.get(lh.pk, 0)}
            # ▸ Chi tiết mỗi mục: 'ma' = mã loại hình; 'ten' = tên hiển thị (vd "Cưới");
            # ▸ 'so_nguoi' = số người tra trong từ điển ở trên, nếu loại hình chưa ai nhận thì lấy 0.
            for lh in LoaiHinhChup.objects.all()]


# ▸ HÀM CHÍNH của file: Django gọi hàm này mỗi khi có khách mở Trang chủ. "request" là thông tin yêu cầu của khách (trình duyệt, tài khoản đăng nhập...).
def trang_chu(request):
    # ▸ Dựng trang web: dùng file giao diện 'core/trang_chu.html' và truyền vào 3 gói dữ liệu dưới đây; kết quả trả thẳng về trình duyệt của khách.
    return render(request, 'core/trang_chu.html', {
        # ▸ Gói 1: các thẻ nhiếp ảnh gia nổi bật (khối số 2 trên trang).
        'noi_bat': _the_noi_bat(),
        # ▸ Gói 2: danh sách loại hình chụp kèm số người (dùng ở ô "Gợi ý nhanh" và khối số 4).
        'loai_hinh_ds': _loai_hinh_kem_so_nguoi(),
        # ▸ Gói 3: 5 bước đặt lịch (khối số 3).
        'buoc_dat_lich': BUOC_DAT_LICH,
    # ▸ Đóng ngoặc: kết thúc lệnh render và kết thúc hàm.
    })
