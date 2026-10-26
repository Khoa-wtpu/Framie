# =====================================================================
# bookings/services.py  -  Module 4: hàm DUY NHẤT để đổi trạng thái Booking (Tuyền)
# Người dùng hàm này: Nguyên (payments, delivery), Khoa (schedule, profiles), Phanh (thông báo, chat...).
#
#   chuyen_trang_thai_booking(booking, trang_thai_moi, ben_thuc_hien, ly_do=None)
#
# QUY TẮC CHUNG CỦA NHÓM:
#   - KHÔNG ai tự gán booking.TrangThai = ... rồi save(), cũng không .update(TrangThai=...).
#   - Muốn đổi trạng thái thì gọi hàm này. Hàm tự kiểm tra, tự đổi, tự ghi Lịch sử trạng thái.
#
# Ví dụ:
#   from bookings.services import chuyen_trang_thai_booking
#   from core.constants import TrangThaiBooking, BenThucHien
#
#   chuyen_trang_thai_booking(booking, TrangThaiBooking.CHOT_BOOKING, BenThucHien.NHIEP_ANH_GIA)
#   chuyen_trang_thai_booking(booking, TrangThaiBooking.DA_TU_CHOI, BenThucHien.NHIEP_ANH_GIA,
#                             ly_do='Trùng lịch cá nhân')
#   chuyen_trang_thai_booking(booking, TrangThaiBooking.HET_THOI_HAN_DAT_COC, BenThucHien.HE_THONG,
#                             ly_do='Quá 1 ngày chưa đặt cọc')
#
# Chữ trạng thái luôn lấy từ core/constants.py, không gõ trực tiếp.
# =====================================================================

# ---------------------------------------------------------------------
# PHẦN 1: IMPORT (khai báo các thư viện / thành phần cần dùng)
# ---------------------------------------------------------------------
from datetime import timedelta  # timedelta = "khoảng thời gian" (vd 1 ngày, 2 ngày) để cộng vào mốc giờ khi tính hạn chót

from django.core.exceptions import ValidationError  # loại lỗi chuẩn của Django, dùng để báo "dữ liệu/thao tác không hợp lệ"
from django.db import transaction  # transaction = gói nhiều thao tác DB làm một: hoặc thành công hết, hoặc hủy hết
from django.utils import timezone  # lấy giờ hiện tại có múi giờ (timezone.now()), đúng chuẩn của Django

from bookings.models import Booking, LichSuTrangThaiBooking  # 2 bảng: Booking (đơn đặt lịch) và Lịch sử đổi trạng thái
from core.constants import BenThucHien, LoaiHauKy, TrangThaiSlot  # các hằng số: bên thực hiện, loại hậu kỳ của gói, trạng thái slot
from core.constants import TrangThaiBooking as TT  # đặt tên ngắn TT cho TrangThaiBooking để viết bảng bên dưới cho gọn
from schedule.services import doi_trang_thai_khung_gio  # hàm của Khoa: đổi trạng thái khung giờ (slot) trong lịch

# Đặt tên ngắn cho 3 bên thực hiện để các dòng bên dưới ngắn gọn, dễ đọc
KH = BenThucHien.KHACH_HANG  # KH = Khách hàng
NAG = BenThucHien.NHIEP_ANH_GIA  # NAG = Nhiếp ảnh gia
HT = BenThucHien.HE_THONG  # HT = Hệ thống (các tác vụ tự động, vd quá hạn)

# ---------------------------------------------------------------------
# PHẦN 2: BẢNG CHUYỂN TRẠNG THÁI (quy trình TO-BE)
#   khóa  : (trạng thái cũ, trạng thái mới)
#   giá trị: tập các bên ĐƯỢC PHÉP thực hiện bước chuyển đó
# Bước nào không có trong bảng thì bị cấm.
# Đã đối chiếu với quy trình TO-BE (các mục 4 đến 10).
# ---------------------------------------------------------------------
CHUYEN_HOP_LE = {  # dict (từ điển): mỗi cặp (cũ, mới) -> tập các bên được phép. Không có trong dict = cấm
    # --- Nhận / từ chối Booking ---
    (TT.CHO_XAC_NHAN, TT.CHO_DAT_COC): {NAG},          # Chờ xác nhận -> Chờ đặt cọc: chỉ Nhiếp ảnh gia (chấp nhận)
    (TT.CHO_XAC_NHAN, TT.DA_TU_CHOI): {NAG},           # Chờ xác nhận -> Đã từ chối: chỉ Nhiếp ảnh gia (bắt buộc có lý do)

    # --- Đặt cọc 40% ---
    (TT.CHO_DAT_COC, TT.CHOT_BOOKING): {NAG},          # Chờ đặt cọc -> Chốt Booking: Nhiếp ảnh gia xác nhận đã nhận đủ cọc
    (TT.CHO_DAT_COC, TT.HET_THOI_HAN_DAT_COC): {HT},   # Chờ đặt cọc -> Hết hạn cọc: chỉ Hệ thống tự làm (quá 1 ngày chưa cọc)

    # --- Hủy (chỉ ở Chờ đặt cọc hoặc Chốt Booking, BR4.6-1) ---
    (TT.CHO_DAT_COC, TT.DA_HUY): {KH, NAG},            # Hủy khi đang chờ cọc: cả Khách và Nhiếp ảnh gia đều được (bắt buộc lý do)
    (TT.CHOT_BOOKING, TT.DA_HUY): {KH, NAG},           # Hủy khi đã chốt: cả hai bên đều được (bắt buộc lý do)

    # --- Buổi chụp ---
    (TT.CHOT_BOOKING, TT.DA_CHUP): {NAG},              # mục 8.1: Nhiếp ảnh gia cập nhật "Đã chụp" sau buổi chụp

    # --- Chọn ảnh (chỉ gói "Giới hạn số lượng ảnh") / vào hậu kỳ ---
    (TT.DA_CHUP, TT.CHO_KH_CHON_ANH): {NAG},           # chỉ gói giới hạn số ảnh (kiểm tra thêm ở bước 6 trong hàm)
    (TT.DA_CHUP, TT.CHO_HAU_KY): {NAG},                # mục 9.2: gói hậu kỳ toàn bộ, Nhiếp ảnh gia tự hậu kỳ sau "Đã chụp", bỏ qua bước chọn ảnh
    (TT.CHO_KH_CHON_ANH, TT.CHO_HAU_KY): {KH},         # mục 9.1.2: Khách chọn xong (TO-BE không có bước tự động khi quá 2 ngày)

    # --- Hậu kỳ ---
    (TT.CHO_HAU_KY, TT.DANG_HAU_KY): {NAG},            # Nhiếp ảnh gia bắt đầu hậu kỳ
    (TT.DANG_HAU_KY, TT.CHO_KH_KIEM_TRA): {NAG},       # hậu kỳ xong, gửi Khách kiểm tra

    # --- Kiểm tra ảnh và thanh toán 60% ---
    (TT.CHO_KH_KIEM_TRA, TT.DANG_HAU_KY): {KH},               # mục 9.5.1: Khách yêu cầu chỉnh sửa (tối đa 3 lần/Booking) -> quay lại hậu kỳ
    (TT.CHO_KH_KIEM_TRA, TT.CHO_XAC_NHAN_THANH_TOAN): {KH},   # mục 9.5.2: Khách xác nhận hoàn tất bàn giao
    (TT.CHO_XAC_NHAN_THANH_TOAN, TT.HOAN_THANH): {NAG},       # mục 10.2.1 và 10.4: Nhiếp ảnh gia xác nhận đủ 60% -> Hoàn thành
}  # hết bảng CHUYEN_HOP_LE

# Các bước chuyển BẮT BUỘC có lý do (ghi vào LyDo của Lịch sử).
BUOC_BAT_BUOC_LY_DO = {  # set (tập hợp) các cặp (cũ, mới) mà người dùng phải nhập lý do
    (TT.CHO_XAC_NHAN, TT.DA_TU_CHOI),  # từ chối thì phải nói vì sao
    (TT.CHO_DAT_COC, TT.DA_HUY),       # hủy lúc chờ cọc phải có lý do
    (TT.CHOT_BOOKING, TT.DA_HUY),      # hủy lúc đã chốt phải có lý do
}

# Hạn chót tự gán khi Booking VÀO trạng thái mới (trạng thái mới: (tên field của Booking, thời hạn)).
DAT_HAN = {  # khi Booking vào trạng thái ở khóa, hệ thống gán luôn hạn chót tương ứng
    TT.CHO_DAT_COC: ('HanDatCoc', timedelta(days=1)),                   # 4.2.2: 1 ngày kể từ lúc chấp nhận
    TT.CHO_KH_CHON_ANH: ('HanChonAnh', timedelta(days=2)),              # 9.1.1: 2 ngày kể từ lúc tải ảnh
    TT.DANG_HAU_KY: ('HanHauKy', timedelta(days=3)),                    # 9.3: 3 ngày kể từ lúc Nhiếp ảnh gia bấm bắt đầu hậu kỳ (vào "Đang hậu kỳ"); Khách yêu cầu chỉnh sửa quay lại "Đang hậu kỳ" thì tính lại 3 ngày
    TT.CHO_XAC_NHAN_THANH_TOAN: ('HanThanhToanConLai', timedelta(days=2)),  # 9.5.2: 2 ngày kể từ lúc Khách xác nhận bàn giao
}

# Trạng thái slot (MaLich) đi kèm khi Booking VÀO trạng thái mới (TO-BE mục 4.2.1, 5.1, 6.1, 6.2.1, 7).
# Slot đổi bằng hàm của Khoa (doi_trang_thai_khung_gio), cùng transaction với Booking.
DOI_SLOT = {  # trạng thái Booking mới -> trạng thái slot phải đổi theo
    TT.CHOT_BOOKING: TrangThaiSlot.DA_DAT,               # đã nhận đủ cọc -> slot chuyển "Đã đặt"
    TT.DA_TU_CHOI: TrangThaiSlot.TRONG,                  # bị từ chối -> giải phóng slot (Trống)
    TT.HET_THOI_HAN_DAT_COC: TrangThaiSlot.TRONG,        # hết hạn cọc -> trả slot về Trống
    TT.DA_HUY: TrangThaiSlot.TRONG,                      # bị hủy -> trả slot về Trống
}

DO_DAI_LY_DO_TOI_DA = 255   # LichSuTrangThaiBooking.LyDo là CharField(max_length=255) nên lý do không được dài hơn 255 ký tự


# ---------------------------------------------------------------------
# PHẦN 3: HÀM CHÍNH
# ---------------------------------------------------------------------
def chuyen_trang_thai_booking(booking, trang_thai_moi, ben_thuc_hien, ly_do=None):  # khai báo hàm; ly_do mặc định None (không bắt buộc)
    """Đổi trạng thái một Booking và tự ghi một dòng Lịch sử trạng thái.

    booking        : mã Booking (MaBooking) hoặc đối tượng Booking.
    trang_thai_moi : một giá trị của TrangThaiBooking (core/constants.py).
    ben_thuc_hien  : BenThucHien.KHACH_HANG / NHIEP_ANH_GIA / HE_THONG.
    ly_do          : chữ giải thích; BẮT BUỘC khi Từ chối hoặc Hủy.

    Trả về đối tượng Booking đã cập nhật (TrangThai mới).
    Báo ValidationError (tiếng Việt) nếu: Booking không tồn tại, trạng thái hoặc bên thực hiện
    không hợp lệ, bước chuyển không có trong bảng TO-BE, bên này không được làm bước này,
    thiếu lý do, gói không khớp bước chọn ảnh/hậu kỳ, hoặc có người khác vừa đổi trạng thái trước.
    Mọi thứ nằm trong một transaction: lỗi ở đâu thì không đổi gì, không ghi lịch sử.
    """
    ma = getattr(booking, 'pk', booking)  # lấy khóa chính: nếu booking là đối tượng thì lấy .pk, nếu là số/mã sẵn thì giữ nguyên

    # 1. Kiểm tra tham số (chưa chạm database)
    if trang_thai_moi not in TT.ALL:  # trạng thái mới không nằm trong danh sách trạng thái hợp lệ
        raise ValidationError('Trạng thái Booking không hợp lệ.')  # báo lỗi và dừng hàm
    if ben_thuc_hien not in {KH, NAG, HT}:  # bên thực hiện không phải 1 trong 3 bên được định nghĩa
        raise ValidationError('Bên thực hiện không hợp lệ.')  # báo lỗi và dừng hàm
    ly_do = (ly_do or '').strip() or None  # None -> '' ; cắt khoảng trắng 2 đầu ; chuỗi rỗng/toàn dấu cách -> None
    if ly_do and len(ly_do) > DO_DAI_LY_DO_TOI_DA:  # có lý do nhưng dài quá 255 ký tự
        raise ValidationError(f'Lý do tối đa {DO_DAI_LY_DO_TOI_DA} ký tự.')  # báo lỗi (f-string chèn số 255 vào câu)

    with transaction.atomic():  # mở transaction: mọi thứ trong khối này thành công cùng nhau hoặc rollback cùng nhau
        # 2. Khóa dòng Booking để đọc trạng thái hiện tại mới nhất (tránh dùng bản cũ trong bộ nhớ)
        try:  # thử lấy Booking từ database
            bk = Booking.objects.select_for_update().select_related('MaGoi').get(pk=ma)  # select_for_update: khóa dòng, người khác phải chờ; select_related('MaGoi'): lấy luôn Gói trong 1 truy vấn; get(pk=ma): lấy đúng 1 Booking
        except Booking.DoesNotExist:  # không tìm thấy Booking có mã đó
            raise ValidationError('Booking không tồn tại.')  # đổi lỗi DB thành ValidationError tiếng Việt

        cu = bk.TrangThai  # trạng thái hiện tại LẤY TỪ DATABASE (không tin bản trong bộ nhớ)
        buoc = (cu, trang_thai_moi)  # gom thành cặp (cũ, mới) để tra bảng

        # 3. Bước chuyển có trong bảng TO-BE không?
        if buoc not in CHUYEN_HOP_LE:  # cặp này không có trong bảng = bị cấm
            raise ValidationError(f'Không thể chuyển Booking từ "{cu}" sang "{trang_thai_moi}".')  # báo rõ cũ -> mới

        # 4. Bên này có được làm bước này không?
        if ben_thuc_hien not in CHUYEN_HOP_LE[buoc]:  # tra tập các bên được phép của bước này
            raise ValidationError(  # bên thực hiện không có quyền
                f'{ben_thuc_hien} không có quyền chuyển Booking từ "{cu}" sang "{trang_thai_moi}".')

        # 5. Lý do bắt buộc với Từ chối / Hủy
        if buoc in BUOC_BAT_BUOC_LY_DO and not ly_do:  # bước thuộc nhóm cần lý do mà ly_do đang rỗng/None
            raise ValidationError('Vui lòng nhập lý do.')  # yêu cầu nhập lý do

        # 6. Sau "Đã chụp": đi đường nào tùy loại hậu kỳ của gói
        if cu == TT.DA_CHUP:  # chỉ kiểm tra khi đang ở "Đã chụp" (lúc này có 2 đường rẽ)
            loai = bk.MaGoi.LoaiHauKy  # loại hậu kỳ của gói dịch vụ (Giới hạn số ảnh hoặc Toàn bộ)
            if trang_thai_moi == TT.CHO_KH_CHON_ANH and loai != LoaiHauKy.GIOI_HAN:  # đi đường "Khách chọn ảnh" mà gói không phải loại giới hạn
                raise ValidationError('Chỉ gói "Giới hạn số lượng ảnh" mới có bước Khách hàng chọn ảnh.')
            if trang_thai_moi == TT.CHO_HAU_KY and loai != LoaiHauKy.TOAN_BO:  # nhảy thẳng vào hậu kỳ mà gói không phải loại toàn bộ
                raise ValidationError('Gói "Giới hạn số lượng ảnh" phải qua bước Khách hàng chọn ảnh trước.')

        # 7. Đổi trạng thái. UPDATE có điều kiện "trạng thái vẫn là cũ" (cùng kiểu với Khoa):
        #    nếu hai người cùng đổi một lúc, chỉ một người thành công (số dòng = 1).
        #    LyDoTuChoi do CHECK ck_booking_lydotuchoi trong database ép: có lý do khi "Đã từ chối", NULL ở mọi trạng thái khác.
        bay_gio = timezone.now()  # lấy 1 mốc giờ duy nhất, dùng chung cho cập nhật, hạn chót và lịch sử
        cac_cot = {'TrangThai': trang_thai_moi,  # các cột sẽ được cập nhật: trạng thái mới
                   'LyDoTuChoi': ly_do if trang_thai_moi == TT.DA_TU_CHOI else None,  # lý do từ chối chỉ lưu khi "Đã từ chối", còn lại là None
                   'NgayCapNhat': bay_gio}  # thời điểm cập nhật
        if trang_thai_moi in DAT_HAN:               # vào trạng thái có hạn chót thì gán hạn luôn
            ten_han, thoi_han = DAT_HAN[trang_thai_moi]  # tách tên cột hạn và khoảng thời gian (vd 'HanDatCoc', 1 ngày)
            cac_cot[ten_han] = bay_gio + thoi_han  # hạn chót = bây giờ + khoảng thời gian
        so_dong = Booking.objects.filter(pk=ma, TrangThai=cu).update(**cac_cot)   # UPDATE chỉ khi trạng thái vẫn là "cu"; trả về số dòng bị đổi; .update() không kích hoạt auto_now nên phải gán tay
        if so_dong != 1:  # 0 dòng = đã có người khác đổi trạng thái trước
            raise ValidationError('Booking vừa được người khác thay đổi, vui lòng tải lại trang.')

        # 8. Ghi Lịch sử trạng thái (cùng transaction với bước 7)
        LichSuTrangThaiBooking.objects.create(  # tạo 1 dòng lịch sử mới
            MaBooking=bk,  # thuộc Booking nào
            TrangThaiCu=cu,  # trạng thái trước khi đổi
            TrangThaiMoi=trang_thai_moi,  # trạng thái sau khi đổi
            ThoiDiemThayDoi=bay_gio,  # thời điểm đổi (cùng mốc giờ với bước 7)
            BenThucHien=ben_thuc_hien,  # ai thực hiện
            LyDo=ly_do,  # lý do (có thể None)
        )

        # 9. Đổi trạng thái slot nếu bước này có đi kèm (lỗi ở đây thì rollback cả Booking lẫn Lịch sử)
        if trang_thai_moi in DOI_SLOT:  # trạng thái mới có yêu cầu đổi slot không
            doi_trang_thai_khung_gio(bk.MaLich_id, DOI_SLOT[trang_thai_moi])  # gọi hàm của Khoa: truyền mã slot (MaLich_id) và trạng thái slot mới

        # 10. Trả lại đối tượng đã cập nhật
        for ten_cot, gia_tri in cac_cot.items():  # duyệt từng cột vừa cập nhật ở bước 7
            setattr(bk, ten_cot, gia_tri)  # gán giá trị mới vào đối tượng bk (vì .update() chỉ sửa DB, không sửa đối tượng trong bộ nhớ)
        return bk  # trả về Booking đã có dữ liệu mới