# =====================================================================
# reviews/models.py  -  Module 6: Đánh giá (Nguyên)
# Bảng: DANHGIA. Tên bảng và tên cột giống hệt Data Dictionary v2.
# Khóa chính là MaDanhGia nên KHÔNG có .id, các module khác dùng .pk.
# =====================================================================
# Nạp thành phần từ module django.core.exceptions để dùng bên dưới.
from django.core.exceptions import ValidationError
# Nạp thành phần từ module django.db để dùng bên dưới.
from django.db import models
# Nạp thành phần từ module django.db.models để dùng bên dưới.
from django.db.models import Q
# Nạp thành phần từ module django.utils để dùng bên dưới.
from django.utils import timezone

# Nạp thành phần từ module core.constants để dùng bên dưới.
from core.constants import TrangThaiBooking


# Lớp DanhGia: gom các dữ liệu hoặc hành vi liên quan.
class DanhGia(models.Model):
    # Gán giá trị cho MaDanhGia.
    MaDanhGia = models.AutoField(primary_key=True)
    # Gán giá trị cho MaBooking.
    MaBooking = models.OneToOneField('bookings.Booking', on_delete=models.RESTRICT,
                                     db_column='MaBooking', related_name='danh_gia',
                                     verbose_name='Booking')
    # Gán giá trị cho MaNhiepAnhGia.
    MaNhiepAnhGia = models.ForeignKey('profiles.NhiepAnhGia', on_delete=models.RESTRICT,
                                      db_column='MaNhiepAnhGia', related_name='danh_gias',
                                      verbose_name='nhiếp ảnh gia')
    # Gán giá trị cho Diem.
    Diem = models.IntegerField('điểm')
    # Gán giá trị cho NhanXet.
    NhanXet = models.CharField('nhận xét', max_length=500, null=True, blank=True)
    # Gán giá trị cho NgayDanhGia.
    NgayDanhGia = models.DateTimeField('ngày đánh giá', default=timezone.now)

    # Lớp Meta: gom các dữ liệu hoặc hành vi liên quan.
    class Meta:
        # Gán giá trị cho db_table.
        db_table = 'DANHGIA'
        # Gán giá trị cho verbose_name.
        verbose_name = 'đánh giá'
        # Gán giá trị cho verbose_name_plural.
        verbose_name_plural = 'đánh giá'
        # Gán giá trị cho constraints.
        constraints = [
            models.CheckConstraint(condition=Q(Diem__gte=1, Diem__lte=5), name='ck_danhgia_diem',
                                   violation_error_message='Điểm đánh giá chỉ từ 1 đến 5.'),
        ]

    # Hàm clean: xử lý một bước nghiệp vụ của phần này.
    def clean(self):
        # Thực hiện lời gọi hàm để xử lý bước này.
        super().clean()
        # Gán giá trị cho errors.
        errors = {}
        # Ràng buộc "kiểm tra ở tầng ứng dụng" (Data Dictionary):
        # Rẽ nhánh theo điều kiện để xử lý các trường hợp khác nhau.
        if self.MaBooking_id:
            # Gán giá trị cho booking.
            booking = self.MaBooking
            # 1. Chỉ đánh giá khi Booking đã Hoàn thành.
            # Rẽ nhánh theo điều kiện để xử lý các trường hợp khác nhau.
            if booking.TrangThai != TrangThaiBooking.HOAN_THANH:
                # Lưu kết quả xử lý vào biến.
                errors['MaBooking'] = 'Chỉ có thể đánh giá khi Booking ở trạng thái "Hoàn thành".'
            # 2. Nhiếp ảnh gia được đánh giá phải là nhiếp ảnh gia của Booking.
            # Rẽ nhánh theo điều kiện để xử lý các trường hợp khác nhau.
            if self.MaNhiepAnhGia_id and booking.MaNhiepAnhGia_id != self.MaNhiepAnhGia_id:
                # Lưu kết quả xử lý vào biến.
                errors['MaNhiepAnhGia'] = 'Nhiếp ảnh gia không trùng với nhiếp ảnh gia của Booking.'
        # Rẽ nhánh theo điều kiện để xử lý các trường hợp khác nhau.
        if errors:
            # Phát sinh lỗi để báo trường hợp không hợp lệ.
            raise ValidationError(errors)

    # Hàm __str__: xử lý một bước nghiệp vụ của phần này.
    def __str__(self):
        # Trả kết quả của bước xử lý hiện tại.
        return f'Đánh giá Booking {self.MaBooking_id}: {self.Diem}/5'