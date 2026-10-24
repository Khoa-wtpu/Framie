"""
Module 4 - Quản lý Booking (FRAMIE)
Models theo Data Dictionary: BOOKING, GIUCHO, LICHSUTRANGTHAIBOOKING, YEUCAUHUY.


"""

# ===========================================================================
# PHẦN 1: IMPORT (gọi các công cụ cần dùng)
# ===========================================================================
from datetime import timedelta  # timedelta = một khoảng thời gian (ví dụ 5 phút), dùng để cộng vào giờ

from django.conf import settings  # settings = file config/settings.py của project
from django.core.exceptions import ValidationError  # lỗi để báo "dữ liệu không hợp lệ"
from django.core.validators import MinValueValidator  # bộ kiểm tra "giá trị phải >= số nào đó"
from django.db import models  # chứa các kiểu cột (CharField, DateTimeField...) và lớp Model
from django.db.models import F, Q, Value  # F = tham chiếu tới cột khác; Q = điều kiện; Value = giá trị cố định
from django.db.models.functions import Trim  # hàm cắt khoảng trắng đầu/cuối chuỗi (như TRIM trong SQL)
from django.db.models.lookups import Exact  # phép so sánh "bằng" (=) dùng trong điều kiện
from django.utils import timezone  # lấy giờ hiện tại, có tính múi giờ

from core.constants import (  # lấy tên trạng thái từ file chung của nhóm, KHÔNG tự gõ chữ tiếng Việt
    BenThucHien,  # ai thực hiện: Khách hàng / Nhiếp ảnh gia / Hệ thống
    TrangThaiBooking,  # 13 trạng thái của Booking
    TrangThaiGiuCho,  # trạng thái một lượt giữ chỗ
    TrangThaiGoi,  # trạng thái gói dịch vụ (Đang áp dụng...)
    TrangThaiHoanTien,  # Chờ hoàn tiền / Đã hoàn tiền
    VaiTro,  # tên 3 vai trò (cũng là tên 3 Group của Django)
    XuLyTienCoc,  # Không phát sinh / Mất cọc / Hoàn cọc
)

# ===========================================================================
# PHẦN 2: HẰNG SỐ VÀ HÀM HỖ TRỢ
# ===========================================================================
# Tên model của app khác, viết dạng "tên_app.TênModel" (chuỗi) để tránh import vòng.
NHIEP_ANH_GIA_MODEL = "profiles.NhiepAnhGia"  # bảng NHIEPANHGIA (app profiles của Khoa)
GOI_DICH_VU_MODEL = "profiles.GoiDichVu"  # bảng GOIDICHVU (app profiles của Khoa)
LICH_KHA_DUNG_MODEL = "schedule.LichKhaDung"  # bảng LICHKHADUNG (app schedule của Khoa)

USER_MODEL = settings.AUTH_USER_MODEL  # bảng User của Django (tài khoản), lấy từ settings
NHOM_KHACH_HANG = VaiTro.KHACH_HANG  # tên Group "Khách hàng" để kiểm tra quyền

THOI_GIAN_GIU_CHO = timedelta(minutes=5)  # giữ chỗ tối đa 5 phút (quy tắc BR4.1-1)


def _rong(ten_cot):
    """Tạo điều kiện "cột này, sau khi cắt khoảng trắng, là chuỗi rỗng"."""
    # Tương đương SQL: TRIM(ten_cot) = ''. Dùng để cấm người dùng nhập toàn dấu cách.
    return Exact(Trim(ten_cot), Value(""))


def _gia_tri(choices):
    """Từ danh sách [(giá trị, nhãn), ...] chỉ lấy ra các giá trị."""
    # CHOICES trong core/constants.py là danh sách cặp (giá trị, nhãn);
    # ở đây ta chỉ cần phần giá trị để kiểm tra "nằm trong danh sách hợp lệ".
    return [v for v, _ in choices]


# core.constants không có lớp riêng cho "bên yêu cầu hủy",
# nên lấy 2 giá trị từ BenThucHien (bỏ "Hệ thống" vì hệ thống không được yêu cầu hủy).
BEN_YEU_CAU_HUY = [BenThucHien.KHACH_HANG, BenThucHien.NHIEP_ANH_GIA]
BEN_YEU_CAU_HUY_CHOICES = [(v, v) for v in BEN_YEU_CAU_HUY]  # dạng cặp (giá trị, nhãn) cho cột có choices

# Booking rơi vào 3 trạng thái này thì KHÔNG còn chiếm slot nữa (quy tắc BR4.2-3).
TRANG_THAI_HET_HIEU_LUC = [
    TrangThaiBooking.DA_TU_CHOI,  # Nhiếp ảnh gia từ chối
    TrangThaiBooking.HET_THOI_HAN_DAT_COC,  # Khách không cọc trong 1 ngày
    TrangThaiBooking.DA_HUY,  # đã hủy
]


# ===========================================================================
# PHẦN 3: BẢNG GIUCHO (mỗi dòng = một lượt Khách hàng giữ slot tạm thời)
# ===========================================================================
class GiuCho(models.Model):  # kế thừa models.Model => đây là một bảng trong database
    MaGiuCho = models.AutoField(primary_key=True)  # khóa chính, số tự tăng 1, 2, 3...
    MaKhachHang = models.ForeignKey(  # khóa ngoại: trỏ tới bảng User (người đang giữ chỗ)
        USER_MODEL,  # bảng được trỏ tới
        on_delete=models.PROTECT,  # không cho xóa User nếu còn lượt giữ chỗ (= ON DELETE RESTRICT)
        db_column="MaKhachHang",  # tên cột thật trong database (giữ đúng Data Dictionary)
        related_name="giu_cho",  # từ một User có thể gọi user.giu_cho.all() để lấy các lượt giữ
        verbose_name="Khách hàng",  # tên hiển thị trong trang admin
    )
    MaLich = models.ForeignKey(  # khóa ngoại: trỏ tới slot (khung giờ) được giữ
        LICH_KHA_DUNG_MODEL,
        on_delete=models.PROTECT,  # không cho xóa slot nếu đã có lượt giữ
        db_column="MaLich",
        related_name="giu_cho",
        verbose_name="Slot được giữ",
    )
    ThoiDiemGiu = models.DateTimeField(default=timezone.now)  # lúc bắt đầu giữ; mặc định là giờ hiện tại
    ThoiDiemHetHan = models.DateTimeField(blank=True)  # lúc hết hạn; để trống được vì save() sẽ tự tính = giữ + 5 phút
    TrangThai = models.CharField(  # cột chữ lưu trạng thái lượt giữ
        max_length=30,  # tối đa 30 ký tự
        choices=TrangThaiGiuCho.CHOICES,  # chỉ cho chọn trong danh sách ở core/constants.py
        default=TrangThaiGiuCho.DANG_GIU,  # mặc định là "Đang giữ chỗ"
    )

    class Meta:  # cấu hình thêm cho bảng
        db_table = "GIUCHO"  # tên bảng thật trong database
        verbose_name = "Giữ chỗ"  # tên số ít hiển thị ở admin
        verbose_name_plural = "Giữ chỗ"  # tên số nhiều hiển thị ở admin
        constraints = [  # các ràng buộc do DATABASE kiểm tra, sai là không cho lưu
            # BR4.1-2: mỗi slot chỉ có MỘT lượt đang giữ tại một thời điểm
            models.UniqueConstraint(  # ràng buộc "không được trùng"
                fields=["MaLich"],  # cột không được trùng là MaLich...
                condition=Q(TrangThai=TrangThaiGiuCho.DANG_GIU),  # ...nhưng chỉ xét các dòng đang "Đang giữ chỗ"
                name="uq_giucho_malich_dang_giu",  # tên ràng buộc (phải khác nhau trong toàn project)
            ),
            models.CheckConstraint(  # ràng buộc "phải thỏa điều kiện"
                condition=Q(ThoiDiemHetHan__gt=F("ThoiDiemGiu")),  # giờ hết hạn phải SAU giờ bắt đầu giữ
                name="ck_giucho_hethan_sau_giu",
            ),
            models.CheckConstraint(
                condition=Q(TrangThai__in=_gia_tri(TrangThaiGiuCho.CHOICES)),  # TrangThai phải thuộc danh sách hợp lệ
                name="ck_giucho_trangthai",
            ),
        ]

    def __str__(self):  # chuỗi hiển thị khi in một lượt giữ chỗ (ở admin, log)
        return f"GiuCho #{self.pk} - slot {self.MaLich_id} ({self.TrangThai})"  # ví dụ: GiuCho #3 - slot 12 (Đang giữ chỗ)

    def clean(self):  # kiểm tra quy tắc nghiệp vụ (database không tự làm được)
        # Người giữ chỗ phải thuộc nhóm (Group) Khách hàng
        if self.MaKhachHang_id and not self.MaKhachHang.groups.filter(  # đã chọn User và User đó KHÔNG có Group...
            name=NHOM_KHACH_HANG  # ...tên "Khách hàng"
        ).exists():
            raise ValidationError({"MaKhachHang": "Người dùng không thuộc nhóm Khách hàng."})  # báo lỗi ở ô MaKhachHang

    def save(self, *args, **kwargs):  # chạy mỗi khi lưu một lượt giữ chỗ
        # BR4.1-2: giữ đúng 5 phút, do tầng ứng dụng (đoạn code này) đảm bảo
        if not self.ThoiDiemHetHan:  # nếu chưa có giờ hết hạn
            self.ThoiDiemGiu = self.ThoiDiemGiu or timezone.now()  # đảm bảo có giờ bắt đầu giữ
            self.ThoiDiemHetHan = self.ThoiDiemGiu + THOI_GIAN_GIU_CHO  # giờ hết hạn = giờ giữ + 5 phút
        super().save(*args, **kwargs)  # sau đó mới lưu thật vào database

    @property  # biến hàm thành thuộc tính: dùng giu_cho.da_het_han (không có dấu ngoặc)
    def da_het_han(self):  # lượt giữ này đã quá hạn chưa?
        return (
            self.TrangThai == TrangThaiGiuCho.DANG_GIU  # vẫn đang "Đang giữ chỗ"
            and timezone.now() >= self.ThoiDiemHetHan  # và giờ hiện tại đã tới/quá giờ hết hạn
        )


# ===========================================================================
# PHẦN 4: BẢNG BOOKING (mỗi dòng = một yêu cầu đặt lịch chụp)
# ===========================================================================
class Booking(models.Model):  # bảng BOOKING
    MaBooking = models.AutoField(primary_key=True)  # khóa chính tự tăng
    MaKhachHang = models.ForeignKey(  # khách hàng tạo Booking (trỏ tới User)
        USER_MODEL,
        on_delete=models.PROTECT,  # không cho xóa User khi còn Booking
        db_column="MaKhachHang",
        related_name="booking_khach_hang",  # user.booking_khach_hang.all() = các Booking của khách
        verbose_name="Khách hàng",
    )
    MaNhiepAnhGia = models.ForeignKey(  # nhiếp ảnh gia nhận Booking
        NHIEP_ANH_GIA_MODEL,
        on_delete=models.PROTECT,
        db_column="MaNhiepAnhGia",
        related_name="booking",
        verbose_name="Nhiếp ảnh gia",
    )
    MaGoi = models.ForeignKey(  # gói dịch vụ khách chọn
        GOI_DICH_VU_MODEL,
        on_delete=models.PROTECT,  # gói bị "xóa" thì chỉ ngừng áp dụng, vẫn giữ lịch sử Booking
        db_column="MaGoi",
        related_name="booking",
        verbose_name="Gói dịch vụ",
    )
    MaLich = models.ForeignKey(  # slot (khung giờ) được đặt
        LICH_KHA_DUNG_MODEL,
        on_delete=models.PROTECT,
        db_column="MaLich",
        related_name="booking",
        verbose_name="Slot được đặt",
    )
    NgayGioChup = models.DateTimeField(verbose_name="Ngày giờ chụp")  # ngày giờ dự kiến chụp
    DiaDiem = models.CharField(max_length=255, verbose_name="Địa điểm")  # nơi chụp, tối đa 255 ký tự
    SoNguoi = models.IntegerField(  # số người tham gia
        validators=[MinValueValidator(1)],  # form phải nhập >= 1
        verbose_name="Số người",
    )
    Concept = models.CharField(max_length=500)  # ý tưởng/phong cách buổi chụp
    YeuCauRieng = models.CharField(  # ghi chú riêng của khách
        max_length=1000,
        null=True,  # database cho phép NULL (không có giá trị)
        blank=True,  # form cho phép bỏ trống
    )
    TrangThai = models.CharField(  # trạng thái hiện tại của Booking (1 trong 13)
        max_length=30,
        choices=TrangThaiBooking.CHOICES,  # chỉ nhận 13 trạng thái trong core/constants.py
        default=TrangThaiBooking.CHO_XAC_NHAN,  # Booking mới tạo luôn là "Chờ xác nhận"
    )
    HanDatCoc = models.DateTimeField(null=True, blank=True)  # hạn chót khách đặt cọc 40% (1 ngày)
    HanChonAnh = models.DateTimeField(null=True, blank=True)  # hạn chót khách chọn ảnh (2 ngày)
    HanHauKy = models.DateTimeField(null=True, blank=True)  # hạn chót nhiếp ảnh gia hậu kỳ xong (3 ngày)
    HanThanhToanConLai = models.DateTimeField(null=True, blank=True)  # hạn chót trả 60% còn lại
    TongGiaTri = models.DecimalField(max_digits=12, decimal_places=0)  # tổng tiền, số nguyên tối đa 12 chữ số (VNĐ)
    LyDoTuChoi = models.CharField(  # lý do nhiếp ảnh gia từ chối
        max_length=500,
        null=True,
        blank=True,  # chỉ có giá trị khi Booking ở trạng thái "Đã từ chối"
    )
    NgayTao = models.DateTimeField(default=timezone.now)  # lúc khách gửi yêu cầu Booking
    NgayCapNhat = models.DateTimeField(auto_now=True)  # Django tự ghi giờ mỗi lần lưu (không dùng ON UPDATE của SQL)

    class Meta:
        db_table = "BOOKING"
        verbose_name = "Booking"
        verbose_name_plural = "Booking"
        constraints = [
            # BR4.2-3: một slot chỉ gắn với MỘT Booking còn hiệu lực
            models.UniqueConstraint(
                fields=["MaLich"],  # MaLich không được trùng...
                condition=~Q(TrangThai__in=TRANG_THAI_HET_HIEU_LUC),  # ...với các Booking KHÔNG thuộc 3 trạng thái hết hiệu lực (dấu ~ = phủ định)
                name="uq_booking_malich_con_hieu_luc",
            ),
            models.CheckConstraint(
                condition=Q(NgayGioChup__gt=F("NgayTao")),  # ngày giờ chụp phải sau lúc tạo Booking
                name="ck_booking_ngaygiochup_sau_ngaytao",
            ),
            models.CheckConstraint(
                condition=~Q(_rong("DiaDiem")),  # địa điểm KHÔNG được rỗng (kể cả toàn dấu cách)
                name="ck_booking_diadiem_khong_rong",
            ),
            models.CheckConstraint(
                condition=Q(SoNguoi__gte=1),  # số người >= 1 (gte = greater than or equal)
                name="ck_booking_songuoi",
            ),
            models.CheckConstraint(
                condition=~Q(_rong("Concept")),  # concept không được rỗng
                name="ck_booking_concept_khong_rong",
            ),
            models.CheckConstraint(
                condition=Q(TrangThai__in=TrangThaiBooking.ALL),  # trạng thái phải nằm trong 13 trạng thái
                name="ck_booking_trangthai",
            ),
            models.CheckConstraint(
                condition=Q(HanDatCoc__isnull=True) | Q(HanDatCoc__gt=F("NgayTao")),  # chưa có hạn (NULL) HOẶC (dấu |) hạn phải sau NgayTao
                name="ck_booking_handatcoc",
            ),
            models.CheckConstraint(
                condition=Q(HanChonAnh__isnull=True) | Q(HanChonAnh__gt=F("NgayTao")),  # tương tự cho hạn chọn ảnh
                name="ck_booking_hanchonanh",
            ),
            models.CheckConstraint(
                condition=Q(HanHauKy__isnull=True) | Q(HanHauKy__gt=F("NgayTao")),  # tương tự cho hạn hậu kỳ
                name="ck_booking_hanhauky",
            ),
            models.CheckConstraint(
                condition=(
                    Q(HanThanhToanConLai__isnull=True)
                    | Q(HanThanhToanConLai__gt=F("NgayTao"))  # tương tự cho hạn thanh toán còn lại
                ),
                name="ck_booking_hanthanhtoanconlai",
            ),
            models.CheckConstraint(
                condition=Q(TongGiaTri__gt=0),  # tổng giá trị phải > 0
                name="ck_booking_tonggiatri",
            ),
            # LyDoTuChoi: phải có (không rỗng) khi "Đã từ chối", và phải NULL ở mọi trạng thái khác
            models.CheckConstraint(
                condition=(
                    (  # trường hợp 1: đã từ chối
                        Q(TrangThai=TrangThaiBooking.DA_TU_CHOI)  # trạng thái là "Đã từ chối"
                        & Q(LyDoTuChoi__isnull=False)  # VÀ (dấu &) có lý do
                        & ~Q(_rong("LyDoTuChoi"))  # VÀ lý do không rỗng
                    )
                    | (  # HOẶC trường hợp 2: không bị từ chối
                        ~Q(TrangThai=TrangThaiBooking.DA_TU_CHOI)  # trạng thái khác "Đã từ chối"
                        & Q(LyDoTuChoi__isnull=True)  # VÀ lý do phải để NULL
                    )
                ),
                name="ck_booking_lydotuchoi",
            ),
            models.CheckConstraint(
                condition=Q(NgayCapNhat__gte=F("NgayTao")),  # ngày cập nhật không được trước ngày tạo
                name="ck_booking_ngaycapnhat",
            ),
        ]

    def __str__(self):  # chuỗi hiển thị của một Booking
        return f"Booking #{self.pk} - {self.TrangThai}"  # ví dụ: Booking #7 - Chờ đặt cọc

    def save(self, *args, **kwargs):  # chạy mỗi khi lưu Booking
        # TongGiaTri = giá gói tại thời điểm đặt. Chốt cứng, sau này Khoa sửa giá gói thì Booking cũ không đổi.
        if self.TongGiaTri is None and self.MaGoi_id:  # chưa gán tổng tiền và đã chọn gói
            self.TongGiaTri = self.MaGoi.Gia  # lấy giá của gói làm tổng giá trị
        super().save(*args, **kwargs)  # rồi lưu thật vào database

    def clean(self):  # kiểm tra các quy tắc mà Data Dictionary giao cho "tầng ứng dụng"
        """Các kiểm tra mà Data Dictionary giao cho trigger/tầng ứng dụng."""
        errors = {}  # gom tất cả lỗi vào đây, cuối hàm báo một lần

        # 1. Người đặt phải thuộc Group Khách hàng
        if self.MaKhachHang_id and not self.MaKhachHang.groups.filter(
            name=NHOM_KHACH_HANG
        ).exists():
            errors["MaKhachHang"] = "Người dùng không thuộc nhóm Khách hàng."

        # 2. Nhiếp ảnh gia của Booking phải trùng với nhiếp ảnh gia của gói và của slot
        #    (giả định GoiDichVu và LichKhaDung đều có FK tên MaNhiepAnhGia)
        if self.MaGoi_id and self.MaNhiepAnhGia_id:  # đã chọn cả gói và nhiếp ảnh gia
            if self.MaGoi.MaNhiepAnhGia_id != self.MaNhiepAnhGia_id:  # gói thuộc người khác
                errors["MaGoi"] = "Gói dịch vụ không thuộc Nhiếp ảnh gia đã chọn."
        if self.MaLich_id and self.MaNhiepAnhGia_id:  # đã chọn cả slot và nhiếp ảnh gia
            if self.MaLich.MaNhiepAnhGia_id != self.MaNhiepAnhGia_id:  # slot thuộc người khác
                errors["MaLich"] = "Slot không thuộc Nhiếp ảnh gia đã chọn."

        # 2b. Booking MỚI chỉ được chọn gói "Đang áp dụng" (Booking cũ vẫn giữ gói đã ngừng)
        if self._state.adding and self.MaGoi_id and "MaGoi" not in errors:  # _state.adding = True nghĩa là đang tạo mới
            if self.MaGoi.TrangThai != TrangThaiGoi.DANG_AP_DUNG:
                errors["MaGoi"] = "Gói dịch vụ không còn được áp dụng."

        # 3. NgayGioChup phải nằm trong khung giờ của slot (Ngay, GioBatDau đến GioKetThuc)
        #    (giả định LichKhaDung có Ngay, GioBatDau, GioKetThuc)
        if self.MaLich_id and self.NgayGioChup:
            thoi_diem = self.NgayGioChup  # lấy ngày giờ chụp
            if timezone.is_aware(thoi_diem):  # nếu có thông tin múi giờ
                thoi_diem = timezone.localtime(thoi_diem)  # đổi về giờ địa phương (VN) để so với slot
            lich = self.MaLich  # slot đã chọn
            if not (
                thoi_diem.date() == lich.Ngay  # cùng ngày với slot
                and lich.GioBatDau <= thoi_diem.time() <= lich.GioKetThuc  # và giờ nằm trong khoảng của slot
            ):
                errors["NgayGioChup"] = "Ngày giờ chụp phải nằm trong khung giờ của slot."

        if errors:  # nếu có ít nhất một lỗi
            raise ValidationError(errors)  # báo toàn bộ lỗi ra form/admin


# ===========================================================================
# PHẦN 5: BẢNG LICHSUTRANGTHAIBOOKING (mỗi dòng = một lần Booking đổi trạng thái)
# ===========================================================================
class LichSuTrangThaiBooking(models.Model):
    MaLichSu = models.AutoField(primary_key=True)  # khóa chính tự tăng
    MaBooking = models.ForeignKey(  # Booking có trạng thái thay đổi
        Booking,
        on_delete=models.PROTECT,  # không cho xóa Booking nếu còn lịch sử
        db_column="MaBooking",
        related_name="lich_su_trang_thai",  # booking.lich_su_trang_thai.all() = toàn bộ lịch sử của Booking
    )
    TrangThaiCu = models.CharField(  # trạng thái TRƯỚC khi đổi
        max_length=30,
        choices=TrangThaiBooking.CHOICES,
        null=True,
        blank=True,  # NULL ở bản ghi đầu tiên (lúc mới tạo thì chưa có trạng thái cũ)
    )
    TrangThaiMoi = models.CharField(max_length=30, choices=TrangThaiBooking.CHOICES)  # trạng thái SAU khi đổi
    ThoiDiemThayDoi = models.DateTimeField(default=timezone.now)  # lúc trạng thái thay đổi
    BenThucHien = models.CharField(max_length=20, choices=BenThucHien.CHOICES)  # ai gây ra thay đổi (Khách hàng / Nhiếp ảnh gia / Hệ thống)
    LyDo = models.CharField(max_length=255, null=True, blank=True)  # lý do hoặc ghi chú kèm theo thay đổi

    class Meta:
        db_table = "LICHSUTRANGTHAIBOOKING"
        verbose_name = "Lịch sử trạng thái Booking"
        verbose_name_plural = "Lịch sử trạng thái Booking"
        ordering = ["ThoiDiemThayDoi", "MaLichSu"]  # mặc định sắp xếp từ cũ đến mới
        constraints = [
            models.CheckConstraint(
                condition=Q(TrangThaiCu__isnull=True)  # trạng thái cũ để trống (NULL)...
                | Q(TrangThaiCu__in=TrangThaiBooking.ALL),  # ...hoặc phải thuộc 13 trạng thái
                name="ck_lichsu_trangthaicu",
            ),
            models.CheckConstraint(
                condition=Q(TrangThaiMoi__in=TrangThaiBooking.ALL),  # trạng thái mới bắt buộc thuộc 13 trạng thái
                name="ck_lichsu_trangthaimoi",
            ),
            models.CheckConstraint(
                condition=Q(BenThucHien__in=_gia_tri(BenThucHien.CHOICES)),  # bên thực hiện phải hợp lệ
                name="ck_lichsu_benthuchien",
            ),
        ]

    def __str__(self):
        return f"#{self.MaBooking_id}: {self.TrangThaiCu or '∅'} → {self.TrangThaiMoi}"  # ví dụ: #7: Chờ xác nhận → Chờ đặt cọc


# ===========================================================================
# PHẦN 6: BẢNG YEUCAUHUY (mỗi dòng = một yêu cầu hủy Booking)
# ===========================================================================
class YeuCauHuy(models.Model):
    MaYeuCauHuy = models.AutoField(primary_key=True)  # khóa chính tự tăng
    MaBooking = models.OneToOneField(  # OneToOne = "một-một": mỗi Booking chỉ có tối đa 1 yêu cầu hủy (tự UNIQUE)
        Booking,
        on_delete=models.PROTECT,
        db_column="MaBooking",
        related_name="yeu_cau_huy",  # booking.yeu_cau_huy trả về yêu cầu hủy của Booking đó
    )
    BenYeuCau = models.CharField(max_length=20, choices=BEN_YEU_CAU_HUY_CHOICES)  # bên gửi yêu cầu: Khách hàng / Nhiếp ảnh gia
    LyDo = models.CharField(max_length=500)  # lý do hủy (bắt buộc)
    # Chỉ được hủy khi Booking đang ở "Chờ đặt cọc" hoặc "Chốt Booking" (quy tắc BR4.6-1)
    TrangThaiBookingLucHuy = models.CharField(
        max_length=30,
        choices=[  # chỉ cho chọn 2 trạng thái này
            (TrangThaiBooking.CHO_DAT_COC, TrangThaiBooking.CHO_DAT_COC),
            (TrangThaiBooking.CHOT_BOOKING, TrangThaiBooking.CHOT_BOOKING),
        ],
    )
    XuLyTienCoc = models.CharField(max_length=20, choices=XuLyTienCoc.CHOICES)  # hệ quả tiền cọc: không phát sinh / mất cọc / hoàn cọc
    TrangThaiHoanTien = models.CharField(  # theo dõi hoàn cọc (chỉ có khi "Hoàn cọc")
        max_length=20,
        choices=TrangThaiHoanTien.CHOICES,
        null=True,
        blank=True,
    )
    ThoiDiemXacNhanHoanTien = models.DateTimeField(null=True, blank=True)  # lúc khách xác nhận đã nhận lại tiền cọc
    ThoiDiemYeuCau = models.DateTimeField(default=timezone.now)  # lúc gửi yêu cầu hủy (cũng là lúc việc hủy có hiệu lực)

    class Meta:
        db_table = "YEUCAUHUY"
        verbose_name = "Yêu cầu hủy"
        verbose_name_plural = "Yêu cầu hủy"
        constraints = [
            models.CheckConstraint(
                condition=Q(BenYeuCau__in=BEN_YEU_CAU_HUY),  # bên yêu cầu chỉ là Khách hàng hoặc Nhiếp ảnh gia
                name="ck_yeucauhuy_benyeucau",
            ),
            models.CheckConstraint(
                condition=~Q(_rong("LyDo")),  # lý do không được rỗng
                name="ck_yeucauhuy_lydo_khong_rong",
            ),
            models.CheckConstraint(
                condition=Q(
                    TrangThaiBookingLucHuy__in=[  # chỉ 2 trạng thái được phép hủy
                        TrangThaiBooking.CHO_DAT_COC,
                        TrangThaiBooking.CHOT_BOOKING,
                    ]
                ),
                name="ck_yeucauhuy_trangthailuchuy",
            ),
            models.CheckConstraint(
                condition=Q(XuLyTienCoc__in=_gia_tri(XuLyTienCoc.CHOICES)),  # xử lý tiền cọc phải hợp lệ
                name="ck_yeucauhuy_xulytiencoc",
            ),
            # Khách hàng hủy: chỉ "Không phát sinh" hoặc "Mất cọc"
            # Nhiếp ảnh gia hủy: chỉ "Không phát sinh" hoặc "Hoàn cọc"
            models.CheckConstraint(
                condition=(
                    (
                        Q(BenYeuCau=BenThucHien.KHACH_HANG)
                        & Q(XuLyTienCoc__in=[XuLyTienCoc.KHONG_PHAT_SINH, XuLyTienCoc.MAT_COC])
                    )
                    | (
                        Q(BenYeuCau=BenThucHien.NHIEP_ANH_GIA)
                        & Q(XuLyTienCoc__in=[XuLyTienCoc.KHONG_PHAT_SINH, XuLyTienCoc.HOAN_COC])
                    )
                ),
                name="ck_yeucauhuy_ben_xulytiencoc",
            ),
            # Hủy lúc "Chờ đặt cọc" (chưa có tiền) => Không phát sinh
            # Hủy lúc "Chốt Booking" (đã cọc) => Mất cọc hoặc Hoàn cọc
            models.CheckConstraint(
                condition=(
                    (
                        Q(TrangThaiBookingLucHuy=TrangThaiBooking.CHO_DAT_COC)
                        & Q(XuLyTienCoc=XuLyTienCoc.KHONG_PHAT_SINH)
                    )
                    | (
                        Q(TrangThaiBookingLucHuy=TrangThaiBooking.CHOT_BOOKING)
                        & Q(XuLyTienCoc__in=[XuLyTienCoc.MAT_COC, XuLyTienCoc.HOAN_COC])
                    )
                ),
                name="ck_yeucauhuy_luchuy_xulytiencoc",
            ),
            # TrangThaiHoanTien chỉ có giá trị khi XuLyTienCoc là "Hoàn cọc"; các trường hợp khác phải NULL
            models.CheckConstraint(
                condition=(
                    (
                        Q(XuLyTienCoc=XuLyTienCoc.HOAN_COC)
                        & Q(TrangThaiHoanTien__in=_gia_tri(TrangThaiHoanTien.CHOICES))
                    )
                    | (
                        ~Q(XuLyTienCoc=XuLyTienCoc.HOAN_COC)
                        & Q(TrangThaiHoanTien__isnull=True)
                    )
                ),
                name="ck_yeucauhuy_trangthaihoantien",
            ),
            # ThoiDiemXacNhanHoanTien chỉ có khi "Đã hoàn tiền" và phải >= ThoiDiemYeuCau
            models.CheckConstraint(
                condition=(
                    (
                        Q(TrangThaiHoanTien=TrangThaiHoanTien.DA_HOAN_TIEN)
                        & Q(ThoiDiemXacNhanHoanTien__isnull=False)
                        & Q(ThoiDiemXacNhanHoanTien__gte=F("ThoiDiemYeuCau"))
                    )
                    | (
                        ~Q(TrangThaiHoanTien=TrangThaiHoanTien.DA_HOAN_TIEN)
                        & Q(ThoiDiemXacNhanHoanTien__isnull=True)
                    )
                ),
                name="ck_yeucauhuy_thoidiemxacnhanhoantien",
            ),
        ]

    def __str__(self):
        return f"YeuCauHuy #{self.pk} - Booking {self.MaBooking_id} ({self.BenYeuCau})"  # ví dụ: YeuCauHuy #2 - Booking 7 (Khách hàng)

    def save(self, *args, **kwargs):  # chạy mỗi khi lưu yêu cầu hủy
        # Nếu là "Hoàn cọc" mà chưa ghi trạng thái hoàn tiền => mặc định "Chờ hoàn tiền"
        if self.XuLyTienCoc == XuLyTienCoc.HOAN_COC and not self.TrangThaiHoanTien:
            self.TrangThaiHoanTien = TrangThaiHoanTien.CHO_HOAN_TIEN
        super().save(*args, **kwargs)  # rồi lưu thật vào database