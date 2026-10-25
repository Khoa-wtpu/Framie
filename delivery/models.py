# =====================================================================
# delivery/models.py  -  Module 6: Bàn giao ảnh (Nguyên)
# Bảng: ANH, LICHSUTAIANH, YEUCAUCHINHSUA, YEUCAUCHINHSUA_ANH, BANGIAO.
# Tên bảng và tên cột giống hệt Data Dictionary v2. Khóa chính là MaXxx
# nên KHÔNG có .id, các module khác dùng .pk.
# Bảng nối YEUCAUCHINHSUA_ANH: khóa chính là id + UniqueConstraint (quy ước nhóm).
# =====================================================================
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from core.constants import HOAN_TAT_BAN_GIAO, LuuTruAnh, VaiTro
# Đặt bí danh vì field cũng tên LoaiAnh / KetQuaTaiAnh / DinhDangAnh (tránh nhầm hai thứ cùng tên).
from core.constants import LoaiAnh as HangSoLoaiAnh
from core.constants import KetQuaTaiAnh as HangSoKetQuaTaiAnh
from core.constants import DinhDangTep as HangSoDinhDang   # dùng chung danh sách JPG/PNG/JPEG


def _gia_tri(choices):
    return [v for v, _ in choices]


CO_KHONG = [(0, 'Không'), (1, 'Có')]   # cờ 0/1 (DD ghi chú số 1)


class Anh(models.Model):
    MaAnh = models.AutoField(primary_key=True)
    MaBooking = models.ForeignKey('bookings.Booking', on_delete=models.RESTRICT,
                                  db_column='MaBooking', related_name='anhs',
                                  verbose_name='Booking')
    TenAnh = models.CharField('tên ảnh', max_length=255)
    # Đường dẫn dạng chữ: ảnh gốc không để ở thư mục media công khai;
    # view tự lưu file vào thư mục riêng rồi ghi đường dẫn (UC5.3).
    DuongDanAnh = models.CharField('đường dẫn ảnh', max_length=500)
    DinhDangAnh = models.CharField('định dạng ảnh', max_length=10,
                                   choices=HangSoDinhDang.CHOICES)
    KichThuocAnh = models.IntegerField('kích thước ảnh')
    LoaiAnh = models.CharField('loại ảnh', max_length=20, choices=HangSoLoaiAnh.CHOICES)
    PhienBanAnh = models.IntegerField('phiên bản ảnh', default=1)
    CoWatermark = models.IntegerField('có watermark', default=1, choices=CO_KHONG)
    DuocChonHauKy = models.IntegerField('được chọn hậu kỳ', default=0, choices=CO_KHONG)
    TrangThaiLuuTru = models.CharField('trạng thái lưu trữ', max_length=20,
                                       choices=LuuTruAnh.CHOICES, default=LuuTruAnh.CON_LUU)
    NgayTaiLen = models.DateTimeField('ngày tải lên', default=timezone.now)

    class Meta:
        db_table = 'ANH'
        verbose_name = 'ảnh'
        verbose_name_plural = 'ảnh'
        constraints = [
            models.CheckConstraint(condition=Q(KichThuocAnh__gt=0), name='ck_anh_kichthuoc',
                                   violation_error_message='Kích thước ảnh phải lớn hơn 0.'),
            models.CheckConstraint(condition=Q(DinhDangAnh__in=_gia_tri(HangSoDinhDang.CHOICES)),
                                   name='ck_anh_dinhdang'),
            models.CheckConstraint(condition=Q(LoaiAnh__in=_gia_tri(HangSoLoaiAnh.CHOICES)),
                                   name='ck_anh_loai'),
            models.CheckConstraint(condition=Q(PhienBanAnh__gte=1), name='ck_anh_phienban',
                                   violation_error_message='Phiên bản ảnh phải từ 1 trở lên.'),
            models.CheckConstraint(condition=Q(CoWatermark__in=[0, 1]), name='ck_anh_cowatermark'),
            # Ảnh "Hoàn chỉnh" không watermark; các loại còn lại có watermark.
            models.CheckConstraint(
                condition=(Q(LoaiAnh=HangSoLoaiAnh.HOAN_CHINH, CoWatermark=0)
                           | (~Q(LoaiAnh=HangSoLoaiAnh.HOAN_CHINH) & Q(CoWatermark=1))),
                name='ck_anh_watermark_theo_loai',
                violation_error_message='Ảnh "Hoàn chỉnh" phải không watermark, các loại khác phải có watermark.'),
            models.CheckConstraint(condition=Q(DuocChonHauKy__in=[0, 1]), name='ck_anh_duocchonhauky'),
            models.CheckConstraint(condition=Q(TrangThaiLuuTru__in=_gia_tri(LuuTruAnh.CHOICES)),
                                   name='ck_anh_trangthailuutru'),
        ]

    def __str__(self):
        return f'{self.TenAnh} (#{self.pk})'


class LichSuTaiAnh(models.Model):
    MaLichSuTaiAnh = models.AutoField(primary_key=True)
    MaAnh = models.ForeignKey(Anh, on_delete=models.RESTRICT, db_column='MaAnh',
                              related_name='lich_su_tais', verbose_name='ảnh')
    MaKhachHang = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT,
                                    db_column='MaKhachHang', related_name='lich_su_tai_anhs',
                                    verbose_name='khách hàng')
    ThoiDiemTaiAnh = models.DateTimeField('thời điểm tải ảnh', default=timezone.now)
    KetQuaTaiAnh = models.CharField('kết quả tải ảnh', max_length=30,
                                    choices=HangSoKetQuaTaiAnh.CHOICES)

    class Meta:
        db_table = 'LICHSUTAIANH'
        verbose_name = 'lịch sử tải ảnh'
        verbose_name_plural = 'lịch sử tải ảnh'
        constraints = [
            models.CheckConstraint(
                condition=Q(KetQuaTaiAnh__in=_gia_tri(HangSoKetQuaTaiAnh.CHOICES)),
                name='ck_lichsutaianh_ketqua'),
        ]

    def clean(self):
        super().clean()
        # Ràng buộc "kiểm tra ở tầng ứng dụng": người tải phải thuộc nhóm Khách hàng.
        if self.MaKhachHang_id and not self.MaKhachHang.groups.filter(
                name=VaiTro.KHACH_HANG).exists():
            raise ValidationError({'MaKhachHang': 'Người dùng tải ảnh phải thuộc nhóm Khách hàng.'})

    def __str__(self):
        return f'Tải ảnh #{self.MaAnh_id} - {self.KetQuaTaiAnh}'


class YeuCauChinhSua(models.Model):
    MaYeuCauChinhSua = models.AutoField(primary_key=True)
    MaBooking = models.ForeignKey('bookings.Booking', on_delete=models.RESTRICT,
                                  db_column='MaBooking', related_name='yeu_cau_chinh_suas',
                                  verbose_name='Booking')
    NgayYeuCau = models.DateTimeField('ngày yêu cầu', default=timezone.now)
    NoiDung = models.CharField('nội dung', max_length=1000)
    SoLanYeuCau = models.IntegerField('số lần yêu cầu')

    # Quan hệ nhiều-nhiều với ANH qua bảng nối YEUCAUCHINHSUA_ANH (không phải cột trong DB).
    anhs = models.ManyToManyField(Anh, through='YeuCauChinhSua_Anh',
                                  related_name='yeu_cau_chinh_suas')

    class Meta:
        db_table = 'YEUCAUCHINHSUA'
        verbose_name = 'yêu cầu chỉnh sửa'
        verbose_name_plural = 'yêu cầu chỉnh sửa'
        constraints = [
            models.UniqueConstraint(fields=['MaBooking', 'SoLanYeuCau'],
                                    name='yeucauchinhsua_booking_solan_duy_nhat'),
            models.CheckConstraint(condition=Q(SoLanYeuCau__gte=1, SoLanYeuCau__lte=3),
                                   name='ck_yeucauchinhsua_solan',
                                   violation_error_message='Số lần yêu cầu chỉnh sửa chỉ từ 1 đến 3.'),
            models.CheckConstraint(condition=~Q(NoiDung=''), name='ck_yeucauchinhsua_noidung'),
        ]

    def clean(self):
        super().clean()
        if self.NoiDung is not None and not self.NoiDung.strip():
            raise ValidationError({'NoiDung': 'Nội dung không được chỉ chứa khoảng trắng.'})

    def __str__(self):
        return f'Yêu cầu chỉnh sửa lần {self.SoLanYeuCau} - Booking {self.MaBooking_id}'


# ---------------------------------------------------------------------
# Bảng nối YEUCAUCHINHSUA_ANH (thực thể kết hợp, có thêm cột NoiDungChinhSua)
# Khóa chính là id; hai mã còn lại là FK và không được trùng cặp.
# ---------------------------------------------------------------------
class YeuCauChinhSua_Anh(models.Model):
    id = models.AutoField(primary_key=True)
    MaYeuCauChinhSua = models.ForeignKey(YeuCauChinhSua, on_delete=models.CASCADE,
                                         db_column='MaYeuCauChinhSua')
    MaAnh = models.ForeignKey(Anh, on_delete=models.RESTRICT, db_column='MaAnh')
    NoiDungChinhSua = models.CharField('nội dung chỉnh sửa', max_length=500)

    class Meta:
        db_table = 'YEUCAUCHINHSUA_ANH'
        verbose_name = 'ảnh cần chỉnh sửa'
        verbose_name_plural = 'ảnh cần chỉnh sửa'
        constraints = [
            models.UniqueConstraint(fields=['MaYeuCauChinhSua', 'MaAnh'],
                                    name='yeucauchinhsua_anh_duy_nhat'),
            models.CheckConstraint(condition=~Q(NoiDungChinhSua=''),
                                   name='ck_yeucauchinhsua_anh_noidung'),
        ]

    def clean(self):
        super().clean()
        if self.NoiDungChinhSua is not None and not self.NoiDungChinhSua.strip():
            raise ValidationError({'NoiDungChinhSua': 'Nội dung chỉnh sửa không được chỉ chứa khoảng trắng.'})


class BanGiao(models.Model):
    MaBanGiao = models.AutoField(primary_key=True)
    MaBooking = models.OneToOneField('bookings.Booking', on_delete=models.RESTRICT,
                                     db_column='MaBooking', related_name='ban_giao',
                                     verbose_name='Booking')
    NgayXacNhan = models.DateTimeField('ngày xác nhận')
    TrangThaiBanGiao = models.CharField(
        'trạng thái bàn giao', max_length=30, default=HOAN_TAT_BAN_GIAO,
        choices=[(HOAN_TAT_BAN_GIAO, HOAN_TAT_BAN_GIAO)])
    ThoiHanTaiAnh = models.DateTimeField('thời hạn tải ảnh', null=True, blank=True)

    class Meta:
        db_table = 'BANGIAO'
        verbose_name = 'bàn giao'
        verbose_name_plural = 'bàn giao'
        constraints = [
            models.CheckConstraint(condition=Q(TrangThaiBanGiao__in=[HOAN_TAT_BAN_GIAO]),
                                   name='ck_bangiao_trangthai'),
            models.CheckConstraint(
                condition=Q(ThoiHanTaiAnh__isnull=True) | Q(ThoiHanTaiAnh__gt=F('NgayXacNhan')),
                name='ck_bangiao_thoihan_sau_ngayxacnhan',
                violation_error_message='Thời hạn tải ảnh phải sau ngày xác nhận.'),
        ]

    def __str__(self):
        return f'Bàn giao Booking {self.MaBooking_id}'