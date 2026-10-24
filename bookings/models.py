"""
Module 4 - Quản lý Booking (FRAMIE)
Models theo Data Dictionary: BOOKING, GIUCHO, LICHSUTRANGTHAIBOOKING, YEUCAUHUY.


"""
from datetime import timedelta # Dùng để biểu diễn khoảng thời gian giữ chỗ 5 phút.

from django.conf import settings # Lấy cấu hình của dự án Django.
from django.core.exceptions import ValidationError # Dùng để báo lỗi khi dữ liệu không hợp lệ.
from django.core.validators import MinValueValidator # Bộ kiểm tra giá trị tối thiểu của trường dữ liệu.
from django.db import models # Cung cấp các kiểu trường và mô hình của Django ORM.
from django.db.models import F, Q, Value # F tham chiếu trường; Q tạo điều kiện; Value tạo giá trị cố định trong truy vấn.
from django.db.models.functions import Trim # Loại bỏ khoảng trắng ở đầu và cuối chuỗi trong truy vấn.
from django.db.models.lookups import Exact # So sánh chính xác hai giá trị trong truy vấn.
from django.utils import timezone # Lấy thời gian hiện tại theo cấu hình múi giờ của Django.

from core.constants import (
    BenThucHien,
    TrangThaiBooking,
    TrangThaiGiuCho,
    TrangThaiGoi,
    TrangThaiHoanTien,
    VaiTro,
    XuLyTienCoc,
)

# ---------------------------------------------------------------------------
NHIEP_ANH_GIA_MODEL = "profiles.NhiepAnhGia"   # NHIEPANHGIA(MaNhiepAnhGia)
GOI_DICH_VU_MODEL = "profiles.GoiDichVu"              # GOIDICHVU(MaGoi)
LICH_KHA_DUNG_MODEL = "schedule.LichKhaDung"          # LICHKHADUNG(MaLich)

USER_MODEL = settings.AUTH_USER_MODEL                # User(id) của Django
NHOM_KHACH_HANG = VaiTro.KHACH_HANG                  # tên Group trong Django

THOI_GIAN_GIU_CHO = timedelta(minutes=5)             # BR4.1-1


def _rong(ten_cot): # Tạo điều kiện kiểm tra một cột có chuỗi rỗng sau khi bỏ khoảng trắng.
    """TRIM(cot) = '' (dùng cho CHECK TRIM(...) <> '')."""
    return Exact(Trim(ten_cot), Value("")) # Trả về điều kiện TRIM(cột) = chuỗi rỗng.


def _gia_tri(choices): # Lấy các giá trị hợp lệ từ danh sách choices.
    """Lấy danh sách giá trị từ CHOICES [(giá trị, nhãn), ...] của core.constants."""
    return [v for v, _ in choices] # Chỉ lấy phần giá trị, bỏ phần nhãn hiển thị.


# core.constants không có lớp riêng cho "bên yêu cầu hủy": chỉ Khách hàng / Nhiếp ảnh gia
BEN_YEU_CAU_HUY = [BenThucHien.KHACH_HANG, BenThucHien.NHIEP_ANH_GIA] # Chỉ khách hàng hoặc nhiếp ảnh gia được yêu cầu hủy.
BEN_YEU_CAU_HUY_CHOICES = [(v, v) for v in BEN_YEU_CAU_HUY] # Tạo danh sách lựa chọn cho trường BenYeuCau.


# Booking ở các trạng thái này thì KHÔNG còn hiệu lực -> slot được giải phóng (BR4.2-3)
TRANG_THAI_HET_HIEU_LUC = [ # Các trạng thái này không còn chiếm slot.
    TrangThaiBooking.DA_TU_CHOI,
    TrangThaiBooking.HET_THOI_HAN_DAT_COC,
    TrangThaiBooking.DA_HUY,
]


# ---------------------------------------------------------------------------
# BẢNG GIUCHO
# ---------------------------------------------------------------------------
class GiuCho(models.Model): # Model quản lý lượt giữ chỗ của khách hàng.
    MaGiuCho = models.AutoField(primary_key=True) # Khóa chính tự tăng của bản ghi giữ chỗ.
    MaKhachHang = models.ForeignKey( # Khóa ngoại liên kết tài khoản khách hàng.
        USER_MODEL, on_delete=models.PROTECT, db_column="MaKhachHang",
        related_name="giu_cho", verbose_name="Khách hàng",
    )
    MaLich = models.ForeignKey( # Khóa ngoại liên kết slot lịch được giữ.
        LICH_KHA_DUNG_MODEL, on_delete=models.PROTECT, db_column="MaLich",
        related_name="giu_cho", verbose_name="Slot được giữ",
    )
    ThoiDiemGiu = models.DateTimeField(default=timezone.now) # Thời điểm bắt đầu giữ chỗ; mặc định là hiện tại.
    ThoiDiemHetHan = models.DateTimeField(blank=True)  # tự tính = ThoiDiemGiu + 5 phút
    TrangThai = models.CharField( # Trạng thái giữ chỗ, giới hạn theo choices.
        max_length=30, choices=TrangThaiGiuCho.CHOICES,
        default=TrangThaiGiuCho.DANG_GIU,
    )

    class Meta: # Khai báo cấu hình bổ sung cho model.
        db_table = "GIUCHO" # Chỉ định tên bảng tương ứng trong cơ sở dữ liệu.
        verbose_name = "Giữ chỗ"
        verbose_name_plural = "Giữ chỗ"
        constraints = [ # Các ràng buộc dữ liệu ở cấp cơ sở dữ liệu.
            # BR4.1-2: mỗi slot chỉ một lượt đang giữ
            models.UniqueConstraint( # Đảm bảo không có bản ghi trùng theo điều kiện chỉ định.
                fields=["MaLich"],
                condition=Q(TrangThai=TrangThaiGiuCho.DANG_GIU),
                name="uq_giucho_malich_dang_giu",
            ),
            models.CheckConstraint( # Buộc dữ liệu phải thỏa mãn điều kiện kiểm tra.
                condition=Q(ThoiDiemHetHan__gt=F("ThoiDiemGiu")),
                name="ck_giucho_hethan_sau_giu",
            ),
            models.CheckConstraint( # Buộc dữ liệu phải thỏa mãn điều kiện kiểm tra.
                condition=Q(TrangThai__in=_gia_tri(TrangThaiGiuCho.CHOICES)),
                name="ck_giucho_trangthai",
            ),
        ]

    def __str__(self): # Chuỗi tóm tắt Booking khi hiển thị trong log/admin.
        return f"GiuCho #{self.pk} - slot {self.MaLich_id} ({self.TrangThai})"

    def clean(self): # Kiểm tra các quy tắc nghiệp vụ ở tầng ứng dụng.
        # User phải thuộc Group Khách hàng
        if self.MaKhachHang_id and not self.MaKhachHang.groups.filter(
            name=NHOM_KHACH_HANG
        ).exists():
            raise ValidationError({"MaKhachHang": "Người dùng không thuộc nhóm Khách hàng."})

    def save(self, *args, **kwargs): # Tùy chỉnh quy trình lưu đối tượng vào cơ sở dữ liệu.
        # BR4.1-1: đúng 5 phút do tầng ứng dụng đảm bảo
        if not self.ThoiDiemHetHan:
            self.ThoiDiemGiu = self.ThoiDiemGiu or timezone.now()
            self.ThoiDiemHetHan = self.ThoiDiemGiu + THOI_GIAN_GIU_CHO
        super().save(*args, **kwargs)

    @property
    def da_het_han(self): # Thuộc tính kiểm tra lượt giữ chỗ đã hết hạn chưa.
        return (
            self.TrangThai == TrangThaiGiuCho.DANG_GIU
            and timezone.now() >= self.ThoiDiemHetHan
        )


# ---------------------------------------------------------------------------
# BẢNG BOOKING
# ---------------------------------------------------------------------------
class Booking(models.Model): # Model lưu thông tin đặt lịch chụp.
    MaBooking = models.AutoField(primary_key=True) # Khóa chính tự tăng của Booking.
    MaKhachHang = models.ForeignKey( # Khóa ngoại liên kết tài khoản khách hàng.
        USER_MODEL, on_delete=models.PROTECT, db_column="MaKhachHang",
        related_name="booking_khach_hang", verbose_name="Khách hàng",
    )
    MaNhiepAnhGia = models.ForeignKey(
        NHIEP_ANH_GIA_MODEL, on_delete=models.PROTECT, db_column="MaNhiepAnhGia",
        related_name="booking", verbose_name="Nhiếp ảnh gia",
    )
    MaGoi = models.ForeignKey(
        GOI_DICH_VU_MODEL, on_delete=models.PROTECT, db_column="MaGoi",
        related_name="booking", verbose_name="Gói dịch vụ",
    )
    MaLich = models.ForeignKey( # Khóa ngoại liên kết slot lịch được giữ.
        LICH_KHA_DUNG_MODEL, on_delete=models.PROTECT, db_column="MaLich",
        related_name="booking", verbose_name="Slot được đặt",
    )
    NgayGioChup = models.DateTimeField(verbose_name="Ngày giờ chụp") # Ngày và giờ khách đặt lịch chụp.
    DiaDiem = models.CharField(max_length=255, verbose_name="Địa điểm") # Địa điểm diễn ra buổi chụp.
    SoNguoi = models.IntegerField(validators=[MinValueValidator(1)], verbose_name="Số người") # Số người tham gia; validator yêu cầu ít nhất 1.
    Concept = models.CharField(max_length=500) # Ý tưởng/chủ đề buổi chụp.
    YeuCauRieng = models.CharField(max_length=1000, null=True, blank=True) # Yêu cầu bổ sung của khách; có thể để trống hoặc NULL.
    TrangThai = models.CharField( # Trạng thái giữ chỗ, giới hạn theo choices.
        max_length=30, choices=TrangThaiBooking.CHOICES,
        default=TrangThaiBooking.CHO_XAC_NHAN,
    )
    HanDatCoc = models.DateTimeField(null=True, blank=True) # Hạn khách phải đặt cọc.
    HanChonAnh = models.DateTimeField(null=True, blank=True) # Hạn khách chọn ảnh.
    HanHauKy = models.DateTimeField(null=True, blank=True) # Hạn hoàn thành hậu kỳ.
    HanThanhToanConLai = models.DateTimeField(null=True, blank=True) # Hạn thanh toán phần tiền còn lại.
    TongGiaTri = models.DecimalField(max_digits=12, decimal_places=0) # Tổng giá trị Booking, lưu dạng số thập phân.
    LyDoTuChoi = models.CharField(max_length=500, null=True, blank=True) # Lý do từ chối; chỉ có giá trị khi Booking bị từ chối.
    NgayTao = models.DateTimeField(default=timezone.now) # Thời điểm tạo Booking.
    NgayCapNhat = models.DateTimeField(auto_now=True)  # Django auto_now, không dùng ON UPDATE

    class Meta: # Khai báo cấu hình bổ sung cho model.
        db_table = "BOOKING" # Chỉ định tên bảng tương ứng trong cơ sở dữ liệu.
        verbose_name = "Booking"
        verbose_name_plural = "Booking"
        constraints = [ # Các ràng buộc dữ liệu ở cấp cơ sở dữ liệu.
            # BR4.2-3: một slot chỉ gắn một Booking còn hiệu lực
            models.UniqueConstraint( # Đảm bảo không có bản ghi trùng theo điều kiện chỉ định.
                fields=["MaLich"],
                condition=~Q(TrangThai__in=TRANG_THAI_HET_HIEU_LUC),
                name="uq_booking_malich_con_hieu_luc",
            ),
            models.CheckConstraint( # Buộc dữ liệu phải thỏa mãn điều kiện kiểm tra.
                condition=Q(NgayGioChup__gt=F("NgayTao")),
                name="ck_booking_ngaygiochup_sau_ngaytao",
            ),
            models.CheckConstraint( # Buộc dữ liệu phải thỏa mãn điều kiện kiểm tra.
                condition=~Q(_rong("DiaDiem")),
                name="ck_booking_diadiem_khong_rong",
            ),
            models.CheckConstraint( # Buộc dữ liệu phải thỏa mãn điều kiện kiểm tra.
                condition=Q(SoNguoi__gte=1),
                name="ck_booking_songuoi",
            ),
            models.CheckConstraint( # Buộc dữ liệu phải thỏa mãn điều kiện kiểm tra.
                condition=~Q(_rong("Concept")),
                name="ck_booking_concept_khong_rong",
            ),
            models.CheckConstraint( # Buộc dữ liệu phải thỏa mãn điều kiện kiểm tra.
                condition=Q(TrangThai__in=TrangThaiBooking.ALL),
                name="ck_booking_trangthai",
            ),
            models.CheckConstraint( # Buộc dữ liệu phải thỏa mãn điều kiện kiểm tra.
                condition=Q(HanDatCoc__isnull=True) | Q(HanDatCoc__gt=F("NgayTao")),
                name="ck_booking_handatcoc",
            ),
            models.CheckConstraint( # Buộc dữ liệu phải thỏa mãn điều kiện kiểm tra.
                condition=Q(HanChonAnh__isnull=True) | Q(HanChonAnh__gt=F("NgayTao")),
                name="ck_booking_hanchonanh",
            ),
            models.CheckConstraint( # Buộc dữ liệu phải thỏa mãn điều kiện kiểm tra.
                condition=Q(HanHauKy__isnull=True) | Q(HanHauKy__gt=F("NgayTao")),
                name="ck_booking_hanhauky",
            ),
            models.CheckConstraint( # Buộc dữ liệu phải thỏa mãn điều kiện kiểm tra.
                condition=(
                    Q(HanThanhToanConLai__isnull=True)
                    | Q(HanThanhToanConLai__gt=F("NgayTao"))
                ),
                name="ck_booking_hanthanhtoanconlai",
            ),
            models.CheckConstraint( # Buộc dữ liệu phải thỏa mãn điều kiện kiểm tra.
                condition=Q(TongGiaTri__gt=0),
                name="ck_booking_tonggiatri",
            ),
            # LyDoTuChoi: bắt buộc (không rỗng) khi Đã từ chối, phải NULL ở trạng thái khác
            models.CheckConstraint( # Buộc dữ liệu phải thỏa mãn điều kiện kiểm tra.
                condition=(
                    (
                        Q(TrangThai=TrangThaiBooking.DA_TU_CHOI)
                        & Q(LyDoTuChoi__isnull=False)
                        & ~Q(_rong("LyDoTuChoi"))
                    )
                    | (
                        ~Q(TrangThai=TrangThaiBooking.DA_TU_CHOI)
                        & Q(LyDoTuChoi__isnull=True)
                    )
                ),
                name="ck_booking_lydotuchoi",
            ),
            models.CheckConstraint( # Buộc dữ liệu phải thỏa mãn điều kiện kiểm tra.
                condition=Q(NgayCapNhat__gte=F("NgayTao")),
                name="ck_booking_ngaycapnhat",
            ),
        ]

    def __str__(self): # Chuỗi tóm tắt Booking khi hiển thị trong log/admin.
        return f"Booking #{self.pk} - {self.TrangThai}"

    def save(self, *args, **kwargs): # Tùy chỉnh quy trình lưu đối tượng vào cơ sở dữ liệu.
        # TongGiaTri = giá gói tại thời điểm đặt (chốt cứng, không đổi khi Khoa sửa giá gói sau này)
        if self.TongGiaTri is None and self.MaGoi_id:
            self.TongGiaTri = self.MaGoi.Gia
        super().save(*args, **kwargs)

    def clean(self): # Kiểm tra các quy tắc nghiệp vụ ở tầng ứng dụng.
        """Các kiểm tra mà Data Dictionary giao cho trigger/tầng ứng dụng."""
        errors = {}

        # 1. MaKhachHang thuộc Group Khách hàng
        if self.MaKhachHang_id and not self.MaKhachHang.groups.filter(
            name=NHOM_KHACH_HANG
        ).exists():
            errors["MaKhachHang"] = "Người dùng không thuộc nhóm Khách hàng."

        # 2. MaNhiepAnhGia phải trùng NAG của gói dịch vụ và của slot
        #    (giả định GoiDichVu và LichKhaDung đều có FK MaNhiepAnhGia)
        if self.MaGoi_id and self.MaNhiepAnhGia_id:
            if self.MaGoi.MaNhiepAnhGia_id != self.MaNhiepAnhGia_id:
                errors["MaGoi"] = "Gói dịch vụ không thuộc Nhiếp ảnh gia đã chọn."
        if self.MaLich_id and self.MaNhiepAnhGia_id:
            if self.MaLich.MaNhiepAnhGia_id != self.MaNhiepAnhGia_id:
                errors["MaLich"] = "Slot không thuộc Nhiếp ảnh gia đã chọn."

        # 2b. Booking mới chỉ được chọn gói "Đang áp dụng" (Booking cũ vẫn giữ gói đã ngừng)
        if self._state.adding and self.MaGoi_id and "MaGoi" not in errors:
            if self.MaGoi.TrangThai != TrangThaiGoi.DANG_AP_DUNG:
                errors["MaGoi"] = "Gói dịch vụ không còn được áp dụng."

        # 3. NgayGioChup nằm trong Ngay, GioBatDau–GioKetThuc của slot
        #    (giả định LichKhaDung có Ngay, GioBatDau, GioKetThuc)
        if self.MaLich_id and self.NgayGioChup:
            thoi_diem = self.NgayGioChup
            if timezone.is_aware(thoi_diem):
                thoi_diem = timezone.localtime(thoi_diem)
            lich = self.MaLich
            if not (
                thoi_diem.date() == lich.Ngay
                and lich.GioBatDau <= thoi_diem.time() <= lich.GioKetThuc
            ):
                errors["NgayGioChup"] = "Ngày giờ chụp phải nằm trong khung giờ của slot."

        if errors:
            raise ValidationError(errors)


# ---------------------------------------------------------------------------
# BẢNG LICHSUTRANGTHAIBOOKING
# ---------------------------------------------------------------------------
class LichSuTrangThaiBooking(models.Model): # Model lưu lại lịch sử thay đổi trạng thái Booking.
    MaLichSu = models.AutoField(primary_key=True) # Khóa chính tự tăng của bản ghi lịch sử.
    MaBooking = models.ForeignKey(
        Booking, on_delete=models.PROTECT, db_column="MaBooking",
        related_name="lich_su_trang_thai",
    )
    TrangThaiCu = models.CharField( # Trạng thái trước khi thay đổi; có thể NULL với bản ghi đầu tiên.
        max_length=30, choices=TrangThaiBooking.CHOICES, null=True, blank=True,
    )
    TrangThaiMoi = models.CharField(max_length=30, choices=TrangThaiBooking.CHOICES) # Trạng thái sau khi thay đổi.
    ThoiDiemThayDoi = models.DateTimeField(default=timezone.now) # Thời điểm trạng thái được thay đổi.
    BenThucHien = models.CharField(max_length=20, choices=BenThucHien.CHOICES) # Bên thực hiện thay đổi, theo danh sách choices.
    LyDo = models.CharField(max_length=255, null=True, blank=True) # Lý do yêu cầu hủy.

    class Meta: # Khai báo cấu hình bổ sung cho model.
        db_table = "LICHSUTRANGTHAIBOOKING" # Chỉ định tên bảng tương ứng trong cơ sở dữ liệu.
        verbose_name = "Lịch sử trạng thái Booking"
        verbose_name_plural = "Lịch sử trạng thái Booking"
        ordering = ["ThoiDiemThayDoi", "MaLichSu"]
        constraints = [ # Các ràng buộc dữ liệu ở cấp cơ sở dữ liệu.
            models.CheckConstraint( # Buộc dữ liệu phải thỏa mãn điều kiện kiểm tra.
                condition=Q(TrangThaiCu__isnull=True)
                | Q(TrangThaiCu__in=TrangThaiBooking.ALL),
                name="ck_lichsu_trangthaicu",
            ),
            models.CheckConstraint( # Buộc dữ liệu phải thỏa mãn điều kiện kiểm tra.
                condition=Q(TrangThaiMoi__in=TrangThaiBooking.ALL),
                name="ck_lichsu_trangthaimoi",
            ),
            models.CheckConstraint( # Buộc dữ liệu phải thỏa mãn điều kiện kiểm tra.
                condition=Q(BenThucHien__in=_gia_tri(BenThucHien.CHOICES)),
                name="ck_lichsu_benthuchien",
            ),
        ]

    def __str__(self): # Chuỗi tóm tắt Booking khi hiển thị trong log/admin.
        return f"#{self.MaBooking_id}: {self.TrangThaiCu or '∅'} → {self.TrangThaiMoi}"


# ---------------------------------------------------------------------------
# BẢNG YEUCAUHUY
# ---------------------------------------------------------------------------
class YeuCauHuy(models.Model): # Model lưu yêu cầu hủy Booking và xử lý tiền cọc.
    MaYeuCauHuy = models.AutoField(primary_key=True) # Khóa chính tự tăng của yêu cầu hủy.
    MaBooking = models.OneToOneField(  # NOT NULL + UNIQUE
        Booking, on_delete=models.PROTECT, db_column="MaBooking",
        related_name="yeu_cau_huy",
    )
    BenYeuCau = models.CharField(max_length=20, choices=BEN_YEU_CAU_HUY_CHOICES) # Bên gửi yêu cầu hủy.
    LyDo = models.CharField(max_length=500) # Lý do yêu cầu hủy.
    # Chỉ được hủy khi Booking ở Chờ đặt cọc hoặc Chốt Booking (BR4.6-1)
    TrangThaiBookingLucHuy = models.CharField(
        max_length=30,
        choices=[
            (TrangThaiBooking.CHO_DAT_COC, TrangThaiBooking.CHO_DAT_COC),
            (TrangThaiBooking.CHOT_BOOKING, TrangThaiBooking.CHOT_BOOKING),
        ],
    )
    XuLyTienCoc = models.CharField(max_length=20, choices=XuLyTienCoc.CHOICES) # Cách xử lý tiền cọc khi hủy.
    TrangThaiHoanTien = models.CharField( # Trạng thái hoàn tiền; có thể chưa phát sinh.
        max_length=20, choices=TrangThaiHoanTien.CHOICES, null=True, blank=True,
    )
    ThoiDiemXacNhanHoanTien = models.DateTimeField(null=True, blank=True) # Thời điểm xác nhận đã hoàn tiền.
    ThoiDiemYeuCau = models.DateTimeField(default=timezone.now) # Thời điểm tạo yêu cầu hủy.

    class Meta: # Khai báo cấu hình bổ sung cho model.
        db_table = "YEUCAUHUY" # Chỉ định tên bảng tương ứng trong cơ sở dữ liệu.
        verbose_name = "Yêu cầu hủy"
        verbose_name_plural = "Yêu cầu hủy"
        constraints = [ # Các ràng buộc dữ liệu ở cấp cơ sở dữ liệu.
            models.CheckConstraint( # Buộc dữ liệu phải thỏa mãn điều kiện kiểm tra.
                condition=Q(BenYeuCau__in=BEN_YEU_CAU_HUY),
                name="ck_yeucauhuy_benyeucau",
            ),
            models.CheckConstraint( # Buộc dữ liệu phải thỏa mãn điều kiện kiểm tra.
                condition=~Q(_rong("LyDo")),
                name="ck_yeucauhuy_lydo_khong_rong",
            ),
            models.CheckConstraint( # Buộc dữ liệu phải thỏa mãn điều kiện kiểm tra.
                condition=Q(
                    TrangThaiBookingLucHuy__in=[
                        TrangThaiBooking.CHO_DAT_COC,
                        TrangThaiBooking.CHOT_BOOKING,
                    ]
                ),
                name="ck_yeucauhuy_trangthailuchuy",
            ),
            models.CheckConstraint( # Buộc dữ liệu phải thỏa mãn điều kiện kiểm tra.
                condition=Q(XuLyTienCoc__in=_gia_tri(XuLyTienCoc.CHOICES)),
                name="ck_yeucauhuy_xulytiencoc",
            ),
            # Khách hàng: Không phát sinh / Mất cọc; Nhiếp ảnh gia: Không phát sinh / Hoàn cọc
            models.CheckConstraint( # Buộc dữ liệu phải thỏa mãn điều kiện kiểm tra.
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
            # Chờ đặt cọc -> Không phát sinh; Chốt Booking -> Mất cọc / Hoàn cọc
            models.CheckConstraint( # Buộc dữ liệu phải thỏa mãn điều kiện kiểm tra.
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
            # TrangThaiHoanTien chỉ có giá trị khi Hoàn cọc
            models.CheckConstraint( # Buộc dữ liệu phải thỏa mãn điều kiện kiểm tra.
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
            # ThoiDiemXacNhanHoanTien chỉ có khi Đã hoàn tiền, và >= ThoiDiemYeuCau
            models.CheckConstraint( # Buộc dữ liệu phải thỏa mãn điều kiện kiểm tra.
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

    def __str__(self): # Chuỗi tóm tắt Booking khi hiển thị trong log/admin.
        return f"YeuCauHuy #{self.pk} - Booking {self.MaBooking_id} ({self.BenYeuCau})"

    def save(self, *args, **kwargs): # Tùy chỉnh quy trình lưu đối tượng vào cơ sở dữ liệu.
        # Mặc định "Chờ hoàn tiền" khi Hoàn cọc
        if self.XuLyTienCoc == XuLyTienCoc.HOAN_COC and not self.TrangThaiHoanTien:
            self.TrangThaiHoanTien = TrangThaiHoanTien.CHO_HOAN_TIEN
        super().save(*args, **kwargs)
from django.db import models

# Create your models here.
