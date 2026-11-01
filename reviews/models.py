# =====================================================================
# reviews/models.py  -  Module 6: Đánh giá (Nguyên)
# Bảng: DANHGIA. Tên bảng và tên cột giống hệt Data Dictionary v2.
# Khóa chính là MaDanhGia nên KHÔNG có .id, các module khác dùng .pk.
# =====================================================================
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.constants import TrangThaiBooking


class DanhGia(models.Model):
    MaDanhGia = models.AutoField(primary_key=True)
    MaBooking = models.OneToOneField('bookings.Booking', on_delete=models.RESTRICT,
                                     db_column='MaBooking', related_name='danh_gia',
                                     verbose_name='Booking')
    MaNhiepAnhGia = models.ForeignKey('profiles.NhiepAnhGia', on_delete=models.RESTRICT,
                                      db_column='MaNhiepAnhGia', related_name='danh_gias',
                                      verbose_name='nhiếp ảnh gia')
    Diem = models.IntegerField('điểm')
    NhanXet = models.CharField('nhận xét', max_length=500, null=True, blank=True)
    NgayDanhGia = models.DateTimeField('ngày đánh giá', default=timezone.now)

    class Meta:
        db_table = 'DANHGIA'
        verbose_name = 'đánh giá'
        verbose_name_plural = 'đánh giá'
        constraints = [
            models.CheckConstraint(condition=Q(Diem__gte=1, Diem__lte=5), name='ck_danhgia_diem',
                                   violation_error_message='Điểm đánh giá chỉ từ 1 đến 5.'),
        ]

    def clean(self):
        super().clean()
        errors = {}
        # Ràng buộc "kiểm tra ở tầng ứng dụng" (Data Dictionary):
        if self.MaBooking_id:
            booking = self.MaBooking
            # 1. Chỉ đánh giá khi Booking đã Hoàn thành.
            if booking.TrangThai != TrangThaiBooking.HOAN_THANH:
                errors['MaBooking'] = 'Chỉ có thể đánh giá khi Booking ở trạng thái "Hoàn thành".'
            # 2. Nhiếp ảnh gia được đánh giá phải là nhiếp ảnh gia của Booking.
            if self.MaNhiepAnhGia_id and booking.MaNhiepAnhGia_id != self.MaNhiepAnhGia_id:
                errors['MaNhiepAnhGia'] = 'Nhiếp ảnh gia không trùng với nhiếp ảnh gia của Booking.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'Đánh giá Booking {self.MaBooking_id}: {self.Diem}/5'