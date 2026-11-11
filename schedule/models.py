# =====================================================================
# schedule/models.py  -  Module 3: Quản lý lịch (Khoa)
# Bảng: LICHKHADUNG (khung giờ nhiếp ảnh gia mở nhận Booking)
# Tên bảng và cột giống hệt Data Dictionary v2; khóa chính là MaLich (dùng .pk).
# =====================================================================
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from core.constants import TrangThaiSlot


class LichKhaDung(models.Model):
    MaLich = models.AutoField(primary_key=True)
    # Trỏ bằng chữ 'profiles.NhiepAnhGia' để tránh import vòng giữa hai app.
    MaNhiepAnhGia = models.ForeignKey('profiles.NhiepAnhGia', on_delete=models.PROTECT,
                                      db_column='MaNhiepAnhGia', related_name='lich_kha_dung',
                                      verbose_name='Nhiếp ảnh gia')
    Ngay = models.DateField('Ngày')
    GioBatDau = models.TimeField('Giờ bắt đầu')
    GioKetThuc = models.TimeField('Giờ kết thúc')
    TrangThai = models.CharField('Trạng thái', max_length=30, choices=TrangThaiSlot.CHOICES,
                                 default=TrangThaiSlot.TRONG)

    class Meta:
        db_table = 'LICHKHADUNG'
        verbose_name = 'Lịch khả dụng'
        verbose_name_plural = 'Lịch khả dụng'
        ordering = ['Ngay', 'GioBatDau']
        constraints = [
            # Giờ kết thúc phải sau giờ bắt đầu.
            models.CheckConstraint(
                condition=Q(GioKetThuc__gt=F('GioBatDau')),
                name='lich_gio_ket_thuc_sau_gio_bat_dau',
                violation_error_message='Giờ kết thúc phải sau giờ bắt đầu.'),
            # Mỗi nhiếp ảnh gia không có hai khung giờ trùng giờ bắt đầu trong cùng một ngày.
            models.UniqueConstraint(
                fields=['MaNhiepAnhGia', 'Ngay', 'GioBatDau'],
                name='lich_nag_ngay_gio_bat_dau_duy_nhat',
                violation_error_message='Bạn đã có khung giờ bắt đầu vào giờ này trong ngày.'),
            # TrangThai chỉ nhận 3 giá trị của Quy ước trạng thái (CHECK trong Data Dictionary).
            models.CheckConstraint(
                condition=Q(TrangThai__in=[c[0] for c in TrangThaiSlot.CHOICES]),
                name='lich_trang_thai_hop_le',
                violation_error_message='Trạng thái khung giờ không hợp lệ.'),
        ]

    def clean(self):
        super().clean()
        # Không cho các khung giờ chồng nhau (Data Dictionary: kiểm tra ở tầng ứng dụng).
        # Hai khoảng [a,b) và [c,d) chồng nhau khi a < d và c < b.
        if self.MaNhiepAnhGia_id and self.Ngay and self.GioBatDau and self.GioKetThuc:
            chong = LichKhaDung.objects.filter(
                MaNhiepAnhGia_id=self.MaNhiepAnhGia_id, Ngay=self.Ngay,
                GioBatDau__lt=self.GioKetThuc, GioKetThuc__gt=self.GioBatDau,
            ).exclude(pk=self.pk)      # bỏ chính nó khi đang sửa
            if chong.exists():
                raise ValidationError('Khung giờ này bị chồng lên một khung giờ đã có trong ngày.')

    def __str__(self):
        return f'{self.Ngay} {self.GioBatDau:%H:%M}-{self.GioKetThuc:%H:%M}'