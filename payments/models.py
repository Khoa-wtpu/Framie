# =====================================================================
# payments/models.py  -  Module 5: Thanh toán (Nguyên)
# Bảng: THANHTOAN, MINHCHUNGTHANHTOAN.
# Tên bảng và tên cột giống hệt Data Dictionary v2. Khóa chính là MaXxx
# nên KHÔNG có .id, các module khác dùng .pk.
# Chữ trạng thái lấy từ core/constants.py, không gõ trực tiếp.
# =====================================================================
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.constants import TrangThaiThanhToan
# Đặt bí danh vì field cũng tên LoaiThanhToan / DinhDangTep (tránh nhầm hai thứ cùng tên).
from core.constants import LoaiThanhToan as HangSoLoaiThanhToan
from core.constants import DinhDangTep as HangSoDinhDangTep


def _gia_tri(choices):
    # Từ danh sách [(giá trị, nhãn), ...] chỉ lấy phần giá trị, dùng cho CHECK ... IN (...).
    return [v for v, _ in choices]


def tinh_so_tien(tong_gia_tri, loai_thanh_toan):
    """Số tiền đúng của một khoản thanh toán: cọc = 40% (làm tròn), còn lại = Tổng - cọc.
    Tính phần còn lại bằng phép trừ để hai khoản luôn cộng đúng bằng TongGiaTri."""
    tong = Decimal(tong_gia_tri)
    coc = (tong * Decimal('0.4')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    if loai_thanh_toan == HangSoLoaiThanhToan.TIEN_COC:
        return coc
    if loai_thanh_toan == HangSoLoaiThanhToan.PHAN_CON_LAI:
        return tong - coc
    return None


# Hai nhóm trạng thái đã được Nhiếp ảnh gia xác nhận (có NgayXacNhan).
TRANG_THAI_DA_XAC_NHAN = [TrangThaiThanhToan.DA_DAT_COC, TrangThaiThanhToan.DA_THANH_TOAN]


class ThanhToan(models.Model):
    MaThanhToan = models.AutoField(primary_key=True)
    MaBooking = models.ForeignKey('bookings.Booking', on_delete=models.RESTRICT,
                                  db_column='MaBooking', related_name='thanh_toans',
                                  verbose_name='Booking')
    LoaiThanhToan = models.CharField('loại thanh toán', max_length=20,
                                     choices=HangSoLoaiThanhToan.CHOICES)
    SoTien = models.DecimalField('số tiền (VNĐ)', max_digits=12, decimal_places=0)
    TrangThai = models.CharField('trạng thái', max_length=50,
                                 choices=TrangThaiThanhToan.CHOICES)
    NgayThanhToan = models.DateTimeField('ngày thanh toán', null=True, blank=True)
    NgayXacNhan = models.DateTimeField('ngày xác nhận', null=True, blank=True)
    LyDoTuChoi = models.CharField('lý do từ chối', max_length=255, null=True, blank=True)

    class Meta:
        db_table = 'THANHTOAN'
        verbose_name = 'thanh toán'
        verbose_name_plural = 'thanh toán'
        constraints = [
            # UNIQUE (MaBooking, LoaiThanhToan): mỗi Booking chỉ một khoản cọc và một khoản còn lại.
            models.UniqueConstraint(fields=['MaBooking', 'LoaiThanhToan'],
                                    name='thanhtoan_booking_loai_duy_nhat'),
            models.CheckConstraint(condition=Q(SoTien__gt=0), name='ck_thanhtoan_sotien',
                                   violation_error_message='Số tiền phải lớn hơn 0.'),
            models.CheckConstraint(
                condition=Q(LoaiThanhToan__in=_gia_tri(HangSoLoaiThanhToan.CHOICES)),
                name='ck_thanhtoan_loai'),
            # Trạng thái phải đúng với loại thanh toán.
            models.CheckConstraint(
                condition=(
                    Q(LoaiThanhToan=HangSoLoaiThanhToan.TIEN_COC,
                      TrangThai__in=[TrangThaiThanhToan.CHO_XAC_NHAN_COC,
                                     TrangThaiThanhToan.DA_DAT_COC])
                    | Q(LoaiThanhToan=HangSoLoaiThanhToan.PHAN_CON_LAI,
                        TrangThai__in=[TrangThaiThanhToan.CHO_XAC_NHAN_60,
                                       TrangThaiThanhToan.QUA_HAN,
                                       TrangThaiThanhToan.DA_THANH_TOAN])),
                name='ck_thanhtoan_trangthai_theo_loai'),
            # Có NgayXacNhan khi và chỉ khi đã đặt cọc / đã thanh toán.
            models.CheckConstraint(
                condition=(
                    Q(TrangThai__in=TRANG_THAI_DA_XAC_NHAN, NgayXacNhan__isnull=False)
                    | (~Q(TrangThai__in=TRANG_THAI_DA_XAC_NHAN) & Q(NgayXacNhan__isnull=True))),
                name='ck_thanhtoan_ngayxacnhan'),
            # Có lý do thì không được rỗng. (Kiểm tra "chỉ toàn dấu cách" nằm ở clean(),
            # vì DB Browser không có hàm kiểm tra chuỗi nâng cao.)
            models.CheckConstraint(
                condition=Q(LyDoTuChoi__isnull=True) | ~Q(LyDoTuChoi=''),
                name='ck_thanhtoan_lydotuchoi'),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.LyDoTuChoi is not None and not self.LyDoTuChoi.strip():
            errors['LyDoTuChoi'] = 'Lý do từ chối không được chỉ chứa khoảng trắng.'
        # Ràng buộc "kiểm tra ở tầng ứng dụng": cọc = 40%, còn lại = 60% của TongGiaTri.
        if self.MaBooking_id and self.SoTien is not None and self.LoaiThanhToan:
            dung = tinh_so_tien(self.MaBooking.TongGiaTri, self.LoaiThanhToan)
            if dung is not None and Decimal(self.SoTien) != dung:
                errors['SoTien'] = f'Số tiền phải là {dung:,.0f} VNĐ theo tổng giá trị Booking.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'Thanh toán #{self.pk} - {self.LoaiThanhToan} ({self.TrangThai})'


class MinhChungThanhToan(models.Model):
    MaMinhChung = models.AutoField(primary_key=True)
    MaThanhToan = models.ForeignKey(ThanhToan, on_delete=models.RESTRICT,
                                    db_column='MaThanhToan', related_name='minh_chungs',
                                    verbose_name='thanh toán')
    TenTep = models.CharField('tên tệp', max_length=255)
    # Đường dẫn dạng chữ: file minh chứng không để ở thư mục media công khai,
    # phần lưu file do view tự viết rồi ghi đường dẫn vào đây (UC5.1).
    DuongDanTep = models.CharField('đường dẫn tệp', max_length=500)
    DinhDangTep = models.CharField('định dạng tệp', max_length=10,
                                   choices=HangSoDinhDangTep.CHOICES)
    KichThuocTep = models.IntegerField('kích thước tệp')
    NgayTaiLen = models.DateTimeField('ngày tải lên', default=timezone.now)

    class Meta:
        db_table = 'MINHCHUNGTHANHTOAN'
        verbose_name = 'minh chứng thanh toán'
        verbose_name_plural = 'minh chứng thanh toán'
        constraints = [
            models.CheckConstraint(condition=Q(KichThuocTep__gt=0), name='ck_minhchung_kichthuoc',
                                   violation_error_message='Kích thước tệp phải lớn hơn 0.'),
            models.CheckConstraint(
                condition=Q(DinhDangTep__in=_gia_tri(HangSoDinhDangTep.CHOICES)),
                name='ck_minhchung_dinhdang'),
        ]

    def __str__(self):
        return f'{self.TenTep} (thanh toán #{self.MaThanhToan_id})'